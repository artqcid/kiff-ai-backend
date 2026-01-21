"""
documents.py

Document management endpoints
"""

import json
import sys
import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
import httpx
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.api.v1.models import (
    DocumentInfo,
    DocumentList,
    DocumentSessionMessage,
    DocumentSessionResponse,
    DocumentSessionHistoryResponse,
    DocumentUploadResponse,
    DocumentVersionInfo,
    GoogleImportRequest,
    GoogleExportRequest,
    GoogleExportResponse,
)

router = APIRouter()

# Document storage paths
INPUT_DOCS_PATH = Path("./documents/input")
OUTPUT_DOCS_PATH = Path("./documents/output")
SESSIONS_PATH = Path("./documents/sessions")


def _ensure_session(session_id: str) -> Path:
    session_dir = SESSIONS_PATH / session_id
    if not session_dir.exists() or not session_dir.is_dir():
        raise HTTPException(status_code=404, detail="Session not found")
    return session_dir


@router.get("/documents", response_model=DocumentList)
async def list_documents():
    """
    Get list of uploaded documents
    """
    INPUT_DOCS_PATH.mkdir(parents=True, exist_ok=True)
    
    documents = []
    
    for file_path in INPUT_DOCS_PATH.iterdir():
        if file_path.is_file():
            stat = file_path.stat()
            documents.append(DocumentInfo(
                id=file_path.stem,
                filename=file_path.name,
                path=str(file_path),
                size=stat.st_size,
                mime_type=None,  # TODO: detect mime type
                uploaded_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
                metadata={}
            ))
    
    return DocumentList(documents=documents, total=len(documents))


@router.post("/documents", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a document
    """
    try:
        INPUT_DOCS_PATH.mkdir(parents=True, exist_ok=True)
        
        # Generate unique ID
        doc_id = str(uuid.uuid4())[:8]
        
        # Save file
        file_path = INPUT_DOCS_PATH / file.filename
        with open(file_path, 'wb') as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return DocumentUploadResponse(
            id=doc_id,
            filename=file.filename,
            message=f"Document '{file.filename}' uploaded successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/documents/session", response_model=DocumentSessionResponse)
async def upload_document_session(file: UploadFile = File(...)):
    """Upload a DOCX into a new session for iterative editing"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    session_id = str(uuid.uuid4())
    session_dir = SESSIONS_PATH / session_id

    try:
        session_dir.mkdir(parents=True, exist_ok=True)

        original_filename = Path(file.filename).name
        state_path = session_dir / "state.docx"
        meta_path = session_dir / "meta.json"

        with open(state_path, "wb") as destination:
            shutil.copyfileobj(file.file, destination)

        meta = {"original_filename": original_filename}
        meta_path.write_text(json.dumps(meta))

        return DocumentSessionResponse(
            session_id=session_id,
            filename=original_filename,
            message="Session created and document stored",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session upload failed: {str(e)}")


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """
    Delete a document by ID
    """
    try:
        # Find and delete file
        for file_path in INPUT_DOCS_PATH.iterdir():
            if file_path.stem == document_id or file_path.name.startswith(document_id):
                file_path.unlink()
                return {"message": f"Document deleted", "id": document_id}
        
        raise HTTPException(status_code=404, detail="Document not found")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@router.get("/documents/{document_id}")
async def get_document(document_id: str):
    """
    Get document information by ID
    """
    for file_path in INPUT_DOCS_PATH.iterdir():
        if file_path.stem == document_id or file_path.name.startswith(document_id):
            stat = file_path.stat()
            return DocumentInfo(
                id=document_id,
                filename=file_path.name,
                path=str(file_path),
                size=stat.st_size,
                mime_type=None,
                uploaded_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
                metadata={}
            )
    
    raise HTTPException(status_code=404, detail="Document not found")


@router.get("/documents/session/{session_id}/export")
async def export_document_session(session_id: str):
    """Export the current DOCX state for a session"""
    session_dir = SESSIONS_PATH / session_id
    state_path = session_dir / "state.docx"
    meta_path = session_dir / "meta.json"

    if not state_path.exists():
        raise HTTPException(status_code=404, detail="Session or document not found")

    filename = "export.docx"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
            original = meta.get("original_filename")
            if original:
                filename = f"edited-{original}"
        except Exception:
            # If metadata is unreadable, fall back to default filename
            pass

    return FileResponse(path=state_path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=filename)


@router.post("/documents/session/{session_id}/apply", response_model=DocumentSessionMessage)
async def apply_document_session(session_id: str, file: UploadFile = File(...)):
    """Replace current session state with a new DOCX, keeping a history backup"""
    session_dir = _ensure_session(session_id)
    state_path = session_dir / "state.docx"
    history_dir = session_dir / "history"

    if not state_path.exists():
        raise HTTPException(status_code=404, detail="Session document not found")

    try:
        history_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = history_dir / f"state-{timestamp}.docx"
        shutil.copy2(state_path, backup_path)

        with open(state_path, "wb") as destination:
            shutil.copyfileobj(file.file, destination)

        return DocumentSessionMessage(session_id=session_id, message="Session updated; previous version archived")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Apply failed: {str(e)}")


@router.get("/documents/session/{session_id}/history", response_model=DocumentSessionHistoryResponse)
async def history_document_session(session_id: str):
    """List saved history versions for a session"""
    session_dir = _ensure_session(session_id)
    history_dir = session_dir / "history"

    versions: list[DocumentVersionInfo] = []
    if history_dir.exists():
        for file_path in sorted(history_dir.iterdir(), reverse=True):
            if file_path.is_file():
                stat = file_path.stat()
                versions.append(
                    DocumentVersionInfo(
                        version_id=file_path.stem,
                        filename=file_path.name,
                        size=stat.st_size,
                        created_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    )
                )

    return DocumentSessionHistoryResponse(session_id=session_id, versions=versions)


@router.delete("/documents/session/{session_id}", response_model=DocumentSessionMessage)
async def delete_document_session(session_id: str):
    """Delete a session and all stored files"""
    session_dir = _ensure_session(session_id)

    try:
        shutil.rmtree(session_dir)
        return DocumentSessionMessage(session_id=session_id, message="Session removed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@router.post("/documents/google/import", response_model=DocumentSessionResponse)
async def import_google_doc(payload: GoogleImportRequest):
    """Import a Google Doc (public or authorized) as DOCX and start a session"""
    doc_id = payload.doc_id.strip()
    if not doc_id:
        raise HTTPException(status_code=400, detail="doc_id is required")

    url = f"https://docs.google.com/document/d/{doc_id}/export?format=docx"
    session_id = str(uuid.uuid4())
    session_dir = SESSIONS_PATH / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    state_path = session_dir / "state.docx"
    meta_path = session_dir / "meta.json"

    try:
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            response = client.get(url)
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Google Docs download failed (status {response.status_code})")
            state_path.write_bytes(response.content)

        meta = {"original_filename": f"gdoc-{doc_id}.docx", "source": "google_doc", "doc_id": doc_id}
        meta_path.write_text(json.dumps(meta))

        return DocumentSessionResponse(
            session_id=session_id,
            filename=f"gdoc-{doc_id}.docx",
            message="Google Doc import successful; session created",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google import failed: {str(e)}")


@router.post("/documents/google/export/{session_id}", response_model=GoogleExportResponse)
async def export_google_doc(session_id: str, payload: GoogleExportRequest):
    """Export a session DOCX to Google Drive via simple upload (requires access_token)"""
    session_dir = _ensure_session(session_id)
    state_path = session_dir / "state.docx"
    meta_path = session_dir / "meta.json"

    if not state_path.exists():
        raise HTTPException(status_code=404, detail="Session document not found")

    access_token = payload.access_token.strip()
    if not access_token:
        raise HTTPException(status_code=400, detail="access_token is required for Google Drive upload")

    filename = payload.name or "edited-document.docx"
    if meta_path.exists() and not payload.name:
        try:
            meta = json.loads(meta_path.read_text())
            original = meta.get("original_filename")
            if original:
                filename = f"edited-{original}"
        except Exception:
            pass

    files = {
        "metadata": (
            None,
            json.dumps({"name": filename, **({"parents": [payload.folder_id]} if payload.folder_id else {})}),
            "application/json",
        ),
        "file": (filename, state_path.read_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    }

    headers = {"Authorization": f"Bearer {access_token}"}

    upload_url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"

    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(upload_url, headers=headers, files=files)
            if response.status_code not in (200, 201):
                detail = response.text[:500]
                raise HTTPException(status_code=400, detail=f"Google Drive upload failed: {detail}")

            data = response.json()
            file_id = data.get("id")
            if not file_id:
                raise HTTPException(status_code=500, detail="Google Drive response missing file id")

            return GoogleExportResponse(
                session_id=session_id,
                file_id=file_id,
                name=filename,
                message="Uploaded to Google Drive",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google export failed: {str(e)}")
