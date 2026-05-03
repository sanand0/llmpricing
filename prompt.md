# Prompts

## Deprecations, 29 Apr 2026

<!--
cd /home/sanand/code/llmpricing
dev.sh
copilot --yolo --model gpt-5.4 --effort medium
-->

Update the "end" column in elo.csv with the deprecation/shutdown dates documented at:

- https://developers.openai.com/api/docs/deprecations.md
- https://platform.claude.com/docs/en/about-claude/model-deprecations.md
- https://ai.google.dev/gemini-api/docs/deprecations

Use sub-agents if required for token efficiency.

<!-- copilot --resume="Update Elo CSV End Dates" --yolo -->

## Update Elo, 1 Apr 2026 (GitHub Copilot - GPT 5.4 xhigh)

<!-- copilot --yolo --model gpt-5.4 --effort xhigh -->

Write a Python script update_elo.py that can be run as:

```bash
uv run update_elo.py file.txt --column column
```

This should read file.txt as a TSV file. Ignore the header and treat the two columns as model and $column (e.g. if the CLI argument is `--column code` then the second column is `code`).

If the model is present in elo.csv, update the corresponding $column value in elo.csv with the value from file.txt.
If the model is not present in elo.csv, add a new row with the model and the $column value, and set the "launch" column to the previous month with a question mark (e.g. "2024-05?").
Search for the pricing using OpenRouter's models endpoint (the model may be named differently in OpenRouter - see elo.csv to see if you can find a robust fuzzy match but avoid incorrect matches) and when you find a match, update the cpmi (cost per million tokens) column in elo.csv with the pricing information, as well as the "source" column.

Run and test using `text.txt`, `hard.txt` and `code.txt` (which are named after the columns). Revert elo.csv to its original state to retest if needed.

---

If cpmi, launch, end, or source exist, do NOT update it.

Insert new models just above the first model with $column value lower than the new model, so the file remains (roughly) sorted by $column.

If a model is not present when the $column is "overall", and "end" is not present, set "end" to the current month with a question mark (e.g. "2024-06?").

Run and test.

---

Find any opportunities to simplify the code, make it more elegant and maintainable.

---

If the model launch date can be inferred from openrouter, update it where it is missing.

---

If you get the launch date from OpenRouter, no need to add the ? after the date.

---

Modify the visualization to ignore any models with a missing ELO score (overall, coding, or hard).

---

In the visualization, the hover tooltip shows fillOpacity, strokeOpacity and strokeWidth. Remove these from the tooltip. cost, elo, and model are shown and should remain.

--- <!-- 12 Apr 2026, gpt-5.4 medium -->

Currently, if a model is missing ANY ELO score (overall, coding, or hard), it is hidden in ALL views.
Instead, change it so that if only coding is missing, it is hidden in the coding view, etc.

---

Now NOTHING is visible, i.e. no models!

---

Actually, normalizing quality URL aliases wasn't the problem, so I undid the change.

The problem is that if the cpmi value is zero, script.js fails. So, make two changes, minimally.

1. Modify script.js to ignore rows with cpmi of zero
2. Modify update_elo.py to set a blank cpmi if the value is zero

<!-- copilot --resume=60cd6f58-38f7-4f45-b4a9-294e7ad04f18 -->

## Scrolly v2

<!-- copilot --yolo --model claude-sonnet-4.6 --effort high -->

Add a scrollytelling narrative.

Do not disturb the current screen. But when the user scrolls further down, below the chart, the scrollytelling should smoothly appear as glassmorphism or semi-transparent cards that occupy a small portion of the screen positioned horizontally so that they don't overlap too much of the important content in the chart (e.g. models to highlight), and not too tall and with plenty of gap between cards (half a screen, maybe) so that users can see the visual between the cards.

Think about the effect this will have while people are reading, and aim for high engagement.

As they scroll down, the cards and the month slider should smoothly move to the earliest month, and then animate month by month on scroll, and explaining the key events and insights in terms of model quality and pricing. Use the data story skill to do this effectively, narrating like Malcolm Gladwell, preserving the visual style of the page, using the education progression as a framework for measure of intelligence (read prompts.md for context). Highlight specific models to support the story.

Begin by explaining the axes and the annotations on the right "HS freshman", etc. at the start of the story. Explain the X-axis - cost per million - intuitively, e.g. "That's roughly the cost to process all 7 volumes of Harry Potter or the King James Bible" (I think - but check this and give a good intuitive sense of the cost).

Augment the story with authoritative external references, expert commentary, benchmarks, and critical insights. Link to these (opening in a new tab) as part of the story cards.

Use the data story skill to explain the IMPLICATIONS (especially business implications) in a compelling way.

Store the narrative text in a separate JSON file and read from it. This should control the entire narrative, including what month to jump to next, what models to highlight, what insights to share, and so on.

Make edits incrementally to avoid large output (over 32K output tokens) that might fail.

---

I'd like the cards to scroll as the user scrolls.
#chart-sticky can have a top of var(--navbar-height) + some gap.
I'd like the circles to have the same size they originally did.
MILDLY fade out the non-highlighted models and their labels (if any) so that the highlighted model is far more visually prominent, but the others are still visible and can be read if the user wants to.
Make the content more scannable - just reading the stuff in bold should tell them the crux of the story.

---

The cards should be ABOVE the chart. Update z-index.
Fact-check the contents of the cards CAREFULLY. Edit as required - ensuring high engagement and insight.
Allow scrolling the last card as well, so that it vanishes on top too, with them seeing the final version of the chart with the models and being able to explore them.

---

Time the stories when all models in the story are visible. For example, we mention "Haigh: college-grad capability" when it is not visible.
Keep in mind that this will be updated constantly - so avoid things that will need to be constantly updated, e.g. "how the world got there - in 27 months". Keep cards independent and timeless.

---

Too much in bold. The bold text should still convey the story, but with less in bold.

---

At the end of the story, allow the last card to scroll well past the top of the screen. Make sure I can see the entire chart, filters, etc. and all the models are visible and I can explore the visualization again after scrolling past the bottom.

## Scrolly v1 (GitHub Copilot - Claude Sonnet 4.6 high)

Add a scrollytelling narrative. So, when users first visit the page, they see roughly the same thing as now (but prettier). As they scroll down, the page should smoothly move to the earliest month, and then animate month by month on scroll, and explaining the key events and insights in terms of model quality and pricing. Use the data story skill to do this effectively, narrating like Malcolm Gladwell, with the visual style of The New York Times, using the education progression as a framework for measure of intelligence (read prompts.md for context). Store the narrative text in a separate JSON file and read from it. This should control the entire narrative, including what month to jump to next, what models to highlight, what insights to share, and so on.

---

Augment the story with authoritative external references, expert commentary, benchmarks, and critical insights. Link to these (opening in a new tab) as part of the story.

---

It should begin with the full page visual along with the dropdown to select Overall/Coding/Hard, the model search filter, the timeline slider, and legends. The user should begin by being able to explore the screen. Retain the original layout for that.

THEN, when the user scrolls down, the scrollytelling should smoothly appear - while the dropdown, model search filter, timeline slider, etc. vanish. It can appear as glassmorphism or semi-transparent cards that occupy a third or quarter of the screen on the center, left, or right as specific models get highlighted. Allow some whitespace between the cards. Break the story up into smaller sections. Think about the effect this will have while people are reading, and aim for high engagement. If required, make it more concise for this.

The other models are currently greyed out strongly - allow them a _bit_ more visibility.

Highlight the annotations on the right "HS freshman", etc. at the start of the story and explain the Y axis. Also the X-axis - cost per million. That's roughly the cost to process all 7 volumes of Harry Potter or the King James Bible I think - but check this and give a good intuitive sense of the cost.

Use the data story skill to explain the IMPLICATIONS (especially business implications) in a compelling way.

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
