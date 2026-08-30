import assert from "node:assert/strict";
import { dominates, paretoStatus } from "./pareto.js";

const model = (cost, elo) => ({ cost, elo });
const opusThinking = model(5, 1505);
const opusHigh = model(5, 1505);

assert.equal(dominates(opusHigh, opusThinking), false, "an exact tie must not dominate");
assert.equal(dominates(model(4, 1505), opusThinking), true, "a cheaper tie must dominate");
assert.equal(dominates(model(5, 1506), opusThinking), true, "a higher-quality tie must dominate");
assert.equal(dominates(model(6, 1506), opusThinking), false, "a more expensive model must not dominate");

const statuses = paretoStatus([opusThinking, opusHigh]);
assert.deepEqual(
  statuses.map(({ status }) => status),
  ["best", "best"],
  "exactly overlapping models must both remain on the best frontier"
);
