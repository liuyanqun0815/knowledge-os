from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from infra.upload_utils import relative_path_from_kb_root, source_id_from_relative_path
from akos.domain.errors import DomainError
from akos.domain.models.knowledge import Source


@dataclass
class StoredFile:
    source: Source
    text: str


class LocalFileStore:
    def __init__(self, data_root: str = "./data") -> None:
        self._data_root = Path(data_root)

    def store(self, path: str, source_type: str, knowledge_base_id: str | None = None) -> StoredFile:
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
        if knowledge_base_id:
            kb_root = self._data_root / knowledge_base_id
            try:
                relative = relative_path_from_kb_root(file_path, kb_root)
                source_id = source_id_from_relative_path(relative)
            except ValueError:
                pass

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
