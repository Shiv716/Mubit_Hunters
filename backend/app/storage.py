"""Small evidence attachments: local disk offline, shared database on Neon."""
from hashlib import sha256
from pathlib import Path

from .config import get_settings


def put_evidence(conn, case_id: int, content: bytes, filename: str) -> str:
    digest = sha256(content).hexdigest()
    settings = get_settings()
    if settings.evidence_storage == "database":
        key = f"db:{case_id}/{digest}"
        conn.execute("INSERT INTO evidence_blobs (storage_key, content) VALUES (?,?) ON CONFLICT(storage_key) DO NOTHING",
                     (key, content))
        return key
    folder = settings.evidence_dir / str(case_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{digest}{Path(filename).suffix.lower()[:8]}"
    path.write_bytes(content)
    return str(path)


def read_evidence(conn, stored_path: str) -> bytes:
    if stored_path.startswith("db:"):
        row = conn.execute("SELECT content FROM evidence_blobs WHERE storage_key=?", (stored_path,)).fetchone()
        if row is None:
            raise FileNotFoundError("Evidence attachment is unavailable.")
        return bytes(row[0])
    path = Path(stored_path).resolve()
    if not path.is_relative_to(get_settings().evidence_dir.resolve()) or not path.is_file():
        raise FileNotFoundError("Evidence attachment is unavailable.")
    return path.read_bytes()
