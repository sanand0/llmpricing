import io
import json
import subprocess
from collections import deque

import pytest
from typer.testing import CliRunner
from websocket import WebSocketTimeoutException

import download

TSV = "Model\tScore\tPrice $/M\nmodel\t1500\t$1 / $2"


@pytest.mark.parametrize(
    "data, expected",
    [
        ([], None),
        ([["Loading…"]], None),
        ([["1", "1", "model", "", "$1 / $2"]], None),
        ([["1", "1", "model", "1500 ± 5", "$1 / $2"]], TSV),
        ([["1", "1", "model", "1500±5Preliminary", "$1 / $2"]], TSV),
        ([["1", "1", "model", "1500", "$1 / $2"], ["Loading…"]], None),
    ],
)
@pytest.mark.parametrize("ready", ["loading", "interactive", "complete"])
def test_extraction_waits_for_complete_table(data, expected, ready):
    """Run the actual JavaScript against loading and populated DOM-shaped rows."""
    rows = [["Rank", "Rank", "Model", "Score", "Price $/M"], *data]
    script = """
    const rows = JSON.parse(process.argv[1]);
    global.document = {readyState: process.argv[3], querySelectorAll: () => rows.map((row, index) => ({
        querySelector: () => index ? {} : null,
        querySelectorAll: () => row.map(innerText => ({innerText, querySelector: () => null}))
    }))};
    console.log(JSON.stringify(eval(process.argv[2])));
    """
    result = subprocess.run(
        ["node", "-e", script, json.dumps(rows), download.EXTRACT_SCRIPT, ready],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == (expected if ready == "complete" else None)


class FakeSocket:
    def __init__(self, *, values=(TSV,), failure=None):
        self.values = deque(values)
        self.failure = failure
        self.commands = []
        self.messages = deque()
        self.closed = False

    def settimeout(self, timeout):
        assert timeout > 0

    def send(self, value):
        command = json.loads(value)
        self.commands.append(command)
        method = command["method"]
        result = {}
        if method == "Target.createTarget":
            result = {"targetId": "owned-tab"}
        elif method == "Target.attachToTarget":
            result = {"sessionId": "owned-session"}
        elif method == "Runtime.evaluate":
            if isinstance(self.failure, Exception):
                self.messages.append(self.failure)
                return
            result = self.failure or {"result": {"value": self.values.popleft()}}
        self.messages.extend(
            [
                {"method": "Target.targetCreated", "params": {"targetId": "unrelated"}},
                {"id": command["id"], "result": result},
            ]
        )

    def recv(self):
        message = self.messages.popleft()
        if isinstance(message, Exception):
            raise message
        return json.dumps(message)

    def close(self):
        self.closed = True


def install_socket(monkeypatch, socket):
    calls = []

    def connect(url, **kwargs):
        calls.append((url, kwargs))
        return socket

    monkeypatch.setattr(download, "create_connection", connect)
    return calls


def test_download_attaches_only_owned_tab_and_waits_for_data(tmp_path, monkeypatch):
    socket = FakeSocket(values=(None, TSV))
    calls = install_socket(monkeypatch, socket)
    monkeypatch.setattr(download.time, "sleep", lambda _: None)
    output = tmp_path / "nested" / "arena.tsv"
    summary = download.write_leaderboard(
        url="https://arena.ai/leaderboard/text",
        output=output,
        cdp="ws://localhost:9222/devtools/browser/test",
        timeout=1000,
    )
    assert output.read_text() == TSV + "\n"
    assert summary["lines"] == 2
    assert summary["bytes"] == len(output.read_bytes())
    assert calls[0][1] == {"timeout": 1.0, "suppress_origin": True}
    assert [c["method"] for c in socket.commands] == [
        "Target.createTarget",
        "Target.attachToTarget",
        "Page.navigate",
        "Runtime.evaluate",
        "Runtime.evaluate",
        "Target.closeTarget",
    ]
    assert socket.commands[1]["params"] == {"targetId": "owned-tab", "flatten": True}
    assert all(c["sessionId"] == "owned-session" for c in socket.commands[2:-1])
    assert socket.commands[-1]["params"] == {"targetId": "owned-tab"}
    assert socket.closed


def test_http_endpoint_discovery(tmp_path, monkeypatch):
    socket = FakeSocket()
    calls = install_socket(monkeypatch, socket)
    requests = []

    def urlopen(url, *, timeout):
        requests.append((url, timeout))
        return io.BytesIO(b'{"webSocketDebuggerUrl":"ws://remote/browser/test"}')

    monkeypatch.setattr(download, "urlopen", urlopen)
    download.write_leaderboard(
        url="https://arena.ai",
        output=tmp_path / "out",
        cdp="http://remote:9222/",
        timeout=1000,
    )
    assert requests == [("http://remote:9222/json/version", 1.0)]
    assert calls[0][0] == "ws://remote/browser/test"


@pytest.mark.parametrize(
    "failure, message",
    [
        (WebSocketTimeoutException("stalled"), "Runtime.evaluate timed out"),
        (
            {"exceptionDetails": {"exception": {"description": "missing Price $/M"}}},
            "missing Price",
        ),
    ],
)
def test_failure_preserves_export_and_closes_owned_tab(
    tmp_path, monkeypatch, failure, message
):
    socket = FakeSocket(failure=failure)
    install_socket(monkeypatch, socket)
    output = tmp_path / "out"
    output.write_text("previous export")
    with pytest.raises((RuntimeError, TimeoutError), match=message):
        download.write_leaderboard(
            url="https://arena.ai",
            output=output,
            cdp="ws://remote/browser/test",
            timeout=1000,
        )
    assert output.read_text() == "previous export"
    assert socket.commands[-1]["params"] == {"targetId": "owned-tab"}
    assert socket.closed


def test_events_do_not_reset_command_deadline(monkeypatch):
    socket = FakeSocket()
    times = iter([0, 0, 0.5, 1.1])
    monkeypatch.setattr(download.time, "monotonic", lambda: next(times))
    with pytest.raises(TimeoutError, match="Target.createTarget"):
        download.CDP(socket, 1000).send("Target.createTarget")


def test_protocol_errors_are_reported():
    socket = FakeSocket()
    socket.messages.append({"id": 1, "error": {"message": "Permission denied"}})
    with pytest.raises(RuntimeError, match="Target.createTarget: Permission denied"):
        download.CDP(socket, 1000).send("Target.createTarget")


def test_table_wait_has_overall_deadline_and_cleans_up(tmp_path, monkeypatch):
    socket = FakeSocket(values=(None,))
    install_socket(monkeypatch, socket)
    now = [0.0]
    monkeypatch.setattr(download.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(download.time, "sleep", lambda _: now.__setitem__(0, 2.0))
    output = tmp_path / "out"
    with pytest.raises(TimeoutError, match="waiting for leaderboard rows"):
        download.write_leaderboard(
            url="https://arena.ai",
            output=output,
            cdp="ws://remote/browser/test",
            timeout=1000,
        )
    assert not output.exists()
    assert socket.commands[-1]["method"] == "Target.closeTarget"
    assert socket.closed


@pytest.mark.parametrize(
    "method, result, message",
    [
        (
            "Target.attachToTarget",
            {"error": {"message": "Cannot attach"}},
            "Cannot attach",
        ),
        (
            "Page.navigate",
            {"result": {"errorText": "net::ERR_FAILED"}},
            "net::ERR_FAILED",
        ),
    ],
)
def test_attach_and_navigation_failure_close_tab(
    tmp_path, monkeypatch, method, result, message
):
    socket = FakeSocket()
    install_socket(monkeypatch, socket)
    original_send = socket.send

    def send(value):
        original_send(value)
        command = json.loads(value)
        if command["method"] == method:
            socket.messages.clear()
            socket.messages.append({"id": command["id"], **result})

    monkeypatch.setattr(socket, "send", send)
    with pytest.raises(RuntimeError, match=message):
        download.write_leaderboard(
            url="https://arena.ai",
            output=tmp_path / "out",
            cdp="ws://remote/browser/test",
            timeout=1000,
        )
    assert socket.commands[-1]["method"] == "Target.closeTarget"
    assert socket.closed


def test_cli_reports_connection_timeout_without_claiming_page_loaded(monkeypatch):
    def fail(**kwargs):
        raise TimeoutError("CDP Target.attachToTarget timed out")

    monkeypatch.setattr(download, "write_leaderboard", fail)
    result = CliRunner().invoke(download.app, ["https://arena.ai", "out.tsv"])
    assert result.exit_code == 1
    assert "Target.attachToTarget timed out" in result.output
    assert "while loading" not in result.output
