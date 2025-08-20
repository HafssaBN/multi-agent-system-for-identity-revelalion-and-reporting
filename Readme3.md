

### 1. What the **XAI_judge** is doing

* The **judge** must pick **which candidate is best** (from the list of search results).
* Sometimes, LLMs are biased by **the order** of candidates.
  Example: if the “best” result is put **first**, the model may pick it just because it’s first.

---

### 2. What this file adds

This file is just a **checker**:
👉 It asks **“does the judge change its mind if I swap the first two candidates?”**

---

### 3. How it works

* The judge runs twice:

  1. **Base** → candidates in normal order.
  2. **Swap** → first two candidates swapped.

* For each run, the model picks a winner.
  Then this file checks:

  * If the winner is **the same** in base vs swap → ✅ stable.
  * If the winner **changes** → ⚠️ position bias.

---

### 4. The output JSON (simplified)

This file returns something like:

```json
{
  "position_bias_rate": 0.25,
  "swap_total": 12,
  "swap_flips": 3,
  "per_model": [
    {
      "model": "qwen/qwen3-32b",
      "runs": [
        {"base": 2, "swap": 2},
        {"base": 1, "swap": 0}
      ]
    }
  ]
}
```

* `swap_total = 12` → we ran 12 base/swap comparisons.
* `swap_flips = 3` → in 3 cases, the winner changed after swapping.
* `position_bias_rate = 3 / 12 = 0.25` (25% bias).
* `per_model` → details per judge model.

---

### 5. Why this matters

If **position\_bias\_rate** is high:

* It means the judge may not really understand the content.
* It may just pick based on position (e.g., “top of the list looks best”).
* You might want to:

  * Add more models (committee voting).
  * Shuffle candidates more often.
  * Pause for a human.

---

✅ So in one sentence:
This file **measures how much the judge’s choice changes if you swap candidate order** — a way to detect position bias.

