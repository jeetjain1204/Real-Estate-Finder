# RealEstateFinder — Presentation Deck Content
## Group 10 | UGDSAI 29 | Designing & Deploying AI Agents
### Jeet Marlecha · Tanmay Agarwal · Lakshya Goel · Ansh

---

## Slide 1 — Problem Framing  *(1 min)*

**What is the problem?**
Home buying is iterative. A buyer tours properties over weeks or months. They start with "3 BHK, Bengaluru, ₹1.8 Cr" and discover after 12 tours that natural light matters more than square footage.

**Today's portals don't learn.** Every visit is a cold start. The buyer re-filters from scratch.

**Who is the user?**
Urban first-time or move-up buyer searching over 4–8 weeks. Fixed budget, evolving soft trade-offs.

**KPIs this agent moves:**
| KPI | Baseline | Target |
|---|---|---|
| Sessions to first "strong yes" | 8–12 | 3–5 |
| Listings filtered from cold start | 0% | 30–50% |
| Preference inference accuracy | N/A | > 70% |
| Buyer engagement (sessions/week) | 1.2 | 2.5+ |

---

## Slide 2 — Why This Needs LangGraph  *(part of architecture walkthrough)*

A simple chatbot or ReAct agent cannot do this because:
- State must **persist across Python process restarts** (SQLite checkpoint)
- Each session the graph **routes differently**: recommendation vs. feedback
- Preference learning uses a **typed state schema** — weights change only on the feedback path
- 8 nodes with **single responsibilities** — not one giant prompt

LangGraph gives us: `StateGraph + SqliteSaver + conditional_edges + Pydantic v2 state`

---

## Slide 3 — Graph Architecture  *(2 min walkthrough)*

*[Insert docs/architecture.png here]*

**Two execution paths from one state:**

```
state_loader
   ├─[recommend]→ listing_fetcher → matcher → Ranker → presenter → state_saver → END
   └─[feedback] → feedback_receiver → preference_updater → state_saver → END
```

**Node responsibilities (one each):**
- `state_loader`: reads current session context, sets loaded_from_checkpoint flag
- `listing_fetcher`: returns broad candidates within budget + city from 36 synthetic listings
- `matcher`: scores each listing against weighted dimensions, enforces hard requirements, computes fair-price estimate
- `Ranker`: sorts by score, takes top 5, marks seen_listings
- `presenter`: generates tour summary + downloadable .ics calendar event
- `feedback_receiver`: validates buyer feedback against current shortlist
- `preference_updater`: sends feedback to Gemini with structured output → PreferenceDelta → update weights
- `state_saver`: increments session_count (recommend path only), updates KPIs, checkpoints state

---

## Slide 4 — Pydantic State Schema  *(part of architecture walkthrough)*

`BuyerPreferenceState` — all 6 required fields:

```python
class BuyerPreferenceState(BaseModel):
    buyer_profile: BuyerProfile          # budget, city, min_bedrooms, required_amenities
    preference_weights: dict[str, float] # price, size, location, light, age, amenities
    seen_listings: list[str]             # cooldown strategy — avoids immediate repeats
    feedback_log: list[FeedbackEvent]    # full history of ratings + comments
    session_count: int                   # incremented only on recommend path
    last_updated: datetime               # persisted via SqliteSaver to SQLite
```

**Why SqliteSaver (not MemorySaver):**
MemorySaver lives in-process — it dies when the app restarts. SqliteSaver writes to `data/checkpoints.sqlite`. Session 2 picks up exactly where Session 1 left off, even after a process kill.

---

## Slide 5 — Preference Learning  *(part of architecture walkthrough)*

**6 soft dimensions**: price · size · location · light · age · amenities

**Learning mechanism:**
```
buyer comment: "too dark, not enough windows"
     ↓
Gemini structured output → PreferenceDelta(deltas={"light": +0.28}, rationale="...")
     ↓
preference_weights["light"] += 0.28  → clamped to [0.1, 3.0]
     ↓
next session: Ranker surfaces high-light listings first
```

**Prompt engineering (3 iterations):**
- v1: free-text adjustment → inconsistent output
- v2: structured output added → directionality wrong ("too dark" decreased light)
- v3 (current): explicit rule — *"If buyer downvotes because listing lacks quality, increase that weight"* — correct, bounded, consistent

**LangSmith tracing** shows each Gemini call and the exact delta returned.

---

## Slide 6 — Demo  *(3 min pre-recorded video)*

*[Play demo_video.mp4 here]*

Demo shows:
1. Session 1 — cold start, equal weights, 5 listings shown
2. Buyer downvotes dark homes ("too dark", "not enough windows")
3. **App restarted** — SQLite checkpoint proves persistence
4. Session 2 — `light` weight drifted up, brighter listings surface
5. Session 3 — further preference drift visible in "Memory" panel, preference drift chart

---

## Slide 7 — KPIs, Edge Cases, Learnings  *(1.5 min)*

**KPI tracking (live in UI):**
- Preference inference accuracy (blind test: select top-3 after session 3, compare to learned top-3)
- Sessions to first strong yes
- Listings filtered out % (hard requirements)
- Buyer engagement sessions/week

**Edge cases handled:**
| Scenario | Mitigation |
|---|---|
| LLM unavailable | Feedback saved; weights frozen; UI shows error |
| Repeated listings | `seen_listings` + cooldown (prefer last 10 unseen) |
| Runaway drift | Deltas clamped ±0.35 per call; weights clamped [0.1, 3.0] |
| Couple with conflicting preferences | Couple mode: blended weights, conflict flagged in UI |
| Hard requirements conflict with learned soft weights | Hard requirements enforced before ranking; can never be overridden |

**Learnings:**
- LangGraph's `graph.get_state()` is the correct way to inspect the checkpointed state — not SQL queries
- Pydantic `model_validate` handles nested model reconstruction from dicts automatically
- `with_structured_output(PreferenceDelta)` is more reliable than asking Gemini to output valid JSON

---

## Slide 8 — Bonus Features  *(part of demo or Q&A)*

All four problem-specific bonuses implemented:

| Bonus | Implementation |
|---|---|
| Negotiation aide | Fair-price estimate from comparable synthetic listings (by bedroom count + area) |
| Tour scheduling | `.ics` iCalendar event for top listing — imports into Google Calendar |
| Explanation mode | "Shown because you reacted to natural light in earlier feedback" — references feedback history |
| Multi-buyer mode | Couple profile: blended weights, conflict detection when \|A−B\| ≥ 0.7 |

General bonuses:
- **LangSmith +4**: `LANGSMITH_API_KEY` → auto-traces every graph run and Gemini call
- **Evaluation framework +4**: 20 tests in 4 files; dedicated `test_evaluation_framework.py` has 5 named buyer scenarios
- **Prompt iteration +3**: Documented in README (3 iterations with rationale)

---

## Slide 9 — What's Next · Limitations  *(0.5 min)*

**Limitations:**
- Synthetic Bengaluru listings (36 homes) — production needs live 99acres / MagicBricks ingestion
- Preference weights are per-thread, not multi-device — production needs identity management
- No formal evaluation against real buyer stated preferences (held-out test set)

**Next steps for production:**
1. Live listing ingestion (MagicBricks API or scraper with rate limiting)
2. Direct Google Calendar API integration (OAuth) instead of .ics download
3. A/B evaluation: session-count-to-first-offer vs. baseline portal
4. RLHF-style loop: use human buyer outcomes to fine-tune dimension weights

---

## Slide 10 — Q&A Preparation

**Architectural:** Why LangGraph over a simple while-loop? → Typed state, named nodes, visual graph, checkpoint-backed resume, inspectable state at any point.

**Implementation:** What happens when Gemini fails? → `preference_updater` catches `RuntimeError`, saves feedback to `feedback_log`, returns `learning_error` to UI. Weights are unchanged. State is still checkpointed.

**Business:** What KPI moves most? → "Sessions to first strong yes" — buyers find the right home faster because the shortlist improves with each visit.

**Scalability:** Where are the bottlenecks if traffic scales 10x? → `listing_fetcher` with a live DB and `preference_updater` (Gemini call). Both are I/O-bound; the graph handles them in separate nodes so each can be replaced independently.

---

*Export this file to a PDF slide deck using your preferred tool (Google Slides, Canva, PowerPoint). Add screenshots of the Streamlit UI and the architecture.png diagram.*
