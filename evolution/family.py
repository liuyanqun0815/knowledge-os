import hashlib


def family_key(subject: str, predicate: str, object_type: str) -> str:
    """Family id aligned with compiler ``_family_id``."""
    raw = f"{subject}|{predicate}|{object_type}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
