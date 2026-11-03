# Doody: An Interpretable State-Space Engine for Rebuilding Daily Routines and Financial Self-Reliance

English | [한국어](./README.ko.md)

Doody is a service that helps young adults who have withdrawn from work, school, or social life rebuild daily routines and financial self-reliance. This repository is its AI engine. It was developed in the four-month Hana Financial Talent Program (2026.03–2026.07), where the team was among 13 of 220 teams selected. I was Team Lead and AI Engine Lead.

The engine represents a user's state as a vector on three axes, rhythm, autonomy, and connection, and uses that vector to choose one small action for the day. Decisions come from explicit formulas. An LLM only writes the text that explains them.

The frontend and backend are in separate repositories: [doody-frontend](https://github.com/HanaDoody/doody-frontend), [doody-backend](https://github.com/HanaDoody/doody-backend).

## Three axes, three mechanisms

The axes share one coordinate system, but each moves differently.

| Axis | Mechanism | Unlock |
|---|---|---|
| Rhythm | Morning and evening check-ins. Not a mission axis; it is always open and seeds the mission gate | None |
| Autonomy | A 10-stage mission path. Onboarding sets the starting stage, and fallback missions also advance the stage | Completing the normal stage-10 signature mission |
| Connection | Collecting Doody characters. Onboarding sets the required count N | Collected count ≥ N |

## How a decision is made

Each call has three steps: read the state, choose the next action, and write the text.

### 1. Read the state

| Quantity | Formula | Meaning |
|---|---|---|
| Rhythm presence | `v ← v + α(aₜ − v)`, `aₜ = (morning + evening) / 2` | EMA over whether check-ins exist. With `α_up > α_down`, recovery is reflected faster than decline |
| Gap | `gap = g − v` | Remaining direction to the goal |
| Velocity | `velocity = vₜ − vₜ₋₁` | Recent direction of change |
| Recovery drag | `recovery_drag = gap − velocity` | The residual after subtracting recent progress. The largest axis is the bottleneck |

### 2. Choose the next action

| Quantity | Rule | Meaning |
|---|---|---|
| Gate | `gate = clamp((v_rhythm − r_floor) / (r_open − r_floor))` | Maps rhythm to [0, 1]. At 0, only the rhythm check-in remains. After a long stall, an escape hatch raises the floor |
| Fallback first | `gate < 0.5` or `energy ≤ 2` | Offers the smaller mission first |
| Step size | `vₜ₊₁ = vₜ + η(energy)Δ`, η from 0.4 to 1.0 | The same mission moves the state less on a low-energy day |
| Axis priority | `bottleneck_axis(recovery_drag)` | Replaces the autonomy mission with a connection prompt when connection lags further behind |

### 3. Write the text

Every decision leaves a trace: `decision_trace = {situation, primary_constraint, stage, waypoint, fallback_first}`. The LLM receives this trace and renders it as text. It cannot override the decision.

## Failure modes

Each failure condition has a defined path.

| Condition | Trigger | Handling |
|---|---|---|
| Rhythm at floor | `gate = 0` | Locks autonomy and connection; keeps the rhythm check-in |
| Low condition | `gate < 0.5` or `energy ≤ 2` | Offers the smaller mission first |
| Long stall | `days_without ≥ escape_days` | Raises the gate floor |
| Crisis signal in user text | Crisis keyword match | Bypasses the LLM and returns fixed safety text |
| LLM failure or guard violation | Exception, length or digit violation | Falls back to fixed text; the engine does not propagate the exception |

Live measurement over 30 calls: median latency about 3.5s, p95 about 10s, no fallbacks (timeout 20s, retry 1). The harness is in [`evals/`](./evals).

## A limit of the state estimate

The service does not record avoidance or failure, so the logs contain mostly positive events. Modeling engagement as a noisy readout of latent state, as in item response theory, shows what this does to the estimate: only the positive part of the innovation passes through, the estimate drifts upward, and the bias is larger for low-state users. Downward dynamics are not identifiable from these logs.

Idle gaps and utterance probes could recover part of the missing signal without penalizing users. This is an analysis of the model structure and has not been measured on user data. Details: [`docs/research_track.md`](./docs/research_track.md) (Korean).

## Current scope

- Implemented: the state-space formulas above, 12 FastAPI endpoints, LLM text generation with fallback and crisis guard, and a test suite.
- The state space is designed by hand, not learned from data. Learning it from logs or validating it with probing are possible extensions.
- Natural-language signal extraction (`app/nlu/`) is a stub in the MVP. Its design is in [`app/nlu/README.md`](./app/nlu/README.md) (Korean).

## Repository

```
app/
├── api/       FastAPI routes
├── schemas/   Request and response models
├── core/      State-space math, gate, mission selection, unlocks
├── llm/       Text generation, fallback, crisis guard
├── data/      Catalogs and configuration
├── nlu/       Signal extraction (stub)
└── fusion/    Signal fusion (stub)
evals/         LLM evaluation harness
tests/         Contract and unit tests
```

| Document | Contents |
|---|---|
| [`DESIGN.md`](./DESIGN.md) | Design decisions (Korean) |
| [`docs/research_track.md`](./docs/research_track.md) | Limits of the state estimate and research extensions (Korean) |
| [`docs/api_contract.md`](./docs/api_contract.md) | API contract (Korean) |

## Run

```bash
pip install -r requirements.txt
python -m pytest -q
uvicorn app.main:app --reload
```

The LLM is off by default, so the engine runs on fixed text without an API key. To enable it, set `ANTHROPIC_API_KEY` and `LLM_ENABLED=true`.

This repository is a curated release of the AI engine. Development history remains in the team's private repository.
