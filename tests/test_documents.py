import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.api.main import app
from backend.api.v1 import documents


DOCX_BYTES_INITIAL = b"PK\x03\x04initial-docx"
DOCX_BYTES_UPDATED = b"PK\x03\x04updated-docx"


@pytest.fixture(autouse=True)
def temp_doc_paths(tmp_path, monkeypatch):
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"
    sessions_path = tmp_path / "sessions"

    input_path.mkdir(parents=True, exist_ok=True)
    output_path.mkdir(parents=True, exist_ok=True)
    sessions_path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(documents, "INPUT_DOCS_PATH", input_path)
    monkeypatch.setattr(documents, "OUTPUT_DOCS_PATH", output_path)
    monkeypatch.setattr(documents, "SESSIONS_PATH", sessions_path)

    return sessions_path


def test_session_upload_apply_history_export_delete(temp_doc_paths):
    client = TestClient(app)

    # Upload initial DOCX to create session
    upload_resp = client.post(
        "/api/v1/documents/session",
        files={"file": ("sample.docx", io.BytesIO(DOCX_BYTES_INITIAL), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert upload_resp.status_code == 200
    data = upload_resp.json()
    session_id = data["session_id"]

    state_path = documents.SESSIONS_PATH / session_id / "state.docx"
    assert state_path.exists()
    assert state_path.read_bytes() == DOCX_BYTES_INITIAL

    # Apply update, expect history backup
    apply_resp = client.post(
        f"/api/v1/documents/session/{session_id}/apply",
        files={"file": ("sample-updated.docx", io.BytesIO(DOCX_BYTES_UPDATED), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert apply_resp.status_code == 200
    assert "Session updated" in apply_resp.json()["message"]

    history_dir = documents.SESSIONS_PATH / session_id / "history"
    backups = list(history_dir.glob("state-*.docx"))
    assert len(backups) == 1
    assert state_path.read_bytes() == DOCX_BYTES_UPDATED

    # History listing shows one version
    history_resp = client.get(f"/api/v1/documents/session/{session_id}/history")
    assert history_resp.status_code == 200
    versions = history_resp.json().get("versions", [])
    assert len(versions) == 1

    # Export returns updated bytes
    export_resp = client.get(f"/api/v1/documents/session/{session_id}/export")
    assert export_resp.status_code == 200
    assert export_resp.content == DOCX_BYTES_UPDATED

    # Delete session removes directory
    delete_resp = client.delete(f"/api/v1/documents/session/{session_id}")
    assert delete_resp.status_code == 200
    assert not (documents.SESSIONS_PATH / session_id).exists()
