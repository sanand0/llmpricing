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

Last updated: **01 Jan 2025**

Alternatives: [ArtificialAnalysis.ai](https://artificialanalysis.ai/)

<!--

# How to update

- Visit <https://lmarena.ai/?leaderboard>
- Click on "New: Overview"
- Click on "Sort by Arena Score" button
- Copy the JSON from the event stream at `data?session_hash=...`
- Format the data: event stream as JSON in VS Code
- Extract the "data": array of arrays as a table via https://tools.s-anand.net/json2csv/
- Update `elo.csv` via lookups with the STYLE CONTROLLED Elo scores

-->
