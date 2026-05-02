"""
Main FastAPI application for StudySync.
"""

import logging

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.circuit_breaker import (
    call_llm_naive,
    call_llm_with_breaker,
    get_circuit_state,
    llm_circuit_breaker,
)
from app.database import Base, engine, get_db
from app.models import Document, LLMRequestLog
from app.schemas import DocumentCreate, DocumentResponse, DocumentUpdate, LLMRequest, LLMResponse


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("studysync")

Base.metadata.create_all(bind=engine)

STUDENT_ID = "BSAI23005"

app = FastAPI(
    title="StudySync API",
    description="Resilient backend for the StudySync ed-tech platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_student_id_header(request: Request, call_next):
    """Add the required assignment header to every API response."""
    response = await call_next(request)
    response.headers["X-Student-ID"] = STUDENT_ID
    return response


@app.get("/")
async def root():
    return {
        "app": "StudySync API",
        "status": "running",
        "student_id": STUDENT_ID,
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "circuit_breaker_state": get_circuit_state(),
    }


@app.get("/circuit-status")
async def circuit_status():
    return {
        "state": get_circuit_state(),
        "fail_counter": llm_circuit_breaker.fail_counter,
        "fail_max": llm_circuit_breaker.fail_max,
        "timeout_duration": str(llm_circuit_breaker.timeout_duration),
    }


@app.post("/documents", response_model=DocumentResponse)
async def create_document(doc: DocumentCreate, db: Session = Depends(get_db)):
    new_doc = Document(
        title=doc.title,
        content=doc.content,
        owner_id=doc.owner_id,
        version=1,
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    return new_doc


@app.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@app.put("/documents/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: int,
    update: DocumentUpdate,
    db: Session = Depends(get_db),
):
    """
    Update a document with optimistic locking.

    The client sends the version it last read. If the database version has
    moved ahead, the API rejects the stale write with 409 Conflict.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.version != update.version:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Conflict: you have version {update.version}, "
                f"but the document is now at version {doc.version}. "
                "Please refresh and retry."
            ),
        )

    if update.title is not None:
        doc.title = update.title
    if update.content is not None:
        doc.content = update.content
    doc.version += 1

    db.commit()
    db.refresh(doc)
    return doc


@app.post("/llm/ask", response_model=LLMResponse)
async def ask_llm_protected(req: LLMRequest, db: Session = Depends(get_db)):
    result = await call_llm_with_breaker(req.prompt)

    log_entry = LLMRequestLog(
        prompt=req.prompt,
        response=result["answer"][:500],
        status=result["status"],
        duration_ms=result["duration_ms"],
    )
    db.add(log_entry)
    db.commit()

    return LLMResponse(
        answer=result["answer"],
        source=result["source"],
        circuit_state=result["circuit_state"],
    )


@app.post("/llm/ask-naive")
async def ask_llm_naive(req: LLMRequest, db: Session = Depends(get_db)):
    result = await call_llm_naive(req.prompt)

    log_entry = LLMRequestLog(
        prompt=req.prompt,
        response=str(result.get("answer", ""))[:500],
        status=result["status"],
        duration_ms=result["duration_ms"],
    )
    db.add(log_entry)
    db.commit()

    return result
