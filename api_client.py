"""Vision LLM API client with batch processing."""

import asyncio
import random
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from openai import AsyncOpenAI, APIStatusError


@dataclass
class TranscriptionResult:
    """Result from a transcription call, including token usage."""
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class VisionLLMClient:
    """Client for vision LLM APIs (Kimi, OpenAI, Gemini via OpenAI-compatible interface)."""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def transcribe_pages(
        self,
        images_b64: List[str],
        prompt: str,
        start_page: int = 1,
        max_retries: int = 10,
        pdf_page_indicators: bool = False,
    ) -> TranscriptionResult:
        """Send multiple page images in a single API call for transcription."""
        content = [{"type": "text", "text": prompt}]

        for i, img_b64 in enumerate(images_b64):
            if pdf_page_indicators:
                page_num = start_page + i
                content.append({
                    "type": "text",
                    "text": f"\n--- PDF PAGE {page_num} ---\n",
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
                    max_tokens=32768,
                )
                text = response.choices[0].message.content or ""

                if response.choices[0].finish_reason == "length":
                    text += "\n\n[WARNING: Response was truncated due to length limit]"

                # Extract token usage
                input_tokens = 0
                output_tokens = 0
                if response.usage:
                    input_tokens = response.usage.prompt_tokens or 0
                    output_tokens = response.usage.completion_tokens or 0

                return TranscriptionResult(
                    text=text,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
            except APIStatusError as e:
                if e.status_code == 429 and attempt < max_retries - 1:
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
        pdf_page_indicators: bool = False,
    ) -> TranscriptionResult:
        """Process all pages sequentially in batches. Returns combined result with total tokens."""
        results = []
        total_input_tokens = 0
        total_output_tokens = 0
        total_pages = len(images_b64)

        for batch_start in range(0, total_pages, batch_size):
            batch_end = min(batch_start + batch_size, total_pages)
            batch_images = images_b64[batch_start:batch_end]

            try:
                result = await self.transcribe_pages(
                    batch_images,
                    prompt,
                    start_page=batch_start + 1,
                    pdf_page_indicators=pdf_page_indicators,
                )
                results.append(result.text)
                total_input_tokens += result.input_tokens
                total_output_tokens += result.output_tokens
            except Exception as e:
                results.append(f"[ERROR: Failed to transcribe pages {batch_start + 1}-{batch_end}: {str(e)}]")

            if on_progress:
                on_progress(batch_end, total_pages)

        return TranscriptionResult(
            text="\n\n---\n\n".join(results),
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )
