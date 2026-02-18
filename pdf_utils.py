"""PDF to image conversion and rotation detection utilities."""

import base64
import io
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


def is_tesseract_installed() -> bool:
    """Check if Tesseract OCR is installed."""
    return shutil.which("tesseract") is not None


def detect_rotation(image: Image.Image) -> Dict:
    """
    Use Tesseract OSD to detect page rotation.

    Args:
        image: PIL Image object

    Returns:
        Dict with "angle" (0, 90, 180, 270) and "confidence" (float)
    """
    if not is_tesseract_installed():
        return {"angle": 0, "confidence": 0.0}

    import pytesseract

    try:
        osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
        return {
            "angle": osd.get("rotate", 0),
            "confidence": osd.get("orientation_conf", 0.0),
        }
    except Exception:
        return {"angle": 0, "confidence": 0.0}


def fix_rotation(
    image: Image.Image, confidence_threshold: float = 2.0
) -> Tuple[Image.Image, bool]:
    """
    Auto-rotate if confidence is above threshold.

    Args:
        image: PIL Image object
        confidence_threshold: Minimum confidence to auto-rotate

    Returns:
        Tuple of (corrected_image, was_low_confidence).
        was_low_confidence=True means the page should be flagged for user review.
    """
    result = detect_rotation(image)
    angle = result["angle"]
    confidence = result["confidence"]

    if angle == 0:
        return image, False

    if confidence >= confidence_threshold:
        return image.rotate(-angle, expand=True), False
    else:
        # Low confidence - flag for user review
        return image, True


def fix_rotation_batch(
    images: List[Image.Image], confidence_threshold: float = 2.0
) -> Tuple[List[Image.Image], List[int]]:
    """
    Auto-rotate a batch of images, returning flagged page indices.

    Args:
        images: List of PIL Image objects
        confidence_threshold: Minimum confidence to auto-rotate

    Returns:
        Tuple of (corrected_images, flagged_page_indices).
        flagged_page_indices contains 0-based indices of pages needing user review.
    """
    corrected = []
    flagged = []

    for i, image in enumerate(images):
        fixed, low_confidence = fix_rotation(image, confidence_threshold)
        corrected.append(fixed)
        if low_confidence:
            flagged.append(i)

    return corrected, flagged


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
