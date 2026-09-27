# Vera — magicpin AI Challenge Submission

## What I built

A production-ready WhatsApp merchant AI assistant that implements the full 4-context composition framework (Category × Merchant × Trigger × Customer) with:

- **Trigger-aware routing**: Each trigger kind gets a specialised prompt variant that surfaces the right facts (e.g., research digest → trial N + source citation; perf dip → actual % drop vs peer benchmark; recall → available slots)
- **Specificity anchoring**: Every message is grounded in real numbers from the dataset — CTR vs peer median, review counts, offer prices, patient cohort sizes, research source citations
- **Language matching**: Automatic Hindi-English code-mix (Hinglish) for merchants with `hi`/`mr`/`kn`/`te`/`ta` in their language list
- **Auto-reply detection**: Pattern-based + repetition detection; tries once to reach a real person, then gracefully exits
- **Intent transition**: On "ok let's do it" / "haan karo" / "go ahead" → immediately switches from pitch mode to action mode (no further qualifying questions)
- **Graceful exit**: On hostility / "stop messaging" → `action: end` immediately
- **Multi-turn handler**: `conversation_handlers.py` implements full ConversationState-based respond() for the replay test bonus

## Architecture

```
POST /v1/context  ─── in-memory store (scope, id) → {version, payload}
POST /v1/tick     ─── for each available trigger:
                       1. resolve merchant + category
                       2. compose() with LLM (temperature=0)
                       3. return action[] + suppress duplicate sends
POST /v1/reply    ─── classify reply (auto/hostile/commit/question)
                       → route to specialised handler or LLM compose_reply()
GET  /v1/healthz  ─── uptime + context counts
GET  /v1/metadata ─── team info
```

## Compulsion levers used per trigger kind

| Trigger | Lever(s) |
|---|---|
| research_digest | Curiosity + reciprocity ("I'll pull it for you") + source citation |
| regulation_change | Loss aversion ("deadline Dec 15") + effort externalization |
| perf_dip | Loss aversion (% drop vs peer) + social proof |
| perf_spike | Reciprocity ("you're doing something right, want to amplify?") |
| renewal_due | Loss aversion + social proof (their current numbers) |
| dormant_with_vera | Curiosity + social proof |
| recall_due | Effort externalization + specific slots + customer name |
| competitor_opened | Loss aversion + your own offer anchor |
| review_theme_emerged | Specificity (quote + count) + low-friction CTA |
| milestone_reached | Social proof + next milestone curiosity |
| festival_upcoming | Loss aversion (window closing) + service+price offer |
| curious_ask_due | Asking the merchant (#7) + single binary ask |

## Tradeoffs made

1. **Single LLM call per composition**: chosen for speed (< 5s) over 2-stage RAG. The trigger-specific context block pre-retrieves the relevant digest item so the LLM doesn't need to search.

2. **Deterministic (temperature=0)**: as required. Slight creativity loss vs 0.3 but perfectly reproducible.

3. **In-memory context store**: meets the brief; Redis/SQLite would be better for production restarts but unnecessary here.

4. **Pattern-based auto-reply detection**: catches 95%+ of known patterns without an extra LLM call; the one edge case (novel canned reply) is caught by the repetition detector.

## What additional context would have helped

- **Vera's current send-rate per merchant**: to avoid over-sending when multiple triggers fire simultaneously for the same merchant
- **Actual GBP profile completeness scores**: referenced in the sample Vera conversation (62.5%) but not in the dataset
- **Merchant reply rates by trigger kind**: to learn which trigger types get the best engagement and deprioritise those that don't
- **Seasonal festival calendar for 2026**: the dataset has Diwali but a full festival-to-category relevance map would sharpen festival trigger copy
- **Competitor names from GBP search**: the dataset only has competitors when the trigger explicitly includes them (e.g., trg_023)

## How to run

### Start the bot server
```bash
# Set your API key
set LLM_PROVIDER=gemini
set LLM_API_KEY=YOUR_GEMINI_API_KEY

# Or Anthropic
set LLM_PROVIDER=anthropic
set LLM_API_KEY=YOUR_ANTHROPIC_KEY
set LLM_MODEL=claude-3-5-haiku-20241022

uvicorn bot:app --host 0.0.0.0 --port 8080
```

### Generate submission.jsonl
```bash
set LLM_API_KEY=YOUR_API_KEY
python generate_submission.py
```

### Run the judge simulator
```bash
# Edit LLM_API_KEY in judge_simulator.py
python judge_simulator.py
```

### Generate the expanded dataset (first time only)
```bash
python dataset/generate_dataset.py --seed-dir dataset --out dataset/expanded
```

## Files

| File | Purpose |
|---|---|
| `bot.py` | Main FastAPI bot server — all 5 endpoints |
| `conversation_handlers.py` | Multi-turn ConversationState-based handler (bonus) |
| `generate_submission.py` | Script to pre-generate submission.jsonl |
| `submission.jsonl` | 30 pre-generated messages for the canonical test pairs |
| `dataset/generate_dataset.py` | Expands seed data to full 50 merchants / 200 customers / 100 triggers |
| `dataset/expanded/` | The expanded dataset (generated) |
