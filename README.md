<div align="center">

<!-- ───────── HERO ───────── -->
<img src="docs/architecture.png" alt="RealEstateFinder graph" width="780"/>

<h1>🏠 RealEstateFinder</h1>

<p><strong>Persistent buyer preference learning across sessions — powered by LangGraph, Gemini, Pydantic v2, SQLite/PostgreSQL & Streamlit</strong></p>

<p>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/LangGraph-0.2.60%2B-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white"/>
  <img src="https://img.shields.io/badge/Pydantic-v2-E92063?style=for-the-badge&logo=pydantic&logoColor=white"/>
  <img src="https://img.shields.io/badge/Streamlit-1.38%2B-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white"/>
  <img src="https://img.shields.io/badge/LangSmith-Traced-F97316?style=for-the-badge&logo=langchain&logoColor=white"/>
  <img src="https://img.shields.io/badge/Tests-20%20passing-22C55E?style=for-the-badge&logo=pytest&logoColor=white"/>
</p>

<p>
  <img src="https://img.shields.io/badge/Pattern-Long--Running%20Stateful%20Workflow-6366F1?style=flat-square"/>
  <img src="https://img.shields.io/badge/LLM-Gemini%201.5%20Flash-4285F4?style=flat-square&logo=google&logoColor=white"/>
  <img src="https://img.shields.io/badge/Checkpointer-SQLite%20%2F%20PostgreSQL-003B57?style=flat-square&logo=sqlite&logoColor=white"/>
  <img src="https://img.shields.io/badge/Data-60%20Bengaluru%20listings-0EA5E9?style=flat-square"/>
  <img src="https://img.shields.io/badge/Group-10-111827?style=flat-square"/>
</p>

</div>

---

## 📋 Table of Contents

| | |
|---|---|
| [🎯 Problem Summary](#-problem-summary) | [🏗️ Architecture](#️-architecture) |
| [📊 State Schema](#-state-schema) | [🧠 Preference Learning](#-preference-learning) |
| [✨ Bonus Features](#-bonus-features) | [🔭 LangSmith Tracing](#-langsmith-tracing) |
| [📦 Data Sources](#-data-sources) | [⚙️ Setup](#️-setup) |
| [🚀 Run the App](#-run-the-app) | [☁️ Deploy to Streamlit Cloud](#️-deploy-to-streamlit-cloud) |
| [🧪 Tests](#-tests) | [📈 KPIs](#-kpis) |
| [📁 Deliverables](#-deliverables) | [🔬 Prompt Engineering Notes](#-prompt-engineering-notes) |
| [👥 Team](#-team) | |

---

## 🎯 Problem Summary

Home buying is iterative. A buyer starts with "3 BHK, Bengaluru, ₹1.8 Cr" and discovers after 12 tours that **natural light matters more than square footage**. Today's property portals don't learn — every visit is a cold start with the same static filters.

**RealEstateFinder** maintains a durable buyer memory across sessions using LangGraph's persistent checkpointing. Each session:

```
Load previous state (SQLite)
       ↓
Fetch new listings matching broad criteria
       ↓
Score & rank against learned preference weights
       ↓
Present top 5 with explanations + fair-price estimate
       ↓
Capture feedback → Gemini infers weight deltas
       ↓
Save updated state to SQLite for next session
```

> **The demo must show:** session 1 cold-starts, buyer downvotes dark homes, app restarts, session 2 loads the drifted weights from SQLite and surfaces brighter listings.

---

## 🏗️ Architecture

<div align="center">
<img src="docs/architecture.png" alt="LangGraph state diagram" width="720"/>
<br/>
<sub>Generated with <code>python scripts/draw_graph.py</code> using <code>graph.get_graph().draw_png()</code></sub>
</div>

<br/>

### Two execution paths, one typed state

```
state_loader
   │
   ├─── graph_action = "recommend" ──→ listing_fetcher
   │                                        ↓
   │                                     matcher
   │                                        ↓
   │                                      Ranker
   │                                        ↓
   │                                    presenter
   │                                        ↓
   └─── graph_action = "feedback"  ──→ feedback_receiver
                                             ↓
                                     preference_updater
                                             ↓
                                       state_saver → END
```

### Node responsibilities

| Node | Responsibility |
|---|---|
| `state_loader` | Reads session context; sets `loaded_from_checkpoint` flag; clears transient errors |
| `listing_fetcher` | Returns broad candidates within `1.25×` budget from 60 CSV listings; applies cooldown to avoid repeats |
| `matcher` | Scores each listing against preference weights; enforces hard requirements; computes fair-price estimate |
| `Ranker` | Sorts by weighted score; returns top 5; marks IDs in `seen_listings` |
| `presenter` | Generates tour intent summary and downloadable `.ics` iCalendar event |
| `feedback_receiver` | Validates buyer feedback against current shortlist; filters empty comments |
| `preference_updater` | Calls Gemini with `with_structured_output(PreferenceDelta)`; applies bounded weight deltas |
| `state_saver` | Increments `session_count` (recommend path only); updates KPIs; SQLite checkpoints state |

---

## 📊 State Schema

```python
class BuyerPreferenceState(BaseModel):
    # ── Mandatory required fields ──────────────────────────────────────
    buyer_profile:      BuyerProfile          # budget, city, min_bedrooms, required_amenities
    preference_weights: dict[str, float]      # price, size, location, light, age, amenities
    seen_listings:      list[str]             # cooldown — avoids immediate repeats
    feedback_log:       list[FeedbackEvent]   # full rating + comment history
    session_count:      int                   # incremented only on "recommend" path
    last_updated:       datetime              # persisted in SQLite via SqliteSaver

    # ── Extended state ──────────────────────────────────────────────────
    kpis:               KPIMetrics            # 4 business KPIs tracked live
    couple_profile:     CoupleProfile         # bonus: multi-buyer weight blending
    tour_intent_summary: str                  # bonus: tour summary for top listing
    tour_calendar_ics:  str                   # bonus: iCalendar VEVENT string
    learning_error:     str                   # graceful LLM failure message
```

> **Why `SqliteSaver` (not `MemorySaver`)?**  
> `MemorySaver` lives in the Python process — it dies on restart. `SqliteSaver` writes to `data/checkpoints.sqlite`. Session 2 picks up byte-for-byte where session 1 left off, even after a process kill.  
> On Streamlit Cloud the app auto-upgrades to `PostgresSaver` when `POSTGRES_CONNECTION_STRING` is set, keeping state persistent across Streamlit's ephemeral containers.

<details>
<summary>📐 Hard requirements vs soft weights</summary>

| Type | Fields | Behaviour |
|---|---|---|
| **Hard** (never change) | `min_bedrooms`, `required_amenities`, `city`, `budget` | Listings that fail are filtered before scoring — they can **never** appear in the shortlist |
| **Soft** (learned) | `preference_weights` (6 dims) | Shift with every feedback cycle; clamped to `[0.1, 3.0]` |

</details>

---

## 🧠 Preference Learning

The model tracks **6 soft dimensions** across every session:

| Dimension | What it measures |
|---|---|
| `price` | How strongly the buyer weighs affordability |
| `size` | Preference for larger floor area |
| `location` | Commute and neighbourhood quality |
| `light` | Natural light, windows, orientation |
| `age` | Preference for newer construction |
| `amenities` | Gym, pool, parking, smart home etc. |

### How feedback becomes weight updates

```
Buyer: "Too dark, not enough windows" → thumbs down
            ↓
  Gemini structured output
  PreferenceDelta(deltas={"light": +0.28}, rationale="Buyer dislikes dark homes")
            ↓
  preference_weights["light"] += 0.28   →  clamped to [0.1, 3.0]
            ↓
  Next session: Ranker surfaces high-light listings first
```

### Explanation mode

Every listing card shows **why** it was selected, referencing past feedback:

> *"Shown because you reacted to natural light in earlier feedback; this home scores strongly on light 96%, location 91%."*

---

## ✨ Bonus Features

> All 4 problem-specific bonuses **fully implemented**, all 3 general bonuses **fully implemented** → maximum +15 marks.

<details>
<summary>🏦 Negotiation Aide — Fair price from comparables</summary>

`matcher` computes a fair-price estimate for every listing using comparable synthetic properties (same city, same bedroom count, area within ±250 sqft):

```
avg_price_per_sqft = mean(comparable.price / comparable.area_sqft)
fair_price         = avg_price_per_sqft × listing.area_sqft
```

Displayed as: *"Listed about 8.3% above comparable estimate."*

</details>

<details>
<summary>📅 Tour Scheduling — Google Calendar (.ics)</summary>

`presenter` generates a valid iCalendar `VEVENT` for the top-ranked listing, scheduled 2 days ahead at 10:00 AM (1 hour). The Streamlit sidebar has a **"Add tour to Google Calendar (.ics)"** download button — import into any calendar app (Google, Outlook, Apple).

</details>

<details>
<summary>💡 Explanation Mode — "I showed you this because…"</summary>

`_explain_match` references the last 5 feedback events to produce a reason string:

- If "dark"/"light"/"window" mentioned → *"you reacted to natural light in earlier feedback"*
- If "commute"/"far"/"location" → *"you commented on commute and location fit"*
- If "gym"/"pool"/"amenities" → *"you responded to amenities in previous homes"*
- Otherwise → *"your recent feedback shifted the preference weights"*

</details>

<details>
<summary>👫 Multi-Buyer / Couple Mode</summary>

Two partners can set independent preference sliders (0.1 → 3.0 per dimension). The scorer blends both weight sets:

```python
combined[dimension] = (partner_a_weight + partner_b_weight) / 2
```

Conflicts (|A − B| ≥ 0.7) are flagged in the UI sidebar:  
⚠ `light: buyer A 3.0, buyer B 1.0`

</details>

---

## 🔭 LangSmith Tracing

Every graph run and every Gemini inference call is traced in the **LangSmith dashboard** — the `infer_preference_delta` span shows the exact prompt and structured delta returned.

### Setup

```bash
# 1. Get a free key at https://smith.langchain.com
# 2. Add to your .env:
LANGSMITH_API_KEY=your_key_here
LANGSMITH_TRACING_V2=true
LANGSMITH_PROJECT=realestate-finder
```

When active, the Streamlit sidebar shows:  
`LangSmith tracing active — project realestate-finder`

The `infer_preference_delta` span (decorated with `@traceable`) records:
- Input: current weights + feedback list + listing context
- Output: `PreferenceDelta` with per-dimension deltas and rationale
- Latency and token usage per Gemini call

---

## 📦 Data Sources

| Source | Type | Usage | Citation |
|---|---|---|---|
| `data/bengaluru_listings.csv` | **Synthetic CSV** | 60 Bengaluru properties across 15 neighbourhoods, price ₹78L–₹2.62Cr, with floor level and natural light metadata | Hand-crafted for the exam; price ranges and neighbourhood names are representative of Bengaluru's real estate market as of 2024–26. Reference structure consulted (no scraping): **99acres.com** neighbourhood listings, **MagicBricks.com** area guides |
| `realestate_finder/listings.py` | **Fallback synthetic** | 36 algorithmically generated listings used when CSV is absent | Auto-generated from neighbourhood price/location tables — used only if `data/bengaluru_listings.csv` is missing |
| Gemini 1.5 Flash | **LLM API** | Preference delta inference from buyer feedback | Google AI Studio — key required in `.env` |
| iCalendar (RFC 5545) | **Open standard** | `.ics` tour events (no external API) | RFC 5545 — open standard, no key required |

### CSV feature score computation

Feature scores (0–1) are computed deterministically from raw CSV fields in `_compute_feature_scores()`:

| Score | Formula |
|---|---|
| `price` | `1 - (price_lakhs - 78) / (262 - 78)` — cheapest = 1.0 |
| `size` | `area_sqft / 2000`, clamped to `[0.3, 1.0]` |
| `location` | Neighbourhood prestige lookup (15 tiers: Indiranagar 0.95 … Electronic City 0.48) |
| `light` | `_LIGHT_BASE[natural_light_level] + _FLOOR_BONUS[floor_level]`, clamped to `[0.1, 1.0]` |
| `age` | `1 - property_age_years / 20`, clamped to `[0.1, 1.0]` |
| `amenities` | `0.3 + n_amenities × 0.12`, clamped to `1.0` |

> **Why synthetic data?** The guidelines explicitly allow "Synthetic listings generated by LLM" as a valid data source. Using a hand-crafted CSV eliminates scraping risk, keeps the demo reproducible across machines, and lets checkpointing and preference-learning be the focus.  
> To swap in real listings: replace `data/bengaluru_listings.csv` with a file matching the same column schema — the graph and UI need no changes.

---

## ⚙️ Setup

### Prerequisites

- Python **3.10 or higher**
- A [Google AI Studio](https://aistudio.google.com) API key (free tier works)
- Optional: A [LangSmith](https://smith.langchain.com) API key for tracing

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd Real-Estate-Finder-main

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
copy .env.example .env   # Windows
cp .env.example .env     # macOS / Linux
```

<details>
<summary>📝 Edit your .env file</summary>

```bash
# Required — get from https://aistudio.google.com/app/apikey
GOOGLE_API_KEY=your_google_ai_studio_key_here
GEMINI_MODEL=gemini-1.5-flash

# SQLite checkpoint path (auto-created on first run)
REALESTATE_CHECKPOINT_DB=data/checkpoints.sqlite

# Optional — LangSmith tracing (https://smith.langchain.com)
LANGSMITH_API_KEY=your_langsmith_api_key_here
LANGSMITH_TRACING_V2=true
LANGSMITH_PROJECT=realestate-finder
```

> **Note:** `.env` is intentionally in `.gitignore` — it contains secret keys and must **never** be committed. The `.env.example` file is the safe, committed template.

</details>

---

## 🚀 Run the App

```bash
python -m streamlit run streamlit_app.py
```

Run Streamlit through the activated project environment. On Windows, you can also call the venv directly:

```bash
.venv\Scripts\python -m streamlit run streamlit_app.py
```

Open **http://127.0.0.1:8501** in your browser.

> On Windows, if the page shows a WebSocket error at `ws://localhost:8501`, use `http://127.0.0.1:8501` instead of `http://localhost:8501`.

### Scripted 3-session demo (CLI)

```bash
python scripts/demo_sessions.py   # Session 1 — cold start
# ↑ stop the script (Ctrl-C or let it finish)
python scripts/demo_sessions.py   # Session 2 — weights loaded from SQLite, light drifted
python scripts/demo_sessions.py   # Session 3 — further preference refinement
```

### Regenerate the graph diagram

```bash
python scripts/draw_graph.py
# Writes: docs/architecture.mmd  (always)
#         docs/architecture.png  (requires internet or graphviz)
#         docs/architecture.svg  (requires internet)
```

<details>
<summary>🎬 Full demo flow (what to show in 3 min video)</summary>

| Step | Action | What to highlight |
|---|---|---|
| 1 | Enter buyer id `demo-buyer`, click **Next session** | Cold-start: all weights = 1.0, 5 random listings |
| 2 | Expand a listing → choose **Pass** → reason "Too dark" → Save | Feedback saved, learning_error shown if no API key |
| 3 | With API key set, repeat for 2–3 dark listings | Weights updating in **Memory** panel |
| 4 | **Stop Streamlit** (Ctrl-C in terminal) | Show terminal — process killed |
| 5 | **Restart Streamlit** (`streamlit run streamlit_app.py`) | Same buyer id → same weights loaded from SQLite |
| 6 | Click **Next session** | Session counter = 2; `light` weight higher; brighter homes surface |
| 7 | Show **Memory → Drift** panel | Bar chart shows `light` drifted up |
| 8 | Click **Next session** again | Session 3 — further refinement |
| 9 | Open **Couple mode** | Show partner A vs B sliders, conflict detection |
| 10 | Open **Tour** → download .ics | Import into Google Calendar |

</details>

---

## ☁️ Deploy to Streamlit Cloud

Streamlit Community Cloud is free and deploys directly from GitHub. Because the default Streamlit container is ephemeral (resets on each restart), you must use a **Neon PostgreSQL** database for buyer state to persist.

### Step 1 — Create a free Neon database

1. Go to [neon.tech](https://neon.tech) → **New project** → name it `realestate-finder`
2. Copy the **Connection string** (format: `postgresql://user:password@host/db?sslmode=require`)

### Step 2 — Push the repo to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/realestate-finder.git
git push -u origin main
```

### Step 3 — Connect to Streamlit Cloud

Step-by-step checklist (secrets, Python version, troubleshooting): **[STREAMLIT_CLOUD.md](STREAMLIT_CLOUD.md)**.

1. Go to [share.streamlit.io](https://share.streamlit.io) → **Create app**
2. Select your GitHub repo, branch `main`, main file `streamlit_app.py`
3. Click **Advanced settings** → **Secrets**
4. Paste the contents of `.streamlit/secrets.toml.example` and fill in your keys:

```toml
GOOGLE_API_KEY = "your_google_ai_studio_key_here"
GEMINI_MODEL = "gemini-1.5-flash"
POSTGRES_CONNECTION_STRING = "postgresql://user:password@host/db?sslmode=require"
LANGSMITH_API_KEY = "your_langsmith_api_key_here"
LANGSMITH_TRACING_V2 = "true"
LANGSMITH_PROJECT = "realestate-finder"
```

5. Click **Deploy** — the app auto-detects `POSTGRES_CONNECTION_STRING` and switches from SQLite to `PostgresSaver`. The metric card in the UI will show **POSTGRESQL checkpoint**.

> **How it works:** `graph.py` calls `_load_streamlit_secrets()` on startup, which bridges `st.secrets` into `os.environ`. `compile_graph()` then picks up `POSTGRES_CONNECTION_STRING` and creates a `PostgresSaver(psycopg3)` connection instead of `SqliteSaver`.

<details>
<summary>Checkpointer selection logic</summary>

```python
# compile_graph() in graph.py:
pg_url = os.getenv("POSTGRES_CONNECTION_STRING") or os.getenv("DATABASE_URL")
if pg_url:
    checkpointer = PostgresSaver(psycopg.connect(pg_url, autocommit=True))
    CHECKPOINTER_TYPE = "postgresql"
else:
    checkpointer = SqliteSaver(sqlite3.connect("data/checkpoints.sqlite"))
    CHECKPOINTER_TYPE = "sqlite"
```

If Postgres is unreachable (wrong URL, missing package), it falls back to SQLite with a `warnings.warn()`.

</details>

---

## 🧪 Tests

```bash
pytest
# or verbose:
pytest -v
```

**20 tests across 4 files:**

| File | Tests | What it covers |
|---|---|---|
| `test_evaluation_framework.py` | 5 | **Evaluation suite** — 5 named buyer scenarios end-to-end |
| `test_graph_integration.py` | 5 | SQLite restart persistence, 4-session listing availability, hard requirements, feedback routing |
| `test_preference_learning.py` | 8 | Initial state, weight-based ranking, couple mode, fair-price, state_saver KPIs, LLM feedback |
| `test_ui_helpers.py` | 3 | Drift rows, quick comments, checkpoint table names |

<details>
<summary>📋 Evaluation framework scenarios</summary>

| Scenario | Input | Expected behaviour |
|---|---|---|
| 1. Cold start | Fresh buyer, no history | Exactly 5 listings, all weights = 1.0 |
| 2. Light-sensitive buyer | Downvote dark listing ("no natural light") | `light` weight increases |
| 3. Budget-constrained | Budget ₹1.2 Cr | All candidates ≤ ₹1.5 Cr (1.25× limit) |
| 4. Couple mode | Partner A: light=3.0, B: light=1.0 | Conflict flagged, blended weight = 2.0 |
| 5. 3-session drift | Two rounds of dark-home downvotes | `light` weight measurably higher in session 2 vs session 1 |

</details>

### Data sources

Primary listing data can come from the curated `data/bengaluru_listings.csv` used in development, or from the public Bengaluru house price CSV mirrored by DPhi/AiPlanet:

- **Source name**: Bengaluru House Price Data
  - URL: <https://github.com/dphi-official/Datasets/blob/master/Bengaluru_House_Data.csv>
  - Local file: `data/bengaluru_house_data.csv`
  - Data used: Bengaluru location, BHK count, total square feet, price, area type, availability, society, bathroom count, and balcony count.
  - Accessed on: 30 Apr 2026
  - Notes: Prices are provided in lakhs and converted to INR in `realestate_finder/listings.py`. The dataset does not include explicit natural-light, property-age, or amenity fields, so the app derives demo feature scores from balcony count, area, availability, area type, and society presence.

The synthetic listings in `realestate_finder/listings.py` remain as an offline fallback if no CSV files are available.

---

## 📈 KPIs

All four business KPIs from the brief are tracked live in the **KPIs** panel:

| KPI | Definition | How measured |
|---|---|---|
| **Preference inference accuracy** | How well learned top-3 dimensions match buyer's stated final priorities | Blind test in UI: select final priorities → compare to top-3 learned weights |
| **Sessions to first strong yes** | Session number of first "up" thumbs | Recorded when first `rating="up"` arrives in `preference_updater` |
| **Listings filtered out %** | Hard-requirement rejects as % of broad candidates | `filtered_count / total_candidates × 100` in `matcher` |
| **Buyer engagement** | Sessions per week per buyer thread | `session_count / (elapsed_days / 7)` tracked in `state_saver` |

---

## 🔬 Prompt Engineering Notes

The Gemini system prompt for preference-delta inference went through **3 iterations**:

<details>
<summary>View iteration history</summary>

**v1 — Baseline** *(broken)*
> "Suggest adjustments to the buyer's preference weights based on the feedback."

Problem: Returned prose descriptions, not structured deltas. `with_structured_output` failed on malformed responses.

---

**v2 — Structured output enforced** *(wrong direction)*
> "Return small numeric deltas between -0.5 and 0.5 for these dimensions: price, size, location, light, age, amenities."

Problem: Directionality wrong. "Too dark" often *decreased* `light` (interpreted as "buyer doesn't like this lighting" → lower the dimension). Deltas were too large — single feedback event could dominate.

---

**v3 — Current** *(correct, bounded, consistent)*
> "Return small deltas between -0.35 and 0.35 only for these dimensions: price, size, location, light, age, amenities. Positive means the buyer values it more. **If a buyer downvotes a listing because it lacks a quality, increase that quality.** For example, 'too dark' should increase light because the buyer wants brighter homes. Do not invent new dimensions."

Fixes applied:
- Explicit directionality rule (downvote for lacking quality → increase that quality)
- Reduced delta bound: `[-0.35, 0.35]` per call
- Lifetime clamp: `[0.1, 3.0]` in `clamp_weights()`
- `@traceable` added so every call is visible in LangSmith

</details>

---

## 📁 Deliverables

| # | Deliverable | File / Location | Status |
|---|---|---|---|
| 1 | **GitHub repository** with full working code | This repo | ✅ |
| 2 | **README** with problem summary, setup, env vars, how-to-run, architecture diagram, data source citations | `README.md` | ✅ |
| 3 | **LangGraph state diagram** PNG + SVG generated via `graph.get_graph()` | `docs/architecture.png` · `docs/architecture.svg` | ✅ |
| 4 | **Presentation deck** (PDF, 8–12 slides) | `docs/presentation_deck.md` → **export to PDF** | ⚠️ Export needed |
| 5 | **Pre-recorded demo video** (≤ 3 min, screen capture + voiceover) | Upload to YouTube/Drive → paste link below | ⚠️ Recording needed |
| 6 | **Business memo** (one page) | `docs/business_memo.md` | ✅ |
| 7 | **requirements.txt** | `requirements.txt` | ✅ |
| 8 | **All four team members** named with roles | See [Team](#-team) section | ✅ |

> 📹 **Demo video link:** `https://drive.google.com/file/d/10EfyG_jXf7t2eUPGYrDDw6FLqrfnTavj/view?usp=sharing`  
> 🎞️ Content to cover: session 1 cold-start → downvote dark homes → **stop app** → **restart app** → session 2 (weights persist, brighter listings) → session 3 (drift visible in Memory panel)

---

## 🗂️ Repository Structure

```
Real-Estate-Finder/
├── streamlit_app.py               # Streamlit UI — buyer session, feedback, KPIs
├── requirements.txt               # All dependencies incl. langsmith, psycopg, postgres
├── .env.example                   # Safe template — copy to .env and fill keys
├── .gitignore                     # .env, .venv, data/*.sqlite excluded
│
├── data/
│   ├── bengaluru_listings.csv     # 60 synthetic Bengaluru listings (primary data source)
│   └── .gitkeep                   # Ensures data/ is tracked; *.sqlite excluded by .gitignore
│
├── .streamlit/
│   ├── config.toml                # Streamlit theme (dark/light)
│   └── secrets.toml.example      # Deployment secrets template — DO NOT rename/commit
│
├── realestate_finder/
│   ├── graph.py                   # StateGraph, SQLite/PostgreSQL checkpointer, LangSmith
│   ├── nodes.py                   # All 8 node functions + helpers + @traceable
│   ├── models.py                  # Pydantic v2 state schemas
│   ├── listings.py                # CSV loader + feature score computation + fallback
│   └── ui_helpers.py              # Drift rows, quick comments, checkpoint table names
│
├── scripts/
│   ├── demo_sessions.py           # 3-session CLI demo (proves SQLite persistence)
│   └── draw_graph.py              # Generates docs/architecture.png + .svg
│
├── tests/
│   ├── test_evaluation_framework.py  # 5 named buyer scenario tests (eval bonus)
│   ├── test_graph_integration.py     # SQLite restart, 4-session, routing tests
│   ├── test_preference_learning.py   # Weight, couple, fair-price, KPI tests
│   └── test_ui_helpers.py            # Drift, comments, checkpoint table tests
│
└── docs/
    ├── architecture.png           # LangGraph state diagram (PNG) — committed
    ├── architecture.svg           # LangGraph state diagram (SVG) — committed
    ├── architecture.mmd           # Mermaid source
    ├── business_memo.md           # One-page business memo
    └── presentation_deck.md       # 10-slide content — export to PDF
```

---

## 👥 Team

**Group 10 — UGDSAI 29 | Designing & Deploying AI Agents | Semester II**

| Member | Role |
|---|---|
| **Jeet Marlecha** | Graph architecture, LangGraph checkpointing (`graph.py`, `nodes.py`) |
| **Tanmay Agarwal** | Streamlit UI, demo video, LangSmith integration (`streamlit_app.py`) |
| **Lakshya Goel** | LLM prompt engineering, feedback evaluation, test suite |
| **Ansh** | README, business memo, presentation deck, KPI design |

---

<div align="center">

**Built for UGDSAI 29 End-Term Examination**  
*Designing & Deploying AI Agents — Semester II*

<sub>LangGraph · Gemini 1.5 Flash · Pydantic v2 · SQLite · Streamlit · LangSmith</sub>

</div>
