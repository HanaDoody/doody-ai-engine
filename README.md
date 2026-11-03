# doody-ai-engine

English | [한국어](./README.ko.md)

The **AI engine** repository of Doody, *An Interpretable State-Space Engine for Rebuilding Daily Routines and Financial Self-Reliance*.

It models the state of young adults on a long gap from work, school, or social life (공백 청년) as a vector in a **three-dimensional recovery space of rhythm, autonomy, and connection**, then narrows the gap between the current state (ARI) and the goal through **small missions (movement vectors)**.
Instead of handing judgment to an LLM, it computes the **position, size, difficulty, tone, and unlocks** of *the one step possible today* inside an interpretable state space.

> The Doody service is split into **separate [front](https://github.com/HanaDoody/doody-frontend) / [back](https://github.com/HanaDoody/doody-backend) / AI repositories**, and this one is the **AI engine**.
> The three connect only through an HTTP API and a JSON contract.

### [Design decisions → `DESIGN.md`](./DESIGN.md)
Why it was built this way (ADR). Centered on the **deterministic core + LLM language surface** (D0), it records the context, alternatives, and tradeoffs of the **stateless engine** (D1), **crisis safety guard** (D2), and **cost gating** (D3). (Korean)

## Three Axes, Different Mechanisms

The three axes share one ARI coordinate system, but each moves in its own way. (They are not three symmetric features.)

| Axis | Mechanism | Unlock |
|---|---|---|
| **Rhythm** | The daily base routine (morning and evening check-ins). Not a mission axis: an always-open floor layer and the seed of the mission gate | None |
| **Autonomy** | A 10-stage mission path (stage 1→10). The onboarding diagnosis personalizes the starting stage, and fallback missions also advance the stage | Normal stage-10 signature completed → contact |
| **Connection** | A Doody collection path. The onboarding connection diagnosis personalizes the required count N (more isolation, larger N) | Collected Doody ≥ N → contact |

> Engine = *a state-space controller that picks the next step*. The core (math) decides, and the LLM supplies the words.

## Architecture: A Stateless Calculator

The AI engine **has no database (stateless).** On every call the backend sends the state it needs (current ARI, trajectory, history, collected count, and so on), and the engine returns only the computed result. So *"what the engine requires as input" = "what the backend must store"*.

```
[App screen] ──▶ [Backend: auth, DB, relay] ──▶ [AI engine (this repo): compute only]
                    │
                  [ DB ]  ← storage and accumulation (Hana Money, etc.) belong to the backend
```

- **AI engine**: ARI computation · mission selection · waypoint replanning · reward calculation · contact unlock decisions · dynamic text generation
- **Backend**: auth · state, history, and reward storage · relaying engine calls

## What the AI Engine Actually Does

Doody's AI is **neither a black box that judges nor a generative model trained on data.** It reads a user's behavior logs as a **state vector in an interpretable three-dimensional representation space (rhythm, autonomy, connection)** and is a **deterministic controller** that picks *today's one step* on top of that representation. The whole path `input (behavior) → internal representation (state vector) → action (next mission)` is **exposed as hand-designed formulas** rather than learned weights, and only the words (text) come from the LLM. Each call has three steps:

```
① Read (state estimation)  →  ② Choose (decision)  →  ③ Speak (text)
   state-space math              gate, stage              Sonnet 5 + fallback
```

### ① Read: Estimate the State as a Vector
| Quantity | Formula | Meaning |
|---|---|---|
| Rhythm presence | `v ← v + α·(aₜ − v)`, `aₜ=(morning+evening)/2` | An EMA over the **presence** of check-ins only. The asymmetry `α_up>α_down` is a hysteresis that **credits recovery generously and registers decline conservatively**. Starting value = the onboarding rhythm answer |
| Gap | `gap = g − v` | The direction vector remaining to the goal |
| Velocity | `velocity = vₜ − vₜ₋₁` | The recent direction of recovery |
| Recovery drag | `recovery_drag = gap − velocity` | The **residual after subtracting what the user is closing on their own**, so only the part that needs intervention remains. Largest axis = bottleneck |

### ② Choose: Decide the Next Cell with the Gate and Stage
| Quantity | Formula | Meaning |
|---|---|---|
| Gate | `gate = clamp((v_rhythm − r_floor)/(r_open − r_floor))` | The rhythm axis mapped to [0,1]. When rhythm is at the floor, `gate=0` **locks** the autonomy and connection axes (rhythm card only). After days of inactivity, the floor rises (escape hatch) |
| Fallback-first | `gate<0.5` or `energy≤2` | On low condition, **a smaller cell first** |
| Autonomy path | `next_stage(history)` | End condition = normal stage-10 signature. ARI is not used for routing and stays only in diagnostics |
| Step size | `v_{t+1} = v_t + η·Δ`, `η(energy)` 0.4~1.0 | The same mission counts for more or less depending on condition |
| Axis priority | `bottleneck_axis(recovery_drag)` | If connection lags further behind than autonomy, today's card switches from an autonomy mission to a connection prompt (`mission_state="connection_priority"`). There is one card per day, so it is replaced rather than added to |
| Contact unlock | Autonomy: signature completed / Connection: collected Doody ≥ N | Rule-based, with N personalized at onboarding |

### ③ Speak: Separating Decision from Language
- The engine records every decision as **`decision_trace = {situation, primary_constraint, stage, waypoint, fallback_first}`**, an interpretable account of why this mission came up.
- This trace is the **LLM input**. **Interpretable math owns the decision, and the generative model only produces surface text grounded in that trace.** The LLM (Sonnet 5) supplies the tone and **cannot override the decision.** On failure or crisis, the engine falls back to deterministic text.

### Failure Modes by Design
**"When and why it breaks" is defined before** the normal path, and each breakdown point has a safe path.

| Breakdown condition | Trigger | Safe handling |
|---|---|---|
| Rhythm at floor: no mission momentum | `gate = 0` | Locks autonomy and connection, leaving only the rhythm floor layer |
| Low condition | `gate<0.5` or `energy≤2` | Fallback-first: a smaller cell first |
| Long stall | `days_without ≥ escape_days` | Escape hatch: bypass by raising the gate floor |
| Crisis signal (user's raw text) | Crisis keyword detected | Bypasses the LLM and returns fixed safety text (rewards are still granted) |
| LLM failure or guard violation | Call exception, length or digit violation | Falls back to deterministic text (the engine never propagates the exception) |

### Current Scope: Implemented / Not Yet
- **Implemented**: all of the state-space math above (presence EMA, gate, recovery_drag, η, unlocks), 12 endpoints, LLM text generation + fallback + crisis guard, tests. Live LLM measurement (30 calls, Sonnet 5): latency **median ~3.5s / p95 ~10s**, 0 fallbacks (timeout 20s, retry 1). The instrumentation and eval harness are in [`evals/`](./evals).
- **Not yet**: the current representation space is **designed, not learned from data**. Learning the representation from logs or validating state estimates through probing are open extensions (roadmap seam), but it is rule- and formula-based today. Natural-language understanding (`nlu/`) is deferred in the MVP (stub). Distance and difficulty grading for connection Doody is conceptual only. Prompt caching is not applied.

## API at a Glance (12 Endpoints)

| Method & Path | Role |
|---|---|
| `GET  /health` | Server status check |
| `POST /onboarding/intro` | First entry → a light first mission (**no ARI**) |
| `POST /onboarding/recommend-period` | Goal (+ state) → recommended period (recommendation ≠ final) |
| `POST /onboarding/complete` | Deferred onboarding → initial ARI v₀ · goal g · starting stage · rhythm seed |
| `POST /mission/recommend` | Current state → recommended mission (gate · fallback-first · decision_trace) |
| `POST /mission/complete` | Mission completed → ARI update (vₜ₊₁ = vₜ + η·Δ) · **reward (hana_money)** · contact unlock |
| `POST /mission/reject` | Rejection → smaller candidates / path replanning |
| `POST /collection/capture` | Doody capture → connection ARI update · reward · **count-based contact unlock** |
| `POST /rhythm/morning` | Morning rhythm check-in → greeting · reward |
| `POST /rhythm/evening` | Evening rhythm entry → reply · reward (crisis guard) |
| `POST /chat/message` | Doody reply + natural-language auxiliary signal (stateless single turn, crisis guard) |
| `POST /report/summary` | Recovery report (injected numbers → LLM direction narrative) |

> Request and response JSON and field details per endpoint → [`docs/api_contract.md`](./docs/api_contract.md) (Korean)

## LLM: Words Only, No Decisions

- Dynamic text (`reason` · `rest_message` · `message` · `reply` · `greeting` · `summary`) is generated by **Claude Sonnet 5**.
- If `is_enabled()` (API key AND config toggle) is false or a call fails, it falls back safely to **deterministic text**. The repository default is `enabled:false` (billing and latency are turned on deliberately in production).
- **Crisis guard**: when a crisis signal is detected in the raw `chat` or `evening` text, it bypasses the LLM and returns **fixed safety text** (rewards are granted as usual).
- Static text (`title` · `description` · `how_to`) comes from fixed catalog values and is shown as is.

## Tech Stack
- **Python + FastAPI** (uvicorn, pydantic)
- **Claude API** (`claude-sonnet-5`): dynamic text only, no decisions
- Tests: `python -m pytest -q`

## Documents
| Document | Contents |
|---|---|
| [`DESIGN.md`](./DESIGN.md) | **Design decisions (ADR)**: deterministic core + LLM surface · stateless · crisis safety guard · cost gating (Korean) |
| [`docs/research_track.md`](./docs/research_track.md) | How positive-only engagement logs can bias state estimates upward for low-state users, and research questions this extends to |
| [`docs/api_contract.md`](./docs/api_contract.md) | API contract: request and response JSON · common objects · backend storage · glossary (Korean) |
| [`app/nlu/README.md`](./app/nlu/README.md) | Design of embedding-based signal extraction (Korean) |
| [`evals/README.md`](./evals/README.md) | LLM eval and observability harness (Korean) |

## Repository Structure
Each folder in `app/` does one job:

```
app/
├── api/       Request handling (endpoints → routers, 1:1 with the 12 above)
├── schemas/   DTOs (pydantic)
├── core/      Recovery-space math (gate, mission selection, ARI update, unlocks, rewards)
├── llm/       Dynamic text (single Sonnet 5 entry point + deterministic fallback + crisis guard)
├── data/      Catalogs and config (missions, Doody, pins, goals, gate config)
├── nlu/       Natural-language support (deferred in MVP)
└── fusion/    Signal fusion (deferred in MVP)
```

## Current Status
- [x] Planning and design
- [x] API contract document (`docs/`)
- [x] **AI engine implementation**: 12 FastAPI endpoints, tests
- [x] **v3.2 controller**: diagnosis → starting stage · rhythm seed gate · fallback-first · connection count unlock · mission rewards
- [x] **LLM integration**: single Sonnet 5 entry point + deterministic fallback + crisis guard

## Project Background
Hana Financial Talent Program (ESG + future finance). Four-month program (2026.03–2026.07), 13 of 220 teams selected. Team Lead and AI Engine Lead.

This repository is a curated release of the AI engine. Development history remains in the team's private repository.
