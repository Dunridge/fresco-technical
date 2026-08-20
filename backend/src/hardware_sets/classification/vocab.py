"""Domain vocabulary for door-hardware schedules.

These lists are *evidence*, never verdicts. A value is never classified on its
own: the column it belongs to is classified from the aggregate of its members,
and values that live in both vocabularies contribute nothing either way.
"""

from __future__ import annotations

import re

# Short codes that specbooks use for hardware manufacturers.
MANUFACTURER_CODES = {
    "ABH", "ACC", "ADA", "AD", "AIR", "ARR", "ASA", "BES", "BST", "BUR", "COR",
    "CRL", "CRR", "DCI", "DET", "DOR", "DON", "FAL", "GJ", "GLY", "HAG", "HES",
    "IVE", "IVES", "KAB", "KEE", "LAW", "LCN", "MAR", "MCK", "MK", "NGP", "NOR",
    "OTH", "PEM", "PRE", "REE", "RIX", "ROC", "RUS", "SAR", "SCE", "SCH", "SDC",
    "SEC", "SEL", "STA", "TRI", "VD", "VON", "YAL", "ZE", "ZER", "ZRO",
}

MANUFACTURER_NAMES = {
    "ADAMS RITE", "ARROW", "BEST", "BURNS", "CORBIN", "CORBIN RUSSWIN", "DETEX",
    "DORMA", "FALCON", "GLYNN-JOHNSON", "GLYNN JOHNSON", "HAGER", "HES", "IVES",
    "KABA", "LCN", "LCN CLOSERS", "MARKAR", "MCKINNEY", "NATIONAL GUARD",
    "NORTON", "PEMKO", "REESE", "RIXSON", "ROCKWOOD", "RUSSWIN", "SARGENT",
    "SCHLAGE", "SECURITRON", "STANLEY", "TRIMCO", "VON DUPRIN", "YALE", "ZERO",
    "ZERO INTERNATIONAL",
}

# Named finishes that are not covered by the numeric/US patterns below.
FINISH_WORDS = {
    "ALUM", "ALUMINUM", "ANOD", "BK", "BLACK", "BLK", "BRASS", "BRONZE", "BRZ",
    "BSP", "CHROME", "CL", "CLEAR", "DBRZ", "DKB", "DURO", "GALV", "GREY",
    "GRY", "IVORY", "MILL", "ORB", "PAINTED", "PRIME", "PRIMED", "PTD",
    "SATIN", "SS", "STAINLESS", "WHITE", "WHT",
}

# Codes that specbooks genuinely use for both a manufacturer and a finish.
# They are excluded from column scoring entirely so the column's unambiguous
# members decide, exactly as the challenge requires.
AMBIGUOUS_CODES = {
    "PE",   # Pemko            | Painted Enamel
    "NO",   # Norton           | "No."
    "AL",   # Alarm Lock       | Aluminum
    "PC",   # (mfr shorthand)  | Prime Coat / Powder Coat
    "BR",   # (mfr shorthand)  | Bronze
    "SP",   # (mfr shorthand)  | Special / Sprayed
}

UNIT_CODES = {
    "EA", "EACH", "PR", "PRS", "PAIR", "PAIRS", "SET", "SETS", "DZ", "DOZ",
    "LF", "FT", "LS", "OPG", "OPENING",
}

NOT_USED_MARKERS = (
    "NOT USED", "NOT-USED", "NOTUSED", "N/A", "NA", "NOT APPLICABLE",
    "NOT REQUIRED", "NONE", "OMITTED", "RESERVED", "DELETED", "VOID",
)

# Nouns that identify a hardware component description.
HARDWARE_NOUNS = {
    "ARMOR", "ASTRAGAL", "AUTOMATIC", "BOLT", "BUMPER", "CLOSER", "COORDINATOR",
    "CYLINDER", "DEADBOLT", "DEADLOCK", "DEVICE", "DOOR", "DRIP", "ELECTRIC",
    "EXIT", "FLUSH", "GASKET", "GASKETING", "GUARD", "HINGE", "HINGES",
    "HOLDER", "KICK", "LATCH", "LOCK", "LOCKSET", "MAGNETIC", "MOP", "MULLION",
    "OPERATOR", "OVERHEAD", "PANIC", "PIVOT", "PLATE", "POWER", "PROTECTION",
    "PULL", "PUSH", "RAIN", "SEAL", "SET", "SILENCER", "SPRING", "STOP",
    "STRIKE", "SWEEP", "THRESHOLD", "TRACK", "TRIM", "TURN", "VIEWER",
    "WEATHERSTRIP", "WEATHERSTRIPPING",
}

NOTE_WORDS = {
    "SEE", "NOTE", "NOTES", "OMIT", "PROVIDE", "FIELD", "VERIFY", "COORDINATE",
    "TYP", "TYPICAL", "WITH", "AT", "ALTERNATE", "EXISTING", "REUSE", "BY",
    "REQUIRED", "SPECIFIED", "SIMILAR", "ONLY", "WHERE",
}

US_FINISH_RE = re.compile(r"^US\d{1,2}[A-Z]{0,2}$")
BHMA_FINISH_RE = re.compile(r"^[6-7]\d{2}[A-Z]{0,2}$")
SHORT_FINISH_RE = re.compile(r"^(?:SP|SPR)\d{1,3}[A-Z]?$")
PLAIN_INT_RE = re.compile(r"^\d{1,4}$")
CATALOG_RE = re.compile(r"^(?=.*\d)[A-Z0-9][A-Z0-9\-/.#*]*$")
MIN_NUMERIC_CATALOG_DIGITS = 4


def normalize_code(value: str) -> str:
    return value.strip().upper().rstrip(".,;:")


def is_ambiguous_code(value: str) -> bool:
    return normalize_code(value) in AMBIGUOUS_CODES


def looks_like_manufacturer(value: str) -> bool:
    code = normalize_code(value)
    if not code or code in AMBIGUOUS_CODES:
        return False
    if code in MANUFACTURER_CODES or code in MANUFACTURER_NAMES:
        return True
    # Unknown short all-alpha codes are weak manufacturer evidence, but only
    # when they cannot be read as a finish.
    return bool(re.fullmatch(r"[A-Z]{2,4}", code)) and not looks_like_finish(code)


def looks_like_finish(value: str) -> bool:
    code = normalize_code(value)
    if not code or code in AMBIGUOUS_CODES:
        return False
    if code in FINISH_WORDS:
        return True
    if US_FINISH_RE.match(code) or BHMA_FINISH_RE.match(code) or SHORT_FINISH_RE.match(code):
        return True
    # Composite finishes such as "US26D/US32D" or "630/626".
    parts = [p for p in re.split(r"[/&+-]", code) if p]
    return len(parts) > 1 and all(
        US_FINISH_RE.match(p) or BHMA_FINISH_RE.match(p) or p in FINISH_WORDS for p in parts
    )


def _token_is_catalog_number(token: str) -> bool:
    if not token or looks_like_finish(token):
        return False
    if PLAIN_INT_RE.fullmatch(token):
        # Bare numbers are only model-like when they are too long to be a BHMA
        # finish code or a stray quantity.
        return len(token) >= MIN_NUMERIC_CATALOG_DIGITS
    return bool(CATALOG_RE.fullmatch(token))


def looks_like_catalog_number(value: str) -> bool:
    """A catalog cell is usually a model number plus options: `L9080P 06A`."""
    code = normalize_code(value)
    if not code:
        return False
    return any(_token_is_catalog_number(token) for token in code.split())


def looks_like_unit(value: str) -> bool:
    return normalize_code(value) in UNIT_CODES


def is_not_used_marker(text: str) -> bool:
    cleaned = re.sub(r"[^A-Z0-9/ ]", " ", text.upper())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned in {m.replace("-", " ").replace("_", " ") for m in NOT_USED_MARKERS}


def contains_not_used_marker(text: str) -> bool:
    upper = re.sub(r"\s+", " ", text.upper())
    return any(marker in upper for marker in ("NOT USED", "NOT APPLICABLE", "NOT REQUIRED"))
