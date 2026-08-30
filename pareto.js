/**
 * Return whether `other` strictly dominates `model` for a lower-cost,
 * higher-quality chart: no more expensive, no lower quality, and better in
 * at least one dimension.
 */
export const dominates = (other, model) =>
  other !== model &&
  other.elo >= model.elo &&
  other.cost <= model.cost &&
  (other.elo > model.elo || other.cost < model.cost);

export const paretoStatus = (models) =>
  models.map((model) => {
    const best = !models.some((other) => dominates(other, model));
    const worst = !models.some((other) => dominates(model, other));
    return { model, status: best ? "best" : worst ? "worst" : "" };
  });
