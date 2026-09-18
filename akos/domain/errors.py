class DomainError(Exception):
    """Base domain error."""


class QuarantineError(DomainError):
    def __init__(self, reason: str, raw: dict):
        super().__init__(reason)
        self.reason = reason
        self.raw = raw
