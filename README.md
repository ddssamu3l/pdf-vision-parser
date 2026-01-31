# PDF Vision Parser

A GUI tool that uses vision AI (Kimi K2.5, GPT-4o, Gemini) to convert scanned PDF textbooks into clean, readable text files. Preserves page numbers, headers, footers, and footnotes.

## Setup

### macOS

1. Install [Homebrew](https://brew.sh) if you don't have it (open Terminal and paste):
   ```
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. Install Python and poppler:
   ```
   brew install python poppler python-tk@3.13
   ```

3. Download this project and install dependencies:
   ```
   git clone https://github.com/ddssamu3l/pdf-vision-parser.git
   cd pdf-vision-parser
   pip3 install -r requirements.txt
   ```

4. Run:
   ```
   python3 main.py
   ```

### Windows

1. Install [Python](https://www.python.org/downloads/) (check "Add Python to PATH" during install)

2. Install poppler:
   - Download the latest release from [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases)
   - Extract the zip to `C:\poppler`
   - Add `C:\poppler\Library\bin` to your system PATH:
     - Search "environment variables" in Start menu
     - Click "Environment Variables"
     - Under "Path", click Edit, then add `C:\poppler\Library\bin`

3. Open Command Prompt and run:
   ```
   git clone https://github.com/ddssamu3l/pdf-vision-parser.git
   cd pdf-vision-parser
   pip install -r requirements.txt
   ```

4. Run:
   ```
   python main.py
   ```

## Usage

1. On first launch, you'll be asked to enter an API key. Pick a provider and sign up:

   | Provider | Model | Sign up |
   |----------|-------|---------|
   | Kimi (Moonshot AI) | kimi-k2.5 | https://platform.moonshot.cn/ |
   | OpenAI | gpt-4o | https://platform.openai.com/ |
   | Google Gemini | gemini-2.0-flash | https://aistudio.google.com/ |

2. Click the drop zone to select PDF files
3. Click **Parse Selected Files**
4. Output is saved next to the original PDF as `filename (parsed).txt`

## Output Format

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

## Building a Standalone App

To package as a distributable app (no Python needed for end users):

```
pip install pyinstaller
python build.py
```

This creates:
- **macOS**: `dist/PDF Parser.app`
- **Windows**: `dist/PDF Parser/PDF Parser.exe`

## License

MIT
