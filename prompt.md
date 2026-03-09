# Prompts

## Analogies

Introduce annotations on the Y axis, ELO score, to show what the numbers mean in terms of model quality. Think about the best way to do this visually and apply it. It should not be too in-your-face but should be highly discoverable and intuitive.

Here's research on how to interpret LMArena ELO scores. Use it as you think best. Feel free to use popups as appropriate. Though the content below is dense, you may ignore most of it, picking only what's important.

---

**First, a critical caveat:** LMArena Elo is _not_ the same scale as chess Elo, even though both start at 1000. All models begin with an initial score of 1000, and the _entire meaningful range_ of AI quality is compressed into just ~1000–1510. As of March 5, 2026, the absolute top of the leaderboard is Claude Opus 4.6 at 1504 Elo. So a 500-point range contains the full spectrum from "barely functional chatbot" to "best AI humanity has ever built." In chess, 500 points is the difference between a beginner and a club player. Keep that compression in mind when reading the analogies below.

The Three Analogy Frameworks: I'm giving you three lenses, each calibrated to the actual model landscape. Pick whichever ones click for you.

**Framework A: Education & Academic Progression**
_(Best for: general audiences, knowledge depth, reasoning quality)_

| Elo        | Real models at this level (then/now)               | Analogy                                                                                                                                                |
| ---------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **~1000**  | Earliest Vicuna, basic open-source chatbots (2023) | 🧒 **Middle schooler** — can answer simple factual questions, writes at a basic level, makes frequent errors on anything nuanced                       |
| **~1100**  | Early small open-source models (7B era)            | 🎒 **High school freshman** — handles basic essays and simple research; frequently wrong on complex or ambiguous topics                                |
| **~1200**  | GPT-3, early Llama 2, Mistral 7B                   | 🎓 **High school graduate** — solid general knowledge, decent writing, can follow instructions well, but no deep expertise in anything                 |
| **~1300**  | GPT-3.5-turbo (peak), Claude 1, Llama 3 8B         | 📚 **College junior** — can write competently on most academic topics, good reasoning, handles complexity but makes meaningful errors on hard problems |
| **~1350**  | Claude 2, Gemini Pro (original)                    | 🏫 **Recent college grad / entry analyst** — broadly capable, good for most everyday professional tasks, occasionally shaky on expert-level questions  |
| **~1400**  | GPT-4 (original), Claude 3 Sonnet, Llama 3 70B     | 🎓 **Master's student** — strong reasoning, solid writing, handles most professional tasks well; clearly better than most generalists                  |
| **~1450**  | Claude 3.5 Sonnet (original), GPT-4o               | 🔬 **PhD candidate mid-program** — approaching genuine expert-level on many topics, synthesizes across fields, rarely makes embarrassing errors        |
| **~1480**  | Gemini 3 Pro, GPT-5.2                              | 🏛 **Tenured professor / domain expert** — routinely handles tasks that would stump most educated humans; deep on most subjects                        |
| **~1500+** | Claude Opus 4.6, Gemini 3.1 Pro Preview            | 🏆 **Polymath scholar / world-class generalist** — top 1% of all models ever built; the best AI reasoning currently available to humanity              |

**Framework B: Chess Player Skill** _(structural analogy — same Elo math, different absolute scale)_

This one is counterintuitive but illuminating: in LMArena, scores of 1300+ represent exceptional performance only reached by the most advanced models like GPT-4, Claude, and Gemini — whereas in actual chess, 1300 is a casual weekend club player. The _compression_ of the AI scale is the insight here.

| Elo        | Chess equivalent                                     | What it means for AI                                               |
| ---------- | ---------------------------------------------------- | ------------------------------------------------------------------ |
| **~1000**  | Absolute beginner (just learned the pieces)          | Chatbot that can hold a basic conversation but often nonsensical   |
| **~1100**  | Casual player (knows tactics, loses to club players) | Functional but clearly outclassed by better models                 |
| **~1200**  | Club player (plays tournaments, mid-table finisher)  | Solid for simple tasks; a decent everyday tool                     |
| **~1300**  | Strong club / regional competitor                    | Genuinely useful for most professional tasks                       |
| **~1400**  | Expert / approaching Candidate Master                | Competitive with experienced human professionals                   |
| **~1450**  | National Master strength                             | Noticeably better than most humans on almost any intellectual task |
| **~1480**  | International Master territory                       | Rare-level capability; handles genuinely hard problems             |
| **~1500+** | Grandmaster                                          | Best-in-class, period                                              |

_(Note: In real chess, Grandmasters are ~2500+. The analogy compresses dramatically — the entire AI quality distribution fits where chess puts "beginner to solid club player.")_

**Framework C: Workplace Seniority**
_(Best for: business audiences, evaluating whether to trust a model with professional tasks)_

| Elo        | Analogy                                 | Would you trust them to...                                                     |
| ---------- | --------------------------------------- | ------------------------------------------------------------------------------ |
| **~1000**  | 🆕 Intern, day 1                        | Draft a first-pass email, nothing more                                         |
| **~1100**  | Junior analyst (6 months in)            | Basic research, simple summaries                                               |
| **~1200**  | Analyst (1–2 years)                     | Solid deliverables on routine tasks; needs review                              |
| **~1300**  | Senior analyst / associate              | Most business writing, analysis, coding tasks                                  |
| **~1350**  | Manager                                 | Independent work on complex projects, with occasional blind spots              |
| **~1400**  | Senior manager / experienced consultant | High-quality, near-publication-ready output most of the time                   |
| **~1450**  | Director / principal                    | Handles ambiguous, multi-step problems; judgment is good                       |
| **~1480**  | VP / Partner                            | Rarely makes embarrassing errors; strategic depth visible                      |
| **~1500+** | Chief of Staff / Senior Partner         | Best-in-class thinking; you'd hire them over most humans for intellectual work |

A key thing to internalize: a 50-point ELO difference indicates a substantial advantage, meaning the higher-rated model wins significantly more often in head-to-head comparisons. So the gap between 1300 and 1500 — which is "college junior" vs. "polymath scholar" in Framework A — is genuinely enormous. Models at 1500 would beat 1300-rated models in roughly **76% of head-to-head matchups.**

Also worth noting: 1000–1100 represents basic conversational ability but with frequent errors, and early or smaller models typically score in this range; 1100–1200 shows competent performance with noticeable improvements, and many current open-source models fall here. The "floor" of the useful scale has shifted upward fast — what was 1300 in 2023 is now ordinary.

## billing.py

> Created by [Claude 3.7 Sonnet](https://claude.ai/share/3196a0a7-15f9-4064-ab00-af080edc8741) and [commited](https://github.com/sanand0/llmpricing/blob/9b66480458b712de52ea14502a64bf4c3b6a98ed/billing.py).

Write a concise, minimal Python script that fetches https://openrouter.ai/api/frontend/models

Extract the following information into a endpoints dict:

- id: .data[].endpoint.id
  - model_slug: .data[].endpoint.model.slug
  - pricing_completion: .data[].endpoint.pricing.completion

Then, in groups of 10, fetch the througput stats
https://openrouter.ai/api/frontend/stats/throughput-comparison?ids={",".join(ids)}

The response is like:

```json
{
  "data": [
    {
      "x": "2025-04-24 00:00:00",
      "y": {
        "id1": 57.197,
        "id2": 96.098,
        "id3": 37.0765,
        ...
      }
    }
  ]
}

Add the average "y" value by id to endpoints[id]["throughput"].
Calculate the endpoint's "billing_rate" as pricing_completion ($/token) * throughput (tokens/second) * 3600 (seconds per hour).
For all fetch requests, show progress via tqdm.

Style:
- Use httpx (same API as requests)
- Write SHORT, CONCISE, READABLE code
- Write modular code (iteration, functions). No duplication
- Use functions, not classes
- Validate early. Use the if-return pattern. Avoid unnecessary else statements
- Avoid try blocks unless the operation is error-prone
```
