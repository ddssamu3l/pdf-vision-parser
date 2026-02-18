"""Background PDF processing worker."""

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api_client import VisionLLMClient
from config import PROVIDERS
from parser import PDFParser

DEV_MODE = os.environ.get("DEV_MODE", "").lower() in ("1", "true", "yes")

if not DEV_MODE:
    from . import database as db
    from . import billing


async def process_job(job_id: str, pdf_path: Path, user_id: str, pdf_page_indicators: bool = False):
    """
    Process a PDF parsing job in the background.

    1. Parse PDF using existing parser
    2. Track tokens from API response
    3. Calculate cost (20% markup)
    4. Check balance, deduct, save result
    """
    try:
        db.update_job(job_id, status="processing")

        # Set up LLM client using Kimi
        provider = PROVIDERS["kimi"]
        client = VisionLLMClient(
            api_key=os.environ["KIMI_API_KEY"],
            base_url=provider["base_url"],
            model=provider["model"],
        )

        parser = PDFParser(client, batch_size=5, pdf_page_indicators=pdf_page_indicators)

        # Parse the PDF
        result, flagged = await parser.parse_pdf(pdf_path)

        # Check balance before deducting
        balance = db.get_or_create_balance(user_id)
        cost_cents = billing.calculate_cost_cents(result.input_tokens, result.output_tokens)

        if balance < cost_cents:
            db.update_job(
                job_id,
                status="failed",
                error_message=f"Insufficient balance. Cost: ${cost_cents/100:.2f}, Balance: ${balance/100:.2f}",
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost_cents=cost_cents,
            )
            return

        # Deduct balance and save result
        billing.deduct_for_job(user_id, job_id, result.input_tokens, result.output_tokens)

        db.update_job(
            job_id,
            status="completed",
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_cents=cost_cents,
            result_text=result.text,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as e:
        db.update_job(
            job_id,
            status="failed",
            error_message=str(e),
        )
    finally:
        # Clean up temp file
        try:
            pdf_path.unlink(missing_ok=True)
        except Exception:
            pass


async def process_job_dev(job_id: str, pdf_path: Path, jobs_store: dict, pdf_page_indicators: bool = False):
    """
    Dev mode: process PDF without auth/billing.
    Uses in-memory jobs_store dict instead of database.
    Requires KIMI_API_KEY env var (or any provider key).
    """
    try:
        jobs_store[job_id]["status"] = "processing"

        # Try Kimi first, fall back to Ollama
        api_key = os.environ.get("KIMI_API_KEY")
        if api_key:
            provider = PROVIDERS["kimi"]
        else:
            provider = PROVIDERS.get("ollama", PROVIDERS["kimi"])
            api_key = "ollama"

        client = VisionLLMClient(
            api_key=api_key,
            base_url=provider["base_url"],
            model=provider["model"],
        )

        parser = PDFParser(client, batch_size=5, pdf_page_indicators=pdf_page_indicators)
        result, flagged = await parser.parse_pdf(pdf_path)

        jobs_store[job_id].update({
            "status": "completed",
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_cents": 0,
            "result_text": result.text,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })

    except Exception as e:
        jobs_store[job_id].update({
            "status": "failed",
            "error_message": str(e),
        })
    finally:
        try:
            pdf_path.unlink(missing_ok=True)
        except Exception:
            pass
