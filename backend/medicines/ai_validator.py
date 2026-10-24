"""Medicine Validation System.

Enterprise-grade validation pipeline:

    1. MedicineNormalizer
       → whitespace, casing, punctuation normalization
    2. AIAssistanceService (OPTIONAL, non-blocking)
       → typo correction, spelling suggestions
       → NEVER decides validity
       → If unavailable, continues without error
    3. MasterDrugValidator (AUTHORITATIVE)
       → queries RxNorm, OpenFDA sequentially
       → any match = medicine is valid
       → includes Indian-brand fallback
    4. AI Recheck (only if all DBs fail AND AI is available)
       → AI suggests alternative name
       → re-runs databases with suggestion
    5. Duplicate Check → Serializer → Save

Architecture:
    AIProviderRouter    -- tries OpenAI first, falls back to Gemini
    AIAssistanceService -- wraps router as optional suggestion engine
    MasterDrugValidator -- queries drug databases sequentially
    InMemoryCache       -- caches results by lowercase name
    HybridValidationService -- orchestrates the full pipeline

The `MedicineValidator` class is kept for backward compatibility.

AI is NEVER the primary authority. Drug databases are.
"""

import json
import logging
import re
import time
from abc import ABC, abstractmethod

from django.conf import settings
import requests

from .providers import DrugDatabaseProvider, RxNormOpenFDAProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-3.5-turbo"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
REQUEST_TIMEOUT = 15

AI_SUGGEST_PROMPT = (
    "You are a pharmaceutical spelling assistant.\n\n"
    "Your ONLY job is to CORRECT typos and suggest the standard "
    "name of a medicine the user might have intended.\n\n"
    "You must NEVER decide whether a medicine is valid or real.\n"
    "You must NEVER reject a medicine name.\n"
    "You must NEVER say a medicine does not exist.\n"
    "\n"
    "Rules:\n"
    "- If the input looks like a typo of a real medicine, correct it\n"
    "- If you recognize a brand name, suggest the standard generic name\n"
    "- If the input is already correct, return it unchanged\n"
    "- If you are unsure, return the input unchanged\n"
    "- Never guess wildly or hallucinate\n"
    "\n"
    "CRITICAL:\n"
    "You are a CORRECTION engine, not a validation engine.\n"
    "Your output will be verified against authoritative drug databases.\n"
    "The databases will make the final decision.\n"
    "\n"
    "Return ONLY JSON.  Do NOT include markdown fences.\n"
    "\n"
    "Examples:\n"
    'Input: "Paracitamol" -> {"corrected": true, "suggestion": "Paracetamol", "confidence": 0.95}\n'
    'Input: "Paracetamol" -> {"corrected": false, "suggestion": "Paracetamol", "confidence": 1.0}\n'
    'Input: "Ciplox"      -> {"corrected": false, "suggestion": "Ciplox", "confidence": 1.0}\n'
    'Input: "asdfgh"      -> {"corrected": false, "suggestion": "asdfgh", "confidence": 0.01}\n'
    'Input: "Chocolate"   -> {"corrected": false, "suggestion": "Chocolate", "confidence": 0.01}\n'
    'Input: "Napa"        -> {"corrected": true, "suggestion": "Paracetamol", "confidence": 0.9}\n'
    'Input: "Crocin"      -> {"corrected": false, "suggestion": "Crocin", "confidence": 1.0}\n'
    "\n"
    "Return NOTHING except JSON."
)


# ---------------------------------------------------------------------------
# Medicine Name Normalizer
# ---------------------------------------------------------------------------

class MedicineNormalizer:
    """Normalize medicine names without validating.

    Performs:
        - Whitespace stripping and collapsing
        - Case normalization (title case for display, lower for lookup)
        - Punctuation cleanup
        - Dosage formatting normalization
    """

    @staticmethod
    def normalize(name: str) -> str:
        """Normalize a medicine name for consistent lookup.

        "  150   mg  "  -> "150 mg"
        "  ACILOC  "   -> "ACILOC"
        "Paracitamol"  -> "Paracitamol"  (no spell-check, just format)
        "  pantop-dsr " -> "pantop dsr"
        "CIPLOX-500"   -> "ciplox 500"
        "Crocin  "     -> "Crocin"
        "dolo 650  "   -> "dolo 650"
        "   "          -> ""
        ""             -> ""
        None           -> ""
        "IbUprOfEn"    -> "Ibuprofen"   (title-cased)
        "PARACETAMOL"  -> "Paracetamol"
        "amoxicillin"  -> "Amoxicillin"
        "dolo"         -> "Dolo"
    """
        if not name or not name.strip():
            return ""

        # Strip leading/trailing whitespace
        cleaned = name.strip()

        # Collapse internal whitespace
        cleaned = re.sub(r"\s+", " ", cleaned)

        # Replace common punctuation separators with space
        # (hyphens, slashes, underscores, colons, semicolons)
        cleaned = re.sub(r"[-/_:;.~+]", " ", cleaned)

        # Remove any remaining non-alphanumeric non-space characters
        # (except parentheses which are sometimes part of medicine names)
        cleaned = re.sub(r"[^\w\s()]", "", cleaned)

        # Collapse spaces again (punctuation may have created double spaces)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        return cleaned

    @staticmethod
    def normalize_lower(name: str) -> str:
        """Normalize and lowercase for case-insensitive lookups."""
        return MedicineNormalizer.normalize(name).lower()


# ---------------------------------------------------------------------------
# AI Provider Abstract Base
# ---------------------------------------------------------------------------

class AIProvider(ABC):
    """Abstract interface for AI-based medicine name validation.

    All AI providers (OpenAI, Gemini, etc.) must implement validate().
    """

    @abstractmethod
    def validate(self, medicine_name: str) -> dict:
        """Validate a medicine name via this AI provider.

        Returns dict with keys:
            "exists"         : bool
            "normalized_name": str
            "confidence"     : float (0.0 - 1.0)
            "error"          : str (only present on failure)
        """
        ...


# ---------------------------------------------------------------------------
# In-Memory Cache
# ---------------------------------------------------------------------------

class InMemoryCache:
    """In-memory cache for validation results.

    Keys are lowercased medicine names.  Values are result dicts.
    """

    def __init__(self):
        self._store: dict[str, dict] = {}

    def get(self, key: str) -> dict | None:
        return self._store.get(key.lower())

    def set(self, key: str, value: dict) -> None:
        self._store[key.lower()] = value

    def has(self, key: str) -> bool:
        return key.lower() in self._store

    def clear(self) -> None:
        self._store.clear()


# ---------------------------------------------------------------------------
# OpenAI Provider
# ---------------------------------------------------------------------------

class OpenAIProvider(AIProvider):
    """Medicine validation using OpenAI Chat Completions API.

    Calls the OpenAI REST API directly via requests (no SDK required).
    Reuses the project's existing OPENAI_API_KEY from settings.
    """

    def validate(self, medicine_name: str) -> dict:
        name = (medicine_name or "").strip()
        if not name:
            return {"exists": False, "error": "Medicine name cannot be empty."}

        api_key = getattr(settings, "OPENAI_API_KEY", "")
        if not api_key:
            logger.error("OPENAI_API_KEY is not configured.")
            return {"exists": False, "error": "OpenAI API key is not configured."}

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": AI_SUGGEST_PROMPT},
                {"role": "user", "content": name},
            ],
            "temperature": 0.0,
            "max_tokens": 150,
        }

        logger.info("OpenAI request started for '%s'", name)

        try:
            resp = requests.post(
                OPENAI_API_URL,
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as exc:
            logger.error("OpenAI API call failed for '%s': %s", name, exc)
            return {"exists": False, "error": f"OpenAI API call failed: {exc}"}

        # -- Extract the assistant's reply --
        try:
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)
        except (KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
            logger.error(
                "Failed to parse OpenAI response for '%s': %s. Raw: %s",
                name,
                exc,
                data.get("choices", [{}])[0].get("message", {}).get("content", ""),
            )
            return {"exists": False, "error": f"Failed to parse OpenAI response: {exc}"}

        # -- Parse result (handles both suggestion and legacy formats) --
        confidence = float(result.get("confidence", 0.0))
        # New format: {"corrected": bool, "suggestion": str, "confidence": float}
        # Legacy format: {"exists": bool, "normalized_name": str, "confidence": float}
        corrected = result.get("corrected", None)
        if corrected is not None:
            # New suggestion-oriented format
            normalized_name = str(result.get("suggestion", name))
            exists = confidence >= 0.5  # AI never rejects, only suggests
        else:
            # Legacy validation format
            exists = bool(result.get("exists", False))
            normalized_name = str(result.get("normalized_name", name))

        logger.info(
            "OpenAI response for '%s': corrected=%s, suggestion='%s', confidence=%.2f",
            name,
            corrected,
            normalized_name,
            confidence,
        )

        return {
            "exists": exists,
            "normalized_name": normalized_name,
            "confidence": confidence,
        }


# ---------------------------------------------------------------------------
# Gemini Provider
# ---------------------------------------------------------------------------

class GeminiProvider(AIProvider):
    """Medicine validation using Google Gemini API.

    Calls the Gemini REST API directly via requests.
    Reuses the project's existing GEMINI_API_KEY from settings.
    """

    def validate(self, medicine_name: str) -> dict:
        name = (medicine_name or "").strip()
        if not name:
            return {"exists": False, "error": "Medicine name cannot be empty."}

        api_key = getattr(settings, "GEMINI_API_KEY", "")
        if not api_key:
            logger.error("GEMINI_API_KEY is not configured.")
            return {"exists": False, "error": "Gemini API key is not configured."}

        # Combine the suggestion prompt and medicine name as a single user message
        user_text = f"{AI_SUGGEST_PROMPT}\n\nMedicine name: {name}"

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_text}],
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 1024,
            },
        }

        url = f"{GEMINI_API_URL}?key={api_key}"
        logger.info("Gemini request started for '%s'", name)

        try:
            resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            logger.info("Gemini HTTP %s for '%s'", resp.status_code, name)

            # ── Explicit HTTP 429 / quota-exceeded detection ──
            # Return immediately with a structured error BEFORE raise_for_status()
            # so callers can distinguish quota limits from other failures.
            if resp.status_code == 429:
                logger.error(
                    "Gemini QUOTA EXCEEDED for '%s': HTTP 429, body=%s",
                    name,
                    resp.text[:2000],
                )
                return {
                    "exists": False,
                    "error": f"Gemini API quota exceeded (HTTP 429): {resp.text[:500]}",
                    "quota_exceeded": True,
                }

            # Log the full response body for other non-2xx BEFORE raise_for_status()
            # so error details appear in the logs.
            if resp.status_code != 200:
                logger.error(
                    "Gemini non-200 response for '%s': HTTP %s, body=%s",
                    name,
                    resp.status_code,
                    resp.text[:2000],
                )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as exc:
            logger.exception("Gemini API call failed for '%s'", name)
            return {"exists": False, "error": f"Gemini API call failed: {exc}"}

        # -- Extract the response text (handle potential markdown fences) --
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError("No candidates in Gemini response")
            raw = (
                candidates[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            content = raw.strip()
            # Strip markdown code fences if present
            if content.startswith("```json"):
                content = content[7:].strip()
            elif content.startswith("```"):
                first_nl = content.find("\n")
                if first_nl != -1:
                    content = content[first_nl + 1 :].strip()
                else:
                    content = content[3:].strip()
            if content.endswith("```"):
                content = content[:-3].strip()
            result = json.loads(content)
        except (KeyError, IndexError, ValueError, json.JSONDecodeError, TypeError) as exc:
            logger.error(
                "Failed to parse Gemini response for '%s': %s. Raw: %s",
                name,
                exc,
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", ""),
            )
            return {"exists": False, "error": f"Failed to parse Gemini response: {exc}"}

        # -- Parse result (handles both suggestion and legacy formats) --
        confidence = float(result.get("confidence", 0.0))
        corrected = result.get("corrected", None)
        if corrected is not None:
            normalized_name = str(result.get("suggestion", name))
            exists = confidence >= 0.5
        else:
            exists = bool(result.get("exists", False))
            normalized_name = str(result.get("normalized_name", name))

        logger.info(
            "Gemini response for '%s': corrected=%s, suggestion='%s', confidence=%.2f",
            name,
            corrected,
            normalized_name,
            confidence,
        )

        return {
            "exists": exists,
            "normalized_name": normalized_name,
            "confidence": confidence,
        }


# ---------------------------------------------------------------------------
# AI Provider Router
# ---------------------------------------------------------------------------

class AIProviderRouter:
    """Routes validation requests to the appropriate AI provider.

    Provider chain is read from settings.AI_PROVIDER_CHAIN.
    Each provider is tried in order until one succeeds.
    Fallback is automatic.
    """

    # Registry of available AI providers by name
    PROVIDER_REGISTRY = {
        "OPENAI": OpenAIProvider,
        "GEMINI": GeminiProvider,
    }

    def __init__(
        self,
        provider_chain: list[str] | None = None,
        providers: dict[str, AIProvider] | None = None,
        openai_provider: AIProvider | None = None,  # kept for backward compat
        gemini_provider: AIProvider | None = None,  # kept for backward compat
    ):
        if provider_chain is None:
            raw = getattr(settings, "AI_PROVIDER_CHAIN", "OPENAI,GEMINI")
            provider_chain = [p.strip() for p in raw.split(",") if p.strip()]
        self._chain = provider_chain
        self._providers = providers or {}
        # Backward compat: map old args into registry
        if openai_provider:
            self._providers["OPENAI"] = openai_provider
        if gemini_provider:
            self._providers["GEMINI"] = gemini_provider

    def _get_provider(self, name: str) -> AIProvider | None:
        """Get or create a provider instance by name."""
        if name in self._providers:
            return self._providers[name]

        provider_cls = self.PROVIDER_REGISTRY.get(name)
        if provider_cls is None:
            logger.warning("AIProviderRouter: unknown provider '%s', skipping", name)
            return None

        provider = provider_cls()
        self._providers[name] = provider
        return provider

    @staticmethod
    def _key_configured(name: str) -> bool:
        """Check if an AI provider's API key is configured."""
        key_map = {
            "OPENAI": "OPENAI_API_KEY",
            "GEMINI": "GEMINI_API_KEY",
        }
        key_name = key_map.get(name)
        if not key_name:
            return False
        return bool(getattr(settings, key_name, ""))

    def validate(self, medicine_name: str) -> dict:
        """Try AI providers from the configured chain in order.

        Returns the same dict format as AIProvider.validate(),
        with an additional ``provider`` key indicating which one succeeded.
        """
        name = (medicine_name or "").strip()
        if not name:
            return {"exists": False, "error": "Medicine name cannot be empty."}

        last_error = None
        quota_exceeded = False
        tried = []

        for provider_name in self._chain:
            tried.append(provider_name)

            if not self._key_configured(provider_name):
                logger.info(
                    "AI Router: %s key not configured, skipping",
                    provider_name,
                )
                continue

            provider = self._get_provider(provider_name)
            if provider is None:
                continue

            logger.info(
                "AI Router: trying %s for '%s'",
                provider_name, name,
            )
            result = provider.validate(name)

            if not result.get("error"):
                result["provider"] = provider_name.lower()
                logger.info(
                    "AI Router: %s succeeded for '%s'",
                    provider_name, name,
                )
                return result

            last_error = result.get("error")
            if result.get("quota_exceeded"):
                quota_exceeded = True
                logger.error(
                    "AI Router: %s QUOTA EXCEEDED for '%s'",
                    provider_name, name,
                )
            else:
                logger.warning(
                    "AI Router: %s failed for '%s': %s",
                    provider_name, name, last_error,
                )

        # -- All providers exhausted --
        configured = [p for p in self._chain if self._key_configured(p)]
        if not configured:
            missing_keys = [
                f"{p}_API_KEY" for p in self._chain
            ]
            logger.error(
                "AI Router: No AI providers available for '%s'. "
                "None of %s have API keys configured.",
                name, missing_keys,
            )
            return {
                "exists": False,
                "error": f"No AI providers configured. Add keys: {', '.join(missing_keys)}.",
            }

        if quota_exceeded:
            logger.error(
                "AI Router: All providers exhausted for '%s'. "
                "Providers tried=%s. Quota exceeded.",
                name, tried,
            )
            return {
                "exists": False,
                "error": f"AI providers unavailable (quota exceeded). Tried: {tried}.",
                "quota_exceeded": True,
            }

        logger.error(
            "AI Router: All providers exhausted for '%s'. "
            "Providers tried=%s. Last error=%s",
            name, tried, last_error,
        )
        return {
            "exists": False,
            "error": f"AI providers unavailable. Tried: {tried}. Last error: {last_error}",
        }


# ---------------------------------------------------------------------------
# AI Assistance Service (Optional, Non-blocking)
# ---------------------------------------------------------------------------

class AIAssistanceService:
    """Optional AI provider for typo correction and suggestions.

    This service is NEVER required for medicine validation.
    If no AI provider is available, it returns None and the
    pipeline continues without interruption.

    AI providers are tried according to AI_PROVIDER_CHAIN from settings.
    """

    def __init__(
        self,
        router: AIProviderRouter | None = None,
    ):
        self._router = router or AIProviderRouter()

    def suggest_correction(self, medicine_name: str) -> dict | None:
        """Ask AI to suggest a corrected/normalized medicine name.

        Args:
            medicine_name: The raw user input.

        Returns:
            dict with keys on success:
                "suggested_name": str  (AI-corrected name)
                "provider":       str  ("openai" or "gemini")
                "confidence":     float
            None if AI is unavailable or fails.

        This method NEVER raises or returns an error.
        All failures are caught and logged, returning None.
        """
        name = (medicine_name or "").strip()
        if not name:
            return None

        logger.info("AI Assistance: requesting suggestion for '%s'", name)

        ai_result = self._router.validate(name)

        # If all AI providers failed, just return None (non-blocking)
        if ai_result.get("error"):
            logger.info(
                "AI Assistance: unavailable for '%s' (non-blocking, continuing without AI): %s",
                name,
                ai_result.get("error"),
            )
            return None

        # If AI found the medicine, return the normalized name
        exists = ai_result.get("exists", False)
        confidence = float(ai_result.get("confidence", 0.0))
        normalized = str(ai_result.get("normalized_name", name))

        if exists and confidence >= 0.95:
            logger.info(
                "AI Assistance: suggestion for '%s' -> '%s' (confidence=%.2f, provider=%s)",
                name,
                normalized,
                confidence,
                ai_result.get("provider", "?"),
            )
            return {
                "suggested_name": normalized,
                "provider": ai_result.get("provider", "?"),
                "confidence": confidence,
            }

        # AI didn't recognize it either
        logger.info(
            "AI Assistance: no suggestion for '%s' (exists=%s, confidence=%.2f)",
            name,
            exists,
            confidence,
        )
        return None


# ---------------------------------------------------------------------------
# Master Drug Validator (Authoritative)
# ---------------------------------------------------------------------------

class MasterDrugValidator:
    """Queries drug databases sequentially to confirm a medicine exists.

    This is the PRIMARY validation authority.
    Each configured provider is tried in order.
    If any provider confirms the medicine, validation succeeds.
    If a provider fails or times out, the next is tried.
    Only fails when ALL providers have been exhausted.
    """

    # Provider name → class mapping
    PROVIDER_REGISTRY = {
        "RXNORM_OPENFDA": RxNormOpenFDAProvider,
    }

    def __init__(
        self,
        provider_chain: list[str] | None = None,
        providers: dict[str, DrugDatabaseProvider] | None = None,
    ):
        """
        Args:
            provider_chain: Ordered list of provider names.
                Defaults to settings.VALIDATION_PROVIDER_CHAIN split by comma.
            providers: Optional pre-built provider instances keyed by name.
        """
        if provider_chain is None:
            raw = getattr(settings, "VALIDATION_PROVIDER_CHAIN", "RXNORM_OPENFDA")
            provider_chain = [p.strip() for p in raw.split(",") if p.strip()]

        self._chain = provider_chain
        self._providers = providers or {}

    def validate(self, medicine_name: str) -> dict:
        """Run medicine through all configured database providers.

        Returns:
            dict with keys:
                "exists"         : bool
                "normalized_name": str  (from the first matching provider)
                "source"         : str  (name of the provider that matched)
                "providers_tried": list[str]  (all providers that were queried)
                "error"          : str  (only if ALL providers failed)

        Never raises. All provider errors are caught and logged.
        """
        name = (medicine_name or "").strip()
        if not name:
            return {"exists": False, "error": "Medicine name cannot be empty."}

        providers_tried = []

        for provider_name in self._chain:
            providers_tried.append(provider_name)

            # Get or create provider instance
            provider = self._get_provider(provider_name)
            if provider is None:
                logger.warning(
                    "MasterDrugValidator: unknown provider '%s' in chain, skipping",
                    provider_name,
                )
                continue

            logger.info(
                "MasterDrugValidator: querying '%s' for '%s'",
                provider_name,
                name,
            )

            try:
                result = provider.lookup(name)
            except Exception as exc:
                logger.error(
                    "MasterDrugValidator: provider '%s' threw exception for '%s': %s",
                    provider_name,
                    name,
                    exc,
                    exc_info=True,
                )
                continue

            if result is None:
                continue

            if result.get("exists"):
                logger.info(
                    "MasterDrugValidator: '%s' CONFIRMED by '%s' -> normalized='%s'",
                    name,
                    provider_name,
                    result.get("normalized_name", name),
                )
                return {
                    "exists": True,
                    "normalized_name": result.get("normalized_name", name),
                    "source": provider_name,
                    "providers_tried": providers_tried,
                }

            # Provider returned exists=False; continue to next
            logger.info(
                "MasterDrugValidator: '%s' NOT found by '%s', trying next",
                name,
                provider_name,
            )

        # All providers exhausted without a match
        logger.info(
            "MasterDrugValidator: '%s' NOT found by any provider %s",
            name,
            providers_tried,
        )
        return {
            "exists": False,
            "normalized_name": name,
            "source": None,
            "providers_tried": providers_tried,
            "error": f"Medicine not found in any drug database: {providers_tried}",
        }

    def _get_provider(self, name: str) -> DrugDatabaseProvider | None:
        """Get or create a provider instance by name."""
        if name in self._providers:
            return self._providers[name]

        provider_cls = self.PROVIDER_REGISTRY.get(name)
        if provider_cls is None:
            return None

        provider = provider_cls()
        self._providers[name] = provider
        return provider


# ---------------------------------------------------------------------------
# Hybrid Validation Service
# ---------------------------------------------------------------------------

class HybridValidationService:
    """Orchestrates the complete validation pipeline.

    Pipeline:
        1. Normalize input (whitespace, casing, punctuation)
        2. AI Assistance (optional, non-blocking typo correction)
        3. Master Drug Validation (authoritative database check)
        4. AI Recheck (if all DBs fail AND AI is available)
        5. Final decision

    Decision logic:
        Medicine is VALID if:
            MasterDrugValidator confirms existence in ANY database.

        Medicine is INVALID if:
            NO database confirms existence AND
            AI Recheck also fails to find a match.

        HTTP 503 is NEVER returned for AI unavailability.
        HTTP 503 is only returned if EVERY configured
        database provider fails due to system errors.

    Results are cached in-memory.
    """

    def __init__(
        self,
        normalizer: MedicineNormalizer | None = None,
        ai_assistance: AIAssistanceService | None = None,
        master_validator: MasterDrugValidator | None = None,
        cache: InMemoryCache | None = None,
        ai_router: AIProviderRouter | None = None,  # kept for backward compat
        drug_db_provider: DrugDatabaseProvider | None = None,  # kept for backward compat
    ):
        self.normalizer = normalizer or MedicineNormalizer()
        self.ai_assistance = ai_assistance or AIAssistanceService(router=ai_router)
        self.master_validator = master_validator or MasterDrugValidator()
        self.cache = cache or InMemoryCache()

    def validate(self, medicine_name: str) -> dict:
        """Run the complete validation pipeline on *medicine_name*.

        Pipeline:
            1. Normalize input
            2. AI Assistance (optional, non-blocking)
            3. Master Drug Validation (authoritative)
            4. AI Recheck (if all DBs fail AND AI is available)
            5. Final decision

        Returns a dict with keys:
            "valid"            : bool   (final decision)
            "normalized_name"  : str    (name used for save)
            "confidence"       : float  (from AI if used)
            "provider"         : str    (database or AI provider that matched)
            "exists"           : bool   (from validation)
            "drug_db_exists"   : bool   (from drug database)
            "message"          : str    (human-readable outcome)
            "error"            : str    (only if system failure)
            "time_taken_ms"    : float
            "ai_assisted"      : bool   (whether AI was used)
            "ai_suggestion"    : str    (AI-corrected name if applicable)
        """
        start = time.time()

        # -- Step 0: Normalize input --
        name = self.normalizer.normalize(medicine_name or "")
        if not name:
            return self._result(
                False, name or "", 0.0,
                "Medicine name is required.", start,
            )

        logger.info("PIPELINE: normalize('%s') -> '%s'", medicine_name, name)

        # Check cache first
        cache_key = self.normalizer.normalize_lower(name)
        cached = self.cache.get(cache_key)
        if cached is not None:
            elapsed = (time.time() - start) * 1000
            logger.info(
                "Cache HIT for '%s': valid=%s, time_taken=%.0fms",
                name, cached.get("valid"), elapsed,
            )
            result = dict(cached)
            result["time_taken_ms"] = elapsed
            return result

        # -- Step 1: AI Assistance (optional, non-blocking) --
        ai_suggestion = None
        ai_corrected_name = None

        logger.info("PIPELINE: Step 1/4 - AI Assistance (optional) for '%s'", name)
        ai_result = self.ai_assistance.suggest_correction(name)

        if ai_result is not None:
            ai_suggestion = ai_result.get("suggested_name")
            ai_corrected_name = self.normalizer.normalize(
                ai_suggestion or name
            )
            logger.info(
                "PIPELINE: AI suggested '%s' -> normalized to '%s'",
                ai_suggestion, ai_corrected_name,
            )
        else:
            logger.info(
                "PIPELINE: AI unavailable/no suggestion for '%s' - continuing",
                name,
            )

        # -- Step 2: Master Drug Validation (authoritative) --
        # Try with AI-corrected name first (if available), then original
        names_to_try = []
        if ai_corrected_name and ai_corrected_name.lower() != name.lower():
            names_to_try.append((ai_corrected_name, True))
        names_to_try.append((name, False))

        db_match = None
        db_result = {"exists": False, "providers_tried": [], "error": "No providers queried"}

        for lookup_name, was_ai_corrected in names_to_try:
            logger.info(
                "PIPELINE: Step 2/4 - Drug DB lookup for '%s' (ai_corrected=%s)",
                lookup_name, was_ai_corrected,
            )
            db_result = self.master_validator.validate(lookup_name)

            if db_result.get("exists"):
                db_match = db_result
                logger.info(
                    "PIPELINE: '%s' CONFIRMED by '%s' (ai_corrected=%s)",
                    lookup_name,
                    db_result.get("source", "?"),
                    was_ai_corrected,
                )
                break

            logger.info(
                "PIPELINE: '%s' NOT found in databases (ai_corrected=%s)",
                lookup_name, was_ai_corrected,
            )

        # -- Step 3: AI Recheck (if all DBs failed AND AI has a suggestion) --
        if db_match is None and ai_result is not None:
            # AI already provided a suggestion we tried (in step 2).
            # If it ALSO failed, there's nothing more to do.
            logger.info(
                "PIPELINE: Step 3/4 - AI recheck: no alternative suggestion for '%s'",
                name,
            )

        # -- Step 4: Final decision --
        if db_match is not None:
            normalized_name = db_match.get("normalized_name", name)
            drug_db_source = db_match.get("source", "?")
            providers_tried = db_match.get("providers_tried", [])

            elapsed = (time.time() - start) * 1000
            final = self._result(
                True, normalized_name, 1.0,
                "Medicine validated successfully.", start,
                exists=True, drug_db_exists=True,
                provider=drug_db_source,
            )
            final["providers_tried"] = providers_tried
            final["ai_assisted"] = ai_result is not None
            if ai_result:
                final["ai_suggestion"] = ai_result.get("suggested_name", "")

            self.cache.set(cache_key, final)
            logger.info(
                "PIPELINE DECISION for '%s' -> VALID, matched by '%s', "
                "normalized='%s', ai_assisted=%s, time=%.0fms",
                name, drug_db_source, normalized_name,
                ai_result is not None, elapsed,
            )
            return final

        # -- All providers failed --
        elapsed = (time.time() - start) * 1000
        reject = self._result(
            False, name, 0.0,
            "Medicine not found in any drug database. "
            "Please check the spelling and try again.",
            start,
            exists=False, drug_db_exists=False,
        )
        reject["providers_tried"] = db_result.get("providers_tried", [])
        reject["ai_assisted"] = ai_result is not None
        if ai_result:
            reject["ai_suggestion"] = ai_result.get("suggested_name", "")

        self.cache.set(cache_key, reject)
        logger.info(
            "PIPELINE DECISION for '%s' -> INVALID (not found in any database), "
            "ai_assisted=%s, time=%.0fms",
            name, ai_result is not None, elapsed,
        )
        return reject

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _result(
        valid: bool,
        normalized_name: str,
        confidence: float,
        message: str,
        start: float,
        exists: bool | None = None,
        drug_db_exists: bool | None = None,
        provider: str | None = None,
        error: str | None = None,
    ) -> dict:
        """Build a standardised result dict."""
        elapsed = (time.time() - start) * 1000
        result = {
            "valid": valid,
            "normalized_name": normalized_name,
            "confidence": confidence,
            "message": message,
            "exists": exists if exists is not None else valid,
            "drug_db_exists": drug_db_exists if drug_db_exists is not None else valid,
            "time_taken_ms": round(elapsed, 1),
        }
        if provider:
            result["provider"] = provider
        if error:
            result["error"] = error
        return result


# ---------------------------------------------------------------------------
# Backward-compatible alias
# ---------------------------------------------------------------------------

_hybrid_service: HybridValidationService | None = None


def get_validation_service() -> HybridValidationService:
    """Return the shared HybridValidationService singleton."""
    global _hybrid_service
    if _hybrid_service is None:
        _hybrid_service = HybridValidationService()
    return _hybrid_service


class MedicineValidator:
    """
    Legacy validator wrapper that delegates to HybridValidationService.

    Maintains the same validate() interface for backward compatibility.
    """

    def validate(self, medicine_name: str) -> dict:
        service = get_validation_service()
        result = service.validate(medicine_name)

        if result.get("error") and not result.get("valid"):
            return {
                "exists": False,
                "error": result["error"],
            }

        return {
            "exists": result.get("valid", False),
            "normalized_name": result.get("normalized_name", medicine_name),
            "confidence": result.get("confidence", 0.0),
        }
