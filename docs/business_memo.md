# Business Memo — RealEstateFinder
**To:** Product Team, NestSage  
**From:** Group 10 — UGDSAI 29  
**Date:** May 2026  
**Re:** AI Agent for Persistent Buyer Preference Learning

---

## Problem Statement

Home buying is iterative. A buyer starts with "3 BHK, Bengaluru, ₹1.8 Cr" and discovers after 12 tours that natural light matters more than square footage, or that commute time is non-negotiable. **Today's property portals don't learn** — every session is a cold start with static filters. Buyers re-explain their preferences every visit, and agents lose context between conversations.

---

## User Persona

**Primary:** Urban first-time or move-up buyer, aged 28–42, searching over 4–8 weeks with a fixed budget and evolving soft trade-offs. Uses the portal on weekends; may go 3–5 days between sessions. Discovers preferences by *seeing* homes, not by filling forms.

**Secondary:** Buyer's agent who wants better shortlists per client and an explainable record of why each home was recommended — useful for client trust and compliance.

---

## Agent Capabilities

RealEstateFinder uses LangGraph's `SqliteSaver` to maintain a durable buyer preference state across sessions. Each session:

1. **Loads** the buyer's checkpointed state (preference weights, feedback history, seen listings)
2. **Fetches** broad listing candidates matching city and budget
3. **Scores and ranks** listings against learned preference weights across 6 dimensions
4. **Presents** the top 5 with match explanations and fair-price estimates
5. **Captures** thumbs-up / thumbs-down feedback with comments
6. **Updates** preference weights via Gemini structured output
7. **Saves** the updated state to SQLite for the next session

Hard requirements (minimum bedrooms, required amenities, budget) are enforced before soft ranking and cannot be overridden by preference learning.

---

## KPIs and Impact

| KPI | Baseline (portal) | Agent target | Measurement |
|---|---|---|---|
| **Sessions to first "strong yes"** | 8–12 sessions | 3–5 sessions | Recorded when first `rating="up"` received |
| **Preference inference accuracy** | N/A (no learning) | > 70% | Blind test: compare learned top-3 dims vs buyer's stated final priorities |
| **Listings filtered from cold-start pool** | 0% | 30–50% | `filtered_count / total_candidates` after preference drift |
| **Buyer engagement** | 1.2 sessions/week | 2.5+ sessions/week | `session_count / elapsed_weeks` per buyer thread |

---

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| **Sparse feedback overfits** | Bounded deltas `[-0.35, 0.35]` per Gemini call; lifetime clamp `[0.1, 3.0]` per dimension |
| **Repeated listings cause demo fatigue** | `seen_listings` list + cooldown strategy (prefer last-10 unseen before recycling) |
| **LLM output is malformed** | `with_structured_output(PreferenceDelta)` enforces schema; graceful fallback saves feedback without updating weights |
| **Preference drift conflicts with hard requirements** | Hard requirements are in `BuyerProfile`, never in soft weights; they cannot be learned away |
| **Couple with conflicting preferences** | Couple mode blends partner weights; conflicts (delta ≥ 0.7) are surfaced in the UI |

---

## Scope and Limitations

This agent is scoped to a 14-day build window using synthetic Bengaluru listings. Production deployment would require:
- Live listing ingestion (99acres / MagicBricks API or scraper with rate limiting)
- Multi-device identity management (thread ID per device is insufficient for production)
- Offline evaluation against real buyer stated preferences on a held-out set
- Compliance review for data storage of buyer preference history

---

*Submitted as part of UGDSAI 29 End-Term Examination — Group 10*  
*Jeet Marlecha · Tanmay Agarwal · Lakshya Goel · Ansh*
