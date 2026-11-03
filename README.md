# doody-ai-engine

English | [한국어](./README.ko.md)

The **AI engine** repository of Doody, *An Interpretable State-Space Engine for Rebuilding Daily Routines and Financial Self-Reliance*.

It models the state of young adults on a long gap from work, school, or social life (공백 청년) as a vector in a **three-dimensional recovery space of rhythm, autonomy, and connection**, and narrows the gap between the current state (ARI) and the goal through **small missions (movement vectors)**.
Judgment is not left to an LLM. Inside an interpretable state space, the engine computes the **position, size, difficulty, text, and unlocks** of today's mission.

> The Doody service is split into **separate [front](https://github.com/HanaDoody/doody-frontend) / [back](https://github.com/HanaDoody/doody-backend) / AI repositories**, and this one is the **AI engine**.
> The three connect only through an HTTP API and a JSON contract.

### [Design decisions → `DESIGN.md`](./DESIGN.md)
Centered on **separating the deterministic core from LLM narration** (D0), it records the context, alternatives, and tradeoffs of the **stateless engine** (D1), **crisis safety guard** (D2), and **cost gating** (D3) in ADR format.

### [Limits of state estimation → `docs/research_track.md`](./docs/research_track.md)
How positive-only engagement logs can bias state estimates upward for low-state users, and the probing, identifiability, and failure-mechanism questions this can extend to.

## Three Axes, Different Mechanisms

The three axes share one ARI coordinate system, but each moves differently.

| Axis | Mechanism | Unlock |
|---|---|---|
| **Rhythm** | The daily base routine (morning and evening check-ins). Not a mission axis: an always-open base layer and the seed of the mission gate | None |
| **Autonomy** | A 10-stage mission path (stage 1→10). The onboarding diagnosis personalizes the starting stage, and fallback missions also advance the stage | Contact unlocked after the normal stage-10 signature |
| **Connection** | A Doody collection path. The onboarding connection diagnosis personalizes the required count N (more isolation, larger N) | Contact unlocked when collected Doody ≥ N |

> The engine is a state-space controller that picks the next mission. The core (formulas) decides, and the LLM writes the text.

## Architecture: Stateless

The AI engine **has no database.** On every call the backend sends the state it needs (current ARI, trajectory, history, collected count, and so on), and the engine returns only the computed result. The engine's input is therefore the data the backend must store.

```
[App screen] ──▶ [Backend: auth, DB, relay] ──▶ [AI engine (this repo): compute only]
                    │
                  [ DB ]  ← storage and accumulation (Hana Money, etc.) are handled by the backend
```

- **AI engine**: ARI computation · mission selection · waypoint replanning · reward calculation · contact unlock decisions · dynamic text generation
- **Backend**: auth · state, history, and reward storage · relaying engine calls

## What the AI Engine Does

Doody's AI is a **deterministic controller**, not a model trained on data. It reads a user's behavior logs as a **state vector in an interpretable three-dimensional representation space (rhythm, autonomy, connection)** and uses it to pick today's mission. The path `input (behavior) → internal representation (state vector) → action (next mission)` is defined by **hand-designed formulas** rather than learned weights, and only the text comes from the LLM. Each call has three steps:

```
① State estimation   →   ② Mission decision   →   ③ Text generation
  state-space formulas      gate, stage              Sonnet 5 + fallback
```

### ① State Estimation
| Quantity | Formula | Meaning |
|---|---|---|
| Rhythm presence | `v ← v + α·(aₜ − v)`, `aₜ=(morning+evening)/2` | An EMA over check-in **presence**. Since `α_up>α_down`, increases count more than decreases. Starting value: the onboarding rhythm answer |
| Gap | `gap = g − v` | The direction vector remaining to the goal |
| Velocity | `velocity = vₜ − vₜ₋₁` | The recent direction of change |
| Recovery drag | `recovery_drag = gap − velocity` | The residual after subtracting recent change from the gap. The largest axis is the bottleneck |

### ② Mission Decision
| Quantity | Formula | Meaning |
|---|---|---|
| Gate | `gate = clamp((v_rhythm − r_floor)/(r_open − r_floor))` | The rhythm axis mapped to [0,1]. When rhythm is at the floor, `gate=0` **locks** the autonomy and connection axes (rhythm card only). After consecutive days without a mission, the floor rises (escape hatch) |
| Fallback-first | `gate<0.5` or `energy≤2` | On low condition, **a smaller mission first** |
| Autonomy path | `next_stage(history)` | End condition: normal stage-10 signature. ARI is not used for stage progression and stays in diagnostics |
| Step size | `v_{t+1} = v_t + η·Δ`, `η(energy)` 0.4~1.0 | The same mission counts differently depending on energy |
| Axis priority | `bottleneck_axis(recovery_drag)` | If connection lags further behind than autonomy, today's card switches from an autonomy mission to a connection prompt (`mission_state="connection_priority"`). There is one card per day, so it is replaced rather than added |
| Contact unlock | Autonomy: signature completed / Connection: collected Doody ≥ N | Rule-based, with N personalized at onboarding |

### ③ Text Generation
- The engine records every decision as **`decision_trace = {situation, primary_constraint, stage, waypoint, fallback_first}`**, so the basis for each mission can be inspected.
- The LLM (Sonnet 5) writes mission text from this trace. **The formulas decide and the LLM only writes text; it cannot change a decision.** On failure or a crisis signal, fixed text is used.

### Failure Modes
Each failure condition has a defined handling path.

| Failure condition | Trigger | Handling |
|---|---|---|
| Rhythm at floor | `gate = 0` | Locks autonomy and connection, leaving only the rhythm layer |
| Low condition | `gate<0.5` or `energy≤2` | Fallback-first: a smaller mission first |
| Long stall | `days_without ≥ escape_days` | Escape hatch: raises the gate floor |
| Crisis signal (user's raw text) | Crisis keyword detected | Does not call the LLM and returns fixed safety text (the `evening` reward is still granted) |
| LLM failure or guard violation | Call exception, length or digit violation | Uses fallback text (the engine does not propagate the exception) |

### Current Scope
- **Implemented**: all of the state-space formulas above (presence EMA, gate, recovery_drag, η, unlocks), 12 endpoints, LLM text generation and fallback, crisis guard, tests. Live LLM measurement (30 calls, Sonnet 5): latency **median ~3.5s / p95 ~10s**, 0 fallbacks (timeout 20s, retry 1). The instrumentation and eval harness are in [`evals/`](./evals).
- **Not implemented**: the current representation space is **hand-designed**, not learned from data. It can extend to learning representations from logs and validating state estimates through probing. Natural-language understanding (`nlu/`) is deferred in the MVP (stub). Distance and difficulty grading for connection Doody is at the concept stage. Prompt caching is not applied.

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
| `POST /chat/message` | Doody reply + natural-language auxiliary signal (single turn, crisis guard) |
| `POST /report/summary` | Recovery report (numeric input → LLM narration) |

> For request and response JSON and field details per endpoint, see [`docs/api_contract.md`](./docs/api_contract.md) (Korean).

## LLM: Text Generation Only

- Dynamic text (`reason` · `rest_message` · `message` · `reply` · `greeting` · `summary`) is generated by **Claude Sonnet 5**.
- If `is_enabled()` (API key AND config toggle) is false or a call fails, **fallback text** is used. The repository default is `enabled:false`, and it is turned on only in production.
- **Crisis guard**: when a crisis signal is detected in the raw `chat` or `evening` text, the LLM is not called and **fixed safety text** is returned (the `evening` reward is granted as usual).
- Static text (`title` · `description` · `how_to`) uses fixed catalog values as is.

## Tech Stack
- **Python + FastAPI** (uvicorn, pydantic)
- **Claude API** (`claude-sonnet-5`): dynamic text only
- Tests: `python -m pytest -q`

## Documents
| Document | Contents |
|---|---|
| [`DESIGN.md`](./DESIGN.md) | **Design decisions (ADR)**: deterministic core and LLM narration · stateless · crisis safety guard · cost gating |
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
├── core/      Recovery-space formulas (gate, mission selection, ARI update, unlocks, rewards)
├── llm/       Dynamic text (Sonnet 5 calls, fallback, crisis guard)
├── data/      Catalogs and config (missions, Doody, pins, goals, gate config)
├── nlu/       Natural-language support (deferred in MVP)
└── fusion/    Signal fusion (deferred in MVP)
```

## Current Status
- [x] Planning and design
- [x] API contract document (`docs/`)
- [x] **AI engine implementation**: 12 FastAPI endpoints, tests
- [x] **v3.2 controller**: diagnosis → starting stage · rhythm seed gate · fallback-first · connection count unlock · mission rewards
- [x] **LLM integration**: Sonnet 5 calls, fallback, crisis guard

## Project Background
Hana Financial Talent Program (ESG + future finance). Four-month program (2026.03–2026.07), 13 of 220 teams selected. Team Lead and AI Engine Lead.

This repository is a curated release of the AI engine. Development history remains in the team's private repository.
