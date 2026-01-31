"""PDF to image conversion utilities."""

import base64
import io
import sys
from pathlib import Path
from typing import List, Optional

from pdf2image import convert_from_path
from PIL import Image


def _get_poppler_path() -> Optional[str]:
    """Get path to bundled poppler binaries if running as packaged app."""
    if getattr(sys, "frozen", False):
        # Running as PyInstaller bundle
        bundle_dir = Path(sys._MEIPASS)
        poppler_dir = bundle_dir / "poppler" / "bin"
        if poppler_dir.exists():
            return str(poppler_dir)
    return None


def pdf_to_images(pdf_path: Path, dpi: int = 300) -> List[Image.Image]:
    """
    Convert PDF pages to PIL Images at specified DPI.

    Args:
        pdf_path: Path to the PDF file
        dpi: Resolution for conversion (default 300 for good OCR quality)

    Returns:
        List of PIL Image objects, one per page
    """
    poppler_path = _get_poppler_path()
    images = convert_from_path(str(pdf_path), dpi=dpi, poppler_path=poppler_path)
    return images


def image_to_base64(image: Image.Image, format: str = "PNG") -> str:
    """
    Convert PIL Image to base64 string for API transmission.

    Args:
        image: PIL Image object
        format: Image format (PNG or JPEG)

    Returns:
        Base64 encoded string of the image
    """
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def get_pdf_page_count(pdf_path: Path) -> int:
    """
    Get the number of pages in a PDF without fully converting it.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Number of pages in the PDF
    """
    from pdf2image.pdf2image import pdfinfo_from_path

    info = pdfinfo_from_path(str(pdf_path))
    return info.get("Pages", 0)
