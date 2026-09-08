from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from knowledge.errors import DomainError
from knowledge.models import Source


@dataclass
class StoredFile:
    source: Source
    text: str


class LocalFileStore:
    def store(self, path: str, source_type: str) -> StoredFile:
        file_path = Path(path)
        if not file_path.exists():
            raise DomainError(f"file not found: {path}")

        suffix = file_path.suffix.lower()
        if suffix not in {".md", ".txt"}:
            raise DomainError(f"unsupported file type: {suffix}")

        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise DomainError(f"failed to decode file as utf-8: {path}") from exc

        source_id = file_path.stem
        source = Source(
            id=source_id,
            title=file_path.name,
            type=source_type,
            uri=f"file://{file_path.resolve()}",
            version="1",
            created_at=datetime.now(timezone.utc),
            status="ready",
        )
        return StoredFile(source=source, text=text)
