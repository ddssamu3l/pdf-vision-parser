# PDF Vision Parser

A GUI tool that uses vision LLMs (Kimi K2.5, GPT-4o, Gemini) to parse scanned PDF textbooks into clean, continuous text with preserved metadata (page numbers, headers, footers, footnotes).

## Features

- Convert scanned PDFs to text using vision AI
- Support for multiple AI providers (Kimi, OpenAI, Google Gemini)
- Parallel processing for fast batch conversion
- Preserves document structure (headers, footers, footnotes, page numbers)
- Simple drag-and-drop interface
- First-run setup wizard for easy configuration

## Installation

### Prerequisites

1. **Python 3.9+** is required

2. **Poppler** (for PDF to image conversion) - The app will automatically install this on first run if not present. If auto-install fails, you can install manually:

   ```bash
   # macOS
   brew install poppler

   # Ubuntu/Debian
   sudo apt-get install poppler-utils

   # Windows
   # Download from: https://github.com/oschwartz10612/poppler-windows/releases
   # Add to PATH
   ```

### Install Dependencies

```bash
cd pdf-vision-parser
pip install -r requirements.txt
```

## Usage

1. **Launch the application:**

   ```bash
   python main.py
   ```

2. **First run:** You'll be prompted to enter your API key from your chosen provider (Kimi, OpenAI, or Gemini).

3. **Select PDFs:** Click the drop zone or drag and drop PDF files into the window.

4. **Parse:** Click "Parse Selected Files" to start processing.

5. **Output:** Parsed text files are saved next to the original PDFs with `(parsed).txt` suffix.

## Supported Providers

| Provider | Model | Signup URL |
|----------|-------|------------|
| Kimi (Moonshot AI) | kimi-k2.5 | https://platform.moonshot.cn/ |
| OpenAI | gpt-4o | https://platform.openai.com/ |
| Google Gemini | gemini-2.0-flash | https://aistudio.google.com/ |

## Output Format

The parser preserves document structure using markers:

```
[HEADER: CHAPTER TITLE]
[PAGE 1]

Main body text exactly as written in the document...

[FOOTNOTE 1]: Footnote text here

[FOOTER: Page footer text]

---

[HEADER: CHAPTER TITLE]
[PAGE 2]

...
```

## Configuration

Configuration is stored in `~/.pdf-parser/config.json`:

```json
{
  "api_key": "your-api-key",
  "provider": "kimi"
}
```

You can change the API key and provider from the Settings menu.

## License

MIT
