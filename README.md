# LLM Pricing

The cost of LLMs is steadily falling, and the quality is rising.

A rough estimate of the **cost of an LLM** is
the cost per million tokens of input, mostly from [LLMPriceCheck](https://llmpricecheck.com/).
(Typically, inputs are the bigger component of the cost, compared to outputs.)

A rough estimate of the **quality of an LLM** is
the ELO score on the [LMSYS Leaderboard](https://lmarena.ai/).
(This is like the chess ELO score, but for LLMs, where people compare 2 LLMs on the same task.)

This chart shows the cost and quality of each LLM.

Some LLMs are "pareto optimal", i.e. there is no LLM better in both cost and quality.
These are shown in green 🟢 and are the best LLMs to use.

Some LLMs are "pareto suboptimal", i.e. there is no LLM worse in both cost and quality.
These are shown in red 🔴 and are the LLMs to avoid.

Last updated: **02 Nov 2025**

Alternatives: [ArtificialAnalysis.ai](https://artificialanalysis.ai/)

<!--

# How to update

Go to each of these pages:

- https://lmarena.ai/leaderboard/text
- https://lmarena.ai/leaderboard/text/hard-prompts
- https://lmarena.ai/leaderboard/text/coding

Paste this bookmarklet:

```js
copy($$("table tr").map(d => {
  const cells = d.querySelectorAll("td, th");
  const [model, score] = [cells[2].innerText, cells[3].innerText.split(/\s/)[0]];
  return `${model}\t${score}`;
}).join("\n"));
```

[Update the sheet](https://docs.google.com/spreadsheets/d/1K6ftVTjDxc-s1gY6cqUiUNa2kW4NjaVClr8__oIimTM/edit) via lookups.

Download and save as elo.csv.

# Billing rates

Run `uv run billing.py` to get the per-hour output "billing rates" of LLMs in billing.json.

Blog post: https://www.s-anand.net/blog/wage-rates-of-nations-and-llms/
ChatGPT analysis: https://chatgpt.com/share/68317a06-0cac-800c-ad6f-13646ceb489f

-->
