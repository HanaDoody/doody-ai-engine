# DESIGN: Doody AI Engine Design Decisions

English | [한국어](./DESIGN.ko.md)

**Status**: Accepted · 2026-07 (v3.2)

This document records the core design decisions of the Doody AI engine and the reasons for them, in ADR format.

## D0: Separating the Deterministic Core from LLM Narration

**Context**: The engine suggests a next action every day to vulnerable users (young adults on a long gap from work, school, or social life, 공백 청년). The text should read naturally and warmly, which favors a generative model. Decisions must be safe, consistent, and verifiable, which works against one because of nondeterminism, cost, and hallucination.

**Decision**: The deterministic core makes the decision (what, how much, when), and the LLM only writes the result as text.
- The core (state-space formulas) computes the mission, size, gate, and unlocks, and records a `decision_trace`
- The LLM (Sonnet 5) only generates text and cannot change a decision. Its input is the trace for mission text, the user's raw text and an action set by rules for `chat`, and the user's raw text for `evening`
- All calls go through [`llm/client.py`](app/llm/client.py). `complete()` does not raise exceptions and returns `None` on failure, in which case the fallback text for that field is used
- LLM output is checked for length, and short fields are also checked for digits

**Alternatives considered**
- **LLM also chooses the mission**: nondeterministic, could suggest something risky to a vulnerable user, higher cost and latency, and hard to test. Not adopted
- **Rules only, no LLM**: safe and deterministic, but the text is repetitive and does not suit a recovery context. Not adopted

**Consequences**
- (+) Decisions can be reproduced and tested · LLM outages do not become service outages · the basis of each decision can be inspected
- (−) Text is limited to the catalog and trace · prompt maintenance cost

---

## Other Decisions

### D1: Stateless Engine (Storage in the Backend)
**Context**: Where should the state (ARI, history, collected count, rhythm seed) be managed?

**Decision**: The engine has no database. On every call the backend sends the state it needs, and the engine returns only the computed result. The engine's input is the data the backend must store.

**Why**: The engine stays close to a pure function, which makes testing and horizontal scaling easier. It stores no personal data, and role boundaries are clear.

**Tradeoff**: Every call must send the full state, so payloads are larger, and the backend must manage accumulated values (Hana Money, collected count, rhythm seed). When the LLM is on, raw `chat` and `evening` text without a crisis signal is sent to the Anthropic API.

### D2: Crisis Safety Guard (Bypassing the LLM)
**Context**: In `chat` and `evening`, the LLM reads the user's raw text and replies. Responses in a crisis are not left to a generative model.

**Decision**: When a crisis keyword is detected in the raw text ([`safety.py`](app/llm/safety.py) + [`crisis_terms.json`](app/data/crisis_terms.json)), the engine does not call the LLM and returns **fixed safety text**. `chat` also returns `suggested_action="none"`, and the `evening` reward is granted as usual. Directing users to actual crisis resources (hotlines, institutions) is outside the engine and was assigned to the frontend.

**Why**: The safety path must be deterministic.

**Tradeoff**: Keyword matching produces false positives and misses. Extending it with clinical advice remains open.

### D3: Cost Gating (Off by Default)
**Context**: LLM calls are the only point that incurs cost and latency.

**Decision**: `is_enabled()` = (`config.enabled` OR `LLM_ENABLED` env) AND `ANTHROPIC_API_KEY`. The repository default is `enabled:false` in [`llm_config.json`](app/data/llm_config.json), and production turns it on through env without source changes (`LLM_ENABLED=true` + key). Without a key, it stays off.

**Why**: There is no accidental billing, and the engine still works on fallback text when the LLM is off or fails.

**Tradeoff**: Fallback text is served until the LLM is turned on.

---

## Revisit Conditions
- Higher call volume: system prompt caching and batching
- Fallback text quality issues: eval gate, rewriting the text
- Crisis keywords: incorporating clinical advice
- Representation learning: the current representation is hand-designed and can extend to learning from logs and validation through probing

---

> For the formulas and state space the engine computes, see *"What the AI Engine Does"* in [`README.md`](README.md).
