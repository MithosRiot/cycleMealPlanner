import re


def normalize_name(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip().casefold())
    return normalized
