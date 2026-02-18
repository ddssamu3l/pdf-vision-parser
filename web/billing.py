"""Stripe billing and balance management."""

import os
import stripe
from typing import Optional
from . import database as db

# Kimi K2.5 pricing (per token)
KIMI_INPUT_COST = 0.60 / 1_000_000   # $0.60 per 1M tokens
KIMI_OUTPUT_COST = 2.50 / 1_000_000  # $2.50 per 1M tokens
MARKUP = 1.20  # 20% markup

# Our pricing
USER_INPUT_COST = KIMI_INPUT_COST * MARKUP    # $0.72 per 1M tokens
USER_OUTPUT_COST = KIMI_OUTPUT_COST * MARKUP   # $3.00 per 1M tokens

# Predefined deposit amounts (in cents)
DEPOSIT_OPTIONS = [
    {"amount_cents": 200, "label": "$2.00"},
    {"amount_cents": 500, "label": "$5.00"},
    {"amount_cents": 1000, "label": "$10.00"},
]

def init_stripe():
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

def calculate_cost_cents(input_tokens: int, output_tokens: int) -> int:
    """Calculate cost in cents for a job based on actual token usage."""
    input_cost = input_tokens * USER_INPUT_COST
    output_cost = output_tokens * USER_OUTPUT_COST
    total_dollars = input_cost + output_cost
    # Round up to nearest cent, minimum 1 cent
    return max(1, int(total_dollars * 100 + 0.99))

def create_checkout_session(user_id: str, amount_cents: int, success_url: str, cancel_url: str) -> Optional[str]:
    """Create a Stripe Checkout session for adding funds. Returns checkout URL."""
    init_stripe()
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"PDF Parser Credits",
                        "description": f"Add ${amount_cents / 100:.2f} to your balance",
                    },
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": user_id, "amount_cents": str(amount_cents)},
        )
        return session.url
    except Exception:
        return None

def handle_checkout_webhook(payload: bytes, sig_header: str) -> bool:
    """Handle Stripe webhook for completed checkout. Returns True on success."""
    init_stripe()
    webhook_secret = os.environ["STRIPE_WEBHOOK_SECRET"]
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        return False

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session["metadata"]["user_id"]
        amount_cents = int(session["metadata"]["amount_cents"])
        session_id = session["id"]

        # Credit the user's balance
        db.update_balance(user_id, amount_cents)
        db.create_transaction(
            user_id=user_id,
            type="deposit",
            amount_cents=amount_cents,
            description=f"Added ${amount_cents / 100:.2f} via Stripe",
            stripe_session_id=session_id,
        )
        return True

    return False

def deduct_for_job(user_id: str, job_id: str, input_tokens: int, output_tokens: int) -> int:
    """Deduct balance for a completed job. Returns cost in cents."""
    cost_cents = calculate_cost_cents(input_tokens, output_tokens)
    db.update_balance(user_id, -cost_cents)
    db.create_transaction(
        user_id=user_id,
        type="usage",
        amount_cents=-cost_cents,
        description=f"PDF parsing: {input_tokens + output_tokens} tokens",
        job_id=job_id,
    )
    return cost_cents
