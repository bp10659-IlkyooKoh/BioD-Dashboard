"""Conservative label cleanup: bare numbers are part of the identifier."""
import re


_TIME = r"\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|days?|d|weeks?|wks?|w|시간|분|일|주)"
_TIME_SUFFIX = re.compile(
    rf"(?:[\s_/-]+{_TIME}|\s*\(\s*{_TIME}\s*\)|\s*\[\s*{_TIME}\s*\])$",
    re.IGNORECASE,
)


def clean_group_with_tp(row):
    """Remove only an explicitly unit-labelled time suffix, never a numeric code."""
    value = str(row["group_id"]).strip()
    if not value or value.lower() in {"nan", "none", "<na>"}:
        return "Unknown"
    cleaned = _TIME_SUFFIX.sub("", value).strip()
    return cleaned or value
