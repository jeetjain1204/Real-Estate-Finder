# RealEstateFinder Business Memo

## Problem
Home search is not a one-shot filtering problem. Buyers often begin with obvious constraints such as city, budget, bedrooms, and required amenities, but their real trade-offs emerge only after seeing options. A buyer may start by optimizing for size, then discover that natural light, newer construction, commute, or neighborhood quality matters more. Traditional search tools treat every session as mostly independent, so the buyer has to repeat context and the recommendations do not improve enough from prior feedback.

RealEstateFinder addresses this by using a LangGraph agent with persistent buyer memory. Each recommendation session loads the buyer's saved state, fetches a broad listing set, filters hard requirements, ranks the top homes using learned preference weights, and explains why each listing fits. Feedback sessions capture thumbs-up or thumbs-down comments, infer how preferences should shift, and save that updated state for the next visit.

## User Persona
The primary persona is an urban home buyer in Bengaluru who is actively searching over multiple weeks. They have a real budget, minimum bedroom requirement, and must-have amenities such as covered parking, but they are still learning their softer preferences through comparison. They want fewer irrelevant listings, clearer explanations, and a search experience that remembers what they disliked last time.

A secondary persona is a buyer-side real-estate advisor. They use the agent to produce sharper shortlists, explain recommendation logic to the buyer, and track how the buyer's priorities evolve across sessions.

## KPIs The Agent Impacts
- **Preference inference accuracy:** Measures how closely the learned preference weights match the buyer's final stated priorities after several feedback cycles.
- **Sessions to first strong yes:** Tracks how many recommendation sessions it takes before the buyer finds a listing they would seriously consider touring.
- **Listings filtered out percentage:** Shows how effectively the agent removes broad-market listings that fail hard requirements before ranking.
- **Buyer engagement sessions:** Counts repeat sessions per buyer thread, indicating whether persistent memory makes the search useful enough to continue.

Together, these KPIs show whether the agent is learning buyer intent, reducing search noise, and improving the quality of recommendations over time.

