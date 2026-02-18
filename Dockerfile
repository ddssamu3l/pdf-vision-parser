FROM python:3.12-slim

# Install system dependencies for pdf2image and tesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt web/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r web/requirements.txt itsdangerous

COPY . .

EXPOSE 8000

CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
