# Doody Engine: Limits of State Estimation and Research Extensions

English | [한국어](./research_track.ko.md)

This document records the assumptions behind the Doody AI engine's state estimate, where they fall short, and the research questions that can extend from them. The current engine is rule-based, and the content below is follow-up work outside the implemented scope.

- Basis: v3.1 (v0.7) MVP design. §6 notes how v3.2 uses the estimate.
- Related: [`api_contract.md`](./api_contract.md), [`app/nlu/README.md`](../app/nlu/README.md)
- Claim scope: see [§11](#11-claim-scope)

---

## 0. Summary

The recovery state is a latent variable, and observations are positive-censored and irregularly sampled. Under these conditions, a naive estimator passes only the positive part of the innovation, the difference between observation and expectation, so it is biased upward. The bias is larger for low-state users and can lead to choosing the wrong bottleneck axis. Using idle gaps and utterance probes together could recover part of the negative signal while keeping the no-penalty principle.

This structure can extend to research on probing, identifiability, and failure mechanisms.

---

## 1. Two Parts of the Engine

| Part | Components | Status in the rule-based MVP |
|---|---|---|
| Control | waypoint, downshift, replanning, η (step size) | Works without data, as a state machine and rules |
| Estimation | `v_t` (state), `velocity`, `gap`, `recovery_drag` | The assumptions in §3 are not met, which limits how the estimates can be interpreted |

The limits sit mainly in the estimation part, which depends on the assumption that `v_t` measures the actual state. A controller is only as reliable as the state representation grounded in its observations.

---

## 2. Engagement as Measurement

The probability that a user completes a mission depends on the latent state. Engagement can therefore be read as a noisy readout of that state, with the same structure as the Rasch model in item response theory (IRT).

For one axis (autonomy `v`) and a mission of difficulty `τ`:

```
P(E_t = 1 | v_t, τ) = σ( β (v_t − τ_t) )      # logistic, β = sensitivity
v_{t+1} = v_t + η·E_t − δ·(1−E_t) − λ          # rises on engagement, falls with avoidance and time
```

`E_t` is a Bernoulli measurement of `v`. These equations describe the assumed process used for analysis. They are not the engine's update rule, which §5 compares.

---

## 3. Limits of the Estimate: Six Causes

| # | Cause | Mechanism |
|---|---|---|
| RC1 | No-penalty design conflicts with identifiability | Avoidance, failure, and non-completion are not recorded, so observations are positive-censored. `v` on the mission-driven axes only rises, and the signal in `recovery_drag` weakens |
| RC2 | `v_t` is closer to accumulated activity than to state | `Δ` is a hand-set constant, so `v_t = v_0 + Σ(η·Δ of completed missions)`, clamped to [0, 1]. gap and drag become deterministic functions of activity. There is no independent readout |
| RC3 | The goal vector `g` is a template constant | `g` is a fixed value per goal type and is not estimated from an individual's actual goal. gap becomes the difference between a template constant and accumulated activity |
| RC4 | Irregular sampling | `v_t − v_{t-1}` assumes equal intervals, but target users return at irregular intervals |
| RC5 | Heterogeneous axes | The connection axis is location-based (GPS), which weakens the assumption that all axes are commensurable in `[0,1]³` |
| RC6 | No learning loop | η, Δ, α, and thresholds are all hand-set, with no data or ground-truth signal to calibrate them |

The engine is designed as an estimator plus a controller, but the MVP has no feedback to correct the estimate, so the controller runs as an open loop.

The rhythm axis behaves differently from RC1. It is an EMA over check-in presence and can fall through `α_down`. Days with no log at all are skipped, however, so idle days do not lower it.

---

## 4. Information Structure: What Avoidance Carries

The Fisher information about `v` in a single Bernoulli response is:

```
I(v) = β² · p(1−p),   p = σ(β(v−τ))
```

- It peaks at `p = 1/2`, so information is highest when mission difficulty `τ` is close to state `v`.
- Success on an easy mission (`τ≪v`, `p≈1`) carries almost no information, while failure carries a large surprise (`−log(1−p)`).
- A censored `E=0` contains the information that the user's state is lower than expected.

---

## 5. Half-Wave Rectification of the Innovation

Written formally as a state-space model (POMDP), the structure is as follows. This is notation for the analysis; the engine does not learn a POMDP.

```
v_t ──mission_rule π──▶ a_t (difficulty τ_t)
v_t ──emission──▶ E_t ~ Bern(σ(β(v_t−τ_t)))    # measurement channel
(v_t, E_t) ──transition f──▶ v_{t+1}            # true dynamics
E_t ──inference g──▶ v̂_{t+1}                     # representation update
```

The affected part is the emission→inference path in the last line (`E_t → v̂`). A Kalman or Bayesian update is:

```
v̂_{t+1} = v̂_t + K · (E_t − p̂_t)        # innovation = observation − expectation
```

Avoidance (`E=0`) is a negative innovation and lowers the estimate. Censoring does not cut this path. It removes only the negative part (half-wave rectification):

```
v̂_{t+1} = v̂_t + K · max(0, E_t − p̂_t)
```

Only upward corrections remain, so `v̂` rises monotonically. This mechanism explains the monotonic rise in RC1. What drops out is the negative part of the measurement→inference path, not the dynamics or the mission selection rule.

The engine's actual update is `v_{t+1} = v_t + η·Δ` with `Δ > 0` on the mission-driven axes, and it has no `p̂` term. Rejecting a mission does not change ARI. The equation above is an approximation that describes this positive-only structure.

---

## 6. Direction and Differential Size of the Bias

Observing only `E=1` means estimating conditional on `E=1` (selection on the dependent variable).

```
observed distribution = P(v | E=1) ≠ P(v)
```

`E=1` occurs more often at higher `v`, so `P(v|E=1)` has a higher mean and tends to have a smaller variance.

The size of this bias differs by user state.

```
The bias grows with the censoring probability P(E=0|v) = σ(β(τ−v)), which is larger at lower v
```

Low-state users avoid more, so more of their observations are censored and their state is overestimated. This can lead Goal-Based Intervention to choose the wrong bottleneck axis for them. In v3.2, `recovery_drag` feeds `bottleneck_axis`, which can replace today's card with a connection prompt, so the bias can reach the action the user sees.

---

## 7. Identifiability

From positive-only data:

| Target | Identifiability | Note |
|---|---|---|
| Order of `v`, engagement rate | Identified | |
| Level of `v` | Partially identified | The lower bound shifts upward at low `v` |
| Downward dynamics `δ, λ` (avoidance and decay rates) | Not identified | Decreases are never observed, so recovery speed can be estimated but relapse speed cannot |

---

## 8. Extensions: Recovering Negative Signal Under the No-Penalty Principle

### (a) Idle gap: right-censored inter-event time

Even if avoidance is not recorded as failure, the return time remains. Assuming that low-state users take longer to return, a survival or hazard model can be applied to return time.

```
P(return ≤ Δt | v) = 1 − exp(−h(v)·Δt),   h(v) = hazard rate (smaller at lower v)
```

The idle gap is a negative component that is not half-wave rectified, and it does not act on the user as a penalty or exposure. From this view, the irregular sampling in RC4 can also serve as information and could improve the identifiability of `δ, λ`.

### (b) Utterance probe: a second measurement channel

The engagement channel is selected on `E=1`. A probe that reads `v` from utterance embeddings can also use utterances from days when the user avoided a mission, so its selection structure differs. If the probe carries state signal, combining the two channels could widen the identified region of the latent state.

```
Channel 1 (engagement): selected on E=1, upward bias
Channel 2 (utterance probe): includes utterances on avoidance days, different selection
Combined: wider identified region for latent v
```

The design and research questions for utterance probing are in [`app/nlu/README.md`](../app/nlu/README.md).

---

## 9. Structural Analogy to Interpretability Research

This analysis resembles mechanistic interpretability in how it narrows down a failure point along the path from input to representation to behavior. It is an analogy of method: the state here is hand-designed, not a learned representation.

| Transformer interpretability | Doody engine |
|---|---|
| Observe a behavior (failure) | Goal-Based Intervention under-serves low-`v` users |
| Localize a circuit or path | The negative part of the measurement→inference path |
| Characterize the transformation | Half-wave rectification of the innovation |
| Derive the direction and size of a bias | Selection on the DV, upward bias, differential by `σ(β(τ−v))` |
| Predict and intervene on failure | Wrong axis at low `v`, corrected through idle gaps and probes |

---

## 10. Research Roadmap

| Stage | Work | Output |
|---|---|---|
| R0 (with the MVP) | Log `(state, recommendation, outcome proxy)` tuples, secure one independent readout (energy tap or utterance), record idle gaps | Data infrastructure |
| R1 (simulation) | Set true `δ, λ`, apply censoring, and examine the `v̂` bias at low `v` and the effect of the two recovery channels | Bias curves |
| R2 (probing) | Apply a linear probe or prototype similarity for rhythm, autonomy, and connection to utterance embeddings such as Ko-SBERT | RQ: do short utterances carry recovery-axis signal? |
| R3 (identification) | Censored-likelihood estimation combining the idle-gap hazard and the probe channel | Test of `δ, λ` identifiability |
| R4 (failure) | Analyze under which censoring conditions `recovery_drag` picks the wrong axis | Failure-mode map |

---

## 11. Claim Scope

- The bias analysis here is derived from the model structure. It is not a result measured on user data, and there is no ground truth for users' recovery.
- The claim that can be made today is: "this structure is expected to produce this bias, and the design takes it into account."
- This repository contains no measurement or simulation results for this bias.
- The ARI state is designed, not learned. Idle-gap and utterance-probe recovery are follow-up directions and have not been validated.
