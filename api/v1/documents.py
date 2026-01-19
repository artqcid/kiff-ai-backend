"""
documents.py

Document management endpoints
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import List
import sys
import uuid
import shutil
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.api.v1.models import DocumentInfo, DocumentList, DocumentUploadResponse

router = APIRouter()

# Document storage paths
INPUT_DOCS_PATH = Path("./documents/input")
OUTPUT_DOCS_PATH = Path("./documents/output")


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
