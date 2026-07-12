# LLM Pricing

The cost of LLMs is steadily falling, and the quality is rising.

A rough estimate of the **cost of an LLM** is
the cost per million tokens of input, mostly from [OpenRouter](https://openrouter.ai/models).
(Typically, inputs are the bigger component of the cost, compared to outputs.)

A rough estimate of the **quality of an LLM** is
the ELO score on the [LMSYS Leaderboard](https://lmarena.ai/).
(This is like the chess ELO score, but for LLMs, where people compare 2 LLMs on the same task.)

This chart shows the cost and quality of each LLM.

Some LLMs are "pareto optimal", i.e. there is no LLM better in both cost and quality.
These are shown in green 🟢 and are the best LLMs to use.

Some LLMs are "pareto suboptimal", i.e. there is no LLM worse in both cost and quality.
These are shown in red 🔴 and are the LLMs to avoid.

Last updated: **12 Jul 2026**

Alternatives:
[ArtificialAnalysis.ai](https://artificialanalysis.ai/)
[Gert Labs](https://gertlabs.com/rankings)

<!--

# How to update

Start a browser with Chrome DevTools Protocol available at `localhost:9222`, then run:

```bash
./update.sh
```

This downloads all three LMArena leaderboards to temporary TSV files and updates `elo.csv`:

- https://lmarena.ai/leaderboard/text
- https://lmarena.ai/leaderboard/text/hard-prompts
- https://lmarena.ai/leaderboard/text/coding

For a single leaderboard, run:

```bash
uv run download.py https://lmarena.ai/leaderboard/text file.txt
uv run update_elo.py file.txt --column overall
```

Use `--column hard` for `/hard-prompts` and `--column coding` for `/coding`.
`download.py --describe` prints the machine-readable CLI contract.

`download.py` evaluates this script in the page via CDP:

```js
$$("table tr").map(d => {
  const cells = d.querySelectorAll("td, th");
  const [model, score] = [(cells[2].querySelector("a")?.innerText ?? cells[2].innerText).split(/\n/)[0], cells[3].innerText.split(/\s/)[0]];
  return `${model}\t${score}`;
}).join("\n");
```

# Billing rates

`billing.py` was created in May 2025 to estimate per-hour output "billing rates" in
`billing.json` from OpenRouter completion pricing and throughput stats. It worked when
it was created, but the OpenRouter frontend endpoints it used no longer work with the
script as written. It is kept as historical context and is not part of the `elo.csv`
update flow.

Blog post: https://www.s-anand.net/blog/wage-rates-of-nations-and-llms/
ChatGPT analysis: https://chatgpt.com/share/68317a06-0cac-800c-ad6f-13646ceb489f

-->
