"""Drug database provider interface and implementations.

This module follows the Strategy / Provider pattern so that different
drug database backends can be swapped without changing business logic.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional

import requests

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RXNORM_APPROX_URL = "https://rxnav.nlm.nih.gov/REST/approximateTerm.json"
OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"

# Minimum score from RxNorm approximateTerm to consider a match meaningful.
RXNORM_SCORE_THRESHOLD = 5.0

# HTTP request timeout
REQUEST_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Abstract Provider Interface
# ---------------------------------------------------------------------------

class DrugDatabaseProvider(ABC):
    """Abstract interface for drug database lookups.

    All drug database providers must implement the ``lookup`` method.
    """

    @abstractmethod
    def lookup(self, medicine_name: str) -> dict:
        """Look up a medicine name in the drug database.

        Args:
            medicine_name: The medicine name to look up (raw user input).

        Returns:
            A dict with keys:
                "exists"         : bool
                "normalized_name": str (only when exists=True)
                "source"         : str (optional, indicates which backend found the match)
            If the lookup itself fails (network, timeout, etc.) the provider
            may return {"exists": False, "error": "..."}.
        """
        ...


# ---------------------------------------------------------------------------
# RxNorm + OpenFDA Provider (fallback chain)
# ---------------------------------------------------------------------------

class RxNormOpenFDAProvider(DrugDatabaseProvider):
    """Drug database provider that queries RxNorm first, then OpenFDA.

    Uses entirely free, no-API-key-required public APIs from the
    U.S. National Library of Medicine (RxNorm) and the FDA (OpenFDA).
    Contains hundreds of thousands of drug concepts (brand + generic)
    from global sources including RXNORM, DRUGBANK, ATC, USP, VANDF, etc.
    """

    def lookup(self, medicine_name: str) -> dict:
        """Look up *medicine_name* in RxNorm -> fallback to OpenFDA.

        Decision logic:
            1. Try RxNorm approximate term search (US NLM database)
            2. Try OpenFDA label search (US FDA database)
            3. If both US databases fail and the name looks like a real
               medicine (not obviously fake), return exists=True.

        Why step 3 exists:
            RxNorm and OpenFDA are US-centric databases.  Many valid
            international / Indian brand medicines (e.g. Ciplox, Dolo)
            are not indexed there.  The AI provider (Gemini/OpenAI) is
            trained on a much broader corpus and has already validated
            the medicine.  Forbidding a medicine because it is not in a
            US-only database would block legitimate medicines from
            non-US markets — which is unacceptable for a global app.

        Safety:
            This fallback is only reached when both US APIs have
            genuinely been queried and found no match.  Truly invalid
            inputs ("Chocolate", "RandomMedicineXYZ") are filtered
            earlier by the AI provider, so they never reach this method.
        """
        name = (medicine_name or "").strip()
        if not name:
            return {"exists": False, "error": "Medicine name cannot be empty."}

        # -- 1. Try RxNorm approximate term search --
        rxnorm_result = self._check_rxnorm(name)
        if rxnorm_result is not None and rxnorm_result.get("exists"):
            logger.info(
                "RxNorm found '%s' -> normalized='%s'",
                name,
                rxnorm_result.get("normalized_name", name),
            )
            return rxnorm_result

        # -- 2. Try OpenFDA label search as fallback --
        openfda_result = self._check_openfda(name)
        if openfda_result is not None and openfda_result.get("exists"):
            # OpenFDA returns labels for ANY term found on a drug label, including
            # inactive ingredients and food names.  Cross-check with RxNorm to
            # avoid accepting non-medicine terms (e.g. "Chocolate").
            rxnorm_any = self._check_rxnorm_any(name)
            if rxnorm_any is not None:
                logger.info(
                    "OpenFDA found '%s' (RxNorm also has candidates) -> accepting",
                    name,
                )
                return openfda_result
            logger.info(
                "OpenFDA found '%s' but RxNorm has NO candidates -> rejecting "
                "(likely non-drug term appearing on a label)",
                name,
            )

        # -- 3. RxNorm fuzzy check: any candidate at all? --
        # Even if the score is below threshold or the source is
        # non-authoritative, if RxNorm returned ANY candidate,
        # the name at least resembles something in the drug
        # knowledge base.  Accept with a "fuzzy" source marker.
        rxnorm_any = self._check_rxnorm_any(name)
        if rxnorm_any is not None and rxnorm_any.get("exists"):
            logger.info(
                "Drug DB: '%s' found via RxNorm fuzzy match (source=%s)",
                name,
                rxnorm_any.get("source", "?"),
            )
            return rxnorm_any

        # -- 4. No database found the medicine --
        logger.info(
            "Drug DB: '%s' NOT found in any database (RxNorm, OpenFDA, fuzzy)",
            name,
        )
        return {"exists": False, "error": f"Medicine not found in any drug database."}

    # ------------------------------------------------------------------
    # RxNorm approximate term search
    # ------------------------------------------------------------------

    def _check_rxnorm(self, name: str) -> Optional[dict]:
        """Query RxNorm approximateTerm API. Returns result dict or None on failure."""
        params = {"term": name, "maxEntries": 5}
        try:
            resp = requests.get(
                RXNORM_APPROX_URL,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as exc:
            logger.warning("RxNorm API call failed for '%s': %s", name, exc)
            return None

        candidates = (
            data.get("approximateGroup", {}).get("candidate", [])
        )
        if not candidates:
            return None

        best = None
        for c in candidates:
            score = float(c.get("score", 0))
            source = (c.get("source") or "").upper()
            cand_name = c.get("name", "")

            # Authoritative sources only — USP and NDDF are excluded
            # because they contain non-drug items (foods, products).
            if source in ("RXNORM", "DRUGBANK", "ATC", "VANDF", "GS", "MMSL"):
                if score >= RXNORM_SCORE_THRESHOLD:
                    # Skip candidates where the name is just the input with
                    # extra words appended (e.g. "Chocolate" -> "CHOCOLATE FLAVORING").
                    # This catches non-therapeutic items that happen to exist
                    # in a drug terminology database.
                    if cand_name and self._is_weak_match(name, cand_name):
                        logger.info(
                            "RxNorm weak match for '%s' -> '%s' (source=%s), skipping",
                            name, cand_name, source,
                        )
                        continue
                    if best is None or score > best["score"]:
                        best = {
                            "exists": True,
                            "normalized_name": cand_name or name,
                            "score": score,
                            "source": source,
                        }

        if best:
            return {"exists": True, "normalized_name": best["normalized_name"]}

        return None

    @staticmethod
    def _is_weak_match(input_name: str, candidate_name: str) -> bool:
        """Check if the candidate name is a weak match for the input.

        A weak match occurs when the input is a substring of the
        candidate name and the candidate is significantly longer.
        This catches cases like "Chocolate" -> "CHOCOLATE FLAVORING"
        where the input matches a non-therapeutic item in the database.
        """
        inp = input_name.strip().lower()
        cand = candidate_name.strip().lower()
        if not inp or not cand:
            return False
        # If candidate is more than 50% longer than input and
        # input is a substring of candidate, it's a weak match.
        if len(cand) > len(inp) * 1.5 and inp in cand:
            return True
        return False

    # ------------------------------------------------------------------
    # RxNorm fuzzy / any-candidate check
    # ------------------------------------------------------------------

    def _check_rxnorm_any(self, name: str) -> Optional[dict]:
        """Check if RxNorm returns ANY candidate for *name*.

        Unlike _check_rxnorm, this accepts candidates from ANY source
        and at ANY score.  It is used as a broad fallback to catch
        international / Indian brands that may have a partial match
        in the RxNorm terminology system but fail the authoritative
        source + threshold check.

        Returns {"exists": True, "normalized_name": ..., "source": "rxnorm_fuzzy"}
        if at least one candidate exists, otherwise None.
        """
        params = {"term": name, "maxEntries": 5}
        try:
            resp = requests.get(
                RXNORM_APPROX_URL,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as exc:
            logger.warning("RxNorm fuzzy check failed for '%s': %s", name, exc)
            return None

        candidates = (
            data.get("approximateGroup", {}).get("candidate", [])
        )
        if not candidates:
            return None

        # Fuzzy sources to exclude (known non-drug items or non-authoritative)
        EXCLUDED_SOURCES = {"USP", "NDDF", "MMX", "MTHSPL"}

        # Any candidate at all — find the one with the most meaningful name
        best_candidate = None
        for c in candidates:
            source = (c.get("source") or "").upper()
            # Skip candidates from sources known to contain non-drug items
            if source in EXCLUDED_SOURCES:
                continue
            cand_name = c.get("name", "")
            # Skip candidates with no real name
            if not cand_name or cand_name.strip() in ("", "?"):
                continue
            score = float(c.get("score", 0))
            if best_candidate is None or score > best_candidate["score"]:
                best_candidate = {
                    "name": cand_name.strip(),
                    "score": score,
                }

        if best_candidate:
            logger.info(
                "RxNorm fuzzy match for '%s' -> '%s' (score=%.1f)",
                name,
                best_candidate["name"],
                best_candidate["score"],
            )
            return {
                "exists": True,
                "normalized_name": best_candidate["name"],
                "source": "rxnorm_fuzzy",
            }

        return None

    # ------------------------------------------------------------------
    # OpenFDA label search (fallback)
    # ------------------------------------------------------------------

    def _check_openfda(self, name: str) -> Optional[dict]:
        """Query OpenFDA label endpoint. Returns result dict or None on failure."""
        escaped = self._escape_fda(name)
        search_query = (
            f'openfda.brand_name:"{escaped}"'
            f'+OR+openfda.generic_name:"{escaped}"'
            f'+OR+openfda.substance_name:"{escaped}"'
        )
        url = f"{OPENFDA_LABEL_URL}?search={search_query}&limit=1"

        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 404:
                first_word = name.split()[0] if len(name.split()) > 1 else None
                if first_word and first_word != name:
                    return self._check_openfda(first_word)
                return None
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as exc:
            logger.warning("OpenFDA API call failed for '%s': %s", name, exc)
            return None

        total = data.get("meta", {}).get("results", {}).get("total", 0)
        if total > 0:
            return {"exists": True, "normalized_name": name}

        first_word = name.split()[0] if len(name.split()) > 1 else None
        if first_word and first_word != name:
            return self._check_openfda(first_word)

        return None

    @staticmethod
    def _escape_fda(value: str) -> str:
        """Escape a value for inclusion in an OpenFDA Lucene search string."""
        special = r'+\-&|!(){}[]^"~*?:\\/'
        result = []
        for ch in value:
            if ch in special:
                result.append(f"\\{ch}")
            else:
                result.append(ch)
        return "".join(result)
