# 🦢 Orange Swan — Mood Indicator

A real-time AI system that tracks his emotional state throughout the day by analyzing his Truth Social posts. Updated every 2 hour.

**Live at:** [orange-swan-index.lovable.app](https://orange-swan-index.lovable.app)

---

## What It Does

Every 30 minutes the system:

1. Scrapes his latest Truth Social posts via a headless browser
2. Runs local HuggingFace models to extract signals — sentiment, emotions, named entities, zero-shot mood classification
3. Summarizes the batch using an LLM (Claude Haiku / GPT-4o-mini)
4. Fetches current world news to understand what he's reacting to
5. Synthesizes everything into a single mood assessment using a more powerful LLM (Claude Sonnet / GPT-4o)
6. Stores the result and exposes it via a REST API

---

## Mood Labels

| Label | Description |
|---|---|
| `COMBATIVE` | Attacking opponents by name |
| `TRIUMPHANT` | Celebrating wins, boasting |
| `GRIEVANCE` | Victimhood, witch hunt framing |
| `RALLYING` | Energizing supporters |
| `AGITATED` | Rapid-fire, erratic posting |
| `DEFIANT` | Issuing threats and challenges |
| `TRANSACTIONAL` | Policy announcements, deals |
| `CELEBRATORY` | Praising allies, congratulating |

Each mood comes with an intensity level (`low / medium / high / frenetic`), a confidence score, and an analyst note explaining what's driving the mood.

---

## Architecture

```
Truth Social
     ↓
Playwright (headless browser + residential proxies)
     ↓
Local HuggingFace Models (free, no API cost)
  ├── cardiffnlp/twitter-roberta-base-sentiment  (sentiment)
  ├── j-hartmann/emotion-english-distilroberta   (emotions)
  ├── dslim/bert-base-NER                        (named entities)
  └── facebook/bart-large-mnli                   (zero-shot mood)
     ↓
LLM Batch Summarizer (Claude Haiku / GPT-4o-mini)
     ↓
World Context (Claude with web search, cached 2hrs)
     ↓
LLM Mood Synthesizer (Claude Sonnet / GPT-4o — Opus on high signal cycles)
     ↓
PostgreSQL + pgvector (RAG for historical pattern matching)
     ↓
FastAPI  →  Frontend
```

### Cost Optimization

- Local models handle all signal extraction for free
- LLM calls only on compressed summaries, not raw posts
- World context cached every 2 hours (not every cycle)
- Haiku / GPT-4o-mini for routine cycles
- Sonnet / GPT-4o only when mood shift or high intensity detected
- Target cost: ~$1/day

---

## Signal Extraction

Beyond basic sentiment, the system tracks:

- **Caps ratio** — percentage of words in ALL CAPS
- **Exclamation density** — count and clustering
- **Nickname attacks** — `sleepy`, `crooked`, `fake news`, `witch hunt`, `deep state` etc.
- **Grievance language** — `rigged`, `weaponized`, `lawfare`, `two-tiered` etc.
- **Aggression language** — `destroy`, `prosecute`, `lock up`, `traitor` etc.
- **Rally language** — `MAGA`, `fight back`, `save america`, `patriots` etc.
- **Post type** — ORIGINAL (highest signal) vs LINK_SHARE vs RETRUTH (noise)
- **Posting velocity** — posts per hour, burst detection
- **Engagement** — likes and reposts as signal amplifiers

---

## Tech Stack

- **Python 3.12** with `uv` for dependency management
- **FastAPI** — REST API
- **Playwright** — headless browser scraping
- **PostgreSQL + pgvector** — storage and vector similarity search
- **LangChain** — LLM orchestration with automatic Claude → OpenAI fallback
- **HuggingFace Transformers** — local model inference
- **PM2** — process management on DigitalOcean
- **Nginx** — reverse proxy with SSL

---

## API

```
GET /mood/today
```
Returns the current mood state.

```json
{
  "date": "2026-03-03",
  "mood": "COMBATIVE",
  "intensity": "high",
  "confidence": 0.87,
  "last_updated": "2026-03-03T14:32:00Z"
}
```

```
GET /mood/today/timeline
```
Returns the full mood timeline for today — every shift detected throughout the day.

```json
{
  "date": "2026-03-03",
  "last_updated": "2026-03-03T14:32:00Z",
  "timeline": [
    {
      "time": "2026-03-03T08:12:00Z",
      "mood": "TRIUMPHANT",
      "intensity": "medium",
      "shift_detected": false
    },
    {
      "time": "2026-03-03T11:45:00Z",
      "mood": "COMBATIVE",
      "intensity": "high",
      "shift_detected": true
    }
  ]
}
```

---

## Setup

### Prerequisites

- Python 3.12+
- PostgreSQL with pgvector extension
- Residential US proxies (Truth Social blocks non-US IPs)
- Anthropic API key
- OpenAI API key (optional — used as fallback)

### Install

```bash
git clone https://github.com/your-username/orange-swan-mood-indicator
cd orange-swan-mood-indicator
uv sync
uv run playwright install chromium
uv run playwright install-deps chromium
```

### Configure

```bash
cp .env.example .env
nano .env
```

```env
DATABASE_URL=postgresql://user:password@localhost:5432/mood_analyzer
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...          # optional fallback
PROXIES=us.host.com:10001:username:password,us.host.com:10002:username:password
FETCH_INTERVAL_SECONDS=1800
LOG_LEVEL=INFO
```

### Run locally

```bash
# Start API + worker together
make dev

# Or separately
make api       # API only on port 8000
make worker    # Run one fetch cycle and exit
```

### Deploy

```bash
# On your server
pm2 start ecosystem.config.js   # starts API
pm2 save
pm2 startup

# Add worker cron — runs every 30 minutes
crontab -e
# Add: */30 * * * * cd /path/to/project && /root/.local/bin/uv run python -m app.worker >> /var/log/mood_worker.log 2>&1
```

---

## Project Structure

```
app/
├── api/
│   ├── app.py              # FastAPI app + CORS
│   └── routes.py           # /mood/today and /mood/today/timeline
├── analysis/
│   └── prompts/
│       ├── system_prompts.py
│       └── user_prompts.py
├── config/
│   ├── db.py               # PostgreSQL connection + migrations
│   └── settings.py         # Pydantic settings
├── ingestion/
│   ├── fetcher.py          # Playwright scraper
│   ├── parser.py           # Post parser
│   └── proxy_manager.py    # Proxy rotation
├── rag/
│   └── mood_retriever.py   # pgvector similarity search
├── repositories/
│   ├── mood_state_repo.py
│   └── posts_repo.py
├── services/
│   ├── batch_summarizer.py
│   ├── fetch_cycle.py      # Main orchestration
│   ├── llm_client.py       # Claude + OpenAI with fallback
│   ├── local_analyzer.py   # HuggingFace models
│   └── mood_synthesizer.py
├── utils/
│   ├── constants.py        # Patterns, mood labels, user agents
│   └── logger.py
├── main.py                 # API entry point
└── worker.py               # Single cycle entry point
```

---

## How The Self-Learning Works

Every mood snapshot is stored in pgvector with embeddings. After 2 hours the system enriches each snapshot with outcome data — what actually happened in the 2 hours after that mood was detected (post count, aggression escalation, velocity change).

Over time the RAG retrieval returns context like:

> *"Last 3 times he was AGITATED about courts during market hours, he posted 12+ times in the next 2 hours and shifted to DEFIANT."*

This makes the synthesis progressively smarter without any ML infrastructure or fine-tuning.

---

## Disclaimer

This is an independent research and analysis tool. It is not affiliated with, endorsed by, or connected to Truth Social. All data is publicly available. The mood assessments are AI-generated interpretations and should not be treated as definitive statements about any individual's mental state.