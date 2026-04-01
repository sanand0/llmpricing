#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "httpx>=0.28.1",
#   "typer>=0.16.1",
# ]
# ///
from __future__ import annotations

import csv
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx
import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)

COLUMN_ALIASES = {
    "text": "overall",
    "overall": "overall",
    "hard": "hard",
    "code": "coding",
    "coding": "coding",
}

PAREN_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")
LATEST_SUFFIX = re.compile(r"-latest$", re.IGNORECASE)
EFFORT_SUFFIX = re.compile(r"-(?:high|medium|low)$", re.IGNORECASE)
REASONING_SUFFIX = re.compile(
    r"-(?:thinking|reasoning|no-thinking|non-thinking)$",
    re.IGNORECASE,
)
BETA_SUFFIX = re.compile(r"-beta(?:-\d+|\d+)?$", re.IGNORECASE)
RELEASE_SUFFIXES = (
    re.compile(r"-(?:20\d{2}(?:[-.]\d{2}){1,2})$"),
    re.compile(r"-(?:\d{2}(?:[-.]\d{2}){2})$"),
    re.compile(r"-\d{8}$"),
    re.compile(r"-\d{4}$"),
)

TOKENS_PER_MILLION = Decimal("1000000")
type EloRow = dict[str, str]


class UpdateEloError(Exception):
    """Raised for invalid input or data we can't safely process."""


@dataclass
class UpdateSummary:
    """Tracks what changed during an update run."""

    added: int = 0
    updated: int = 0
    priced: int = 0
    launched: int = 0
    ended: int = 0
    unmatched_openrouter: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OpenRouterModel:
    """A pricing record from OpenRouter's public models endpoint."""

    model_id: str
    canonical_slug: str
    prompt_price: Decimal
    launch_label: str | None

    @property
    def source_url(self) -> str:
        return f"https://openrouter.ai/{self.model_id.split(':', 1)[0]}"


def normalize_key(value: str) -> str:
    """Normalize a model identifier so small punctuation differences don't matter."""

    normalized = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized)
    return normalized.strip("-")


def drop_provider_prefix(value: str) -> str:
    """Drop `provider/` and `:free` style markers from OpenRouter identifiers."""

    providerless = value.split("/", 1)[1] if "/" in value else value
    return providerless.split(":", 1)[0]


def generate_lookup_keys(model: OpenRouterModel) -> set[str]:
    """Return conservative exact-match aliases for an OpenRouter model."""

    values = {
        model.model_id,
        drop_provider_prefix(model.model_id),
    }
    if model.canonical_slug:
        values.add(model.canonical_slug)
        values.add(drop_provider_prefix(model.canonical_slug))
    return {normalize_key(value) for value in values if value}


def drop_parenthetical_suffix(value: str) -> str:
    return PAREN_SUFFIX.sub("", value).strip()


def drop_latest_suffix(value: str) -> str:
    return LATEST_SUFFIX.sub("", value).strip("- ")


def drop_effort_suffix(value: str) -> str:
    return EFFORT_SUFFIX.sub("", value).strip("- ")


def drop_reasoning_suffix(value: str) -> str:
    return REASONING_SUFFIX.sub("", value).strip("- ")


def drop_beta_suffix(value: str) -> str:
    return BETA_SUFFIX.sub("", value).strip("- ")


def drop_release_suffix(value: str) -> str:
    trimmed = value
    for pattern in RELEASE_SUFFIXES:
        trimmed = pattern.sub("", trimmed).strip("- ")
    return trimmed


TRANSFORMS = (
    drop_parenthetical_suffix,
    drop_latest_suffix,
    drop_reasoning_suffix,
    drop_effort_suffix,
    drop_beta_suffix,
    drop_release_suffix,
)


def generate_candidate_keys(model_name: str) -> list[str]:
    """Generate progressively looser exact-match aliases for an input model name."""

    queue = deque([model_name.strip()])
    seen_values: set[str] = set()
    ordered_keys: list[str] = []
    seen_keys: set[str] = set()

    while queue:
        current = queue.popleft().strip()
        if not current or current in seen_values:
            continue
        seen_values.add(current)

        key = normalize_key(current)
        if key and key not in seen_keys:
            ordered_keys.append(key)
            seen_keys.add(key)

        for transform in TRANSFORMS:
            transformed = transform(current)
            if transformed and transformed != current and transformed not in seen_values:
                queue.append(transformed)

    return ordered_keys


class OpenRouterMatcher:
    """Matches repository model names to OpenRouter entries without guessing wildly."""

    def __init__(self, models: list[OpenRouterModel]) -> None:
        self.lookup: dict[str, list[OpenRouterModel]] = defaultdict(list)
        for model in models:
            for key in generate_lookup_keys(model):
                self.lookup[key].append(model)

    def match(self, model_name: str) -> OpenRouterModel | None:
        for key in generate_candidate_keys(model_name):
            match = self._resolve_hits(self.lookup.get(key, []))
            if match is not None:
                return match
        return None

    @staticmethod
    def _resolve_hits(hits: list[OpenRouterModel]) -> OpenRouterModel | None:
        unique_hits = list({hit.model_id: hit for hit in hits}.values())
        if not unique_hits:
            return None
        if len(unique_hits) == 1:
            return unique_hits[0]

        paid_hits = [hit for hit in unique_hits if not hit.model_id.endswith(":free")]
        if len(paid_hits) == 1:
            return paid_hits[0]
        return None


def resolve_column(column_name: str, headers: list[str]) -> str:
    """Map user-facing column names to the actual `elo.csv` header."""

    resolved = COLUMN_ALIASES.get(column_name.lower())
    if resolved is None:
        options = ", ".join(sorted(COLUMN_ALIASES))
        raise UpdateEloError(f"Unsupported column {column_name!r}. Use one of: {options}.")
    if resolved not in headers:
        raise UpdateEloError(f"`elo.csv` does not have a {resolved!r} column.")
    return resolved


def read_updates(tsv_path: Path) -> dict[str, str]:
    """Read a two-column TSV file containing model names and new Elo scores."""

    updates: dict[str, str] = {}
    with tsv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader, None)
        if header is None:
            raise UpdateEloError(f"{tsv_path} is empty.")

        for line_number, row in enumerate(reader, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue
            if len(row) < 2:
                raise UpdateEloError(
                    f"{tsv_path}:{line_number} must have at least two TSV columns."
                )

            model = row[0].strip()
            score = row[1].strip()
            if not model:
                raise UpdateEloError(f"{tsv_path}:{line_number} is missing the model name.")
            if not score:
                raise UpdateEloError(f"{tsv_path}:{line_number} is missing the score value.")

            try:
                Decimal(score)
            except InvalidOperation as exc:
                raise UpdateEloError(
                    f"{tsv_path}:{line_number} has a non-numeric score {score!r}."
                ) from exc

            updates[model] = score

    if not updates:
        raise UpdateEloError(f"{tsv_path} does not contain any data rows.")
    return updates


def read_elo_rows(elo_path: Path) -> tuple[list[str], list[EloRow]]:
    """Load `elo.csv` while preserving header order."""

    with elo_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise UpdateEloError(f"{elo_path} is missing a header row.")
        rows = [{key: (value or "") for key, value in row.items()} for row in reader]
    return reader.fieldnames, rows


def fetch_openrouter_models() -> list[OpenRouterModel]:
    """Fetch model pricing from OpenRouter's public models endpoint."""

    response = httpx.get("https://openrouter.ai/api/v1/models", timeout=30.0)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise UpdateEloError("OpenRouter returned an unexpected models payload.")

    models: list[OpenRouterModel] = []
    for item in payload["data"]:
        model_id = item.get("id")
        pricing = item.get("pricing") or {}
        prompt_price = pricing.get("prompt")
        if not model_id or prompt_price in (None, ""):
            continue
        try:
            price = Decimal(str(prompt_price))
        except InvalidOperation:
            continue
        models.append(
            OpenRouterModel(
                model_id=str(model_id),
                canonical_slug=str(item.get("canonical_slug") or ""),
                prompt_price=price,
                launch_label=infer_openrouter_launch_label(item.get("created")),
            )
        )
    return models


def format_decimal(value: Decimal) -> str:
    """Format Decimal values without exponent notation or trailing zeros."""

    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f").rstrip("0").rstrip(".")


def month_label(now: datetime, *, month_offset: int = 0, approximate: bool = True) -> str:
    """Return a month label, optionally marking it as approximate with `?`."""

    total_months = (now.year * 12) + (now.month - 1) + month_offset
    year, month_index = divmod(total_months, 12)
    suffix = "?" if approximate else ""
    return f"{year:04d}-{month_index + 1:02d}{suffix}"


def infer_openrouter_launch_label(created: object) -> str | None:
    """Convert an OpenRouter creation timestamp into an exact `YYYY-MM` launch label."""

    if created in (None, ""):
        return None
    try:
        created_at = datetime.fromtimestamp(float(created), UTC)
    except (OSError, OverflowError, TypeError, ValueError):
        return None
    return month_label(created_at, approximate=False)


def parse_rank_value(value: str, *, context: str) -> Decimal | None:
    """Parse a leaderboard cell as Decimal, allowing blanks but not invalid values."""

    stripped = value.strip()
    if not stripped:
        return None
    try:
        return Decimal(stripped)
    except InvalidOperation as exc:
        raise UpdateEloError(f"{context} has a non-numeric value {value!r}.") from exc


def insert_row_by_score(
    rows: list[EloRow],
    new_row: EloRow,
    *,
    target_column: str,
) -> None:
    """Insert a new row above the first lower score for the target column."""

    new_score = parse_rank_value(
        new_row[target_column],
        context=f"new row {new_row['model']} {target_column}",
    )
    if new_score is None:
        rows.append(new_row)
        return

    for index, existing_row in enumerate(rows):
        existing_score = parse_rank_value(
            existing_row[target_column],
            context=f"elo.csv row {existing_row['model']} {target_column}",
        )
        if existing_score is None or existing_score < new_score:
            rows.insert(index, new_row)
            return

    rows.append(new_row)


def new_row(headers: list[str], model_name: str) -> EloRow:
    """Create a blank CSV row for a newly seen model."""

    row = {header: "" for header in headers}
    row["model"] = model_name
    return row


@dataclass(frozen=True)
class OpenRouterUpdateResult:
    """Describes which fields were filled from an OpenRouter match."""

    pricing_updated: bool = False
    launch_updated: bool = False
    missing_match: bool = False


def update_openrouter_metadata(
    row: EloRow,
    *,
    model_name: str,
    matcher: OpenRouterMatcher,
) -> OpenRouterUpdateResult:
    """Fill blank OpenRouter-backed metadata for a row.

    Returns which fields were updated, or indicates that no safe match was found.
    """

    needs_pricing = not row["cpmi"] or not row["source"]
    needs_launch = not row["launch"]
    if not needs_pricing and not needs_launch:
        return OpenRouterUpdateResult()

    match = matcher.match(model_name)
    if match is None:
        return OpenRouterUpdateResult(missing_match=True)

    pricing_updated = False
    if not row["cpmi"]:
        row["cpmi"] = format_decimal(match.prompt_price * TOKENS_PER_MILLION)
        pricing_updated = True
    if not row["source"]:
        row["source"] = match.source_url
        pricing_updated = True

    launch_updated = False
    if not row["launch"] and match.launch_label:
        row["launch"] = match.launch_label
        launch_updated = True

    return OpenRouterUpdateResult(
        pricing_updated=pricing_updated,
        launch_updated=launch_updated,
    )


def fill_missing_end_dates(rows: list[EloRow], present_models: set[str], *, end_label: str) -> int:
    """Mark models missing from an overall TSV as ended when they have no end date yet."""

    filled = 0
    for row in rows:
        if row["model"] in present_models or row["end"]:
            continue
        row["end"] = end_label
        filled += 1
    return filled


def apply_updates(
    headers: list[str],
    rows: list[EloRow],
    *,
    target_column: str,
    updates: dict[str, str],
    matcher: OpenRouterMatcher,
    now: datetime,
) -> UpdateSummary:
    """Apply TSV scores and metadata updates to in-memory CSV rows."""

    summary = UpdateSummary()
    rows_by_model = {row["model"]: row for row in rows}
    new_rows: list[EloRow] = []

    for model_name, score in updates.items():
        row = rows_by_model.get(model_name)
        is_new = row is None
        if row is None:
            row = new_row(headers, model_name)
            rows_by_model[model_name] = row
            new_rows.append(row)
            summary.added += 1
        else:
            summary.updated += 1

        row[target_column] = score

        metadata_update = update_openrouter_metadata(row, model_name=model_name, matcher=matcher)
        if metadata_update.missing_match:
            summary.unmatched_openrouter.append(model_name)
        if metadata_update.pricing_updated:
            summary.priced += 1
        if metadata_update.launch_updated:
            summary.launched += 1
        if is_new and not row["launch"]:
            row["launch"] = month_label(now, month_offset=-1)

    for row in new_rows:
        insert_row_by_score(rows, row, target_column=target_column)

    if target_column == "overall":
        summary.ended = fill_missing_end_dates(rows, set(updates), end_label=month_label(now))

    return summary


def print_summary(
    summary: UpdateSummary,
    *,
    column: str,
    target_column: str,
    update_count: int,
    dry_run: bool,
) -> None:
    """Render a concise CLI summary for the completed update."""

    display_column = column if column.lower() == target_column else f"{column} -> {target_column}"
    typer.echo(
        f"{'Dry run:' if dry_run else 'Updated'} "
        f"{summary.updated} existing rows and added {summary.added} new rows "
        f"for {display_column} ({update_count} input models)."
    )
    typer.echo(f"Updated pricing metadata for {summary.priced} touched models from OpenRouter.")
    if summary.launched:
        typer.echo(f"Updated launch dates for {summary.launched} touched models from OpenRouter.")
    if summary.ended:
        typer.echo(f"Filled blank end dates for {summary.ended} rows missing from the overall TSV.")
    if summary.unmatched_openrouter:
        preview = ", ".join(summary.unmatched_openrouter[:10])
        if len(summary.unmatched_openrouter) > 10:
            preview = f"{preview}, ..."
        typer.echo(
            f"No safe OpenRouter match for {len(summary.unmatched_openrouter)} touched models: {preview}",
        )


def write_rows(elo_path: Path, headers: list[str], rows: list[EloRow]) -> None:
    """Write the updated CSV back to disk."""

    with elo_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


@app.command()
def main(
    file_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="TSV file containing Model and Score columns.",
    ),
    column: str = typer.Option(
        ...,
        "--column",
        "-c",
        help="Which leaderboard column to update: text/overall, hard, or code/coding.",
    ),
    elo_path: Path = typer.Option(
        Path("elo.csv"),
        "--elo",
        exists=True,
        dir_okay=False,
        readable=True,
        writable=True,
        help="Path to the elo.csv file to update.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview the update without writing elo.csv.",
    ),
) -> None:
    """Update elo.csv scores from a TSV export and refresh OpenRouter pricing when possible."""

    try:
        headers, rows = read_elo_rows(elo_path)
        target_column = resolve_column(column, headers)
        updates = read_updates(file_path)
        matcher = OpenRouterMatcher(fetch_openrouter_models())
    except UpdateEloError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except httpx.HTTPError as exc:
        typer.echo(f"Error: failed to fetch OpenRouter models: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    now = datetime.now(UTC)
    summary = apply_updates(
        headers,
        rows,
        target_column=target_column,
        updates=updates,
        matcher=matcher,
        now=now,
    )

    if not dry_run:
        write_rows(elo_path, headers, rows)

    print_summary(
        summary,
        column=column,
        target_column=target_column,
        update_count=len(updates),
        dry_run=dry_run,
    )


if __name__ == "__main__":
    app()
