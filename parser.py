"""Core PDF parsing logic."""

import re
from pathlib import Path
from typing import Callable, List, Optional

from PIL import Image

from api_client import VisionLLMClient
from config import TRANSCRIPTION_PROMPT
from pdf_utils import image_to_base64, pdf_to_images

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}


class PDFParser:
    """Orchestrates PDF/image parsing using vision LLM."""

    def __init__(self, client: VisionLLMClient, batch_size: int = 20):
        """
        Initialize the parser.

        Args:
            client: Vision LLM client for API calls
            batch_size: Number of pages per API call
        """
        self.client = client
        self.batch_size = batch_size

    async def parse_pdf(
        self,
        pdf_path: Path,
        on_progress: Optional[Callable[[str, int, int], None]] = None,
    ) -> str:
        """Parse a PDF document into clean text."""
        if on_progress:
            on_progress("Converting PDF to images...", 0, 0)

        images = pdf_to_images(pdf_path)
        return await self._parse_images(images, on_progress)

    async def parse_image_files(
        self,
        image_paths: List[Path],
        on_progress: Optional[Callable[[str, int, int], None]] = None,
    ) -> str:
        """Parse a list of image files into clean text, in order."""
        if on_progress:
            on_progress("Loading images...", 0, 0)

        images = [Image.open(p) for p in image_paths]
        return await self._parse_images(images, on_progress)

    async def _parse_images(
        self,
        images: List[Image.Image],
        on_progress: Optional[Callable[[str, int, int], None]] = None,
    ) -> str:
        """Shared logic: send PIL images to the API."""
        total_pages = len(images)

        if on_progress:
            on_progress("Converting images for API...", 0, total_pages)

        images_b64 = [image_to_base64(img) for img in images]

        def api_progress(completed: int, total: int):
            if on_progress:
                on_progress(f"Processing page {completed}/{total}...", completed, total)

        if on_progress:
            on_progress("Starting transcription...", 0, total_pages)

        result = await self.client.transcribe_document(
            images_b64,
            TRANSCRIPTION_PROMPT,
            batch_size=self.batch_size,
            on_progress=api_progress,
        )

        if on_progress:
            on_progress("Finalizing...", total_pages, total_pages)

        return self.post_process(result)

    def post_process(self, text: str) -> str:
        """
        Post-process transcribed text.

        - Fix hyphenation across page boundaries
        - Normalize whitespace

        Args:
            text: Raw transcribed text

        Returns:
            Clean text
        """
        # Normalize whitespace
        text = self._normalize_whitespace(text)

        # Fix hyphenation across page boundaries
        text = self._fix_cross_page_hyphenation(text)

        return text.strip()

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace while preserving paragraph breaks."""
        # Replace multiple spaces with single space (but not newlines)
        text = re.sub(r'[^\S\n]+', ' ', text)
        # Replace 3+ newlines with 2 newlines (preserve paragraph breaks)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text

    def _fix_cross_page_hyphenation(self, text: str) -> str:
        """Fix words hyphenated across page boundaries."""
        # Pattern: word ending with hyphen, followed by separator, then word continuation
        # e.g., "fire-\n\n---\n\nfighter" -> "firefighter\n\n---\n\n"
        pattern = r'(\w+)-\s*\n\n---\n\n(\w+)'

        def join_hyphenated(match):
            return match.group(1) + match.group(2) + "\n\n---\n\n"

        return re.sub(pattern, join_hyphenated, text)


def get_output_path(pdf_path: Path, output_dir: Optional[Path] = None) -> Path:
    """
    Generate output path for parsed text file.

    Args:
        pdf_path: Original PDF path
        output_dir: Optional output directory (defaults to same as PDF)

    Returns:
        Path for the output text file
    """
    if output_dir is None:
        output_dir = pdf_path.parent

    stem = pdf_path.stem
    return output_dir / f"{stem} (parsed).txt"
