#!/usr/bin/env python3
"""
generate_submission.py — Pre-generate submission.jsonl for the 30 canonical test pairs.

Usage:
    # Set your LLM API key and provider first:
    set LLM_PROVIDER=gemini
    set LLM_API_KEY=YOUR_KEY_HERE
    python generate_submission.py

    # Or with a specific model:
    set LLM_MODEL=gemini-2.0-flash
    python generate_submission.py

Output: submission.jsonl (30 lines, one per test pair)
"""

import json
import os
import sys
import time
from pathlib import Path

# ── Load expanded dataset ─────────────────────────────────────────────────────
EXPANDED = Path(__file__).parent.parent / "dataset" / "expanded"
SEED_DIR = Path(__file__).parent.parent / "dataset"

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_dataset():
    categories = {}
    for f in (EXPANDED / "categories").glob("*.json"):
        cat = load_json(f)
        categories[cat["slug"]] = cat

    # Fallback to seed categories
    for f in (SEED_DIR / "categories").glob("*.json"):
        cat = load_json(f)
        if cat["slug"] not in categories:
            categories[cat["slug"]] = cat

    merchants = {}
    if (EXPANDED / "merchants").exists():
        for f in (EXPANDED / "merchants").glob("*.json"):
            m = load_json(f)
            merchants[m["merchant_id"]] = m
    else:
        seed = load_json(SEED_DIR / "merchants_seed.json")
        for m in seed["merchants"]:
            merchants[m["merchant_id"]] = m

    customers = {}
    if (EXPANDED / "customers").exists():
        for f in (EXPANDED / "customers").glob("*.json"):
            c = load_json(f)
            customers[c["customer_id"]] = c
    else:
        seed = load_json(SEED_DIR / "customers_seed.json")
        for c in seed["customers"]:
            customers[c["customer_id"]] = c

    triggers = {}
    if (EXPANDED / "triggers").exists():
        for f in (EXPANDED / "triggers").glob("*.json"):
            t = load_json(f)
            triggers[t["id"]] = t
    else:
        seed = load_json(SEED_DIR / "triggers_seed.json")
        for t in seed["triggers"]:
            triggers[t["id"]] = t

    return categories, merchants, customers, triggers


def main():
    print("Loading dataset...")
    categories, merchants, customers, triggers = load_dataset()
    print(f"  {len(categories)} categories, {len(merchants)} merchants, "
          f"{len(customers)} customers, {len(triggers)} triggers")

    # Load test pairs
    test_pairs_path = EXPANDED / "test_pairs.json"
    if not test_pairs_path.exists():
        print("ERROR: Run dataset/generate_dataset.py first")
        sys.exit(1)

    pairs = load_json(test_pairs_path)["pairs"]
    print(f"  {len(pairs)} test pairs to process")

    # Import compose from bot.py
    # Inject contexts into bot's in-memory store
    print("Setting up bot context store...")
    import bot as vera_bot

    # Push all contexts
    for slug, cat in categories.items():
        vera_bot.contexts[("category", slug)] = {"version": 1, "payload": cat}
    for mid, m in merchants.items():
        vera_bot.contexts[("merchant", mid)] = {"version": 1, "payload": m}
    for cid, c in customers.items():
        vera_bot.contexts[("customer", cid)] = {"version": 1, "payload": c}
    for tid, t in triggers.items():
        vera_bot.contexts[("trigger", tid)] = {"version": 1, "payload": t}

    print(f"  Loaded {vera_bot._count_by_scope('category')} categories, "
          f"{vera_bot._count_by_scope('merchant')} merchants into bot store")

    results = []
    errors = []

    for i, pair in enumerate(pairs):
        test_id    = pair["test_id"]
        trigger_id = pair["trigger_id"]
        merchant_id = pair["merchant_id"]
        customer_id = pair.get("customer_id")

        print(f"\n[{i+1:02d}/30] {test_id}: {trigger_id[:50]}...", end="", flush=True)

        trigger  = triggers.get(trigger_id)
        merchant = merchants.get(merchant_id)
        customer = customers.get(customer_id) if customer_id else None

        if not trigger or not merchant:
            print(f" SKIP (missing data: trigger={bool(trigger)}, merchant={bool(merchant)})")
            errors.append(test_id)
            continue

        cat_slug = merchant.get("category_slug", "")
        category = categories.get(cat_slug)

        if not category:
            print(f" SKIP (missing category: {cat_slug})")
            errors.append(test_id)
            continue

        try:
            result = vera_bot.compose(category, merchant, trigger, customer)
            row = {
                "test_id": test_id,
                "trigger_id": trigger_id,
                "merchant_id": merchant_id,
                "customer_id": customer_id,
                "body": result.get("body", ""),
                "cta": result.get("cta", "open_ended"),
                "send_as": result.get("send_as", "vera"),
                "suppression_key": result.get("suppression_key", trigger.get("suppression_key", "")),
                "rationale": result.get("rationale", "")
            }
            results.append(row)
            body_preview = result.get("body", "")[:60]
            print(f" [OK] [{result.get('cta','?')}] \"{body_preview}...\"")

            # Small delay to respect rate limits
            time.sleep(0.5)

        except Exception as e:
            print(f" ERROR: {e}")
            errors.append(test_id)
            # Add fallback
            results.append({
                "test_id": test_id,
                "trigger_id": trigger_id,
                "merchant_id": merchant_id,
                "customer_id": customer_id,
                "body": f"Hi, noticed something important for your business — reply YES to know more.",
                "cta": "binary_yes_stop",
                "send_as": "vera",
                "suppression_key": trigger.get("suppression_key", ""),
                "rationale": f"Fallback due to error: {str(e)[:100]}"
            })

    # Write submission.jsonl
    out_path = Path(__file__).parent.parent / "submission.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\n{'='*60}")
    print(f"[OK] Written {len(results)} rows to submission.jsonl")
    if errors:
        print(f"WARNING {len(errors)} errors/skips: {errors}")
    print(f"{'='*60}")

    # Print sample
    print("\nSAMPLE (first 3 messages):\n")
    for row in results[:3]:
        print(f"  [{row['test_id']}] {row['trigger_id'][:40]}")
        print(f"    send_as: {row['send_as']} | cta: {row['cta']}")
        print(f"    body: {row['body'][:120]}...")
        print(f"    rationale: {row['rationale'][:100]}")
        print()


if __name__ == "__main__":
    main()
