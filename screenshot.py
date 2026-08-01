#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "playwright>=1.56.0",
#   "typer>=0.16.1",
# ]
# ///
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Annotated

import typer
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

app = typer.Typer(add_completion=False, no_args_is_help=True)

DEFAULT_URL = "https://sanand0.github.io/llmpricing/"
SAFE_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class ScreenshotError(Exception):
    """Raised when inputs or the live page cannot be captured safely."""


def parse_models(value: str) -> list[str]:
    """Parse a comma-separated model filter while keeping filenames safe."""

    parts = [part.strip() for part in value.split(",")]
    if not parts or any(not part for part in parts):
        raise ScreenshotError("--model must contain non-empty comma-separated values, e.g. gpt,gemini.")
    unsafe = [part for part in parts if SAFE_MODEL.fullmatch(part) is None]
    if unsafe:
        raise ScreenshotError(
            f"Model filters may contain only letters, numbers, dot, underscore, and hyphen: {unsafe[0]!r}."
        )
    return list(dict.fromkeys(parts))


def screenshot_path(output_dir: Path, model: str, date_value: int) -> Path:
    return output_dir / f"{model}-{date_value:03d}.png"


def describe() -> None:
    """Print the machine-readable command contract."""

    typer.echo(
        json.dumps(
            {
                "description": "Capture the LLM pricing chart for each model filter and slider date.",
                "options": {
                    "--model": "Required comma-separated filters, e.g. gpt,gemini.",
                    "--force": "Overwrite PNG files that already exist.",
                    "--dry-run": "Discover the live date range and report work without writing files.",
                    "--output-dir": "Screenshot directory. Default: screenshots",
                    "--url": f"Page to capture. Default: {DEFAULT_URL}",
                    "--timeout": "Navigation/render timeout in milliseconds. Default: 60000",
                    "--format": "Summary format: auto, json, or text. Non-TTY auto output is JSON.",
                    "--describe": "Print this schema and exit.",
                },
                "environment": {
                    "LLMPRICING_CHROMIUM": "Optional Chromium/Chrome executable path.",
                },
                "output": {
                    "captured": "Number of PNGs written.",
                    "skipped": "Number of existing PNGs left untouched.",
                    "planned": "Number of PNGs that a dry run would write.",
                    "date_min/date_max/date_step": "Values discovered from the live #date input.",
                },
            },
            indent=2,
        )
    )


def chromium_executable() -> str | None:
    configured = os.environ.get("LLMPRICING_CHROMIUM")
    if configured:
        path = Path(configured).expanduser()
        if not path.is_file():
            raise ScreenshotError(f"LLMPRICING_CHROMIUM is not a file: {path}")
        return str(path)
    return next(
        (
            path
            for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
            if (path := shutil.which(name))
        ),
        None,
    )


def read_date_range(page: Page) -> tuple[int, int, int]:
    values = page.locator("#date").evaluate(
        "el => ({min: el.min, max: el.max, step: el.step || '1'})"
    )
    try:
        minimum, maximum, step = (int(values[key]) for key in ("min", "max", "step"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ScreenshotError(f"#date has a non-integer range: {values!r}") from exc
    if step <= 0 or maximum < minimum:
        raise ScreenshotError(f"#date has an invalid range: {values!r}")
    return minimum, maximum, step


def wait_for_chart(page: Page, *, model: str, date_value: int, timeout: int) -> None:
    """Wait until input handlers and browser paint have completed."""

    page.wait_for_function(
        """async ({model, dateValue}) => {
            await document.fonts.ready;
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            return document.querySelector('#model')?.value === model
                && document.querySelector('#date')?.value === String(dateValue)
                && document.querySelector('#llm-cost > svg');
        }""",
        arg={"model": model, "dateValue": date_value},
        timeout=timeout,
    )


def capture_screenshots(
    *,
    models: list[str],
    output_dir: Path,
    url: str,
    timeout: int,
    force: bool,
    dry_run: bool,
) -> dict[str, object]:
    """Capture all requested filter/date combinations in one browser session."""

    typer.echo(f"Opening {url}", err=True)
    with sync_playwright() as playwright:
        executable_path = chromium_executable()
        browser = playwright.chromium.launch(headless=True, executable_path=executable_path)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page.set_default_timeout(timeout)
        # Scrollytelling observers can otherwise change #date when the chart scrolls into view.
        page.add_init_script(
            """window.IntersectionObserver = class {
                observe() {} unobserve() {} disconnect() {} takeRecords() { return []; }
            };"""
        )
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            page.locator("#llm-cost > svg").wait_for(state="attached", timeout=timeout)
            minimum, maximum, step = read_date_range(page)
            dates = list(range(minimum, maximum + 1, step))
            captured = skipped = planned = 0

            for model in models:
                page.locator("#model").fill(model)
                for date_value in dates:
                    destination = screenshot_path(output_dir, model, date_value)
                    if destination.exists() and not force:
                        skipped += 1
                        continue
                    if dry_run:
                        planned += 1
                        continue

                    typer.echo(f"Capturing {destination}", err=True)
                    page.locator("#date").evaluate(
                        """(el, value) => {
                            el.value = String(value);
                            el.dispatchEvent(new Event('input', {bubbles: true}));
                        }""",
                        date_value,
                    )
                    wait_for_chart(page, model=model, date_value=date_value, timeout=timeout)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    temporary = destination.with_name(f".{destination.name}.tmp")
                    try:
                        page.locator("#chart-sticky").screenshot(path=temporary, type="png")
                        temporary.replace(destination)
                    finally:
                        temporary.unlink(missing_ok=True)
                    captured += 1
        finally:
            browser.close()

    return {
        "url": url,
        "models": models,
        "output_dir": str(output_dir),
        "date_min": minimum,
        "date_max": maximum,
        "date_step": step,
        "total": len(models) * len(dates),
        "captured": captured,
        "skipped": skipped,
        "planned": planned,
        "dry_run": dry_run,
    }


@app.command()
def main(
    model: Annotated[
        str | None,
        typer.Option("--model", help="Comma-separated model filters, e.g. gpt,gemini."),
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing screenshots.")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Report work without writing PNGs.")] = False,
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Directory for screenshot PNGs."),
    ] = Path("screenshots"),
    url: Annotated[str, typer.Option("--url", help="LLM pricing page URL.")] = DEFAULT_URL,
    timeout: Annotated[
        int,
        typer.Option("--timeout", min=1000, help="Navigation/render timeout in milliseconds."),
    ] = 60_000,
    output_format: Annotated[
        str,
        typer.Option("--format", help="Summary format: auto, json, or text."),
    ] = "auto",
    show_description: Annotated[
        bool,
        typer.Option("--describe", help="Print the command schema and exit."),
    ] = False,
) -> None:
    """Capture model-filtered LLM pricing charts over the live date range."""

    if show_description:
        describe()
        return
    if model is None:
        typer.echo("Error: --model is required unless --describe is used.", err=True)
        raise typer.Exit(code=2)
    if output_format not in {"auto", "json", "text"}:
        typer.echo("Error: --format must be auto, json, or text.", err=True)
        raise typer.Exit(code=2)
    try:
        models = parse_models(model)
        summary = capture_screenshots(
            models=models,
            output_dir=output_dir,
            url=url,
            timeout=timeout,
            force=force,
            dry_run=dry_run,
        )
    except (PlaywrightTimeoutError, PlaywrightError, ScreenshotError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if output_format == "json" or (output_format == "auto" and not sys.stdout.isatty()):
        typer.echo(json.dumps(summary, indent=2))
    else:
        action = "Would capture" if dry_run else "Captured"
        typer.echo(
            f"{action} {summary['planned'] if dry_run else summary['captured']} screenshots; "
            f"skipped {summary['skipped']} existing files in {summary['output_dir']}."
        )


if __name__ == "__main__":
    app()
