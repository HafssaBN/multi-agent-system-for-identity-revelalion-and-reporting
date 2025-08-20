

# How the whole thing works

This repo implements a **multi-agent deep research pipeline**.
Think of it as a team of different AIs with different roles: some **search**, some **summarize**, and one **judge** ranks the results.

It’s designed to be:

* **Robust** (reduce bias, variance, position effects).
* **Configurable** (committee vs router).
* **Auditable** (every step is traced as JSON).

---

## 1) The research loop (MoA for *research*)

This is the **multi-agent orchestration** that gathers information:

1. **Planner**

   * A strong LLM decides what to do next (search query, image lookup, tool call).

2. **Workers / Proposers**

   * One or more diverse models actually run the searches, scrape snippets, and propose **candidates** (e.g. “this page looks relevant”).

3. **Aggregator**

   * A model summarizes the notes from workers so we don’t drown in raw snippets.

This forms the **Mixture of Agents (MoA)**:
Different models do different jobs so we avoid the “single-model bias” problem.

---

## 2) Candidate picking (the **Judge** step)

Once we’ve searched, we now have a **list of possible matches (candidates)**:

```json
[
  {"name": "Trafalgar Square - Wikipedia", "url": "https://en.wikipedia.org/wiki/Trafalgar_Square", "why": "Reverse image search match"},
  {"name": "Visit London - Trafalgar Square", "url": "https://www.visitlondon.com/..."},
  {"name": "Commons file Whitehall.jpg", "url": "https://commons.wikimedia.org/..."}
]
```

The **Judge** gets this **full JSON list** (not just the top 5 shown in traces).
It then ranks/picks them using the **research brief + worker notes**.

There are two modes:

---

### A) Committee (MoA for *judging*)

* Config: `JUDGE_ENABLE_COMMITTEE=1`
* Uses **multiple judge models** (`JUDGE_COMMITTEE_MODELS`).
* Each model **votes** on the winner.

Extra guardrails:

* **Swap** order → mitigates position bias (don’t always show candidate\[0] first).
* **Self-consistency** → shuffle candidates, ask again, average results.

📊 **Result**: votes are tallied, and the candidate with the most votes wins.
*Pros*: robust, fairer, less biased.
*Cons*: more tokens, slower, higher cost.

---

### B) Router / SMoA (pick one judge model)

* Config: `JUDGE_ENABLE_ROUTER=1`, `JUDGE_ENABLE_COMMITTEE=0`
* A **lightweight router** chooses **one judge model** from a pool.

  * Based on **aspect** (relevance, factuality, safety).
  * Based on **cost weights** (`JUDGE_MODEL_COST`).
* Optional **gates** (`JUDGE_SMOA_GATES`) restrict the router to a shortlist for each aspect.

📊 **Result**: cheaper, faster.
*Pros*: cost-efficient, low latency.
*Cons*: no voting — if the chosen model makes a mistake, it sticks.

---

## 3) What each constant actually does

* **`JUDGE_MODEL`**
  Default single judge (used if no committee/router is enabled).

* **`JUDGE_COMMITTEE_MODELS`**
  The **set of judges** used for voting.

* **`JUDGE_SMOA_GATES`**
  Optional shortlists per aspect.
  Example: only allow `relevance` decisions to use certain cheaper models.

* **`JUDGE_MODEL_COST`**
  Router weights — prefer cheaper models when results are similar.

* **Bias & variance controls**

  * `JUDGE_ENABLE_SWAP` → randomly swap first two candidates to reduce position bias.
  * `JUDGE_ENABLE_SELF_CONSISTENCY` + `JUDGE_SELF_CONSISTENCY_RUNS` → shuffle and re-ask to reduce variance.

* **Thresholds**

  * `JUDGE_PAUSE_THRESHOLD` → if average confidence below this, pause for human.
  * `JUDGE_DELTA_THRESH` → if top 2 are too close, pause for human.
  * `JUDGE_MIN_CONF_FOR_AUTOPASS` → if confidence is very high, auto-accept.

---

## 4) How the judge actually works (step-by-step)

1. **Normalize candidates** → all names, URLs, reasons cleaned.
2. **Build full JSON** → entire candidate list goes into the judge prompt.
3. **Run models**

   * If committee: multiple models, multiple runs (swap + shuffle).
   * If router: one selected model.
4. **Voting**

   * Each run produces a `winner_index` + confidence.
   * Mapped back to the original candidate.
   * Votes are tallied across models/runs.
5. **Final decision**

   * Candidate with most votes wins.
   * If tie or low confidence → flagged for human.

✅ **So yes: the judge always sees the entire candidate list, not just a preview.**

---

## 5) JSON parse errors — why they happen

Sometimes a judge model returns junk (empty, markdown, half JSON).
We already guard against this:

* Regex extraction of the first `{...}` block.
* Retry with stricter “return only JSON” instruction.
* If all fails: safe default (`winner_index=None` → pause for human).

Stable models: `qwen/qwen3-32b`, `gemma-2-27b-it`.
Flaky models: some free tier smaller ones.

---

## 6) When to use Committee vs Router

* **Cost-first (router)**

  * Enable router, disable committee.
  * Use cheap + stable models, add cost weights.
  * Good for **large batch runs** where accuracy is “good enough.”

* **Robust-first (committee)**

  * Disable router, enable committee.
  * 2–3 strong models, swap+shuffle.
  * Good for **sensitive/final decisions** where correctness matters.

---

## 7) Example ready configs

### A) Cost-first (router only)

```bash
JUDGE_ENABLE_ROUTER=1
JUDGE_ENABLE_COMMITTEE=0
JUDGE_MODEL="z-ai/glm-4.5-air:free"
JUDGE_SMOA_GATES='{
  "relevance": ["z-ai/glm-4.5-air:free","qwen/qwen3-32b","google/gemma-2-27b-it:free"]
}'
JUDGE_MODEL_COST='{
  "z-ai/glm-4.5-air:free": 0.4,
  "qwen/qwen3-32b": 0.6,
  "google/gemma-2-27b-it:free": 0.5
}'
JUDGE_ENABLE_SELF_CONSISTENCY=1
JUDGE_SELF_CONSISTENCY_RUNS=2
JUDGE_ENABLE_SWAP=1
```

### B) Robust-first (small committee)

```bash
JUDGE_ENABLE_ROUTER=0
JUDGE_ENABLE_COMMITTEE=1
JUDGE_MODEL="z-ai/glm-4.5-air:free"
JUDGE_COMMITTEE_MODELS='[
  "z-ai/glm-4.5-air:free",
  "qwen/qwen3-32b"
]'
JUDGE_ENABLE_SELF_CONSISTENCY=1
JUDGE_SELF_CONSISTENCY_RUNS=2
JUDGE_ENABLE_SWAP=1
```

---

## 8) Bottom line

* The **research loop** already uses MoA (planner, workers, aggregator).
* The **judge** step can be either:

  * **Committee** → robust, slower, more cost.
  * **Router** → faster, cheaper, less robust.
* The **judge always gets the full candidate JSON** (not just a preview).
* JSON errors are a model-stability issue, not a logic bug.


