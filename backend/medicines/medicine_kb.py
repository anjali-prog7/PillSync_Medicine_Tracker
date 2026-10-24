"""Local medicine knowledge base for offline OCR verification.

This knowledge base is the PRIMARY authority for verifying OCR-extracted
medicine names.  It works fully offline (no API keys, no network) and
prevents hallucinated medicine names from ever being returned.
"""

from __future__ import annotations

import datetime
import difflib
import re

MEDICINE_KB: dict[str, list[str]] = {
    "Paracetamol": ["paracetamol", "acetaminophen", "tylenol", "panadol", "pcm"],
    "Dolo 650": ["dolo 650", "dolo"],
    "Crocin": ["crocin"],
    "Calpol": ["calpol"],
    "Combiflam": ["combiflam"],
    "Ibuprofen": ["ibuprofen", "brufen", "ibugesic"],
    "Naproxen": ["naproxen", "naprosyn"],
    "Diclofenac": ["diclofenac", "voveran"],
    "Mefenamic Acid": ["mefenamic acid", "meftal"],
    "Aspirin": ["aspirin", "ecosprin"],
    "Etoricoxib": ["etoricoxib", "etorix", "arcoxia"],
    "Aceclofenac": ["aceclofenac", "zerodol"],
    "Ketorolac": ["ketorolac"],
    "Nimesulide": ["nimesulide", "nise", "nicip"],
    "Saridon": ["saridon"],
    "Disprin": ["disprin"],
    "Analgin": ["analgin", "metamizole"],
    "Tramadol": ["tramadol"],
    "Amoxicillin": ["amoxicillin", "amoxil", "amox"],
    "Amoxicillin-Clavulanate": ["augmentin", "amoxiclav", "clavam"],
    "Azithromycin": ["azithromycin", "azithral", "zithromax", "az", "azi"],
    "Ciprofloxacin": ["ciprofloxacin", "ciplox", "cip", "cifran"],
    "Ofloxacin": ["ofloxacin", "zanocin"],
    "Levofloxacin": ["levofloxacin", "levomac"],
    "Cefixime": ["cefixime", "taxim", "zifi"],
    "Cefpodoxime": ["cefpodoxime"],
    "Ceftriaxone": ["ceftriaxone", "monocef"],
    "Cefuroxime": ["cefuroxime"],
    "Cephalexin": ["cephalexin", "keflex"],
    "Doxycycline": ["doxycycline"],
    "Metronidazole": ["metronidazole", "flagyl"],
    "Tinidazole": ["tinidazole"],
    "Nitrofurantoin": ["nitrofurantoin"],
    "Clarithromycin": ["clarithromycin", "claricid"],
    "Erythromycin": ["erythromycin"],
    "Linezolid": ["linezolid"],
    "Norfloxacin": ["norfloxacin", "norilet"],
    "Fosfomycin": ["fosfomycin"],
    "Metformin": ["metformin", "glycomet", "glucophage"],
    "Glimepiride": ["glimepiride", "amaride", "amaryl"],
    "Gliclazide": ["gliclazide", "diamicron"],
    "Glipizide": ["glipizide"],
    "Pioglitazone": ["pioglitazone"],
    "Sitagliptin": ["sitagliptin", "januvia", "sitaglim"],
    "Vildagliptin": ["vildagliptin", "galvus"],
    "Teneligliptin": ["teneligliptin", "teneglim", "teneza"],
    "Empagliflozin": ["empagliflozin", "jardiance"],
    "Dapagliflozin": ["dapagliflozin", "forxiga"],
    "Canagliflozin": ["canagliflozin"],
    "Insulin Glargine": ["insulin glargine", "lantus"],
    "Insulin Aspart": ["insulin aspart", "novorapid"],
    "Insulin": ["insulin"],
    "Amlodipine": ["amlodipine", "amlopres", "amlong", "amlo"],
    "Atenolol": ["atenolol", "tenormin"],
    "Metoprolol": ["metoprolol", "metolar", "lopressor"],
    "Propranolol": ["propranolol", "ciplar"],
    "Telmisartan": ["telmisartan", "teliget", "telma", "telm", "telmikind", "telsartan"],
    "Losartan": ["losartan", "losar"],
    "Valsartan": ["valsartan"],
    "Ramipril": ["ramipril", "cardace"],
    "Enalapril": ["enalapril"],
    "Enalapril Maleate": ["envas"],
    "Atorvastatin": ["atorvastatin", "atorva", "lipitor", "ator", "storvas"],
    "Rosuvastatin": ["rosuvastatin", "rosuvas", "crestor", "rosuv"],
    "Simvastatin": ["simvastatin"],
    "Pitavastatin": ["pitavastatin"],
    "Furosemide": ["furosemide", "lasix"],
    "Torsemide": ["torsemide", "dytor"],
    "Spironolactone": ["spironolactone", "aldactone"],
    "Nitroglycerin": ["nitroglycerin", "sorbitrate"],
    "Isosorbide Mononitrate": ["isosorbide mononitrate"],
    "Clopidogrel": ["clopidogrel", "clopitab", "deplatt"],
    "Digoxin": ["digoxin"],
    "Warfarin": ["warfarin"],
    "Apixaban": ["apixaban"],
    "Dabigatran": ["dabigatran", "pradaxa"],
    "Fenofibrate": ["fenofibrate"],
    "Nifedipine": ["nifedipine", "nicardia", "depin"],
    "Diltiazem": ["diltiazem"],
    "Omeprazole": ["omeprazole", "omez", "risek", "ocid"],
    "Pantoprazole": ["pantoprazole", "pantop", "pantodac", "pantocid", "sompraz"],
    "Esomeprazole": ["esomeprazole", "nexium", "nexpro"],
    "Rabeprazole": ["rabeprazole", "acipan", "razo", "rabeloc"],
    "Lansoprazole": ["lansoprazole"],
    "Ranitidine": ["ranitidine", "rantac", "zinetac", "aciloc", "histac"],
    "Famotidine": ["famotidine"],
    "Antacid": ["antacid", "antacids"],
    "Digene": ["digene"],
    "Gelusil": ["gelusil"],
    "Pantoprazole + Domperidone": ["pan d", "pantop d", "pantop-d", "pantop-dsr"],
    "Domperidone": ["domperidone", "domstal"],
    "Ondansetron": ["ondansetron", "emmeset", "vomilast", "vomikind"],
    "Itopride": ["itopride"],
    "Sucralfate": ["sucralfate", "sucrafil"],
    "Salbutamol": ["salbutamol", "asthalin"],
    "Levosalbutamol": ["levosalbutamol", "levolin"],
    "Montelukast": ["montelukast", "montair"],
    "Ambroxol": ["ambroxol"],
    "Acetylcysteine": ["acetylcysteine", "n-acetylcysteine"],
    "Budesonide": ["budesonide", "budesal", "pulmicort", "budecort"],
    "Formoterol": ["formoterol"],
    "Ipratropium": ["ipratropium"],
    "Cetirizine": ["cetirizine", "cetzine", "zyrtec", "cetrizine"],
    "Levocetirizine": ["levocetirizine", "levocet", "xyzal"],
    "Fexofenadine": ["fexofenadine", "allegra", "telfast"],
    "Loratadine": ["loratadine", "claritin"],
    "Chlorpheniramine": ["chlorpheniramine", "piriton"],
    "Dextromethorphan": ["dextromethorphan", "benadryl"],
    "Guaifenesin": ["guaifenesin"],
    "Benadryl": ["benadryl"],
    "Phenylephrine": ["phenylephrine"],
    "Pseudoephedrine": ["pseudoephedrine"],
    "Theophylline": ["theophylline", "deriphyllin"],
    "Doxofylline": ["doxofylline", "doxovent"],
    "Vitamin D3": ["vitamin d3", "cholecalciferol", "uprise d3", "calcitol"],
    "Vitamin B12": ["vitamin b12", "methylcobalamin", "mecobalamin"],
    "Vitamin C": ["vitamin c", "ascorbic acid", "limcee"],
    "Multivitamin": ["multivitamin", "multivitamins", "supradyn", "revital"],
    "Calcium + Vitamin D3": ["calcium", "calcium sandoz", "shelcal"],
    "Iron Supplement": ["iron", "ferrous", "ferritin"],
    "Folic Acid": ["folic acid", "folate"],
    "Zinc Supplement": ["zinc"],
    "Omega-3": ["omega 3", "omega-3", "fish oil"],
    "Levothyroxine": ["levothyroxine", "thyroxine", "thyronorm", "eltroxin"],
    "Liothyronine": ["liothyronine"],
    "Methimazole": ["methimazole"],
    "Sertraline": ["sertraline", "serlift"],
    "Escitalopram": ["escitalopram", "nexito"],
    "Fluoxetine": ["fluoxetine", "prozac"],
    "Paroxetine": ["paroxetine"],
    "Duloxetine": ["duloxetine", "dulot"],
    "Venlafaxine": ["venlafaxine"],
    "Alprazolam": ["alprazolam", "alprax"],
    "Clonazepam": ["clonazepam", "clonotril", "rivotril"],
    "Diazepam": ["diazepam", "calmpose"],
    "Lorazepam": ["lorazepam", "ativan"],
    "Zolpidem": ["zolpidem"],
    "Pregabalin": ["pregabalin", "pregalin"],
    "Gabapentin": ["gabapentin", "gabantin"],
    "Carbamazepine": ["carbamazepine", "tegrital", "zeptol"],
    "Valproate": ["valproate", "valproic acid", "encorate", "epilex", "valparin"],
    "Levetiracetam": ["levetiracetam", "levipil"],
    "Risperidone": ["risperidone"],
    "Olanzapine": ["olanzapine"],
    "Quetiapine": ["quetiapine"],
    "Betamethasone": ["betamethasone", "betnovate"],
    "Hydrocortisone": ["hydrocortisone"],
    "Clotrimazole": ["clotrimazole", "candid"],
    "Fluconazole": ["fluconazole", "fungicide"],
    "Ketoconazole": ["ketoconazole"],
    "Terbinafine": ["terbinafine", "terbinax"],
    "Miconazole": ["miconazole"],
    "Mupirocin": ["mupirocin", "bactroban"],
    "Neomycin": ["neomycin"],
    "Calamine": ["calamine"],
    "Pancreatin": ["pancreatin", "creon"],
    "Lactulose": ["lactulose", "duphalac"],
    "Isabgol": ["isabgol", "psyllium"],
    "Loperamide": ["loperamide", "imodium"],
    "Ursodeoxycholic Acid": ["ursodeoxycholic", "udiliv"],
    "Silymarin": ["silymarin", "liv 52", "liv-52"],
    "Rifaximin": ["rifaximin"],
    "Moxifloxacin": ["moxifloxacin", "vigamox"],
    "Tobramycin": ["tobramycin"],
    "Olopatadine": ["olopatadine", "olopat"],
    "Latanoprost": ["latanoprost"],
    "Tamsulosin": ["tamsulosin", "tamlosin", "flomax"],
    "Finasteride": ["finasteride"],
    "Sildenafil": ["sildenafil", "viagra"],
    "Tadalafil": ["tadalafil"],
    "Allopurinol": ["allopurinol", "zyloric"],
    "Febuxostat": ["febuxostat", "feburic"],
    "Potassium Citrate": ["potassium citrate"],
    "Himalaya Liv.52": ["liv 52", "liv-52", "liv52"],
    "Chyawanprash": ["chyawanprash", "dabur chyawanprash"],
    "ORS": ["ors", "electral"],
    "Pan 40": ["pan 40", "pan40"],
    "Gas-O-Fast": ["gas-o-fast", "gas o fast"],
    "Eno": ["eno"],
    "Otrivin": ["otrivin"],
    "Vicks": ["vicks"],
    "Calpol 500": ["calpol 500"],
    "Zincovit": ["zincovit"],
    "Sporlac": ["sporlac"],
    "Enterogermina": ["enterogermina"],
    # --- Added common Indian brands / generics (coverage expansion) ---
    "Prochlorperazine": ["prochlorperazine", "stemetil"],
    "Dicyclomine": ["dicyclomine", "cyclopam"],
    "Sitagliptin + Metformin": ["janumet", "sitagliptin metformin"],
    "Cilnidipine": ["cilnidipine", "cilacar"],
    "Bisoprolol": ["bisoprolol", "concor"],
    "Carvedilol": ["carvedilol", "cardivas"],
    "Candesartan": ["candesartan", "candepres"],
    "Olmesartan": ["olmesartan", "olmezest"],
    "Irbesartan": ["irbesartan", "irovel"],
    "Nebivolol": ["nebivolol", "nebicard"],
    "Ivabradine": ["ivabradine", "coralan"],
    "Rivaroxaban": ["rivaroxaban", "xarelto"],
    "Acenocoumarol": ["acenocoumarol", "acitrom"],
    "Meloxicam": ["meloxicam", "mobic"],
    "Pheniramine": ["pheniramine", "avil"],
    "Formoterol + Budesonide": ["foracort", "formoterol budesonide"],
    "Levosalbutamol + Ipratropium": ["duolin", "levosalbutamol ipratropium"],
    "Fluticasone + Salmeterol": ["seretide", "fluticasone salmeterol"],
    "Fluticasone": ["fluticasone", "flixotide", "flohale"],
    "Beclomethasone": ["beclomethasone", "becotide"],
    "Lamotrigine": ["lamotrigine", "lamitor", "lametec"],
    "Oxcarbazepine": ["oxcarbazepine", "trileptal"],
    "Topiramate": ["topiramate", "topamax"],
    "Clobazam": ["clobazam", "frisium"],
    "Mirtazapine": ["mirtazapine"],
    "Carbimazole": ["carbimazole", "neomercazole"],
    "Gemfibrozil": ["gemfibrozil"],
    "Perindopril": ["perindopril", "coversyl"],
    "Albendazole": ["albendazole", "zentel"],
    "Mebendazole": ["mebendazole", "wormin"],
    "Ivermectin": ["ivermectin", "ivermec"],
    "Chloroquine": ["chloroquine"],
    "Hydroxychloroquine": ["hydroxychloroquine", "hcq"],
    "Nitazoxanide": ["nitazoxanide", "nizonide"],
    "Oseltamivir": ["oseltamivir", "tamiflu"],
    "Amikacin": ["amikacin"],
    "Gentamicin": ["gentamicin"],
    "Clindamycin": ["clindamycin", "clindac"],
    "Framycetin": ["framycetin", "soframycin"],
    "Chymoral": ["chymoral", "trypsin chymotrypsin"],
    "Serratiopeptidase": ["serratiopeptidase", "enzim", "seradase"],
}

DISEASE_KEYWORDS: list[str] = [
    "fever", "cold", "cough", "flu", "infection", "bacterial infection",
    "viral infection", "headache", "migraine", "body ache", "pain",
    "diabetes", "type 2 diabetes", "hypertension", "high blood pressure",
    "blood pressure", "cholesterol", "thyroid", "hypothyroidism",
    "acidity", "gastritis", "gas", "indigestion", "ulcer",
    "arthritis", "joint pain", "osteoarthritis", "back pain",
    "allergy", "allergic rhinitis", "asthma", "bronchitis",
    "pneumonia", "tonsillitis", "sore throat", "sinusitis",
    "anemia", "iron deficiency", "vitamin deficiency",
    "depression", "anxiety", "insomnia",
    "uti", "urinary tract infection", "kidney stone",
    "gout", "constipation", "diarrhea", "vomiting", "nausea",
    "skin infection", "fungal infection", "dermatitis", "eczema", "psoriasis",
    "eye infection", "conjunctivitis", "ear infection",
    "heart disease", "cardiac", "angina",
]

# Dosage = a number with a unit of measure (mg, ml, etc.).
# NOTE: tablet/capsule words are deliberately NOT in this regex so that
# "10 tablets" is only ever treated as a QUANTITY, never a dosage.
DOSAGE_RE = re.compile(
    r"(?<!\d)(\d{1,4}(?:\.\d+)?)\s*(mg|mcg|microgram|gram|g|ml|iu|units?)",
    re.IGNORECASE,
)

QUANTITY_RE = re.compile(
    r"(?<!\d)(\d{1,4})\s*(tablets?|tabs?|capsules?|caps?|strips?|bottles?|sachets?|injections?|ampoules?|ml)",
    re.IGNORECASE,
)

DOCTOR_RE = re.compile(
    r"\b(?:dr\.?|doctor)[ \t]+([A-Z][a-zA-Z]+(?:[ \t]+[A-Z][a-zA-Z]+){0,2})",
    re.IGNORECASE,
)

HOSPITAL_RE = re.compile(
    r"\b([A-Z][A-Za-z&.'-]*(?:[ \t]+[A-Z][A-Za-z&.'-]*){0,4})[ \t]+"
    r"(?:hospital|clinic|medical centre|medical center|nursing home|"
    r"care centre|care center|institute|health centre|health center|dispensary)\b",
    re.IGNORECASE,
)

DATE_RE = re.compile(
    r"(?<!\d)(?:"
    # DD/MM/YYYY, DD-MM-YYYY, MM/DD/YYYY (optional spaces around separators)
    r"\d{1,2}\s*[/-]\s*\d{1,2}\s*[/-]\s*\d{2,4}|"
    # YYYY-MM-DD
    r"\d{4}\s*[/-]\s*\d{1,2}\s*[/-]\s*\d{1,2}|"
    # Textual: 31 Jul 2026
    r"\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{2,4}"
    r")(?!\d)",
    re.IGNORECASE,
)

# Month name -> number (for textual dates such as '31 Jul 2026').
MONTH_NAMES: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Dosage / duration / frequency keywords used for structured summaries.
DURATION_RE = re.compile(
    r"(?<!\d)(\d{1,3})\s*(days?|weeks?|months?)(?!\w)",
    re.IGNORECASE,
)

PATIENT_RE = re.compile(
    r"\b(?:patient(?:'?s)?(?:\s+name)?|name\s+of\s+patient)\s*[:.\-]?\s*"
    r"(?:(?:dr|prof(?:essor)?|md|mbbs|ms|dnb|dm|mch)\s*\.?\s+)?"
    r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})",
    re.IGNORECASE,
)

# OCR label words that must NEVER be treated as a patient name. When a
# 'Patient' label is directly followed by one of these (e.g. "Patient
# Name: Date: 25/07/2026" or "Patient: Doctor: ..."), the captured word
# is rejected so the caller falls back to "Not Available" instead of
# inventing a patient name from a section heading.
PATIENT_LABEL_WORDS: set[str] = {
    "date", "dated", "doctor", "hospital", "clinic", "clinical",
    "medicine", "medicines", "medication", "prescription", "rx",
    "name", "patient", "address", "age", "sex", "male", "female",
    "phone", "mobile", "email", "weight", "temperature", "bp",
    "blood", "pressure", "pulse", "consultant", "department",
    "signature", "sign", "reg", "registration", "id", "opd", "ipd",
    "visit", "follow", "followup", "ward", "bed", "unit", "referred",
    "ref", "dob", "disease", "diagnosis", "complaints", "chief",
    "complaint", "instructions", "information", "leaflet", "guidance",
    "number", "no", "file", "case", "history", "symptoms",
    "treatment", "notes", "note", "allergies", "occupation", "marital",
    "status", "religion", "group", "prof", "professor", "md", "mbbs",
    "ms", "dnb", "dm", "mch", "phd", "not", "available", "none", "nil",
}

FREQUENCY_KEYWORDS: list[str] = [
    "once daily", "once a day", "twice daily", "twice a day",
    "thrice daily", "three times a day", "four times a day",
    "once", "twice", "thrice", "bd", "od", "tds", "qid", "hs",
    "morning", "afternoon", "evening", "night", "bedtime",
    "after meals", "before meals", "after food", "before food",
    "before breakfast", "after breakfast", "before lunch", "after lunch",
    "before dinner", "after dinner",
    "empty stomach", "with meals", "as needed", "as required",
    "1-0-1", "0-0-1", "1-1-1", "1-1-0",
]


def normalize(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.lower())


def find_medicines(text: str) -> list[str]:
    """Return canonical medicine names found in *text* (whole-word match)."""
    if not text or not text.strip():
        return []
    normalized = normalize(text)
    found: list[str] = []
    for canonical, tokens in MEDICINE_KB.items():
        for token in tokens:
            pattern = r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])"
            if re.search(pattern, normalized):
                if canonical not in found:
                    found.append(canonical)
                break
    return found


def find_medicine_positions(text: str) -> list[tuple[int, str]]:
    """Return [(start_index, canonical_name)] for every KB match."""
    if not text or not text.strip():
        return []
    normalized = normalize(text)
    positions: list[tuple[int, str]] = []
    for canonical, tokens in MEDICINE_KB.items():
        for token in tokens:
            pattern = r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])"
            m = re.search(pattern, normalized)
            if m:
                positions.append((m.start(), canonical))
                break
    return positions


def find_first_medicine(text: str) -> str | None:
    """Return the medicine whose token appears EARLIEST in the text.

    For a strip reading 'DOLO 650 PARACETAMOL', 'Dolo 650' appears first
    and is chosen as the primary medicine.
    """
    positions = find_medicine_positions(text)
    if not positions:
        return None
    positions.sort(key=lambda x: x[0])
    return positions[0][1]


# ---------------------------------------------------------------------------
# Production-grade medicine matching (exact → merged-token → alias → fuzzy)
# ---------------------------------------------------------------------------
#
# Exact whole-word matching is the primary authority (never a false
# positive).  When it fails, two SAFE fallbacks are consulted:
#
#   1. MERGED-TOKEN matching: OCR frequently glues words together
#      ('PARACETAMOLTABLETS', 'TABPARACETAMOL500MG').  A KB token embedded
#      inside a longer word is accepted ONLY when the whole word splits
#      into known pieces (KB tokens + packaging words + numbers).
#
#   2. FUZZY matching: a word is matched to the closest KB token when the
#      similarity is high (>= FUZZY_MATCH_THRESHOLD) and unambiguous.  A
#      candidate that is also close to a *different* medicine is rejected
#      so no false positives are introduced.

# Ratio above which a (mis)spelled word is trusted as a medicine name.
FUZZY_MATCH_THRESHOLD = 0.84

# Minimum KB-token length eligible for fuzzy matching (protects short,
# ambiguous tokens such as 'dolo' or 'eno' from false positives).
_FUZZY_MIN_TOKEN_LEN = 5

# Words that must never be fuzzy-matched as medicine names (packaging
# text, instructions, diseases, frequencies, common English words).
_FUZZY_STOP_WORDS: set[str] = {
    "a", "an", "and", "are", "as", "at", "away", "before", "behind",
    "bottle", "bottles", "by", "children", "composition", "consult",
    "contains", "content", "contents", "date", "dated", "days", "day",
    "do", "doctor", "dose", "dosage", "each", "eat", "exp", "fluid",
    "fluids", "food", "for", "from", "in", "is", "keep", "label",
    "leaflet", "lic", "mfg", "mfd", "meals", "meal", "medicine",
    "medicines", "medication", "moisture", "month", "months", "mrp",
    "name", "net", "no", "not", "of", "on", "oral", "pack", "packs",
    "patient", "pharmacy", "pharmacist", "please", "plenty",
    "prescription", "price", "protected", "quantity", "regularly",
    "rest", "salt", "sleep", "store", "strip", "strips", "sugar",
    "symptoms", "tablet", "tablets", "tabs", "tab", "take", "taking",
    "the", "this", "to", "use", "using", "water", "week", "weeks",
    "weight", "with", "you", "your", "capsule", "capsules", "caps",
    "cap", "syrup", "suspension", "drops", "drop", "injection",
    "ointment", "gel", "cream", "spray", "lozenge", "lozenges",
    "sachet", "sachets", "vial", "ampoule", "ampoules", "instructions",
    "ingredients", "information", "fever", "cold", "cough", "flu",
    "pain", "headache", "migraine", "diabetes", "hypertension",
    "cholesterol", "thyroid", "acidity", "gastritis", "indigestion",
    "arthritis", "allergy", "asthma", "bronchitis", "pneumonia",
    "tonsillitis", "sinusitis", "anemia", "depression", "anxiety",
    "insomnia", "constipation", "diarrhea", "vomiting", "nausea",
    "morning", "evening", "night", "afternoon", "bedtime", "breakfast",
    "lunch", "dinner", "daily", "times", "once", "twice", "thrice",
    "food", "meals", "meal", "water", "fluids", "plenty", "avoid",
    "rest", "sleep", "take", "taking", "drink", "consult", "regularly",
    "follow", "visit", "continue", "stop", "report", "exercise",
    "review", "repeat", "before", "after", "with", "empty", "stomach",
    "required", "needed", "please", "contact", "doctor", "hospital",
    "clinic", "ward", "bed", "unit", "opd", "ipd", "history", "notes",
    "signature", "reg", "address", "phone", "mobile", "email", "male",
    "female", "blood", "pressure", "pulse", "temperature", "weight",
    "height", "age", "sex", "dob", "beautiful", "colorful", "pretty",
    "parrot", "sitting", "branch", "photo", "picture", "image",
    "sample", "example", "above", "below", "left", "right", "side",
    "front", "back", "top", "bottom", "centre", "center", "middle",
    "another", "other", "others", "these", "those", "there", "their",
    "they", "them", "have", "has", "had", "been", "being", "will",
    "would", "could", "should", "can", "may", "might", "must", "shall",
    "very", "much", "many", "more", "most", "some", "any", "all",
    "both", "each", "every", "either", "neither", "between", "among",
    "about", "above", "across", "after", "against", "along", "around",
    "because", "before", "behind", "below", "beneath", "beside",
    "between", "beyond", "during", "except", "inside", "outside",
    "into", "onto", "over", "through", "under", "until", "upon",
    "within", "without", "first", "second", "third", "next", "last",
    "again", "also", "always", "never", "often", "sometimes", "usually",
    "today", "tomorrow", "yesterday", "now", "then", "than", "then",
    "there", "where", "when", "what", "which", "who", "whom", "whose",
    "how", "why", "one", "two", "three", "four", "five", "six",
    "seven", "eight", "nine", "ten", "hundred", "thousand", "part",
    "parts", "piece", "pieces", "strip", "strips", "bottle", "bottles",
}

# Packaging / strip words that frequently glue to a medicine name in OCR
# output (e.g. 'PARACETAMOLTABLETS').  Used by the merged-token splitter.
_MERGE_ALLOWED_WORDS: set[str] = {
    "tablet", "tablets", "tabs", "tab", "capsule", "capsules", "caps",
    "cap", "strip", "strips", "bottle", "bottles", "sachet", "sachets",
    "syrup", "suspension", "drops", "drop", "injection", "ampoule",
    "ampoules", "vial", "ointment", "gel", "cream", "spray", "lozenge",
    "lozenges", "ip", "bp", "usp", "each", "contains", "composition",
    "mfg", "mfd", "exp", "mrp", "lic", "net", "wt", "weight", "pack",
    "packs", "leaflet", "label", "price", "mg", "mcg", "ml", "g", "iu",
}

_MERGE_NUMBER_RE = re.compile(r"\d{1,4}(?:mg|mcg|ml|g|iu|tab|tabs|cap|caps)?")

# Single-word KB tokens (>= 4 chars), sorted longest-first for greedy splits.
_KB_SINGLE_TOKENS: list[str] = sorted(
    {
        t.replace(" ", "")
        for tokens in MEDICINE_KB.values()
        for t in tokens
        if len(t.replace(" ", "")) >= 4
    },
    key=len,
    reverse=True,
)

_MERGE_ALLOWED_SORTED: list[str] = sorted(
    _MERGE_ALLOWED_WORDS, key=len, reverse=True
)


def is_fuzzy_candidate(word: str) -> bool:
    """True when *word* may be considered for fuzzy medicine matching."""
    return (
        bool(word)
        and word.isalpha()
        and len(word) >= _FUZZY_MIN_TOKEN_LEN
        and word.lower() not in _FUZZY_STOP_WORDS
    )


def _fuzzy_best(word: str):
    """Return (canonical_name, ratio) for the best unambiguous fuzzy match.

    A word matches only when its closest KB token scores >= threshold and
    no *different* canonical is within 0.06 of that score (ambiguity guard).
    Returns None when there is no safe match.
    """
    matches: list[tuple[float, str]] = []
    wl = word.lower()
    for canonical, tokens in MEDICINE_KB.items():
        best_ratio = 0.0
        for token in tokens:
            token_c = token.replace(" ", "")
            tl = len(token_c)
            if tl < _FUZZY_MIN_TOKEN_LEN or abs(tl - len(wl)) > 3:
                continue
            ratio = difflib.SequenceMatcher(None, wl, token_c).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
        if best_ratio >= FUZZY_MATCH_THRESHOLD:
            matches.append((best_ratio, canonical))
    if not matches:
        return None
    matches.sort(key=lambda x: x[0], reverse=True)
    top_ratio, top_canon = matches[0]
    for ratio, canon in matches[1:]:
        if canon != top_canon and top_ratio - ratio < 0.06:
            return None  # ambiguous — refuse to guess
    return top_canon, top_ratio


def find_medicines_fuzzy(text: str) -> list[str]:
    """Return canonical medicines matched via safe fuzzy (typo) matching.

    No false positives: short words, stop words and ambiguous candidates
    are never returned.
    """
    if not text or not text.strip():
        return []
    normalized = normalize(text)
    found: list[str] = []
    for m in re.finditer(r"[a-z]{%d,}" % _FUZZY_MIN_TOKEN_LEN, normalized):
        word = m.group(0)
        if not is_fuzzy_candidate(word):
            continue
        fb = _fuzzy_best(word)
        if fb and fb[0] not in found:
            found.append(fb[0])
    return found


def _containing_word(text: str, start: int, end: int) -> str:
    """Return the full alnum word of *text* that contains [start, end)."""
    s, e = start, end
    while s > 0 and text[s - 1].isalnum():
        s -= 1
    while e < len(text) and text[e].isalnum():
        e += 1
    return text[s:e]


def _split_word_pieces(word: str) -> list[str] | None:
    """Greedily split *word* into allowed pieces (KB tokens / packaging
    words / numbers).  Returns None if ANY piece is not allowed."""
    pieces: list[str] = []
    i, n = 0, len(word)
    while i < n:
        matched = False
        for t in _KB_SINGLE_TOKENS:
            if word.startswith(t, i):
                pieces.append(t)
                i += len(t)
                matched = True
                break
        if matched:
            continue
        for t in _MERGE_ALLOWED_SORTED:
            if word.startswith(t, i):
                pieces.append(t)
                i += len(t)
                matched = True
                break
        if matched:
            continue
        m = _MERGE_NUMBER_RE.match(word, i)
        if m:
            pieces.append(m.group(0))
            i = m.end()
            continue
        return None
    return pieces


def _is_valid_merge(word: str, token: str) -> bool:
    """True when *word* is a legitimate OCR merge containing *token*.

    The whole word must split into >= 2 allowed pieces and include the
    KB token itself.  Any unrecognisable remainder rejects the merge, so
    a random English word containing a KB token never false-positively
    splits.
    """
    if len(word) <= len(token):
        return False
    pieces = _split_word_pieces(word)
    if not pieces or len(pieces) < 2:
        return False
    return token in pieces


def find_medicines_merged(text: str) -> list[str]:
    """Return canonical medicines found inside merged OCR tokens
    (e.g. 'PARACETAMOLTABLETS' -> Paracetamol)."""
    if not text or not text.strip():
        return []
    normalized = normalize(text)
    found: list[str] = []
    for canonical, tokens in MEDICINE_KB.items():
        for token in tokens:
            token_c = token.replace(" ", "")
            if len(token_c) < 4:
                continue
            hit = False
            for m in re.finditer(re.escape(token_c), normalized):
                word = _containing_word(normalized, m.start(), m.end())
                if word == token_c:
                    continue  # exact standalone match — not a merge
                if _is_valid_merge(word, token_c):
                    hit = True
                    break
            if hit:
                if canonical not in found:
                    found.append(canonical)
                break
    return found


_TYPE_RANK = {"exact": 0, "merged": 1, "fuzzy": 2}


def find_all_matches(text: str) -> list[dict]:
    """Combined production matcher: exact → merged → fuzzy.

    Returns one dict per canonical medicine, ordered by position:
        {"name", "position", "type", "matched"}
    Exact beats merged beats fuzzy for the same canonical; earliest
    occurrence wins within a match type.
    """
    if not text or not text.strip():
        return []
    normalized = normalize(text)
    best: dict[str, dict] = {}

    def consider(name: str, pos: int, mtype: str, matched: str):
        rank = _TYPE_RANK[mtype]
        cur = best.get(name)
        if cur is None or rank < cur["rank"] or (
            rank == cur["rank"] and pos < cur["position"]
        ):
            best[name] = {
                "name": name,
                "position": pos,
                "type": mtype,
                "matched": matched,
                "rank": rank,
            }

    # 1. Exact whole-word matches (primary authority).
    for canonical, tokens in MEDICINE_KB.items():
        for token in tokens:
            pattern = r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])"
            m = re.search(pattern, normalized)
            if m:
                consider(canonical, m.start(), "exact", token)
                break

    # 2. Merged-token matches (KB token glued to packaging words).
    for canonical, tokens in MEDICINE_KB.items():
        for token in tokens:
            token_c = token.replace(" ", "")
            if len(token_c) < 4:
                continue
            for m in re.finditer(re.escape(token_c), normalized):
                word = _containing_word(normalized, m.start(), m.end())
                if word == token_c:
                    continue
                if _is_valid_merge(word, token_c):
                    consider(canonical, m.start(), "merged", token_c)
                    break

    # 3. Fuzzy (typo-tolerant) matches.
    for m in re.finditer(r"[a-z]{%d,}" % _FUZZY_MIN_TOKEN_LEN, normalized):
        word = m.group(0)
        if not is_fuzzy_candidate(word):
            continue
        fb = _fuzzy_best(word)
        if fb:
            consider(fb[0], m.start(), "fuzzy", word)

    return sorted(best.values(), key=lambda x: x["position"])


def find_medicines_extended(text: str) -> list[str]:
    """Canonical medicine names via the full exact→merged→fuzzy pipeline."""
    return [m["name"] for m in find_all_matches(text)]


def find_medicine_positions_extended(text: str) -> list[tuple[int, str]]:
    """[(position, canonical)] for every extended match, earliest first."""
    return [(m["position"], m["name"]) for m in find_all_matches(text)]


def looks_like_medical_text(text: str) -> bool:
    """True when *text* contains strong medicine-context indicators.

    Conservative on purpose: a parrot caption ('a pretty parrot') is not
    medical, while 'Tab 500mg BD for fever' clearly is.  Used only to
    decide between 'Low Confidence Extraction' and a hard rejection.
    """
    if not text or not text.strip():
        return False
    if has_medicine_context(text):
        return True
    return bool(find_dosages(text) or find_quantities(text))


def find_diseases(text: str) -> list[str]:
    if not text:
        return []
    normalized = normalize(text)
    found = []
    for keyword in DISEASE_KEYWORDS:
        pattern = r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])"
        if re.search(pattern, normalized):
            found.append(keyword.title())
    return found


def find_dosages(text: str) -> list[str]:
    if not text:
        return []
    matches = DOSAGE_RE.findall(text)
    return [f"{num} {unit}" for num, unit in matches]


def find_quantities(text: str) -> list[str]:
    if not text:
        return []
    matches = QUANTITY_RE.findall(text)
    return [f"{num} {unit}" for num, unit in matches]


def find_frequencies(text: str) -> list[str]:
    if not text:
        return []
    normalized = normalize(text)
    found = []
    for keyword in FREQUENCY_KEYWORDS:
        pattern = r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])"
        if re.search(pattern, normalized) and keyword not in found:
            found.append(keyword)
    return found


def find_doctors(text: str) -> list[str]:
    if not text:
        return []
    matches = DOCTOR_RE.findall(text)
    return [f"Dr. {m.strip()}" for m in matches]


def find_hospitals(text: str) -> list[str]:
    """Return hospital/clinic names present in *text* (name + keyword)."""
    if not text:
        return []
    found = []
    for m in HOSPITAL_RE.finditer(text):
        name = m.group(1).strip()
        # The keyword text is the match tail after the name group; use a
        # RELATIVE offset because m.end(1) is an absolute index into the
        # original string, not into m.group(0).
        keyword = m.group(0)[m.end(1) - m.start(0):].strip()
        if not name:
            continue
        display = f"{name} {keyword}".strip() if keyword else name
        found.append(display)
    return found


def _valid_calendar(day: int, month: int, year: int) -> bool:
    """True only when (day, month, year) is a real calendar date."""
    try:
        datetime.date(year, month, day)
        return True
    except (ValueError, TypeError):
        return False


def _valid_numeric_date(a: int, b: int, y: int) -> bool:
    """Validate the three numeric parts of a date.

    Understands DD/MM/YYYY, MM/DD/YYYY and YYYY-MM-DD. Ambiguous patterns
    (both leading parts <= 12) follow the Indian DD/MM convention. Junk
    such as '99/99/2026' never validates.
    """
    if y < 100:
        y += 2000
    if not (1900 <= y <= 2100):
        return False
    if a > 31:                      # YYYY-MM-DD (year first)
        return _valid_calendar(y, b, a)
    if a > 12:                      # DD/MM/YYYY
        return _valid_calendar(a, b, y)
    if b > 12:                      # MM/DD/YYYY
        return _valid_calendar(b, a, y)
    return _valid_calendar(a, b, y)  # ambiguous -> DD/MM


def _is_valid_date_string(text: str) -> bool:
    """True when *text* is a real calendar date (numeric or textual)."""
    if not text:
        return False
    # YYYY-MM-DD / YYYY/MM/DD (year first): year is unambiguous, so the
    # month is validated strictly (1-12) instead of the DD/MM heuristic.
    m = re.match(
        r"^\s*(\d{4})\s*[/-]\s*(\d{1,2})\s*[/-]\s*(\d{1,2})\s*$",
        text,
    )
    if m:
        day, month, year = int(m.group(3)), int(m.group(2)), int(m.group(1))
        return (
            1 <= month <= 12
            and 1900 <= year <= 2100
            and _valid_calendar(day, month, year)
        )
    # DD/MM/YYYY, DD-MM-YYYY, MM/DD/YYYY
    m = re.match(
        r"^\s*(\d{1,2})\s*[/-]\s*(\d{1,2})\s*[/-]\s*(\d{2,4})\s*$",
        text,
    )
    if m:
        return _valid_numeric_date(
            int(m.group(1)), int(m.group(2)), int(m.group(3))
        )
    m = re.match(
        r"^\s*(\d{1,2})\s+([a-z]{3,9})\.?\s+(\d{2,4})\s*$",
        text,
        re.IGNORECASE,
    )
    if m:
        month = MONTH_NAMES.get(m.group(2).lower()[:3])
        if month is None:
            return False
        return _valid_numeric_date(int(m.group(1)), month, int(m.group(3)))
    return False


def find_dates(text: str) -> list[str]:
    """Return validated prescription dates found in *text*, in order.

    Supports DD/MM/YYYY, DD-MM-YYYY, MM/DD/YYYY, YYYY-MM-DD and textual
    dates ('31 Jul 2026'). Only REAL calendar dates are returned — junk
    like '99/99/2026' is ignored and the first valid date wins. The
    original text format is preserved (spaces around separators are
    removed for a clean display).
    """
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for m in DATE_RE.finditer(text):
        candidate = re.sub(r"\s*([/-])\s*", r"\1", m.group(0)).strip()
        if candidate in seen:
            continue
        if not _is_valid_date_string(candidate):
            continue
        seen.add(candidate)
        found.append(candidate)
    return found


def _clean_patient_name(raw: str) -> str:
    """Validate and trim a candidate patient name captured by PATIENT_RE.

    - Trailing OCR label words are dropped ('Rahul Sharma Doctor' ->
      'Rahul Sharma') so a neighbouring section heading is never absorbed
      into the patient name.
    - A capture that is (or starts with) an OCR label word is rejected
      entirely ('Date', 'Doctor', 'Hospital', 'Rx', ...), which makes the
      caller fall back to "Not Available" instead of inventing a name.
    """
    tokens = raw.split()
    while tokens and tokens[-1].lower() in PATIENT_LABEL_WORDS:
        tokens.pop()
    if not tokens:
        return ""
    if tokens[0].lower() in PATIENT_LABEL_WORDS:
        return ""
    return " ".join(tokens)


def find_patients(text: str) -> list[str]:
    """Return validated patient names found after a 'Patient' label.

    OCR labels ('Date', 'Doctor', 'Hospital', 'Medicine', 'Prescription',
    'Rx', ...) that happen to follow a 'Patient:' label are NEVER returned
    as patient names — they are filtered out so the caller can show
    "Not Available" instead.
    """
    if not text:
        return []
    results: list[str] = []
    for raw in PATIENT_RE.findall(text):
        name = _clean_patient_name(raw)
        if name and name not in results:
            results.append(name)
    return results


def _pick_nearest(pos: int, candidates: list[tuple[int, str]], radius: int) -> list[str]:
    """Return candidate values near *pos*, preferring those AFTER the token.

    Typical prescription layout is 'Medicine dosage frequency', so for each
    medicine we prefer the closest dosage/quantity/frequency that appears
    AFTER its name.  If nothing appears after it (e.g. '500mg Paracetamol'),
    we fall back to the closest match overall.  This prevents the first
    medicine's values from being attributed to every entry.
    """
    within = [(p, v) for p, v in candidates if abs(p - pos) <= radius]
    if not within:
        return []
    after = [c for c in within if c[0] > pos]
    pool = after if after else within
    pool.sort(key=lambda x: abs(x[0] - pos))
    return [v for _, v in pool]


def _medicine_blocks(text: str) -> dict[str, tuple[int, int]]:
    """Map each canonical medicine to the (start, end) span of its own block.

    A medicine's block runs from its own first token up to the next
    medicine's token in the normalized text. Values (dosage, duration,
    frequency, quantity) are read ONLY from inside the medicine's own
    block, so a value written for one medicine is never reused for another
    (e.g. 'Ibuprofen 20 mg' when the prescription says 'Ibuprofen 400 mg'
    and 'Omeprazole 20 mg').
    """
    normalized = normalize(text)
    positions = sorted(find_medicine_positions_extended(text), key=lambda x: x[0])
    blocks: dict[str, tuple[int, int]] = {}
    for i, (pos, name) in enumerate(positions):
        if name in blocks:
            continue  # keep the earliest occurrence of a repeated name
        end = positions[i + 1][0] if i + 1 < len(positions) else len(normalized)
        blocks[name] = (pos, end)
    return blocks


def _pick_near(
    text: str,
    canonical_name: str,
    candidates: list[tuple[int, str]],
    radius: int,
) -> list[str]:
    """Best candidates for a medicine, STRICTLY scoped to its own block.

    Candidates are read ONLY inside the medicine's own block — from its
    token up to the next medicine's token — so each medicine keeps only
    its own dosage/duration/frequency and NEVER inherits a value written
    for a neighbouring medicine. No global first/nearest/last search is
    performed: a block without its own candidate yields nothing rather
    than borrowing another medicine's value.
    """
    blocks = _medicine_blocks(text)
    block = blocks.get(canonical_name)
    if not block:
        return []
    start, end = block
    in_block = [(p, v) for p, v in candidates if start <= p < end]
    if not in_block:
        return []
    return _pick_nearest(start, in_block, radius)


def _ocr_digit_tolerant(text: str) -> str:
    """1:1 substitution fixing common OCR digit/letter confusions.

    Rules (length-preserving so positions stay aligned):
        - 'o'/'O' -> '0' when adjacent to a digit on either side
          (no dosage unit contains 'o', so this is always safe).
        - 'l'/'L'/'I' -> '1' ONLY when followed by a digit, which
          protects the units 'ml' and 'iu' (e.g. '400IU' stays '400iu',
          '15ml' stays '15ml') while still fixing 'l0' -> '10'.

    Examples: '40Omg' -> '400mg', '10ml' stays '10ml', 'Dolo 650' untouched.
    """
    if not text:
        return text
    chars = list(text)
    n = len(chars)
    for i, ch in enumerate(chars):
        prev_is_digit = i > 0 and chars[i - 1].isdigit()
        next_is_digit = i < n - 1 and chars[i + 1].isdigit()
        if ch in ("o", "O"):
            if prev_is_digit or next_is_digit:
                chars[i] = "0"
        elif ch in ("l", "L", "I"):
            # Only convert when followed by a digit (protects 'ml'/'iu').
            if next_is_digit:
                chars[i] = "1"
    return "".join(chars)


def find_dosages_near(text: str, canonical_name: str, radius: int = 160) -> list[str]:
    """Dosages closest to a medicine's token (misattribution-safe).

    Each medicine receives ONLY the dosage written in its own block — a
    dosage belonging to a neighbouring medicine is never reused.
    OCR-tolerant: '40Omg' (letter O) is read as '400 mg'.
    """
    tolerant = _ocr_digit_tolerant(normalize(text))
    candidates = [
        (m.start(), f"{m.group(1)} {m.group(2)}") for m in DOSAGE_RE.finditer(tolerant)
    ]
    return _pick_near(text, canonical_name, candidates, radius)


def find_quantities_near(text: str, canonical_name: str, radius: int = 160) -> list[str]:
    """Quantities closest to a medicine's token (misattribution-safe)."""
    tolerant = _ocr_digit_tolerant(normalize(text))
    candidates = [
        (m.start(), f"{m.group(1)} {m.group(2)}") for m in QUANTITY_RE.finditer(tolerant)
    ]
    return _pick_near(text, canonical_name, candidates, radius)


def find_frequencies_near(text: str, canonical_name: str, radius: int = 160) -> list[str]:
    """Frequency keywords closest to a medicine's token.

    All occurrences of every keyword are considered (not just the first) so
    that repeated keywords (e.g. 'BD' on two lines) are attributed to the
    medicine they actually follow — scoped to each medicine's own block.
    """
    normalized = normalize(text)
    candidates = []
    for keyword in FREQUENCY_KEYWORDS:
        pattern = r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])"
        for m in re.finditer(pattern, normalized):
            candidates.append((m.start(), keyword))
    return _pick_near(text, canonical_name, candidates, radius)


def find_durations_near(text: str, canonical_name: str, radius: int = 160) -> list[str]:
    """Durations ('5 days', '2 weeks') closest to a medicine's token.

    Each medicine keeps ONLY its own duration ('10 days' stays with
    Omeprazole, never '5 days' inherited from a previous medicine).
    """
    normalized = normalize(text)
    candidates = [
        (m.start(), f"{m.group(1)} {m.group(2).lower()}")
        for m in DURATION_RE.finditer(normalized)
    ]
    return _pick_near(text, canonical_name, candidates, radius)

def has_medicine_context(text: str) -> bool:
    """True if text contains strong medicine-packaging indicators."""
    if not text:
        return False
    normalized = normalize(text)
    strong = re.search(
        r"\b(?:mg|mcg|ml|iu|tablets?|tabs?|capsules?|caps?|strips?|bottles?|"
        r"syrup|suspension|drops|injection|ampoule|ointment|gel|spray)\b",
        normalized,
    )
    return bool(strong)


# ---------------------------------------------------------------------------
# OCR text cleaning (display only — never fed back into extraction)
# ---------------------------------------------------------------------------

# Words that frequently appear MERGED in OCR output (e.g.
# 'Storeprotectedfrommoisture'). clean_ocr_text() re-inserts the missing
# spaces using ONLY this conservative list; tokens that cannot be fully
# resolved are left exactly as OCR produced them, so nothing is ever
# invented or corrupted.
_MERGE_SPLIT_WORDS: set[str] = {
    "a", "an", "and", "are", "as", "at", "away", "before", "bottle",
    "bottles", "by", "children", "composition", "consult", "contains",
    "content", "contents", "date", "days", "day", "do", "doctor",
    "dose", "each", "eat", "exp", "fluid", "fluids", "food", "for",
    "from", "in", "is", "keep", "label", "leaflet", "lic", "mfg",
    "mfd", "meals", "meal", "moisture", "month", "months", "mrp",
    "name", "net", "no", "not", "of", "on", "oral", "pack", "packs",
    "patient", "please", "plenty", "prescription", "price", "protected",
    "regularly", "rest", "salt", "sleep", "store", "strip", "strips",
    "sugar", "symptoms", "tablet", "tablets", "take", "taking", "the",
    "this", "to", "use", "using", "water", "week", "weeks", "weight",
    "with", "you", "your",
}


# Advice-like keywords used to recognise genuine note lines in a
# prescription (e.g. 'Take plenty of fluids', 'Avoid oily food').
NOTES_KEYWORDS: list[str] = [
    "take", "taking", "avoid", "rest", "drink", "fluids", "fluid",
    "plenty", "regularly", "exercise", "diet", "salt", "sugar",
    "water", "food", "eat", "sleep", "consult", "follow up", "review",
    "repeat", "medication", "symptoms", "continue", "stop", "visit",
    "report", "fluid intake", "warm water", "restrict", "stop taking",
]

FREQUENCY_KEYWORD_SET: set[str] = set(FREQUENCY_KEYWORDS)


def _split_merged_token(token: str) -> str | None:
    """Split a merged alpha-only token using the curated word list.

    A split is accepted only when the ENTIRE token is consumed and at
    least two dictionary words are produced; otherwise None is returned
    and the token is left exactly as OCR produced it.
    """
    if len(token) < 6 or not token.isalpha():
        return None
    lower = token.lower()
    if lower in _MERGE_SPLIT_WORDS:
        return None
    words: list[str] = []
    i = 0
    n = len(lower)
    while i < n:
        for j in range(n, i, -1):
            if lower[i:j] in _MERGE_SPLIT_WORDS:
                words.append(lower[i:j])
                i = j
                break
        else:
            return None  # unresolvable remainder -> keep the original token
    if len(words) < 2:
        return None
    if token[0].isupper():
        words[0] = words[0].capitalize()
    return " ".join(words)


def clean_ocr_text(text: str) -> str:
    """Clean raw OCR output for display.

    - Collapses whitespace runs to single spaces.
    - Removes spaces before punctuation ('Composition :' -> 'Composition:').
    - Re-inserts spaces inside merged words ('Storeprotectedfrommoisture').
    - Removes duplicated adjacent words ('the the medicine' -> 'the medicine').

    The original wording is preserved — nothing is invented or removed.
    """
    if not text:
        return ""
    collapsed = re.sub(r"\s+", " ", text)
    collapsed = re.sub(r"\s+([,;.:!?])", r"\1", collapsed)
    collapsed = re.sub(r"\s+", " ", collapsed)

    tokens: list[str] = []
    for token in collapsed.split():
        split = _split_merged_token(token)
        tokens.extend(split.split() if split else [token])

    cleaned: list[str] = []
    prev = ""
    for word in " ".join(tokens).split():
        if word.lower() == prev.lower() and word.lower() not in ("a", "i"):
            continue
        cleaned.append(word)
        prev = word
    return " ".join(cleaned).strip()


# ---------------------------------------------------------------------------
# Structured prescription summary (presentation only)
# ---------------------------------------------------------------------------


def _display_detail(value: str) -> str:
    """Humanise a parsed detail value for the structured summary."""
    v = value.strip()
    if not v:
        return v
    if v.islower() and v in ("od", "bd", "tds", "qid", "hs", "tid"):
        return v.upper()
    return v[:1].upper() + v[1:]


def find_notes(text: str) -> list[str]:
    """Return advice-like note lines actually present in *text*.

    A line is treated as a note only when it contains an advice keyword
    AND does not itself look like a medicine, dosage, date, patient,
    doctor, hospital or frequency line. Nothing is ever invented.
    """
    if not text:
        return []
    notes: list[str] = []
    for raw_line in text.splitlines():
        line = clean_ocr_text(raw_line).strip()
        if len(line) < 4 or len(line) > 140:
            continue
        lowered = normalize(line)
        if not lowered or lowered in FREQUENCY_KEYWORD_SET:
            continue
        if find_medicines(line) or find_dates(line) or DOSAGE_RE.search(line):
            continue
        if DOCTOR_RE.search(line) or PATIENT_RE.search(line) or HOSPITAL_RE.search(line):
            continue
        if not any(kw in lowered for kw in NOTES_KEYWORDS):
            continue
        note = line.strip(" .:,;\t").strip()
        if note and note not in notes:
            notes.append(note)
    return notes


def build_prescription_summary(
    text: str,
    medicine_entries: list[dict],
    doctor: str = "",
    hospital: str = "",
    patient: str = "",
    disease: str = "",
) -> str:
    """Build a structured, human-readable prescription summary.

    Only information actually present in the OCR text is included — never
    invented. Fields with no data are omitted entirely and the raw OCR
    dump is never shown.
    """
    sections: list[str] = []

    meta: list[str] = []
    if doctor:
        meta.append(f"Doctor: {doctor}")
    if hospital:
        meta.append(f"Hospital: {hospital}")
    if patient:
        meta.append(f"Patient: {patient}")
    elif doctor or hospital or disease or medicine_entries:
        # Keep the Patient section visible; an OCR label is never a name,
        # so when no patient is actually found we say so explicitly.
        meta.append("Patient: Not Available")
    if disease:
        meta.append(f"Disease: {disease}")
    if meta:
        sections.append("\n".join(meta))

    if medicine_entries:
        med_lines: list[str] = ["Medicines:"]
        for entry in medicine_entries:
            name = (entry.get("medicine_name") or "").strip()
            dosage = (entry.get("dosage") or "").strip()
            head = f"• {name}" if name else "• —"
            if dosage:
                head += f" {dosage}"
            med_lines.append(head)
            for key in ("frequency", "duration", "quantity"):
                val = (entry.get(key) or "").strip()
                if val:
                    med_lines.append(f"  {_display_detail(val)}")
            med_lines.append("")  # blank line between medicines
        if med_lines and med_lines[-1] == "":
            med_lines.pop()
        sections.append("\n".join(med_lines))

    notes = find_notes(text)
    if notes:
        sections.append("Notes:\n" + "\n".join(f"• {note}" for note in notes))

    return "\n\n".join(sections)
