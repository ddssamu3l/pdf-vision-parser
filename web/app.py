import asyncio
import os
import tempfile
import uuid
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from pdf_utils import get_pdf_page_count

# Dev mode: skip auth/billing, use in-memory storage
DEV_MODE = os.environ.get("DEV_MODE", "").lower() in ("1", "true", "yes")

if DEV_MODE:
    from .worker import process_job_dev
    # In-memory job store for dev mode
    _dev_jobs: dict[str, dict] = {}
else:
    from . import database as db
    from . import billing
    from .auth import send_magic_link, verify_token, exchange_code
    from .worker import process_job

app = FastAPI(title="PDF Parser")
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("APP_SECRET_KEY", "dev-secret"))

web_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=web_dir / "static"), name="static")
templates = Jinja2Templates(directory=web_dir / "templates")

DEV_USER = {"id": "dev-user", "email": "dev@localhost"}


# --- Auth helpers ---

def get_current_user(request: Request) -> dict | None:
    if DEV_MODE:
        return DEV_USER
    token = request.session.get("access_token")
    if not token:
        return None
    return verify_token(token)


def require_auth(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


# --- Routes: Auth ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if DEV_MODE:
        return RedirectResponse("/dashboard", status_code=303)
    user = get_current_user(request)
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return RedirectResponse("/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "sent": request.query_params.get("sent"),
        "error": request.query_params.get("error"),
    })


@app.post("/auth/magic-link")
async def auth_magic_link(request: Request):
    form = await request.form()
    email = form.get("email", "").strip()
    if not email:
        return RedirectResponse("/login?error=Please+enter+your+email", status_code=303)

    base_url = os.environ.get("BASE_URL", "http://localhost:8000")
    redirect_url = f"{base_url}/auth/callback"

    success = send_magic_link(email, redirect_url)
    if success:
        return RedirectResponse("/login?sent=1", status_code=303)
    return RedirectResponse("/login?error=Failed+to+send+magic+link", status_code=303)


@app.get("/auth/callback")
async def auth_callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        return RedirectResponse("/login?error=Invalid+callback", status_code=303)

    session_data = exchange_code(code)
    if not session_data:
        return RedirectResponse("/login?error=Authentication+failed", status_code=303)

    request.session["access_token"] = session_data["access_token"]
    request.session["user_id"] = session_data["user"]["id"]
    request.session["email"] = session_data["user"]["email"]

    db.get_or_create_balance(session_data["user"]["id"])

    return RedirectResponse("/dashboard", status_code=303)


@app.post("/auth/logout")
async def auth_logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# --- Routes: Dashboard ---

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    if DEV_MODE:
        jobs = sorted(_dev_jobs.values(), key=lambda j: j.get("created_at", ""), reverse=True)
        balance = 999999
    else:
        balance = db.get_or_create_balance(user["id"])
        jobs = db.get_user_jobs(user["id"])

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "balance_cents": balance,
        "balance_display": "DEV MODE" if DEV_MODE else f"${balance / 100:.2f}",
        "jobs": jobs,
    })


@app.post("/upload", response_class=HTMLResponse)
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Read toggle from form
    form = await request.form()
    pdf_page_indicators = form.get("pdf_page_indicators") == "1"

    if not DEV_MODE:
        balance = db.get_or_create_balance(user["id"])
        if balance <= 0:
            return RedirectResponse("/billing?error=Insufficient+balance", status_code=303)

    suffix = Path(file.filename or "upload.pdf").suffix
    temp_dir = Path(tempfile.gettempdir()) / "pdf-parser"
    temp_dir.mkdir(exist_ok=True)
    temp_path = temp_dir / f"{uuid.uuid4()}{suffix}"

    content = await file.read()
    temp_path.write_bytes(content)

    try:
        page_count = get_pdf_page_count(temp_path)
    except Exception:
        page_count = None

    if DEV_MODE:
        from datetime import datetime, timezone
        job_id = str(uuid.uuid4())
        job = {
            "id": job_id,
            "user_id": user["id"],
            "filename": file.filename or "upload.pdf",
            "page_count": page_count,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _dev_jobs[job_id] = job
        asyncio.create_task(process_job_dev(job_id, temp_path, _dev_jobs, pdf_page_indicators=pdf_page_indicators))
    else:
        job = db.create_job(
            user_id=user["id"],
            filename=file.filename or "upload.pdf",
            page_count=page_count,
        )
        asyncio.create_task(process_job(job["id"], temp_path, user["id"], pdf_page_indicators=pdf_page_indicators))

    return RedirectResponse("/dashboard", status_code=303)


@app.get("/job/{job_id}/status")
async def job_status(request: Request, job_id: str):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)

    if DEV_MODE:
        job = _dev_jobs.get(job_id)
    else:
        job = db.get_job(job_id)

    if not job or job["user_id"] != user["id"]:
        raise HTTPException(status_code=404)

    return JSONResponse({
        "id": job["id"],
        "status": job["status"],
        "filename": job["filename"],
        "page_count": job.get("page_count"),
        "cost_cents": job.get("cost_cents"),
        "error_message": job.get("error_message"),
    })


@app.get("/job/{job_id}/download")
async def job_download(request: Request, job_id: str):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)

    if DEV_MODE:
        job = _dev_jobs.get(job_id)
    else:
        job = db.get_job(job_id)

    if not job or job["user_id"] != user["id"]:
        raise HTTPException(status_code=404)

    if job["status"] != "completed" or not job.get("result_text"):
        raise HTTPException(status_code=400, detail="Job not completed")

    filename = Path(job["filename"]).stem + " (parsed).txt"
    return PlainTextResponse(
        content=job["result_text"],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Routes: Billing ---

@app.get("/billing", response_class=HTMLResponse)
async def billing_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    if DEV_MODE:
        return templates.TemplateResponse("billing.html", {
            "request": request,
            "user": user,
            "balance_cents": 999999,
            "balance_display": "DEV MODE",
            "transactions": [],
            "deposit_options": [],
            "error": None,
        })

    balance = db.get_or_create_balance(user["id"])
    transactions = db.get_transactions(user["id"])

    return templates.TemplateResponse("billing.html", {
        "request": request,
        "user": user,
        "balance_cents": balance,
        "balance_display": f"${balance / 100:.2f}",
        "transactions": transactions,
        "deposit_options": billing.DEPOSIT_OPTIONS,
        "error": request.query_params.get("error"),
    })


@app.post("/billing/checkout")
async def billing_checkout(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401)

    form = await request.form()
    amount_cents = int(form.get("amount_cents", 0))
    if amount_cents < 100:
        return RedirectResponse("/billing?error=Minimum+deposit+is+$1.00", status_code=303)

    base_url = os.environ.get("BASE_URL", "http://localhost:8000")
    checkout_url = billing.create_checkout_session(
        user_id=user["id"],
        amount_cents=amount_cents,
        success_url=f"{base_url}/billing?success=1",
        cancel_url=f"{base_url}/billing?cancelled=1",
    )

    if checkout_url:
        return RedirectResponse(checkout_url, status_code=303)
    return RedirectResponse("/billing?error=Failed+to+create+checkout", status_code=303)


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    success = billing.handle_webhook(payload, sig)
    if success:
        return JSONResponse({"status": "ok"})
    raise HTTPException(status_code=400, detail="Webhook failed")
