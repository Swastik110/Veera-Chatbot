#!/usr/bin/env python3
"""
conversation_handlers.py — multi-turn conversation handler for Vera.

Implements the optional ConversationState-based respond() function
for the tiebreaker multi-turn replay test.
"""

from __future__ import annotations
from typing import Optional
from bot import (
    compose_reply, _is_auto_reply, _is_intent_commitment, _is_hostile,
    _is_same_message_repeated, _get, _llm_complete, contexts
)
import json


class ConversationState:
    """Lightweight conversation state passed to respond()."""

    def __init__(self, merchant_id: str, customer_id: Optional[str] = None,
                 category_slug: Optional[str] = None):
        self.merchant_id = merchant_id
        self.customer_id = customer_id
        self.category_slug = category_slug
        self.turns: list[dict] = []          # {"from": "vera"|"merchant", "msg": str}
        self.unanswered_auto_replies = 0
        self.ended = False
        self.last_trigger_kind: str = ""

    def add_turn(self, from_role: str, message: str):
        self.turns.append({"from": from_role, "msg": message})

    def last_vera_message(self) -> str:
        for t in reversed(self.turns):
            if t["from"] == "vera":
                return t["msg"]
        return ""


def respond(state: ConversationState, merchant_message: str) -> dict:
    """
    Given the conversation so far + the merchant's latest message,
    produce Vera's next reply.

    Returns a dict with keys:
        action: "send" | "wait" | "end"
        body: str (if action=send)
        cta: str
        rationale: str
    """
    if state.ended:
        return {"action": "end", "rationale": "Conversation already ended"}

    # Record merchant message
    state.add_turn("merchant", merchant_message)

    # ── Hostile / stop ──────────────────────────────────────────────────────
    if _is_hostile(merchant_message):
        state.ended = True
        return {
            "action": "end",
            "rationale": "Merchant signaled not interested — gracefully exiting"
        }

    # ── Auto-reply detection ────────────────────────────────────────────────
    if _is_auto_reply(merchant_message):
        state.unanswered_auto_replies += 1
        if state.unanswered_auto_replies >= 2:
            state.ended = True
            return {
                "action": "end",
                "rationale": "Repeated auto-reply detected — exiting to avoid burn"
            }
        else:
            # One gentle probe
            merchant = _get("merchant", state.merchant_id) or {}
            langs = merchant.get("identity", {}).get("languages", ["en"])
            hi = "hi" in langs
            body = (
                "Samajh gayi — kya owner/manager 2 min ke liye available hain? Seedha kaam karte hain. ✅"
                if hi else
                "Got it — is the owner available for 2 minutes? I can get this done quickly."
            )
            state.add_turn("vera", body)
            return {"action": "send", "body": body, "cta": "open_ended",
                    "rationale": "Auto-reply detected — one retry"}

    # Same message repeated
    merchant_msgs = [t["msg"] for t in state.turns if t["from"] == "merchant"]
    if merchant_msgs.count(merchant_message.strip()) >= 2:
        state.ended = True
        return {
            "action": "end",
            "rationale": "Same message repeated — confirmed auto-reply, exiting"
        }

    # ── Explicit commitment ─────────────────────────────────────────────────
    if _is_intent_commitment(merchant_message):
        state.unanswered_auto_replies = 0
        merchant = _get("merchant", state.merchant_id) or {}
        langs = merchant.get("identity", {}).get("languages", ["en"])
        hi = "hi" in langs
        active_offers = [o for o in merchant.get("offers", []) if o.get("status") == "active"]

        if hi:
            body = (
                f"Perfect! Abhi karte hain. "
                + (f"'{active_offers[0]['title']}' offer GBP pe pin kar rahi hoon. " if active_offers else
                   "Profile audit shuru kar rahi hoon — top 3 improvements 2 min mein. ")
                + "✅"
            )
        else:
            body = (
                "On it! "
                + (f"Pinning your '{active_offers[0]['title']}' offer on GBP right now. " if active_offers else
                   "Running a quick profile audit — top 3 improvements coming in 2 min. ")
                + "✅"
            )

        state.add_turn("vera", body)
        return {"action": "send", "body": body, "cta": "none",
                "rationale": "Commitment detected — switched to action mode"}

    # ── General LLM reply ───────────────────────────────────────────────────
    state.unanswered_auto_replies = 0
    merchant = _get("merchant", state.merchant_id) or {}
    cat_slug = merchant.get("category_slug", state.category_slug or "")
    category = _get("category", cat_slug) or {}
    customer = _get("customer", state.customer_id) if state.customer_id else None

    # Build a minimal conv dict compatible with compose_reply
    conv = {
        "turns": state.turns,
        "merchant_id": state.merchant_id,
        "customer_id": state.customer_id,
        "unanswered": state.unanswered_auto_replies,
        "ended": state.ended,
    }

    result = compose_reply(conv, merchant_message, merchant, category, customer)

    if result.get("action") == "send":
        body = result.get("body", "")
        if body:
            state.add_turn("vera", body)
    elif result.get("action") in ("end", "wait"):
        if result.get("action") == "end":
            state.ended = True

    return result
