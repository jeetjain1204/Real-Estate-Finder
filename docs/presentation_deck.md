# RealEstateFinder Presentation Deck

## 1. Problem Framing
Home buying is iterative. Buyers start with fixed filters, then discover softer preferences after seeing real properties. RealEstateFinder learns those preferences across weeks instead of treating every visit as a cold start.

## 2. User Persona And KPIs
Persona: Bengaluru home buyer searching over multiple sessions with a fixed budget and evolving trade-offs.

KPIs: preference inference accuracy, sessions to first strong yes, listings filtered out from cold-start results, and buyer engagement.

## 3. Why LangGraph
This is a long-running stateful workflow. LangGraph gives typed graph state, named nodes, checkpoint-backed resumption, and durable thread state through `SqliteSaver`.

## 4. Graph Architecture
Show `docs/architecture.png`.

Flow: `state_loader -> listing_fetcher -> matcher -> Ranker -> presenter -> feedback_receiver -> preference_updater -> state_saver`.

## 5. State And Persistence
`BuyerPreferenceState` stores buyer profile, preference weights, seen listings, feedback log, session count, and last updated time. The same buyer id maps to the same LangGraph thread id, so state survives app restarts.

## 6. Preference Learning
The model tracks price, size, location, light, age, and amenities. Buyer comments are parsed by an LLM into bounded preference deltas, then normalised to avoid overfitting.

## 7. Demo Flow
Session 1 cold-starts with equal weights. The buyer dislikes dark homes. After restart, Session 2 resumes from SQLite and raises the `light` weight. Session 3 shows further drift and stronger matches.

## 8. Edge Cases And Learnings
Sparse feedback is bounded. Repeated listings are tracked with `seen_listings`. LLM parsing uses structured output. A demo fallback keeps the app reliable while API keys are configured.

## 9. Limitations
Synthetic data is used for reproducibility. Real deployment needs live listing ingestion, duplicate detection, richer buyer profiles, and evaluation against stated final preferences.

## 10. Next Steps
Add comparable-based fair price estimates, calendar tour scheduling, explanation mode, and multi-buyer preference reconciliation.

