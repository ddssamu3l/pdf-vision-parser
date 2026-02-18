"""Supabase database operations."""

import os
from datetime import datetime, timezone
from typing import List, Optional
from supabase import create_client, Client

_client: Optional[Client] = None

def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_KEY"]
        _client = create_client(url, key)
    return _client

# Balance operations
def get_or_create_balance(user_id: str) -> int:
    """Get user balance in cents. Creates balance row if missing. Returns balance_cents."""
    client = get_client()
    result = client.table("balances").select("balance_cents").eq("user_id", user_id).execute()
    if result.data:
        return result.data[0]["balance_cents"]
    # Create new balance
    client.table("balances").insert({"user_id": user_id, "balance_cents": 0}).execute()
    return 0

def update_balance(user_id: str, amount_cents: int) -> int:
    """Add (positive) or deduct (negative) from balance. Returns new balance."""
    client = get_client()
    current = get_or_create_balance(user_id)
    new_balance = current + amount_cents
    client.table("balances").update({
        "balance_cents": new_balance,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("user_id", user_id).execute()
    return new_balance

# Transaction operations
def create_transaction(user_id: str, type: str, amount_cents: int, description: str, stripe_session_id: str = None, job_id: str = None) -> dict:
    """Create a transaction record."""
    client = get_client()
    data = {
        "user_id": user_id,
        "type": type,
        "amount_cents": amount_cents,
        "description": description,
    }
    if stripe_session_id:
        data["stripe_session_id"] = stripe_session_id
    if job_id:
        data["job_id"] = job_id
    result = client.table("transactions").insert(data).execute()
    return result.data[0] if result.data else {}

def get_transactions(user_id: str, limit: int = 50) -> List[dict]:
    """Get recent transactions for a user."""
    client = get_client()
    result = client.table("transactions").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
    return result.data or []

# Job operations
def create_job(user_id: str, filename: str, page_count: int = None) -> dict:
    """Create a new parsing job."""
    client = get_client()
    data = {
        "user_id": user_id,
        "filename": filename,
        "status": "pending",
    }
    if page_count:
        data["page_count"] = page_count
    result = client.table("jobs").insert(data).execute()
    return result.data[0] if result.data else {}

def update_job(job_id: str, **kwargs) -> dict:
    """Update job fields (status, input_tokens, output_tokens, cost_cents, result_text, error_message, completed_at)."""
    client = get_client()
    result = client.table("jobs").update(kwargs).eq("id", job_id).execute()
    return result.data[0] if result.data else {}

def get_job(job_id: str) -> Optional[dict]:
    """Get a single job by ID."""
    client = get_client()
    result = client.table("jobs").select("*").eq("id", job_id).execute()
    return result.data[0] if result.data else None

def get_user_jobs(user_id: str, limit: int = 50) -> List[dict]:
    """Get recent jobs for a user."""
    client = get_client()
    result = client.table("jobs").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
    return result.data or []
