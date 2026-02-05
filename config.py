"""Configuration and prompts for PDF Vision Parser."""

from pathlib import Path

# Configuration directory
CONFIG_DIR = Path.home() / ".pdf-parser"
CONFIG_FILE = CONFIG_DIR / "config.json"

TRANSCRIPTION_PROMPT = """You are an OCR machine. Your ONLY job is to output the exact text visible in this image. Nothing else.

DO NOT:
- Answer questions about the text
- Summarize or analyze the content
- Explain what the text means
- Add commentary or interpretation
- Have a conversation
- Say "The text says..." or "This passage discusses..."

DO:
- Output ONLY the raw text exactly as printed
- Preserve the exact words, spelling, and punctuation
- Use the format below

LAYOUT:
- Two columns: read LEFT column top-to-bottom, then RIGHT column
- Preserve paragraph breaks
- Join hyphenated words at line breaks (e.g., "fire-\\nfighter" → "firefighter")

VISUAL MARKINGS (only if clearly visible):
- Crossed-out text: [CROSSED-OUT]text[/CROSSED-OUT]
- Inserted text: [INSERTION]text[/INSERTION]
- Deleted text: [DELETED]text[/DELETED]

FORMAT YOUR OUTPUT EXACTLY LIKE THIS:

[HEADER: <header if visible>]
[PAGE <number if visible>]

<exact text from the page>

[FOOTNOTE <N>]: <footnote text>

[FOOTER: <footer if visible>]

STOP at the bottom of the page. Do not continue from memory.

BEGIN TRANSCRIPTION:"""

PROVIDERS = {
    "kimi": {
        "name": "Kimi (Moonshot AI)",
        "base_url": "https://api.moonshot.ai/v1",
        "model": "kimi-k2.5",
        "signup_url": "https://platform.moonshot.cn/",
        "needs_api_key": True,
    },
    "ollama": {
        "name": "Ollama (Local)",
        "base_url": "http://localhost:11434/v1",
        "model": "qwen3-vl:32b",
        "signup_url": "",
        "needs_api_key": False,
    },
    "openai": {
        "name": "OpenAI GPT-4o",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "signup_url": "https://platform.openai.com/",
        "needs_api_key": True,
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.0-flash",
        "signup_url": "https://aistudio.google.com/",
        "needs_api_key": True,
    },
}

# Default provider
DEFAULT_PROVIDER = "kimi"

# Batch processing settings
DEFAULT_BATCH_SIZE = 20  # Pages per API call
