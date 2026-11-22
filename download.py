#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "websocket-client>=1.8.0",
#   "typer>=0.16.1",
# ]
# ///
from __future__ import annotations

import json
import sys
import time
from contextlib import closing
from pathlib import Path
from typing import Annotated
from urllib.request import urlopen

import typer
from websocket import (
    WebSocket,
    WebSocketException,
    WebSocketTimeoutException,
    create_connection,
)

app = typer.Typer(add_completion=False, no_args_is_help=True)

EXTRACT_SCRIPT = r"""
(() => {
// Labels are more stable than column positions, CSS classes or framework internals.
// textContent works in background tabs without waiting for layout or unrelated assets.
const text = node => node.textContent.trim().replace(/\s+/g, " ");
const required = ["Model", "Score", "Price $/M"];
const columnIndices = (headers, labels) =>
  labels.map(label => headers.findIndex(h => h.toLowerCase() === label.toLowerCase()));
const exportRows = (rows, indices, getCells, blendedPrice = false) => {
  if (!rows.length) return {waiting: "Waiting for leaderboard rows"};
  const lines = [required.join("\t")];
  const lastIndex = Math.max(...indices);
  for (const [i, row] of rows.entries()) {
    const cells = getCells(row);
    if (cells.length <= lastIndex) return {waiting: `Incomplete row ${i + 1}`};
    const [modelCell, scoreCell, priceCell] = indices.map(index => cells[index]);
    const modelNode = modelCell.querySelector("a") ?? (blendedPrice ? null : modelCell);
    const model = modelNode?.textContent.trim().split(/\n/)[0].replace(/\s+/g, " ");
    // Scores may concatenate confidence intervals and status badges without spaces.
    const score = text(scoreCell).match(/^\d+(?:,\d{3})*(?:\.\d+)?(?=\s|±|$)/)?.[0].replace(/,/g, "");
    const displayedPrice = text(priceCell);
    // The blended-price cell's tooltip supplies the original input/output pair.
    const price = blendedPrice && displayedPrice !== "N/A"
      ? priceCell.querySelector("[title]")?.title.trim().match(/^\$[\d.,]+\s*\/\s*\$[\d.,]+$/)?.[0]
      : displayedPrice;
    if (!model || !score || !price) return {waiting: `Row ${i + 1} has an empty model, invalid score or missing input/output price`};
    lines.push([model, score, price].join("\t"));
  }
  return lines.join("\n");
};
let waiting = "No leaderboard table found";
for (const table of document.querySelectorAll("table")) {
  const rows = [...table.querySelectorAll("tr")];
  if (!rows.length) continue;
  const headers = [...rows[0].querySelectorAll("th, td")].map(text);
  const indices = columnIndices(headers, required);
  if (indices.includes(-1)) {
    waiting = `Missing columns: ${required.filter((_, i) => indices[i] < 0).join(", ")}; found: ${headers.join(", ")}`;
    continue;
  }
  return exportRows(rows.slice(1), indices, row => row.querySelectorAll("td, th"));
}
for (const list of document.querySelectorAll("ol")) {
  const headers = Array.from(list.previousElementSibling?.children ?? [], text);
  const indices = columnIndices(headers, ["Model Ranking", "Score", "Blended price $/M (3:1)"]);
  if (indices.includes(-1)) continue;
  const buttons = list.closest("section")?.querySelectorAll('button[aria-expanded="false"]') ?? [];
  const expand = [...buttons].find(button => text(button).toLowerCase() === "view all");
  if (expand) {
    expand.click();
    return {waiting: "Waiting for the full model ranking to expand"};
  }
  return exportRows([...list.children], indices, row => row.children, true);
}
return {waiting: `${waiting} (page: ${document.title}; URL: ${location.href})`};
})()
""".strip()


class CDP:
    """Send only explicit commands; never initialize or attach to unrelated tabs."""

    def __init__(self, socket: WebSocket, timeout: int) -> None:
        self.socket = socket
        self.timeout = timeout / 1000
        self.command_id = 0

    def send(
        self,
        method: str,
        params: dict | None = None,
        *,
        session: str | None = None,
        deadline: float | None = None,
    ) -> dict:
        """Ignore events and unrelated replies without extending the command deadline."""
        deadline = deadline if deadline is not None else time.monotonic() + self.timeout
        self.command_id += 1
        command = {"id": self.command_id, "method": method, "params": params or {}}
        if session:
            command["sessionId"] = session
        try:
            self.socket.settimeout(max(0.001, deadline - time.monotonic()))
            self.socket.send(json.dumps(command))
            while (remaining := deadline - time.monotonic()) > 0:
                self.socket.settimeout(remaining)
                message = json.loads(self.socket.recv())
                if message.get("id") != self.command_id:
                    continue
                if error := message.get("error"):
                    raise RuntimeError(f"CDP {method}: {error.get('message', error)}")
                return message.get("result", {})
        except WebSocketTimeoutException as exc:
            raise TimeoutError(f"CDP {method} timed out") from exc
        raise TimeoutError(f"CDP {method} timed out")


def describe() -> None:
    """Print the machine-readable command contract."""

    typer.echo(
        json.dumps(
            {
                "description": "Download Arena model scores and input prices ($/M) via CDP localhost:9222.",
                "arguments": {
                    "url": "Leaderboard URL to visit.",
                    "output": "Path to write the TSV export.",
                },
                "options": {
                    "--cdp": "CDP endpoint. Default: http://localhost:9222",
                    "--timeout": "Connection/command and table wait timeout in milliseconds (default 60000).",
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
    """Export from an owned tab without Playwright's browser-wide target initialization."""

    typer.echo(f"Connecting to CDP {cdp}", err=True)
    if cdp.startswith(("http://", "https://")):
        with urlopen(
            f"{cdp.rstrip('/')}/json/version", timeout=timeout / 1000
        ) as response:
            cdp = json.load(response)["webSocketDebuggerUrl"]
    elif not cdp.startswith(("ws://", "wss://")):
        raise ValueError("--cdp must be an HTTP(S) endpoint or browser WebSocket URL.")

    # Playwright attaches to every existing target during connect_over_cdp. One stuck
    # target can hang that handshake even though the browser WebSocket is healthy.
    with closing(
        create_connection(cdp, timeout=timeout / 1000, suppress_origin=True)
    ) as socket:
        client = CDP(socket, timeout)
        target = client.send(
            "Target.createTarget", {"url": "about:blank", "background": True}
        )["targetId"]
        try:
            session = client.send(
                "Target.attachToTarget", {"targetId": target, "flatten": True}
            )["sessionId"]
            typer.echo(f"Opening {url}", err=True)
            navigation = client.send("Page.navigate", {"url": url}, session=session)
            if error := navigation.get("errorText"):
                raise RuntimeError(f"Navigation to {url} failed: {error}")
            typer.echo("Waiting for leaderboard rows", err=True)
            deadline = time.monotonic() + timeout / 1000
            waiting = "waiting for leaderboard rows"
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"waiting for leaderboard rows at {url}: {waiting}")
                result = client.send(
                    "Runtime.evaluate",
                    {
                        "expression": EXTRACT_SCRIPT,
                        "returnByValue": True,
                    },
                    session=session,
                    deadline=deadline,
                )
                if exception := result.get("exceptionDetails"):
                    detail = exception.get("exception", {}).get(
                        "description"
                    ) or exception.get("text")
                    raise RuntimeError(f"Leaderboard extraction failed: {detail}")
                value = result.get("result", {}).get("value")
                if isinstance(value, str) and value.strip():
                    break
                if isinstance(value, dict):
                    waiting = value.get("waiting", waiting)
                time.sleep(min(0.25, max(0, deadline - time.monotonic())))
        finally:
            try:
                client.send("Target.closeTarget", {"targetId": target})
            except (OSError, ValueError, RuntimeError, WebSocketException) as exc:
                typer.echo(
                    f"Warning: could not close downloader tab {target}: {exc}", err=True
                )

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
    cdp: Annotated[
        str, typer.Option("--cdp", help="CDP endpoint.")
    ] = "http://localhost:9222",
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
        typer.echo(
            "Error: URL and output path are required unless --describe is used.",
            err=True,
        )
        raise typer.Exit(code=2)
    if output_format not in {"json", "text"}:
        typer.echo("Error: --format must be json or text.", err=True)
        raise typer.Exit(code=2)

    try:
        summary = write_leaderboard(url=url, output=output, cdp=cdp, timeout=timeout)
    except (TimeoutError, WebSocketTimeoutException) as exc:
        typer.echo(f"Error: timed out downloading {url}: {exc}", err=True)
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
