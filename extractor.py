"""
Text and document extractor module for "Explain This".
Supports PDF, TXT, and Image files.
"""

import io
from typing import Dict, Any, Tuple
import pypdf
from PIL import Image


def extract_content(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Extracts text or prepares file content for explanation.
    
    Returns a dictionary with:
        - "success": bool
        - "file_type": str ('text', 'pdf', 'image', 'unknown')
        - "extracted_text": str (if direct text extraction succeeded)
        - "page_count": int
        - "is_scanned_or_image": bool (True if AI needs to analyze bytes/multimodal)
        - "mime_type": str
        - "summary_info": str
        - "error": str or None
    """
    lower_name = filename.lower()
    
    # 1. Plain Text files
    if lower_name.endswith(".txt"):
        try:
            # Try utf-8 first, fallback to latin-1
            try:
                text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = file_bytes.decode("latin-1", errors="replace")
                
            text = text.strip()
            return {
                "success": True,
                "file_type": "text",
                "extracted_text": text,
                "page_count": 1,
                "is_scanned_or_image": False,
                "mime_type": "text/plain",
                "summary_info": f"Plain text document ({len(text.split())} words)",
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "file_type": "text",
                "extracted_text": "",
                "page_count": 0,
                "is_scanned_or_image": False,
                "mime_type": "text/plain",
                "summary_info": "Failed to decode text file",
                "error": str(e)
            }

    # 2. PDF files
    elif lower_name.endswith(".pdf"):
        try:
            pdf_file = io.BytesIO(file_bytes)
            reader = pypdf.PdfReader(pdf_file)
            total_pages = len(reader.pages)
            
            pages_text = []
            for i, page in enumerate(reader.pages):
                try:
                    p_text = page.extract_text() or ""
                    if p_text.strip():
                        pages_text.append(f"--- Page {i + 1} ---\n{p_text.strip()}")
                except Exception:
                    continue
            
            combined_text = "\n\n".join(pages_text).strip()
            
            # If extracted text has meaningful length, we have extracted text
            if len(combined_text) > 40:
                word_count = len(combined_text.split())
                return {
                    "success": True,
                    "file_type": "pdf",
                    "extracted_text": combined_text,
                    "page_count": total_pages,
                    "is_scanned_or_image": False,
                    "mime_type": "application/pdf",
                    "summary_info": f"Digital PDF ({total_pages} page{'s' if total_pages != 1 else ''}, ~{word_count} words extracted)",
                    "error": None
                }
            else:
                # Scanned or image-based PDF
                return {
                    "success": True,
                    "file_type": "pdf",
                    "extracted_text": combined_text,
                    "page_count": total_pages,
                    "is_scanned_or_image": True,
                    "mime_type": "application/pdf",
                    "summary_info": f"Scanned/Image PDF ({total_pages} page{'s' if total_pages != 1 else ''}, analyzing visually with Gemini)",
                    "error": None
                }
        except Exception as e:
            return {
                "success": False,
                "file_type": "pdf",
                "extracted_text": "",
                "page_count": 0,
                "is_scanned_or_image": True,
                "mime_type": "application/pdf",
                "summary_info": "Failed to parse PDF file structure",
                "error": str(e)
            }

    # 3. Image files
    elif lower_name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        try:
            image = Image.open(io.BytesIO(file_bytes))
            width, height = image.size
            fmt = image.format or "PNG"
            mime = "image/png" if lower_name.endswith(".png") else "image/jpeg"
            if lower_name.endswith(".webp"):
                mime = "image/webp"

            return {
                "success": True,
                "file_type": "image",
                "extracted_text": "",
                "page_count": 1,
                "is_scanned_or_image": True,
                "mime_type": mime,
                "summary_info": f"Document Image ({fmt}, {width}x{height} px)",
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "file_type": "image",
                "extracted_text": "",
                "page_count": 0,
                "is_scanned_or_image": True,
                "mime_type": "image/jpeg",
                "summary_info": "Invalid or corrupt image",
                "error": str(e)
            }

    else:
        return {
            "success": False,
            "file_type": "unknown",
            "extracted_text": "",
            "page_count": 0,
            "is_scanned_or_image": False,
            "mime_type": "application/octet-stream",
            "summary_info": "Unsupported file format",
            "error": "Please upload a PDF (.pdf), image (.png, .jpg, .jpeg), or text (.txt) file."
        }
