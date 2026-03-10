import { num, num0 } from "https://cdn.jsdelivr.net/npm/@gramex/ui@0.3/dist/format.js";
import { marked } from "https://cdn.jsdelivr.net/npm/marked@12/+esm";
import * as Plot from "https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6/+esm";
import * as d3 from "https://cdn.jsdelivr.net/npm/d3@7.9.0/+esm";
import { default as fuzzysort } from "https://cdn.jsdelivr.net/npm/fuzzysort@3/+esm";

// Load and display README content
const content = await fetch("README.md").then((r) => r.text());
document.querySelector("#README").innerHTML = marked.parse(content);

let quality = new URLSearchParams(window.location.search).get("quality") || "overall";
document.querySelector("#quality").textContent = quality.charAt(0).toUpperCase() + quality.slice(1);

// Load and process model data
const data = await d3.csv("elo.csv");
const models = data.filter((d) => d.cpmi).map((d) => ({ ...d, cost: +d.cpmi, elo: +d[quality] }));

// Scrollytelling state
let scrollyHighlights = new Set();
let scrollyActive = false;

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

// LMArena Elo mapped to academic milestones (Framework A)
const eloAnnotations = [
  { elo: 1000, label: "🧒 Middle schooler" },
  { elo: 1100, label: "🎒 HS freshman" },
  { elo: 1200, label: "🎓 HS graduate" },
  { elo: 1300, label: "📚 College junior" },
  { elo: 1350, label: "🏫 College grad" },
  { elo: 1400, label: "🎓 Master's student" },
  { elo: 1450, label: "🔬 PhD candidate" },
  { elo: 1480, label: "🏛 Tenured professor" },
];

const updateOptimalStatus = (filteredModels) => {
  filteredModels.forEach((model) => {
    model.optimal = filteredModels.every((other) => other === model || other.elo < model.elo || other.cost > model.cost)
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
      Plot.ruleY(eloAnnotations, {
        y: "elo",
        stroke: "#888",
        strokeOpacity: 0.3,
        strokeDasharray: "4,4",
      }),
      Plot.text(eloAnnotations, {
        y: "elo",
        text: "label",
        frameAnchor: "right",
        textAnchor: "end",
        fontSize: 10,
        fill: "#888",
        dx: -4,
        dy: -5,
      }),
      Plot.dot(filteredModels, {
        x: "cost",
        y: "elo",
        r: 8,
        fill: (d) => {
          if (scrollyHighlights.has(d.model)) return "#06b6d4";
          if (d.optimal === "best") return "lime";
          if (d.optimal === "worst") return "red";
          return "rgba(var(--bs-body-color-rgb), 0.1)";
        },
        fillOpacity: (d) =>
          scrollyActive && scrollyHighlights.size > 0 && !scrollyHighlights.has(d.model) ? 0.3 : 1,
        stroke: (d) => (scrollyHighlights.has(d.model) ? "#fff" : "black"),
        strokeWidth: (d) => (scrollyHighlights.has(d.model) ? 1.5 : 0.5),
        strokeOpacity: (d) =>
          scrollyActive && scrollyHighlights.size > 0 && !scrollyHighlights.has(d.model) ? 0.2 : 1,
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
        filteredModels.filter((d) => d.optimal || scrollyHighlights.has(d.model)),
        {
          x: "cost",
          y: "elo",
          text: (d) => d.model,
          fillOpacity: (d) =>
            scrollyActive && scrollyHighlights.size > 0 && !scrollyHighlights.has(d.model) ? 0.25 : 1,
          dy: -10,
          lineAnchor: "bottom",
        }
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
    { threshold: -20 }
  );
  const matches = new Set(results.map((r) => r.target));

  const filteredModels = models.filter(
    (d) => d.launch <= date && (d.end ? d.end > date : true) && (search ? matches.has(d.model) : true)
  );
  updateOptimalStatus(filteredModels);
  renderPlot(filteredModels);
};

$date.addEventListener("input", update);
document.querySelector("#model").addEventListener("input", update);
update();

// ─── Scrollytelling ────────────────────────────────────────────────────────

const narrative = await fetch("narrative.json").then((r) => r.json());

// Build scrolly steps — each contains a sticky glassmorphism card
const scrollySection = document.querySelector("#scrolly-section");
const cardEls = [];

narrative.cards.forEach((card, i) => {
  const linksHtml = card.links.length
    ? `<div class="card-links">${card.links
        .map((l) => `<a href="${l.url}" target="_blank" rel="noopener">${l.text}</a>`)
        .join("")}</div>`
    : "";

  const cardEl = document.createElement("div");
  cardEl.className = `scrolly-card pos-${card.position}${card.vertical === "top" ? " vert-top" : ""}`;
  cardEl.innerHTML = `<h6>${card.title}</h6>${card.body}${linksHtml}`;

  const step = document.createElement("div");
  step.className = "scrolly-step";
  step.dataset.step = i;
  step.appendChild(cardEl);
  scrollySection.appendChild(step);
  cardEls.push(cardEl);

  if (i < narrative.cards.length - 1) {
    const gap = document.createElement("div");
    gap.className = "scrolly-gap";
    scrollySection.appendChild(gap);
  }
});

// Trailing spacer — large enough for the last card to scroll well past the top
const trailing = document.createElement("div");
trailing.style.height = "140vh";
scrollySection.appendChild(trailing);

// Sentinel at the start of the trailing space: when it enters the viewport,
// the last card has already scrolled above the top — restore the chart fully
const endSentinel = document.createElement("div");
trailing.prepend(endSentinel);

const endObserver = new IntersectionObserver(
  ([entry]) => { if (entry.isIntersecting) deactivateScrolly(); },
  { threshold: 0 }
);
endObserver.observe(endSentinel);

// Smooth month animation
let monthAnimFrame = null;
const animateToMonth = (targetIdx) => {
  if (monthAnimFrame) cancelAnimationFrame(monthAnimFrame);
  const startIdx = +$date.value;
  if (startIdx === targetIdx) return;
  const duration = 700;
  const startTime = performance.now();
  const tick = (now) => {
    const t = Math.min((now - startTime) / duration, 1);
    const eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
    const cur = Math.round(startIdx + (targetIdx - startIdx) * eased);
    if (+$date.value !== cur) { $date.value = cur; update(); }
    if (t < 1) monthAnimFrame = requestAnimationFrame(tick);
  };
  monthAnimFrame = requestAnimationFrame(tick);
};

const activateCard = (cardData) => {
  scrollyActive = true;
  scrollyHighlights = new Set(cardData.highlight);
  if (cardData.month) animateToMonth(dates.indexOf(cardData.month));
  else update();
};

const deactivateScrolly = () => {
  if (!scrollyActive && scrollyHighlights.size === 0) return;
  scrollyActive = false;
  scrollyHighlights = new Set();
  update();
};

// Fade cards in/out as they enter/leave viewport
const cardObserver = new IntersectionObserver(
  (entries) => entries.forEach((e) => e.target.classList.toggle("is-active", e.isIntersecting)),
  { threshold: 0.15 }
);
cardEls.forEach((el) => cardObserver.observe(el));

// Update chart state when a step becomes active
const stepObserver = new IntersectionObserver(
  (entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) activateCard(narrative.cards[+entry.target.dataset.step]);
    }
  },
  { threshold: 0.35, rootMargin: "-10% 0px -10% 0px" }
);
document.querySelectorAll(".scrolly-step").forEach((el) => stepObserver.observe(el));

// Deactivate when scrolling back above the section (scroll-up case)
let sectionEverEntered = false;
const sectionObserver = new IntersectionObserver(
  ([entry]) => {
    if (entry.isIntersecting) { sectionEverEntered = true; }
    else if (sectionEverEntered) { deactivateScrolly(); }
  },
  { threshold: 0 }
);
sectionObserver.observe(scrollySection);
