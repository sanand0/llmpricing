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
if (document.readyState !== "complete") return null;
const rows = [...document.querySelectorAll("table tr")];
if (rows.length < 2 || !rows[1].querySelector("td")) return null;
const headers = [...rows[0].querySelectorAll("th, td")].map(d => d.innerText.trim());
const priceIndex = headers.indexOf("Price $/M");
if (priceIndex < 0) throw new Error("Arena table is missing Price $/M");
const data = rows.slice(1).map(d => [...d.querySelectorAll("td, th")]);
// Arena initially renders skeleton/placeholder rows. Export only a complete table.
if (data.some(cells => cells.length <= Math.max(3, priceIndex))) return null;
if (data.some(cells => !/^\d+(?:\.\d+)?/.test(cells[3].innerText.trim()))) return null;
return ["Model\tScore\tPrice $/M", ...data.map(cells => {
  const model = (cells[2].querySelector("a")?.innerText ?? cells[2].innerText).split(/\n/)[0];
  // Background tabs may concatenate score, confidence interval and status text.
  const score = cells[3].innerText.trim().match(/^\d+(?:\.\d+)?/)[0];
  const price = cells[priceIndex].innerText.trim();
  return `${model}\t${score}\t${price}`;
})].join("\n");
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
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"waiting for leaderboard rows at {url}")
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
