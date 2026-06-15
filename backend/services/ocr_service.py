import easyocr

# Lazy init – avoids crash/OOM at import time
_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def extract_text_from_image(image_bytes: bytes) -> str:
    """Extract text from image bytes using EasyOCR."""
    try:
        results = _get_reader().readtext(image_bytes)
        return " ".join([text for (_, text, _) in results])
    except Exception as e:
        print(f"[ocr_service] Error: {e}")
        return ""
