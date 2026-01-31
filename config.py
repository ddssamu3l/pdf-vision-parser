"""Configuration and prompts for PDF Vision Parser."""

from pathlib import Path

# Configuration directory
CONFIG_DIR = Path.home() / ".pdf-parser"
CONFIG_FILE = CONFIG_DIR / "config.json"

TRANSCRIPTION_PROMPT = """
TASK: Extract all text from this document page exactly as written.

You are performing OCR. Output the exact characters you see.

LAYOUT RULES:
- If two columns: read LEFT column top-to-bottom first, then RIGHT column
- Preserve paragraph breaks
- Join hyphenated words at line breaks (e.g., "fire-\\nfighter" → "firefighter")

OUTPUT FORMAT:
[HEADER: <header text if present>]
[PAGE <printed page number>]

<main body text exactly as written>

[FOOTNOTE <N>]: <footnote text>

[FOOTER: <footer text if present>]

CRITICAL:
1. VERBATIM transcription - never paraphrase
2. NEVER add words not visible on the page
3. NEVER skip visible text
4. If unclear, write [unclear]
5. Preserve speaker labels (SOCRATES:, etc.)
6. Include section markers [a], [b], [2], [3] where they appear
7. STOP immediately when you reach the bottom of the page. Do NOT continue with text from memory. Only transcribe what is physically printed on the page image.
8. If a sentence is cut off at the bottom of the page, end with exactly those words even if the sentence is incomplete.
"""

PROVIDERS = {
    "kimi": {
        "name": "Kimi (Moonshot AI)",
        "base_url": "https://api.moonshot.ai/v1",
        "model": "kimi-k2.5",
        "signup_url": "https://platform.moonshot.cn/",
    },
    "openai": {
        "name": "OpenAI GPT-4o",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "signup_url": "https://platform.openai.com/",
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.0-flash",
        "signup_url": "https://aistudio.google.com/",
    },
}

# Default provider
DEFAULT_PROVIDER = "kimi"

# Batch processing settings
DEFAULT_BATCH_SIZE = 20  # Pages per API call
