import io
import easyocr
import fitz  # PyMuPDF
import docx
import pandas as pd
from PIL import Image

# Lazy-init EasyOCR to avoid OOM on startup
_reader = None


def get_ocr_reader():
    global _reader
    if _reader is None:
        print("Initializing EasyOCR Model (first run may take a moment)...")
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def extract_text_from_image_bytes(image_bytes: bytes) -> str:
    """Extract text from image bytes using EasyOCR."""
    try:
        reader = get_ocr_reader()
        results = reader.readtext(image_bytes)
        return " ".join([text for (_, text, _) in results])
    except Exception as e:
        print(f"[extraction_service] Image OCR error: {e}")
        return ""


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF. Falls back to OCR for scanned/image pages."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text_content = []

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text()

            if text.strip():
                text_content.append(text)
            else:
                # Scanned page – run OCR
                pix = page.get_pixmap()
                img_bytes = pix.tobytes("png")
                ocr_text = extract_text_from_image_bytes(img_bytes)
                if ocr_text:
                    text_content.append(ocr_text)

        return "\n".join(text_content)
    except Exception as e:
        print(f"[extraction_service] PDF extraction error: {e}")
        return ""


def extract_text_from_docx_bytes(docx_bytes: bytes) -> str:
    """Extract text from a Word (.docx) document."""
    try:
        document = docx.Document(io.BytesIO(docx_bytes))
        return "\n".join([para.text for para in document.paragraphs])
    except Exception as e:
        print(f"[extraction_service] DOCX extraction error: {e}")
        return ""


def extract_text_from_excel_bytes(excel_bytes: bytes) -> str:
    """Extract text from an Excel (.xlsx/.xls) spreadsheet."""
    try:
        df_dict = pd.read_excel(io.BytesIO(excel_bytes), sheet_name=None)
        text_content = []
        for sheet_name, df in df_dict.items():
            text_content.append(f"--- Sheet: {sheet_name} ---")
            text_content.append(df.to_string(index=False))
        return "\n".join(text_content)
    except Exception as e:
        print(f"[extraction_service] Excel extraction error: {e}")
        return ""


def extract_text_from_file(file_bytes: bytes, filename: str, content_type: str) -> str:
    """Route extraction to the correct handler based on file type."""
    ext = (filename or "").lower().rsplit(".", 1)[-1]
    ct = (content_type or "").lower()

    if ext == "pdf" or "pdf" in ct:
        return extract_text_from_pdf_bytes(file_bytes)
    elif ext in ("doc", "docx") or "wordprocessingml" in ct:
        return extract_text_from_docx_bytes(file_bytes)
    elif ext in ("xls", "xlsx") or "spreadsheetml" in ct or "ms-excel" in ct:
        return extract_text_from_excel_bytes(file_bytes)
    elif ext in ("png", "jpg", "jpeg", "bmp", "tiff", "webp") or ct.startswith(
        "image/"
    ):
        return extract_text_from_image_bytes(file_bytes)
    else:
        # Best-effort fallback: try OCR
        return extract_text_from_image_bytes(file_bytes)
