"""Vision LLM API client with batch processing."""

import asyncio
import random
from typing import Callable, List, Optional

from openai import AsyncOpenAI, APIStatusError


class VisionLLMClient:
    """Client for vision LLM APIs (Kimi, OpenAI, Gemini via OpenAI-compatible interface)."""

    def __init__(self, api_key: str, base_url: str, model: str):
        """
        Initialize the vision LLM client.

        Args:
            api_key: API key for the provider
            base_url: Base URL for the API endpoint
            model: Model identifier to use
        """
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def transcribe_pages(
        self,
        images_b64: List[str],
        prompt: str,
        start_page: int = 1,
        max_retries: int = 10,
    ) -> str:
        """
        Send multiple page images in a single API call for transcription.

        Args:
            images_b64: List of base64 encoded images
            prompt: Transcription prompt/instructions
            start_page: Starting page number for labeling
            max_retries: Maximum retry attempts for rate limit errors

        Returns:
            Transcribed text from all pages
        """
        # Build content with prompt and all images
        content = [{"type": "text", "text": prompt}]

        for i, img_b64 in enumerate(images_b64):
            page_num = start_page + i
            content.append({
                "type": "text",
                "text": f"\n--- PAGE {page_num} ---\n",
            })
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{img_b64}"},
            })

        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": content}],
                    max_tokens=16384,  # Larger limit for multiple pages
                )
                return response.choices[0].message.content or ""
            except APIStatusError as e:
                if e.status_code == 429 and attempt < max_retries - 1:
                    # Exponential backoff with jitter, starting at 5 seconds
                    wait_time = (5 * (2 ** attempt)) + random.uniform(0, 2)
                    await asyncio.sleep(wait_time)
                else:
                    raise

    async def transcribe_document(
        self,
        images_b64: List[str],
        prompt: str,
        batch_size: int = 20,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> str:
        """
        Process all pages sequentially in batches.

        Args:
            images_b64: List of base64 encoded images
            prompt: Transcription prompt/instructions
            batch_size: Number of pages per API call
            on_progress: Optional callback(completed, total) for progress updates

        Returns:
            Concatenated transcribed text from all pages
        """
        results = []
        total_pages = len(images_b64)

        for batch_start in range(0, total_pages, batch_size):
            batch_end = min(batch_start + batch_size, total_pages)
            batch_images = images_b64[batch_start:batch_end]

            try:
                result = await self.transcribe_pages(
                    batch_images,
                    prompt,
                    start_page=batch_start + 1,
                )
                results.append(result)
            except Exception as e:
                results.append(f"[ERROR: Failed to transcribe pages {batch_start + 1}-{batch_end}: {str(e)}]")

            if on_progress:
                on_progress(batch_end, total_pages)

        return "\n\n---\n\n".join(results)
