#!/usr/bin/env python3
"""
Vera — magicpin AI Challenge Bot
==================================
A high-scoring WhatsApp merchant engagement AI.

Features:
- 4-context composition (category + merchant + trigger + customer)
- Trigger-aware routing (each kind gets a specialised prompt)
- Auto-reply detection (same canned message pattern)
- Intent transition (detected "yes let's do it" -> action mode immediately)
- Graceful exit (hostile / 3 unanswered nudges)
- Hindi-English code-mix matching merchant language preference
- Specificity anchoring: real numbers, dates, source citations from context

Run: uvicorn bot:app --host 0.0.0.0 --port 8080
"""

import os
import re
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from urllib import request as urlrequest, error as urlerror

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — set via environment variables or edit here
# ─────────────────────────────────────────────────────────────────────────────

# Preferred provider: "gemini" | "anthropic" | "openai" | "openrouter"
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini")
LLM_API_KEY  = os.environ.get("LLM_API_KEY", "")
LLM_MODEL    = os.environ.get("LLM_MODEL", "")

# Try newer google-genai SDK first, then legacy, then REST only
try:
    from google import genai as _genai_new
    _GEMINI_SDK_NEW = True
except ImportError:
    _GEMINI_SDK_NEW = False

try:
    import google.generativeai as genai
    _GEMINI_SDK = True
except ImportError:
    _GEMINI_SDK = False

try:
    import anthropic as _anthropic_sdk
    _ANTHROPIC_SDK = True
except ImportError:
    _ANTHROPIC_SDK = False

# ─────────────────────────────────────────────────────────────────────────────
# LLM CALL (unified)
# ─────────────────────────────────────────────────────────────────────────────

def _llm_complete(prompt: str, system: str = "", temperature: float = 0.0) -> str:
    """Call LLM and return text. temperature=0 for determinism."""
    key = LLM_API_KEY

    if LLM_PROVIDER == "gemini":
        model = LLM_MODEL or "gemini-2.0-flash"
        if _GEMINI_SDK_NEW and key:
            # New google-genai SDK
            client = _genai_new.Client(api_key=key)
            from google.genai import types as _gtypes
            config = _gtypes.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=800,
                system_instruction=system or None
            )
            resp = client.models.generate_content(
                model=model, contents=prompt, config=config
            )
            return resp.text
        elif _GEMINI_SDK and key:
            genai.configure(api_key=key)
            cfg = {"temperature": temperature, "max_output_tokens": 800}
            g = genai.GenerativeModel(model, generation_config=cfg,
                                       system_instruction=system or None)
            resp = g.generate_content(prompt)
            return resp.text
        else:
            # Gemini via REST (no SDK needed)
            full = f"{system}\n\n{prompt}" if system else prompt
            body = json.dumps({
                "contents": [{"parts": [{"text": full}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": 800}
            }).encode("utf-8")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            req = urlrequest.Request(url, data=body, headers={"Content-Type": "application/json"})
            resp = urlrequest.urlopen(req, timeout=25)
            data = json.loads(resp.read())
            return data["candidates"][0]["content"]["parts"][0]["text"]

    elif LLM_PROVIDER == "anthropic":
        model = LLM_MODEL or "claude-3-5-haiku-20241022"
        if _ANTHROPIC_SDK and key:
            client = _anthropic_sdk.Anthropic(api_key=key)
            msg = client.messages.create(
                model=model, max_tokens=800,
                system=system or "You are a helpful assistant.",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return msg.content[0].text
        else:
            body = json.dumps({
                "model": model, "max_tokens": 800,
                "system": system or "You are a helpful assistant.",
                "messages": [{"role": "user", "content": prompt}]
            }).encode("utf-8")
            req = urlrequest.Request(
                "https://api.anthropic.com/v1/messages", data=body,
                headers={"x-api-key": key, "Content-Type": "application/json",
                         "anthropic-version": "2023-06-01"}
            )
            resp = urlrequest.urlopen(req, timeout=25)
            data = json.loads(resp.read())
            return data["content"][0]["text"]

    elif LLM_PROVIDER == "openai":
        model = LLM_MODEL or "gpt-4o-mini"
        body = json.dumps({
            "model": model, "temperature": temperature, "max_tokens": 800,
            "messages": [
                {"role": "system", "content": system or "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        }).encode("utf-8")
        req = urlrequest.Request(
            "https://api.openai.com/v1/chat/completions", data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        )
        resp = urlrequest.urlopen(req, timeout=25)
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]

    elif LLM_PROVIDER == "openrouter":
        model = LLM_MODEL or "google/gemini-flash-1.5"
        body = json.dumps({
            "model": model, "temperature": temperature, "max_tokens": 800,
            "messages": [
                {"role": "system", "content": system or "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        }).encode("utf-8")
        req = urlrequest.Request(
            "https://openrouter.ai/api/v1/chat/completions", data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "HTTP-Referer": "https://magicpin.com"}
        )
        resp = urlrequest.urlopen(req, timeout=25)
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]

    return "Hi, I'll be in touch."


# ─────────────────────────────────────────────────────────────────────────────
# IN-MEMORY STATE
# ─────────────────────────────────────────────────────────────────────────────

START = time.time()
# (scope, context_id) → {version, payload}
contexts: dict[tuple[str, str], dict] = {}
# conversation_id → {merchant_id, customer_id, turns: list[dict], unanswered: int, ended: bool}
conversations: dict[str, dict] = {}
# suppression dedup: key → True
sent_suppressions: set[str] = set()
# Which triggers have already fired in this session
fired_triggers: set[str] = set()


def _get(scope: str, cid: str) -> Optional[dict]:
    entry = contexts.get((scope, cid))
    return entry["payload"] if entry else None

def _count_by_scope(scope: str) -> int:
    return sum(1 for (s, _) in contexts if s == scope)


# ─────────────────────────────────────────────────────────────────────────────
# AUTO-REPLY DETECTION
# ─────────────────────────────────────────────────────────────────────────────

_AUTOREPLY_PATTERNS = [
    r"thank you for (contacting|reaching out|your message)",
    r"automated (response|reply|assistant|message)",
    r"your (message|query|request) (has been|is being) (received|noted|forwarded)",
    r"our team will (respond|get back to you|reply) (shortly|soon|asap|at the earliest)",
    r"please (call|visit|check) (during|our) (working|business|office) hours",
    r"आपकी जानकारी के लिए बहुत.बहुत शुक्रिया",
    r"main aapki yeh sabhi baatein",
    r"main ek automated assistant",
]

def _is_auto_reply(message: str) -> bool:
    msg_lower = message.lower().strip()
    for pat in _AUTOREPLY_PATTERNS:
        if re.search(pat, msg_lower):
            return True
    return False

def _is_same_message_repeated(conv: dict, message: str) -> bool:
    """If same message appeared ≥2 times in conversation history."""
    count = sum(1 for t in conv["turns"] if t.get("from") == "merchant"
                and t.get("msg", "").strip().lower() == message.strip().lower())
    return count >= 2

def _is_intent_commitment(message: str) -> bool:
    """Detect explicit yes/go-ahead intent."""
    msg = message.lower().strip()
    phrases = [
        "ok let", "okay let", "let's do it", "lets do it",
        "haan karo", "ha karo", "go ahead", "please do it", "do it",
        "yes please", "yes do it", "yes go ahead", "yes let's", "yes lets",
        "i want to join", "mujhe join karna", "mujhe judrna", "proceed",
        "confirm karo", "please proceed", "chalao", "shuruaat karo",
        "aage badho", "kar do", "chalo karte hain",
    ]
    return any(p in msg for p in phrases)

def _is_hostile(message: str) -> bool:
    msg = message.lower().strip()
    hostile = [
        "stop messaging", "don't message", "mat karo", "band karo",
        "spam", "annoying", "useless", "bother", "disturb",
        "not interested", "nahi chahiye", "koi zaroorat nahi",
        "block kar dunga", "block karungi", "block",
    ]
    return any(h in msg for h in hostile)


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSE — SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_COMPOSE = """You are Vera, magicpin's merchant AI assistant on WhatsApp.
You compose the NEXT WhatsApp message to send to a merchant (or their customer).

RULES (violate any = lower score):
1. Specificity: anchor on a VERIFIABLE fact from the context — a number, date, source citation, stat. Never say "increase your sales" generically.
2. Category fit: match the voice/tone of the category. Dentists → peer-clinical. Salons → warm-practical. Restaurants → operator-friendly. Gyms → coaching. Pharmacies → precise-trustworthy.
3. Merchant fit: use THEIR name, THEIR numbers, THEIR active offers, THEIR signals. Not generic advice.
4. Trigger relevance: make clear WHY you're sending this NOW. The trigger is the reason. Name it.
5. Engagement compulsion: use one or more of — loss aversion, social proof, curiosity, effort externalization, single-binary CTA.
6. Language: if merchant has "hi" or "hi-en mix" in languages, use natural Hindi-English code-mix. Full English only for English-only merchants.
7. CTA placement: put the CTA in the LAST sentence. Never bury it.
8. No preamble like "I hope this finds you well."
9. Never re-introduce yourself after the first message.
10. Never fabricate data that is NOT in the context provided.
11. For pure-information triggers (research_digest, digest), CTA = open_ended (want me to pull it?).
12. For action triggers (renewal_due, perf_dip, recall_due), CTA = binary YES/STOP.
13. For customer-facing messages, send_as = "merchant_on_behalf"; for merchant-facing, send_as = "vera".
14. Keep body under 250 words. Concise wins.

OUTPUT FORMAT (JSON only, no markdown):
{
  "body": "<the WhatsApp message>",
  "cta": "open_ended" | "binary_yes_stop" | "none",
  "send_as": "vera" | "merchant_on_behalf",
  "suppression_key": "<unique dedup key>",
  "rationale": "<1-2 sentences: why this message, what lever used>"
}"""


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSE FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def compose(category: dict, merchant: dict, trigger: dict,
            customer: Optional[dict] = None) -> dict:
    """
    Core composition logic. Takes 4 contexts, returns a message dict.
    Deterministic (temperature=0).
    """
    cat_slug   = category.get("slug", "")
    voice      = category.get("voice", {})
    peer_stats = category.get("peer_stats", {})
    digest     = category.get("digest", [])
    offers_cat = category.get("offer_catalog", [])
    seasonal   = category.get("seasonal_beats", [])
    trends     = category.get("trend_signals", [])

    identity   = merchant.get("identity", {})
    m_name     = identity.get("name", "")
    m_owner    = identity.get("owner_first_name", "")
    m_city     = identity.get("city", "")
    m_locality = identity.get("locality", "")
    m_langs    = identity.get("languages", ["en"])
    m_verified = identity.get("verified", False)

    subscription = merchant.get("subscription", {})
    sub_status   = subscription.get("status", "active")
    days_left    = subscription.get("days_remaining", 0)

    perf     = merchant.get("performance", {})
    views    = perf.get("views", 0)
    calls    = perf.get("calls", 0)
    ctr      = perf.get("ctr", 0)
    delta_7d = perf.get("delta_7d", {})

    m_offers  = merchant.get("offers", [])
    active_offers = [o for o in m_offers if o.get("status") == "active"]
    signals   = merchant.get("signals", [])
    conv_hist = merchant.get("conversation_history", [])
    cust_agg  = merchant.get("customer_aggregate", {})
    review_themes = merchant.get("review_themes", [])

    trg_kind    = trigger.get("kind", "")
    trg_scope   = trigger.get("scope", "merchant")
    trg_payload = trigger.get("payload", {})
    trg_urgency = trigger.get("urgency", 2)
    suppression = trigger.get("suppression_key", f"{trg_kind}:{merchant.get('merchant_id','')}")

    # Is Hindi code-mix preferred?
    hi_mix = "hi" in m_langs or "hi-en mix" in m_langs or any(
        l in ["hi", "mr", "kn", "te", "ta"] for l in m_langs
    )

    # Build peer CTR comparison string
    peer_ctr = peer_stats.get("avg_ctr", 0)
    ctr_vs   = ""
    if ctr and peer_ctr:
        diff = round((peer_ctr - ctr) / peer_ctr * 100)
        if diff > 0:
            ctr_vs = f"Aapka CTR {ctr:.1%} hai — peer median {peer_ctr:.1%} se {diff}% neeche" if hi_mix else f"Your CTR {ctr:.1%} is {diff}% below peer median {peer_ctr:.1%}"
        else:
            ctr_vs = f"Aapka CTR {ctr:.1%} — peer se zyada" if hi_mix else f"Your CTR {ctr:.1%} is above peer median"

    # Find relevant digest item from trigger payload
    top_item_id = trg_payload.get("top_item_id", "")
    top_digest  = next((d for d in digest if d.get("id") == top_item_id), None)
    if not top_digest and digest:
        top_digest = digest[0]  # fallback to first

    # Customer context (optional)
    cust_name  = ""
    cust_lang  = ""
    cust_state = ""
    cust_prefs = {}
    cust_rel   = {}
    if customer:
        cust_name  = customer.get("identity", {}).get("name", "")
        cust_lang  = customer.get("identity", {}).get("language_pref", "en")
        cust_state = customer.get("state", "")
        cust_prefs = customer.get("preferences", {})
        cust_rel   = customer.get("relationship", {})

    # Build trigger-specific context block
    trg_extra = ""
    if trg_kind == "research_digest" and top_digest:
        trg_extra = f"""RESEARCH DIGEST TRIGGER:
Title: {top_digest.get('title')}
Source: {top_digest.get('source')}
Trial N: {top_digest.get('trial_n', 'N/A')}
Patient Segment: {top_digest.get('patient_segment', 'general')}
Summary: {top_digest.get('summary', '')}
Actionable: {top_digest.get('actionable', '')}"""

    elif trg_kind == "regulation_change" and top_digest:
        trg_extra = f"""REGULATION CHANGE TRIGGER:
Title: {top_digest.get('title')}
Source: {top_digest.get('source')}
Summary: {top_digest.get('summary', '')}
Deadline: {trg_payload.get('deadline_iso', '')}
Actionable: {top_digest.get('actionable', '')}"""

    elif trg_kind == "perf_dip":
        metric  = trg_payload.get("metric", "views")
        delta   = trg_payload.get("delta_pct", 0)
        window  = trg_payload.get("window", "7d")
        trg_extra = f"""PERF DIP TRIGGER:
Metric: {metric} dropped {abs(delta)*100:.0f}% over last {window}
Current {metric}: {perf.get(metric, '?')}
Peer benchmark: {peer_stats.get(f'avg_{metric}_30d', 'N/A')}
Signals: {signals}"""

    elif trg_kind in ("perf_spike",):
        metric  = trg_payload.get("metric", "views")
        delta   = trg_payload.get("delta_pct", 0)
        driver  = trg_payload.get("likely_driver", "")
        trg_extra = f"""PERF SPIKE TRIGGER:
Metric: {metric} up {delta*100:.0f}% over last {trg_payload.get('window','7d')}
Likely driver: {driver}
Now: {perf.get(metric,'?')}"""

    elif trg_kind == "renewal_due":
        trg_extra = f"""RENEWAL DUE TRIGGER:
Days remaining: {trg_payload.get('days_remaining', days_left)}
Plan: {trg_payload.get('plan', subscription.get('plan','Pro'))}
Renewal amount: ₹{trg_payload.get('renewal_amount', 4999)}
Performance last 30d: views={views}, calls={calls}, CTR={ctr:.1%}"""

    elif trg_kind == "dormant_with_vera":
        days_dormant = trg_payload.get("days_since_last_merchant_message", 14)
        last_topic   = trg_payload.get("last_topic", "")
        trg_extra = f"""DORMANT TRIGGER:
No merchant reply for {days_dormant} days
Last topic: {last_topic}
Current performance: views={views}, calls={calls}"""

    elif trg_kind == "recall_due" and customer:
        slots = trg_payload.get("available_slots", [])
        slot_labels = [s.get("label", "") for s in slots[:2]]
        trg_extra = f"""RECALL DUE TRIGGER (Customer-facing):
Service due: {trg_payload.get('service_due', '')}
Last service: {trg_payload.get('last_service_date', cust_rel.get('last_visit',''))}
Due date: {trg_payload.get('due_date', '')}
Available slots: {', '.join(slot_labels) if slot_labels else 'check with clinic'}
Customer state: {cust_state}
Customer preferred slot: {cust_prefs.get('preferred_slots', '')}
Customer language: {cust_lang}"""

    elif trg_kind in ("customer_lapsed_hard", "customer_lapsed_soft"):
        trg_extra = f"""LAPSED CUSTOMER TRIGGER:
Days since last visit: {trg_payload.get('days_since_last_visit', '?')}
Previous focus: {trg_payload.get('previous_focus', '')}
Previous membership months: {trg_payload.get('previous_membership_months', '')}
Customer state: {cust_state}"""

    elif trg_kind == "chronic_refill_due" and customer:
        meds = trg_payload.get("molecule_list", [])
        runs_out = trg_payload.get("stock_runs_out_iso", "")
        trg_extra = f"""CHRONIC REFILL DUE (Customer-facing):
Medications: {', '.join(meds)}
Last refill: {trg_payload.get('last_refill', '')}
Stock runs out: {runs_out[:10] if runs_out else '?'}
Delivery address saved: {trg_payload.get('delivery_address_saved', False)}
Customer language: {cust_lang}"""

    elif trg_kind == "supply_alert":
        trg_extra = f"""SUPPLY ALERT TRIGGER:
Molecule: {trg_payload.get('molecule', '')}
Affected batches: {trg_payload.get('affected_batches', [])}
Manufacturer: {trg_payload.get('manufacturer', '')}
Urgency: {trg_urgency}/5 — ACT NOW"""

    elif trg_kind == "festival_upcoming":
        festival = trg_payload.get("festival", "")
        days_until = trg_payload.get("days_until", 0)
        trg_extra = f"""FESTIVAL TRIGGER:
Festival: {festival}
Days until: {days_until}
Category relevance: {trg_payload.get('category_relevance', [])}
Active offers: {[o.get('title') for o in active_offers]}"""

    elif trg_kind in ("ipl_match_today", "ipl_match_tonight"):
        trg_extra = f"""IPL MATCH TRIGGER:
Match: {trg_payload.get('match', '')}
Venue: {trg_payload.get('venue', '')}
Match time: {trg_payload.get('match_time_iso', '')}
Active offers: {[o.get('title') for o in active_offers]}"""

    elif trg_kind == "competitor_opened":
        trg_extra = f"""COMPETITOR TRIGGER:
Competitor: {trg_payload.get('competitor_name', '')}
Distance: {trg_payload.get('distance_km', '')} km
Their offer: {trg_payload.get('their_offer', '')}
Your active offers: {[o.get('title') for o in active_offers]}
Your CTR vs peer: {ctr_vs}"""

    elif trg_kind == "review_theme_emerged":
        theme = trg_payload.get("theme", "")
        quote = trg_payload.get("common_quote", "")
        trg_extra = f"""REVIEW THEME TRIGGER:
Theme: {theme} ({trg_payload.get('trend', 'flat')})
Occurrences 30d: {trg_payload.get('occurrences_30d', '?')}
Sample quote: "{quote}"
Reviews in merchant data: {review_themes}"""

    elif trg_kind == "milestone_reached":
        trg_extra = f"""MILESTONE TRIGGER:
Metric: {trg_payload.get('metric', '')}
Current value: {trg_payload.get('value_now', '')}
Milestone: {trg_payload.get('milestone_value', '')}
Is imminent: {trg_payload.get('is_imminent', False)}"""

    elif trg_kind == "winback_eligible":
        trg_extra = f"""WINBACK TRIGGER:
Days since expiry: {trg_payload.get('days_since_expiry', '')}
Perf dip since expiry: {trg_payload.get('perf_dip_pct', 0)*100:.0f}%
Lapsed customers added since expiry: {trg_payload.get('lapsed_customers_added_since_expiry', 0)}"""

    elif trg_kind == "gbp_unverified":
        trg_extra = f"""GBP UNVERIFIED TRIGGER:
Verification path: {trg_payload.get('verification_path', '')}
Estimated uplift if verified: {trg_payload.get('estimated_uplift_pct', 0)*100:.0f}% more views"""

    elif trg_kind == "cde_opportunity" and top_digest:
        trg_extra = f"""CDE OPPORTUNITY:
Title: {top_digest.get('title', '')}
Date: {top_digest.get('date', '')}
Credits: {trg_payload.get('credits', '')}
Fee: {trg_payload.get('fee', '')}"""

    elif trg_kind == "curious_ask_due":
        ask_template = trg_payload.get("ask_template", "what_service_in_demand_this_week")
        trg_extra = f"""CURIOUS ASK TRIGGER:
Ask template: {ask_template}
Note: Ask one genuine question to learn about their business. Make them feel heard.
Use social proof or curiosity lever."""

    elif trg_kind == "active_planning_intent":
        trg_extra = f"""ACTIVE PLANNING TRIGGER:
Intent topic: {trg_payload.get('intent_topic', '')}
Merchant last message: "{trg_payload.get('merchant_last_message', '')}"
IMPORTANT: Merchant is in action mode. Deliver the plan/draft immediately, don't ask more qualifying questions."""

    elif trg_kind == "category_seasonal":
        trg_extra = f"""SEASONAL TRIGGER:
Season: {trg_payload.get('season', '')}
Trends: {trg_payload.get('trends', [])}
Shelf action recommended: {trg_payload.get('shelf_action_recommended', False)}"""

    elif trg_kind == "trial_followup" and customer:
        sessions = trg_payload.get("next_session_options", [])
        session_labels = [s.get("label", "") for s in sessions[:2]]
        trg_extra = f"""TRIAL FOLLOWUP (Customer-facing):
Trial date: {trg_payload.get('trial_date', '')}
Next session options: {session_labels}
Customer state: {cust_state}"""

    elif trg_kind == "wedding_package_followup" and customer:
        trg_extra = f"""WEDDING PACKAGE FOLLOWUP:
Wedding date: {trg_payload.get('wedding_date', '')}
Trial completed: {trg_payload.get('trial_completed', '')}
Days to wedding: {trg_payload.get('days_to_wedding', '')}
Next step window: {trg_payload.get('next_step_window_open', '')}"""

    else:
        trg_extra = f"""TRIGGER:
Kind: {trg_kind}
Payload: {json.dumps(trg_payload, ensure_ascii=False)[:300]}"""

    # Recent conversation (last 2 turns)
    recent_conv = ""
    if conv_hist:
        last_turns = conv_hist[-2:]
        recent_conv = "\nRECENT CONVERSATION:\n" + "\n".join(
            f"  [{t.get('from','?').upper()}]: {t.get('body','')[:120]}" for t in last_turns
        )

    # Customer block (if applicable)
    customer_block = ""
    if customer:
        customer_block = f"""
CUSTOMER CONTEXT:
Name: {cust_name}
State: {cust_state}
Language: {cust_lang}
Visits total: {cust_rel.get('visits_total', 1)}
Last visit: {cust_rel.get('last_visit', '')}
Services received: {cust_rel.get('services_received', [])[:4]}
Preferred slot: {cust_prefs.get('preferred_slots', '')}
Consent scope: {customer.get('consent', {}).get('scope', [])}"""

    # Determine if hi-en mix should be used
    lang_instruction = ""
    if trg_scope == "customer" and customer:
        cl = cust_lang.lower()
        if "hi" in cl or "mix" in cl:
            lang_instruction = "Use natural Hindi-English code-mix (Hinglish). Example: 'Aapka 6-month cleaning recall aa gaya hai.'"
        elif "en" in cl:
            lang_instruction = "Use English only."
        elif "ta" in cl:
            lang_instruction = "Use Tamil-English mix."
        elif "te" in cl:
            lang_instruction = "Use Telugu-English mix."
        elif "kn" in cl:
            lang_instruction = "Use Kannada-English mix."
        else:
            lang_instruction = "Use Hindi-English code-mix."
    elif hi_mix:
        lang_instruction = "Use natural Hindi-English code-mix (Hinglish) — mix both languages naturally."
    else:
        lang_instruction = "Use English."

    prompt = f"""COMPOSE A WHATSAPP MESSAGE:

CATEGORY: {cat_slug} | Voice: {voice.get('tone', '')} | Taboos: {voice.get('vocab_taboo', [])}
OFFER CATALOG: {[o.get('title') for o in offers_cat[:5]]}
PEER STATS: avg_ctr={peer_stats.get('avg_ctr','?')}, avg_rating={peer_stats.get('avg_rating','?')}, avg_reviews={peer_stats.get('avg_review_count','?')}
SEASONAL: {[f"{s['month_range']}: {s['note']}" for s in seasonal[:2]]}
TRENDS: {[f"{t.get('query')} {'+' if t.get('delta_yoy',0)>0 else ''}{t.get('delta_yoy',0)*100:.0f}% YoY" for t in trends[:2]]}

MERCHANT: {m_name} | Owner: {m_owner} | {m_city}, {m_locality}
Subscription: {sub_status}, {days_left} days remaining | Verified GBP: {m_verified}
Performance (30d): views={views}, calls={calls}, CTR={ctr:.1%}
7d delta: views {delta_7d.get('views_pct',0)*100:+.0f}%, calls {delta_7d.get('calls_pct',0)*100:+.0f}%
{ctr_vs}
Active Offers: {[o.get('title') for o in active_offers] or 'None'}
Customer aggregate: {cust_agg}
Signals: {signals}
{recent_conv}

{trg_extra}
{customer_block}

LANGUAGE: {lang_instruction}

Now compose the message. Output ONLY valid JSON."""

    # Call LLM
    try:
        raw = _llm_complete(prompt, SYSTEM_COMPOSE, temperature=0.0)
        # Extract JSON
        match = re.search(r'\{[\s\S]*?\}', raw)
        if match:
            result = json.loads(match.group())
            # Validate keys
            if "body" not in result or not result["body"]:
                raise ValueError("Empty body")
            result.setdefault("cta", "open_ended")
            result.setdefault("send_as", "vera" if trg_scope == "merchant" else "merchant_on_behalf")
            result.setdefault("suppression_key", suppression)
            result.setdefault("rationale", f"Triggered by {trg_kind} for {merchant.get('merchant_id','')}")
            return result
    except Exception as e:
        pass

    # Fallback message
    return {
        "body": f"Hi {m_owner or m_name}, Vera here — noticed something relevant for your business. Reply YES to know more.",
        "cta": "binary_yes_stop",
        "send_as": "vera",
        "suppression_key": suppression,
        "rationale": f"Fallback for {trg_kind}"
    }


# ─────────────────────────────────────────────────────────────────────────────
# REPLY HANDLER (multi-turn)
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_REPLY = """You are Vera, magicpin's merchant AI assistant. You are continuing a WhatsApp conversation.

Rules:
1. If the merchant just said something like "ok let's do it" / "yes proceed" / "kar do" → immediately confirm and describe the NEXT CONCRETE ACTION you'll take. Do NOT ask more qualifying questions.
2. If the merchant asked a specific question → answer it directly with facts from the context.
3. If the merchant showed genuine engagement → advance the conversation to the next step.
4. If the conversation goal is done → wrap up gracefully with "Is there anything else I can help with?"
5. Match the merchant's language (Hinglish if they're using it).
6. Keep reply under 150 words.
7. Never re-introduce yourself.

OUTPUT FORMAT (JSON only):
{
  "action": "send" | "wait" | "end",
  "body": "<reply if action=send, else null>",
  "cta": "open_ended" | "binary_yes_stop" | "none",
  "wait_seconds": <int if action=wait, else null>,
  "rationale": "<1 sentence>"
}"""

def compose_reply(conv: dict, merchant_message: str,
                  merchant: dict, category: dict,
                  customer: Optional[dict] = None) -> dict:
    """Generate reply to a merchant message in context of ongoing conversation."""

    history_text = "\n".join(
        f"  [{t['from'].upper()}]: {t['msg'][:150]}"
        for t in conv["turns"][-6:]
    )

    m_name  = merchant.get("identity", {}).get("name", "")
    m_owner = merchant.get("identity", {}).get("owner_first_name", "")
    m_langs = merchant.get("identity", {}).get("languages", ["en"])
    hi_mix  = "hi" in m_langs or "hi-en mix" in m_langs

    active_offers = [o for o in merchant.get("offers", []) if o.get("status") == "active"]
    signals = merchant.get("signals", [])
    cat_slug = category.get("slug", "")

    lang_instruction = "Use natural Hindi-English code-mix." if hi_mix else "Use English."

    prompt = f"""ONGOING CONVERSATION — produce Vera's NEXT reply:

MERCHANT: {m_name} | {m_owner} | Category: {cat_slug}
Active offers: {[o.get('title') for o in active_offers]}
Signals: {signals}

CONVERSATION HISTORY:
{history_text}

LATEST MERCHANT MESSAGE: "{merchant_message}"

LANGUAGE: {lang_instruction}

Determine: is this an auto-reply? commitment? question? engagement? hostility?
Then output the appropriate action as JSON."""

    try:
        raw = _llm_complete(prompt, SYSTEM_REPLY, temperature=0.0)
        match = re.search(r'\{[\s\S]*?\}', raw)
        if match:
            result = json.loads(match.group())
            result.setdefault("action", "send")
            if result["action"] == "send":
                result.setdefault("body", f"Got it, {m_owner or m_name}! I'll get started on this right away.")
                result.setdefault("cta", "open_ended")
            result.setdefault("rationale", "Continuing conversation")
            return result
    except Exception:
        pass

    # Fallback
    return {
        "action": "send",
        "body": f"Got it! Let me work on that for you, {m_owner or m_name}.",
        "cta": "open_ended",
        "rationale": "Fallback reply"
    }


# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI APP
# ─────────────────────────────────────────────────────────────────────────────

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Vera — magicpin AI Challenge Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Internal Frontend APIs ───────────────────────────────────────────────────

@app.get("/api/dashboard")
async def get_dashboard():
    return {
        "categories": _count_by_scope("category"),
        "merchants": _count_by_scope("merchant"),
        "customers": _count_by_scope("customer"),
        "triggers": _count_by_scope("trigger"),
        "active_conversations": len(conversations),
        "messages_generated": sum(len(c["turns"]) for c in conversations.values()),
        "proactive_actions": len(fired_triggers),
        "uptime_seconds": int(time.time() - START)
    }

@app.get("/api/merchants")
async def get_merchants():
    merchants = []
    for (s, cid), data in contexts.items():
        if s == "merchant":
            p = data["payload"]
            merchants.append({
                "merchant_id": p.get("merchant_id"),
                "name": p.get("identity", {}).get("name"),
                "category": p.get("category_slug"),
                "city": p.get("identity", {}).get("city"),
                "subscription_status": p.get("subscription", {}).get("status"),
                "rating": p.get("performance", {}).get("ctr")  # just exposing ctr as metric
            })
    return {"merchants": merchants}

@app.get("/api/merchants/{merchant_id}")
async def get_merchant(merchant_id: str):
    m = _get("merchant", merchant_id)
    if not m:
        raise HTTPException(404, "Merchant not found")
    return {"merchant": m}

@app.get("/api/triggers")
async def get_triggers():
    triggers = []
    for (s, cid), data in contexts.items():
        if s == "trigger":
            triggers.append(data["payload"])
    return {"triggers": triggers}

@app.get("/api/contexts")
async def get_all_contexts():
    cats = [_get("category", cid) for (s, cid) in contexts if s == "category"]
    mers = [_get("merchant", cid) for (s, cid) in contexts if s == "merchant"]
    trgs = [_get("trigger", cid) for (s, cid) in contexts if s == "trigger"]
    custs = [_get("customer", cid) for (s, cid) in contexts if s == "customer"]
    return {"category": cats, "merchant": mers, "trigger": trgs, "customer": custs}

class ComposeRequest(BaseModel):
    category_slug: str
    merchant_id: str
    trigger_id: str
    customer_id: Optional[str] = None

@app.post("/api/compose")
async def api_compose(req: ComposeRequest):
    cat = _get("category", req.category_slug)
    mer = _get("merchant", req.merchant_id)
    trg = _get("trigger", req.trigger_id)
    cust = _get("customer", req.customer_id) if req.customer_id else None
    if not all([cat, mer, trg]):
        raise HTTPException(400, "Missing context data")
    return compose(cat, mer, trg, cust)

@app.get("/api/conversations")
async def get_conversations():
    return {"conversations": conversations}

@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    if conv_id not in conversations:
        raise HTTPException(404, "Conversation not found")
    return {"conversation": conversations[conv_id]}


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/v1/healthz")
async def healthz():
    counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
    for (scope, _) in contexts:
        if scope in counts:
            counts[scope] += 1
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - START),
        "contexts_loaded": counts
    }


# ── Metadata ─────────────────────────────────────────────────────────────────

@app.get("/v1/metadata")
async def metadata():
    return {
        "team_name": "Vera-AI",
        "team_members": ["Swastik"],
        "model": LLM_MODEL or ("gemini-2.0-flash" if LLM_PROVIDER == "gemini" else LLM_PROVIDER),
        "approach": "Trigger-aware prompt routing with 4-context composition, auto-reply detection, intent transition, and multi-turn handling",
        "contact_email": "swastik@example.com",
        "version": "2.0.0",
        "submitted_at": "2026-09-27T08:00:00Z"
    }


# ── Teardown ─────────────────────────────────────────────────────────────────

@app.post("/v1/teardown")
async def teardown():
    contexts.clear()
    conversations.clear()
    sent_suppressions.clear()
    fired_triggers.clear()
    return {"ok": True}


# ── Context Push ──────────────────────────────────────────────────────────────

class CtxBody(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: str

@app.post("/v1/context")
async def push_context(body: CtxBody):
    valid_scopes = {"category", "merchant", "customer", "trigger"}
    if body.scope not in valid_scopes:
        return {"accepted": False, "reason": "invalid_scope",
                "details": f"scope must be one of {valid_scopes}"}

    key = (body.scope, body.context_id)
    cur = contexts.get(key)
    if cur and cur["version"] >= body.version:
        return {"accepted": False, "reason": "stale_version",
                "current_version": cur["version"]}

    contexts[key] = {"version": body.version, "payload": body.payload}
    return {
        "accepted": True,
        "ack_id": f"ack_{body.context_id}_v{body.version}",
        "stored_at": datetime.now(timezone.utc).isoformat()
    }


# ── Tick ─────────────────────────────────────────────────────────────────────

class TickBody(BaseModel):
    now: str
    available_triggers: list[str] = []

@app.post("/v1/tick")
async def tick(body: TickBody):
    actions = []
    now_ts = body.now

    for trg_id in body.available_triggers:
        # Skip already fired triggers
        if trg_id in fired_triggers:
            continue

        trg = _get("trigger", trg_id)
        if not trg:
            continue

        # Check suppression
        sup_key = trg.get("suppression_key", trg_id)
        if sup_key in sent_suppressions:
            continue

        merchant_id = trg.get("merchant_id")
        customer_id = trg.get("customer_id")

        merchant = _get("merchant", merchant_id) if merchant_id else None
        if not merchant:
            continue

        cat_slug = merchant.get("category_slug", "")
        category = _get("category", cat_slug)
        if not category:
            continue

        customer = _get("customer", customer_id) if customer_id else None

        # Compose the message
        try:
            result = compose(category, merchant, trg, customer)
        except Exception as e:
            continue

        body_text = result.get("body", "")
        if not body_text:
            continue

        # Generate conversation ID
        conv_id = f"conv_{merchant_id}_{trg_id}"

        # Mark as fired + suppressed
        fired_triggers.add(trg_id)
        sent_suppressions.add(sup_key)

        # Store conversation
        conversations[conv_id] = {
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "turns": [{"from": "vera", "msg": body_text}],
            "unanswered": 0,
            "ended": False,
            "last_vera_body": body_text,
        }

        trg_scope = trg.get("scope", "merchant")
        send_as = result.get("send_as", "vera" if trg_scope == "merchant" else "merchant_on_behalf")

        actions.append({
            "conversation_id": conv_id,
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "send_as": send_as,
            "trigger_id": trg_id,
            "template_name": f"vera_{trg.get('kind', 'generic')}_v1",
            "template_params": [
                merchant.get("identity", {}).get("name", ""),
                trg.get("kind", ""),
                now_ts
            ],
            "body": body_text,
            "cta": result.get("cta", "open_ended"),
            "suppression_key": sup_key,
            "rationale": result.get("rationale", "")
        })

        # Cap at 20 actions per tick
        if len(actions) >= 20:
            break

    return {"actions": actions}


# ── Reply ─────────────────────────────────────────────────────────────────────

class ReplyBody(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: str
    turn_number: int

@app.post("/v1/reply")
async def reply(body: ReplyBody):
    conv_id = body.conversation_id
    message = body.message
    merchant_id = body.merchant_id or ""

    # Ensure conversation exists
    if conv_id not in conversations:
        conversations[conv_id] = {
            "merchant_id": merchant_id,
            "customer_id": body.customer_id,
            "turns": [],
            "unanswered": 0,
            "ended": False,
            "last_vera_body": "",
        }

    conv = conversations[conv_id]

    if conv.get("ended"):
        return {"action": "end", "rationale": "Conversation already ended"}

    # Record inbound
    conv["turns"].append({"from": body.from_role, "msg": message})

    # ── Special handling ──────────────────────────────────────────────────────

    # 1. Hostile / stop signal
    if _is_hostile(message):
        conv["ended"] = True
        return {
            "action": "end",
            "rationale": "Merchant signaled not interested or hostility — gracefully exiting"
        }

    # 2. Auto-reply detection
    if _is_auto_reply(message) or _is_same_message_repeated(conv, message):
        conv["unanswered"] += 1
        if conv["unanswered"] >= 2:
            # Already tried once — now exit
            conv["ended"] = True
            return {
                "action": "end",
                "rationale": "Auto-reply detected on repeated message — gracefully exiting to avoid turn burn"
            }
        else:
            # First auto-reply — try once more with a direct appeal
            merchant = _get("merchant", merchant_id) or {}
            m_owner = merchant.get("identity", {}).get("owner_first_name", "")
            m_name  = merchant.get("identity", {}).get("name", "")
            m_langs = merchant.get("identity", {}).get("languages", ["en"])
            hi_mix  = "hi" in m_langs
            if hi_mix:
                reply_body = f"Samajh gayi — kya aap khud ya koi team member 2 minutes ke liye dekh sakta hai? Seedha kaam karte hain. ✅"
            else:
                reply_body = f"Got it — is the owner or manager available for 2 minutes? I can get this done quickly for you."
            conv["turns"].append({"from": "vera", "msg": reply_body})
            return {
                "action": "send",
                "body": reply_body,
                "cta": "open_ended",
                "rationale": "Auto-reply detected — one retry appeal to real decision-maker"
            }

    # 3. Explicit commitment / intent
    if _is_intent_commitment(message):
        merchant = _get("merchant", merchant_id) or {}
        m_owner = merchant.get("identity", {}).get("owner_first_name", "")
        m_name  = merchant.get("identity", {}).get("name", "")
        m_langs = merchant.get("identity", {}).get("languages", ["en"])
        hi_mix  = "hi" in m_langs
        cat_slug = merchant.get("category_slug", "")
        category = _get("category", cat_slug) or {}

        active_offers = [o for o in merchant.get("offers", []) if o.get("status") == "active"]
        if hi_mix:
            _hi_msg = ("Pehle aapke active offer '{}' ko GBP pe pin kar deti hoon.".format(active_offers[0]['title']) if active_offers else "Aapka Google profile audit karte hain aur top 3 improvements identify karte hain.")
            action_body = "Perfect! Main abhi start kar rahi hoon. {} 2-3 minutes mein update share karti hoon. ✅".format(_hi_msg)
        else:
            _en_msg = ("First I will pin your active offer '{}' on your GBP profile.".format(active_offers[0]['title']) if active_offers else "I will run a quick profile audit and identify the top 3 improvements.")
            action_body = "Great! Starting now. {} Will update you in 2-3 minutes. ✅".format(_en_msg)
        conv["turns"].append({"from": "vera", "msg": action_body})
        conv["unanswered"] = 0
        return {
            "action": "send",
            "body": action_body,
            "cta": "none",
            "rationale": "Merchant committed — switched to action mode immediately"
        }

    # 4. Reset unanswered counter on real engagement
    conv["unanswered"] = 0

    # 5. General LLM-powered reply
    merchant = _get("merchant", merchant_id) or {}
    cat_slug = merchant.get("category_slug", "")
    category = _get("category", cat_slug) or {}
    customer_id = conv.get("customer_id")
    customer = _get("customer", customer_id) if customer_id else None

    result = compose_reply(conv, message, merchant, category, customer)

    if result.get("action") == "send":
        reply_body = result.get("body", "")
        if reply_body:
            conv["turns"].append({"from": "vera", "msg": reply_body})
        # Check if it's ending
        if "end" in result.get("rationale", "").lower() or result.get("action") == "end":
            conv["ended"] = True
    elif result.get("action") == "end":
        conv["ended"] = True
    elif result.get("action") == "wait":
        pass

    return result
