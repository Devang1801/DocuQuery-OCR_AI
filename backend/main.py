import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="OCR Graph Application API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Welcome to the OCR Graph Application API"}


from services.extraction_service import extract_text_from_file
from services.document_service import process_text, chat_with_document, compare_document
from pydantic import BaseModel


class ChatRequest(BaseModel):
    query: str


class CompareRequest(BaseModel):
    target_text: str
    strategy: str = "word"


@app.post("/api/process")
async def process_file(file: UploadFile = File(...)):
    allowed_types = [
        "image/",
        "application/pdf",
        "wordprocessingml",
        "spreadsheetml",
        "application/vnd.ms-excel",
    ]
    is_allowed = any(t in (file.content_type or "") for t in allowed_types) or (
        file.filename or ""
    ).endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx"))

    if not is_allowed:
        raise HTTPException(
            status_code=400,
            detail="File type not supported. Please upload an Image, PDF, Word, or Excel document.",
        )

    file_bytes = await file.read()

    extracted_text = extract_text_from_file(
        file_bytes, file.filename, file.content_type or ""
    )

    if not extracted_text or not extracted_text.strip():
        return {
            "status": "error",
            "message": "Failed to extract text from the uploaded file.",
        }

    result = process_text(extracted_text)
    return result

@app.post("/api/update_text")
async def update_text(request: CompareRequest):
    # Quick endpoint to let the frontend update the global text if the user edits OCR text
    # We repurpose CompareRequest since it has a string field
    result = process_text(request.target_text)
    return result

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    result = chat_with_document(request.query)
    return result


@app.post("/api/compare")
async def compare_text_endpoint(request: CompareRequest):
    result = compare_document(request.target_text, request.strategy)
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
