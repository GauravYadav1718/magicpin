# Antigravity Submission - magicpin AI Challenge

## Approach
This bot implements the required 5 endpoints using **FastAPI** to interact with the magicpin Judge Simulator.

The message composition relies on a robust **template-based approach** (heuristic-driven). The logic checks the `trigger` kind and uses the `merchant` performance details and `customer` context to formulate highly specific, personalized messages. 

### Why this approach?
A template-based approach ensures:
1. **Low Latency:** Always responds under the 30s threshold.
2. **Determinism:** The tests are perfectly repeatable, ensuring consistent logic for testing constraints (auto-reply handling, intent transition).
3. **No LLM Hallucinations:** Prevents fabricating fake offers, research citations, or competitor names.

If needed, this composer can be upgraded to an LLM provider by dropping in the API key and calling the completion APIs (OpenAI/Gemini/Anthropic) directly in the `generate_message` method in `bot.py`.

## Tradeoffs Made
- **Personalization vs Generality:** The heuristic rules cover all specified triggers in the prompt but might miss nuanced details that a full LLM could naturally pick up (e.g. nuanced translations or complex intent deductions in open-ended conversations).
- **Hardcoded Auto-reply parsing:** Using simple string matches (`"automated assistant"`, `"team will respond shortly"`) covers the common cases but might not catch complex variations.

## Context Needed
To further refine the bot, it would be useful to understand:
1. Complete list of possible trigger types.
2. Typical conversation transcripts across *all* verticals to optimize the rule-based intent parsing (beyond the few examples provided in the brief).
