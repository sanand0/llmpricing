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
import sys
from pathlib import Path
from typing import Annotated

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)

EXTRACT_SCRIPT = r"""
$$("table tr").map(d => {
  const cells = d.querySelectorAll("td, th");
  const [model, score] = [cells[2].querySelector("a")?.innerText ?? cells[2].innerText, cells[3].innerText.split(/\s/)[0]];
  return `${model}\t${score}`;
}).join("\n");
""".strip()


def describe() -> None:
    """Print the machine-readable command contract."""

    typer.echo(
        json.dumps(
            {
                "description": "Download an LMArena leaderboard TSV via CDP localhost:9222.",
                "arguments": {
                    "url": "Leaderboard URL to visit.",
                    "output": "Path to write the TSV export.",
                },
                "options": {
                    "--cdp": "CDP endpoint. Default: http://localhost:9222",
                    "--timeout": "Navigation and table wait timeout in milliseconds.",
                    "--format": "Use json for structured output or text for a plain summary.",
                    "--describe": "Print this schema and exit.",
                },
                "output": {
                    "url": "Visited URL.",
                    "path": "Written TSV path.",
                    "lines": "Number of non-empty output lines.",
                    "bytes": "Number of bytes written.",
                },
            },
            indent=2,
        )
    )


def write_leaderboard(
    *,
    url: str,
    output: Path,
    cdp: str,
    timeout: int,
) -> dict[str, str | int]:
    """Visit a leaderboard page and save the browser-console extraction result."""

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp, timeout=timeout)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        try:
            typer.echo(f"Opening {url}", err=True)
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            page.wait_for_function(
                "() => [...document.querySelectorAll('table tr')].some(row => row.querySelectorAll('td, th').length >= 4)",
                timeout=timeout,
            )
            session = context.new_cdp_session(page)
            result = session.send(
                "Runtime.evaluate",
                {
                    "expression": EXTRACT_SCRIPT,
                    "awaitPromise": True,
                    "includeCommandLineAPI": True,
                    "returnByValue": True,
                },
            )
        finally:
            page.close()

    if exception := result.get("exceptionDetails"):
        text = exception.get("text", "CDP evaluation failed")
        raise RuntimeError(text)

    value = result.get("result", {}).get("value")
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError("The leaderboard extraction returned no text.")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(value.rstrip() + "\n", encoding="utf-8")
    return {
        "url": url,
        "path": str(output),
        "lines": len([line for line in value.splitlines() if line.strip()]),
        "bytes": output.stat().st_size,
    }


@app.command()
def main(
    url: Annotated[str | None, typer.Argument(help="Leaderboard URL to visit.")] = None,
    output: Annotated[
        Path | None,
        typer.Argument(help="Path where the TSV export should be written."),
    ] = None,
    cdp: Annotated[str, typer.Option("--cdp", help="CDP endpoint.")] = "http://localhost:9222",
    timeout: Annotated[
        int,
        typer.Option("--timeout", min=1000, help="Timeout in milliseconds."),
    ] = 60_000,
    output_format: Annotated[
        str,
        typer.Option("--format", help="Output format: json or text."),
    ] = "json",
    show_description: Annotated[
        bool,
        typer.Option("--describe", help="Print the command schema and exit."),
    ] = False,
) -> None:
    """Download a leaderboard page to the TSV shape expected by update_elo.py."""

    if show_description:
        describe()
        return
    if url is None or output is None:
        typer.echo("Error: URL and output path are required unless --describe is used.", err=True)
        raise typer.Exit(code=2)
    if output_format not in {"json", "text"}:
        typer.echo("Error: --format must be json or text.", err=True)
        raise typer.Exit(code=2)

    try:
        summary = write_leaderboard(url=url, output=output, cdp=cdp, timeout=timeout)
    except PlaywrightTimeoutError as exc:
        typer.echo(f"Error: timed out while loading {url}: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if output_format == "json" or not sys.stdout.isatty():
        typer.echo(json.dumps(summary, indent=2))
    else:
        typer.echo(f"Wrote {summary['lines']} lines to {summary['path']}")


if __name__ == "__main__":
    app()
