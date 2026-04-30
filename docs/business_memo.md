# RealEstateFinder Business Memo

## Problem
Home buyers rarely know their true priorities on day one. They begin with filters like budget, city, and bedrooms, then discover softer preferences after touring homes: natural light, commute tolerance, amenity value, layout, age, or neighborhood feel. RealEstateFinder turns that iterative process into persistent preference learning across sessions.

## User Persona
The primary user is an urban first-time or move-up buyer searching over several weeks. They have a fixed budget and broad location preference, but their trade-offs evolve as they compare real homes. The secondary user is a buyer agent who wants better shortlists and clearer explanations for why each home is being recommended.

## Agent Impact
The agent maintains a durable buyer memory using LangGraph checkpointing. Recommendation sessions retrieve a broad listing pool, enforce hard requirements, rank the best five homes, and explain matches using prior feedback. Feedback sessions validate buyer comments, use Gemini to infer preference deltas, update KPIs, and checkpoint the new state for the next visit.

## KPIs
- Preference inference accuracy: compare learned weights against the buyer's stated final priorities after the search.
- Sessions to first strong yes: fewer sessions means the agent learns useful trade-offs faster.
- Listings filtered out: percentage reduction from broad candidates after hard requirement matching.
- Buyer engagement: repeat sessions per week and feedback completion rate.

## Risks And Edge Cases
- Sparse feedback can overfit. The app applies small bounded deltas and clamps weights.
- Repeated listings create demo fatigue. The graph tracks `seen_listings` and uses a cooldown strategy instead of exhausting the pool.
- LLM output can be malformed. Structured output is requested; if Gemini fails, feedback is saved but weights are not changed.
- Preference drift can conflict with hard requirements. Hard requirements stay in `BuyerProfile`; learned weights only affect soft ranking.

