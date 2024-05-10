import { num, num0 } from "https://cdn.jsdelivr.net/npm/@gramex/ui@0.3/dist/format.js";
import { marked } from "https://cdn.jsdelivr.net/npm/marked@12/+esm";
import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6/+esm";
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";

const content = await fetch("README.md").then((r) => r.text());
document.querySelector("#README").innerHTML = marked.parse(content);

const models = (await d3.csv("elo.csv")).filter((d) => d.cpmi);
models.forEach((d) => {
  d.cost = +d.cpmi;
  d.elo = +d.elo;
});
// model.optimal = "best" if no model has higher ELO and lower cost
// model.optimal = "worst" if no model has lower ELO and higher cost
models.forEach((model) => {
  let isBest = true;
  let isWorst = true;
  models.forEach((other) => {
    if (model === other) return;
    // If other model has higher ELO and lower cost, this model is not best
    if (other.elo >= model.elo && other.cost <= model.cost) isBest = false;
    // If other model has lower ELO and higher cost, this model is not worst
    if (other.elo <= model.elo && other.cost >= model.cost) isWorst = false;
  });
  model.optimal = isBest ? "best" : isWorst ? "worst" : "";
});


document.querySelector("#llm-cost").replaceChildren(
  Plot.plot({
    marginLeft: 50,
    x: { type: "log", grid: true },
    y: { grid: true },
    width: 1000,
    height: 500,
    marks: [
      Plot.dot(models, {
        x: "cost",
        y: "elo",
        r: 8,
        fill: (d) =>
          d.optimal == "best" ? "lime" : d.optimal == "worst" ? "red" : "rgba(var(--bs-body-color-rgb), 0.1)",
        stroke: "black",
        strokeWidth: 0.5,
        channels: { model: "model" },
        tip: {
          fill: "var(--bs-body-bg)",
          format: {
            fill: false,
            x: (d) => `$${num(d)} / MTok`,
            y: (d) => num0(d),
          },
        },
      }),
      Plot.text(
        models.filter((d) => d.optimal),
        {
          x: "cost",
          y: "elo",
          text: (d) => d.model,
          dy: -10,
          lineAnchor: "bottom",
        },
      ),
      Plot.axisX({
        label: "Cost per million input tokens",
      }),
      Plot.axisY({
        label: "ELO score",
        tickSpacing: 100,
      }),
    ],
  }),
);
