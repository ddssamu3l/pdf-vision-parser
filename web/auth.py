"""Supabase magic link authentication."""

import os
from typing import Optional
from supabase import create_client, Client

_auth_client: Optional[Client] = None

def get_auth_client() -> Client:
    """Get Supabase client with anon key (for auth operations)."""
    global _auth_client
    if _auth_client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]  # anon key
        _auth_client = create_client(url, key)
    return _auth_client

def send_magic_link(email: str, redirect_url: str) -> bool:
    """Send magic link email. Returns True on success."""
    client = get_auth_client()
    try:
        client.auth.sign_in_with_otp({
            "email": email,
            "options": {"email_redirect_to": redirect_url},
        })
        return True
    except Exception:
        return False

def verify_token(access_token: str) -> Optional[dict]:
    """Verify a Supabase access token. Returns user dict or None."""
    client = get_auth_client()
    try:
        response = client.auth.get_user(access_token)
        if response and response.user:
            return {
                "id": str(response.user.id),
                "email": response.user.email,
            }
    except Exception:
        pass
    return None

def exchange_code(code: str) -> Optional[dict]:
    """Exchange auth code from magic link callback for session. Returns {"access_token", "refresh_token", "user"} or None."""
    client = get_auth_client()
    try:
        response = client.auth.exchange_code_for_session({"auth_code": code})
        if response and response.session:
            return {
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
                "user": {
                    "id": str(response.user.id),
                    "email": response.user.email,
                },
            }
    except Exception:
        pass
    return None
