# LLM Pricing

The cost of LLMs is steadily falling, and the quality is rising.

A rough estimate of the **cost of an LLM** is a representative API input price per million tokens.
Prefer standard, durable pricing from first-party or mainstream providers (for example OpenAI, Anthropic, Google, AWS/Azure, DeepInfra, Together, Fireworks, Cloudflare, or Alibaba) over unusually cheap small-provider routes, Flex/Batch tiers, or temporary promotions. For legacy models, retain a defensible historical mainstream API price and end date; leave cost blank when no comparable easy-to-use API price is available.

Each model has one representative price, not a historical price series. The month slider therefore shows how today's/historically-audited model economics compare across model lifetimes; it should not be read as an exact invoice price for that past month.
(Typically, inputs are the bigger component of the cost, compared to outputs.)

A rough estimate of the **quality of an LLM** is
the ELO score on the [LMSYS Leaderboard](https://arena.ai/).
(This is like the chess ELO score, but for LLMs, where people compare 2 LLMs on the same task.)
Pre-Arena API models such as GPT-3 Davinci and text-davinci-003 are retained in `elo.csv` with launch/price/end metadata but blank Elo; they provide historical context without mixing incompatible quality benchmarks into the chart or Pareto frontier.

This chart shows the cost and quality of each LLM.

Some LLMs are "pareto optimal", i.e. there is no LLM better in both cost and quality.
These are shown in green 🟢 and are the best LLMs to use.

Some LLMs are "pareto suboptimal", i.e. there is no LLM worse in both cost and quality.
These are shown in red 🔴 and are the LLMs to avoid.

Last updated: **4 Oct 2026**

Alternatives: [ArtificialAnalysis.ai](https://artificialanalysis.ai/)

<!--

# How to update

Start a browser with Chrome DevTools Protocol available at `localhost:9222`, then run:

```bash
just build
```

This downloads all three Arena leaderboards to temporary TSV files and updates `elo.csv`.

Run `just push` to stage all changes, commit them as `Update models`, and push.

- https://arena.ai/leaderboard/text
- https://arena.ai/leaderboard/text/hard-prompts
- https://arena.ai/leaderboard/text/coding

For a single leaderboard, run:

```bash
uv run download.py https://arena.ai/leaderboard/text file.txt
uv run update_elo.py file.txt --column overall
```

Use `--column hard` for `/hard-prompts` and `--column coding` for `/coding`.
The TSV includes `Model`, `Score`, and `Price $/M` (input/output dollars per million tokens).
The updater fills blank costs from the input price, preserves existing costs, and prints
differences as `Model\telo.csv\tarena.ai`. Arena prices marked `N/A` remain unfilled.
OpenRouter supplies launch and end dates, but does not supply costs in this flow.

`download.py --describe` prints the machine-readable CLI contract.

`download.py` evaluates this script in the page via CDP:

```js
const rows = $$("table tr");
const headers = [...rows[0].querySelectorAll("th, td")].map(d => d.innerText.trim());
const priceIndex = headers.indexOf("Price $/M");
if (priceIndex < 0) throw new Error("Arena table is missing Price $/M");
["Model\tScore\tPrice $/M", ...rows.slice(1).map(d => {
  const cells = d.querySelectorAll("td, th");
  const [model, score] = [(cells[2].querySelector("a")?.innerText ?? cells[2].innerText).split(/\n/)[0], cells[3].innerText.split(/\s/)[0]];
  const price = cells[priceIndex].innerText.trim();
  return `${model}\t${score}\t${price}`;
})].join("\n");
```

# Billing rates

`billing.py` was created in May 2025 to estimate per-hour output "billing rates" in
`billing.json` from OpenRouter completion pricing and throughput stats. It worked when
it was created, but the OpenRouter frontend endpoints it used no longer work with the
script as written. It is kept as historical context and is not part of the `elo.csv`
update flow.

Blog post: https://www.s-anand.net/blog/wage-rates-of-nations-and-llms/
ChatGPT analysis: https://chatgpt.com/share/68317a06-0cac-800c-ad6f-13646ceb489f

# Screenshots

Create or update screenshots of the charts with:

```bash
uv run screenshots.py --model gpt,gemini,claude [--force]
```

Create videos with:

```bash
ffmpeg -framerate 2 -i screenshots/gpt-%03d.png -c:v libvpx-vp9 -pix_fmt yuva420p screenshots/gpt.webm
```

-->
