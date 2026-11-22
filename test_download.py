import io
import json
import subprocess
from collections import deque

import pytest
from typer.testing import CliRunner
from websocket import WebSocketTimeoutException

import download

TSV = "Model\tScore\tPrice $/M\nmodel\t1500\t$1 / $2"


def extract(tables, ready="complete", rendered=True, ranking=None):
    """Run the real extractor with independently controllable DOM and rendered text."""
    script = """
    const tables = JSON.parse(process.argv[1]);
    const rendered = JSON.parse(process.argv[4]);
    const ranking = JSON.parse(process.argv[5]);
    const cell = value => {
        const textContent = typeof value === 'string' ? value : value.text;
        return {textContent, innerText: rendered ? textContent : '',
            querySelector: selector => selector === 'a' && typeof value === 'object' && value.link ? cell(value.link)
                : selector === '[title]' && value.title ? {title: value.title} : null};
    };
    let clicked = false;
    const button = {textContent: 'View all', click: () => { clicked = true; }};
    const lists = ranking ? [{
        previousElementSibling: {children: ranking.headers.map(cell)},
        children: ranking.rows.map(row => ({children: row.map(cell)})),
        closest: () => ({querySelectorAll: () => ranking.collapsed ? [button] : []}),
    }] : [];
    global.document = {
        readyState: process.argv[3], title: 'Arena',
        querySelectorAll: selector => selector === 'ol' ? lists : tables.map(rows => ({
            querySelectorAll: () => rows.map(row => ({querySelectorAll: () => row.map(cell)}))
        }))
    };
    global.location = {href: 'https://arena.ai/leaderboard/chat/text'};
    const result = eval(process.argv[2]);
    console.log(JSON.stringify(clicked ? {...result, clicked} : result));
    """
    result = subprocess.run(
        [
            "node", "-e", script, json.dumps(tables), download.EXTRACT_SCRIPT,
            ready, json.dumps(rendered), json.dumps(ranking),
        ],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


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
    result = extract([rows], ready)
    if expected is None:
        assert result["waiting"]
    else:
        assert result == expected


@pytest.mark.parametrize("rendered", [True, False])
def test_extraction_uses_headers_and_dom_text(rendered):
    unrelated = [["Model", "Votes"], ["wrong-model", "9999"]]
    leaderboard = [
        [" Votes ", " Price\n$/M ", " SCORE ", "Rank", " Model "],
        ["5000", "$1 / $2", "1500±5Preliminary", "1", "model"],
    ]
    assert extract([unrelated, leaderboard], "loading", rendered) == TSV


@pytest.mark.parametrize(
    "rows, reason",
    [
        ([], "table"),
        ([["Model", "Score"], ["model", "1500"]], "Price $/M"),
        ([["Model", "Score", "Price $/M"], ["", "1500", "$1"]], "model"),
        ([["Model", "Score", "Price $/M"], ["model", "", "$1"]], "score"),
        ([["Model", "Score", "Price $/M"], ["model", "1500", ""]], "price"),
    ],
)
def test_extraction_reports_why_data_is_not_ready(rows, reason):
    assert reason in extract([rows])["waiting"]


def test_unavailable_price_is_valid_data():
    assert extract([[["Model", "Score", "Price $/M"], ["model", "1500", "N/A"]]]) == TSV.replace("$1 / $2", "N/A")


@pytest.mark.parametrize("model", ["model\nProvider", {"text": "modelProvider", "link": "model"}])
def test_model_metadata_is_not_part_of_name(model):
    assert extract([[["Model", "Score", "Price $/M"], [model, "1500", "$1 / $2"]]]) == TSV


@pytest.mark.parametrize("collapsed", [False, True])
def test_ranked_list_expands_and_reads_input_output_price(collapsed):
    ranking = {
        "headers": ["Model Ranking", "Score", "Cost per task (P50)", "Blended price $/M (3:1)"],
        "rows": [
            [{"text": "1model", "link": "model"}, "1,500", "$0.05", {"text": "$8", "title": "$1 / $2"}],
            [{"text": "2unpriced", "link": "unpriced"}, "1,499", "N/A", "N/A"],
        ],
        "collapsed": collapsed,
    }
    result = extract([], ranking=ranking)
    if collapsed:
        assert result["clicked"] and result["waiting"]
    else:
        assert result == TSV + "\nunpriced\t1499\tN/A"
        ranking["rows"][0][3] = "$8"
        assert "price" in extract([], ranking=ranking)["waiting"]


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
    socket = FakeSocket(values=({"waiting": "No leaderboard table found (page: Just a moment...)"},))
    install_socket(monkeypatch, socket)
    now = [0.0]
    monkeypatch.setattr(download.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(download.time, "sleep", lambda _: now.__setitem__(0, 2.0))
    output = tmp_path / "out"
    with pytest.raises(TimeoutError, match="Just a moment"):
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
