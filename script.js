import { num, num0 } from "https://cdn.jsdelivr.net/npm/@gramex/ui@0.3/dist/format.js";
import { marked } from "https://cdn.jsdelivr.net/npm/marked@12/+esm";
import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6/+esm";
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { default as fuzzysort } from "https://cdn.jsdelivr.net/npm/fuzzysort@3/+esm";

// Load and display README content
const content = await fetch("README.md").then((r) => r.text());
document.querySelector("#README").innerHTML = marked.parse(content);

// Load and process model data
const models = (await d3.csv("elo.csv"))
  .filter((d) => d.cpmi)
  .map((d) => ({
    ...d,
    cost: +d.cpmi,
    elo: +d.elo,
  }));

const dates = Array.from(new Set(models.map((d) => d.launch))).sort();
const $date = document.querySelector("#date");
$date.setAttribute("max", dates.length - 1);
$date.value = dates.length - 1;

const xScale = d3
  .scaleLog()
  .domain(d3.extent(models, (d) => d.cost))
  .range([0, 1000]);
const yScale = d3
  .scaleLinear()
  .domain(d3.extent(models, (d) => d.elo))
  .range([500, 0]);

const updateOptimalStatus = (filteredModels) => {
  filteredModels.forEach((model) => {
    model.optimal = filteredModels.every(
      (other) => other === model || other.elo <= model.elo || other.cost >= model.cost,
    )
      ? "best"
      : filteredModels.every((other) => other === model || other.elo >= model.elo || other.cost <= model.cost)
        ? "worst"
        : "";
  });
};

const renderPlot = (filteredModels) => {
  const plot = Plot.plot({
    marginLeft: 50,
    x: { type: "log", grid: true, domain: xScale.domain() },
    y: { grid: true, domain: yScale.domain() },
    width: 1000,
    height: 500,
    marks: [
      Plot.dot(filteredModels, {
        x: "cost",
        y: "elo",
        r: 8,
        fill: (d) =>
          d.optimal === "best" ? "lime" : d.optimal === "worst" ? "red" : "rgba(var(--bs-body-color-rgb), 0.1)",
        stroke: "black",
        strokeWidth: 0.5,
        channels: { model: "model" },
        tip: {
          fill: "var(--bs-body-bg)",
          format: {
            fill: false,
            x: (d) => `$${num(d.cost)} / MTok`,
            y: (d) => num0(d.elo),
          },
        },
      }),
      Plot.text(
        filteredModels.filter((d) => d.optimal),
        {
          x: "cost",
          y: "elo",
          text: (d) => d.model,
          dy: -10,
          lineAnchor: "bottom",
        },
      ),
      Plot.axisX({ label: "Cost per million input tokens" }),
      Plot.axisY({ label: "ELO score", tickSpacing: 100 }),
    ],
  });
  document.querySelector("#llm-cost").replaceChildren(plot);

  // Add nodes to models for search functionality
  const circles = document.querySelectorAll("#llm-cost circle");
  models.forEach((model, i) => (model.node = circles[i]));
};

const update = () => {
  const date = dates[$date.value];
  document.querySelector("#date-label").textContent = d3.timeFormat("%b %Y")(d3.timeParse("%Y-%m")(date));

  const search = document.querySelector("#model").value.trim();
  const results = fuzzysort.go(
    search,
    models.map((m) => m.model),
    { threshold: -20 },
  );
  const matches = new Set(results.map((r) => r.target));

  const filteredModels = models.filter((d) => d.launch <= date && (search ? matches.has(d.model) : true));
  updateOptimalStatus(filteredModels);
  renderPlot(filteredModels);
};

$date.addEventListener("input", update);
document.querySelector("#model").addEventListener("input", update);
update();
