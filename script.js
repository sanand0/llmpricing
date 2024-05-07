import { num, num0 } from "https://cdn.jsdelivr.net/npm/@gramex/ui@0.3/dist/format.js";
import { marked } from "https://cdn.jsdelivr.net/npm/marked@12/+esm";
import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6/+esm";
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";

const content = await fetch("README.md").then((r) => r.text());
document.querySelector("#README").innerHTML = marked.parse(content);

const data = (await d3.csv("elo.csv")).filter((d) => d.cpmi);
data.forEach((d) => {
  d.cost = +d.cpmi;
  d.elo = +d.elo;
});

document.querySelector("#llm-cost").replaceChildren(
  Plot.plot({
    x: { type: "log", grid: true },
    y: { grid: true },
    width: 1000,
    height: 500,
    marks: [
      Plot.dot(data, {
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
        data.filter((d) => d.optimal),
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
      }),
    ],
  }),
);
