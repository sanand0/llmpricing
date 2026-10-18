from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

import update_elo

from update_elo import (
    OpenRouterMatcher,
    OpenRouterModel,
    UpdateEloError,
    apply_updates,
    apply_arena_prices,
    infer_openrouter_end_label,
    lowest_prompt_price,
    read_elo_rows,
    read_arena_prices,
    write_rows,
)

HEADERS = ["model", "overall", "hard", "coding", "cpmi", "launch", "end", "source"]


def openrouter_model(
    model_id: str,
    *,
    price: str = "0.000001",
    end: str | None = None,
) -> OpenRouterModel:
    return OpenRouterModel(
        model_id=model_id,
        canonical_slug=f"{model_id.split(':', 1)[0]}-20260826",
        prompt_price=Decimal(price),
        launch_label="2026-08",
        end_label=end,
    )


def test_matcher_prefers_base_model_over_batch_variant() -> None:
    matcher = OpenRouterMatcher(
        [
            openrouter_model("z-ai/glm-5.3-flash", price="0.000000075"),
            openrouter_model("z-ai/glm-5.3-flash:batch", price="0.00000015"),
        ]
    )

    assert matcher.match("glm-5.3-flash").model_id == "z-ai/glm-5.3-flash"


def test_matcher_drops_reasoning_effort_suffixes() -> None:
    matcher = OpenRouterMatcher([openrouter_model("z-ai/glm-5.3")])

    assert matcher.match("glm-5.3-max").model_id == "z-ai/glm-5.3"
    assert matcher.match("glm-5.3-xhigh").model_id == "z-ai/glm-5.3"


def test_matcher_drops_preview_and_quantization_suffixes() -> None:
    matcher = OpenRouterMatcher(
        [
            openrouter_model("deepseek/deepseek-v4-flash"),
            openrouter_model("nvidia/nemotron-3-ultra-550b-a55b"),
        ]
    )

    assert (
        matcher.match("deepseek-v4-flash-high-preview").model_id
        == "deepseek/deepseek-v4-flash"
    )
    assert (
        matcher.match("nvidia-nemotron-3-ultra-550b-a55b-nvfp4").model_id
        == "nvidia/nemotron-3-ultra-550b-a55b"
    )


def test_matcher_uses_verified_explicit_alias() -> None:
    matcher = OpenRouterMatcher(
        [
            openrouter_model("meta/muse-glimmer-30b", price="0.0000003"),
            openrouter_model("meta/muse-glimmer-30b:batch", price="0.00000035"),
        ]
    )

    assert matcher.match("muse-glimmer").model_id == "meta/muse-glimmer-30b"


def test_lowest_prompt_price_uses_endpoint_prices() -> None:
    payload = {
        "data": {
            "endpoints": [
                {"pricing": {"prompt": "0.0000014"}},
                {"pricing": {"prompt": "0.0000011875"}},
                {"tag": "openai/flex", "pricing": {"prompt": "0.0000005"}},
                {"pricing": {"prompt": "invalid"}},
            ]
        }
    }

    assert lowest_prompt_price(payload) == Decimal("0.0000011875")


def test_max_alias_uses_live_endpoint_price() -> None:
    row = dict(zip(HEADERS, ["glm-5.3-max", "", "", "", "", "", "", ""]))
    matcher = OpenRouterMatcher(
        [openrouter_model("z-ai/glm-5.3", price="0.0000014")]
    )

    apply_updates(
        HEADERS,
        [row],
        target_column="overall",
        updates={"glm-5.3-max": "1500"},
        matcher=matcher,
        now=datetime(2026, 8, 30, tzinfo=UTC),
        prompt_price=lambda _: Decimal("0.0000011875"),
    )

    assert row == dict(
        zip(
            HEADERS,
            [
                "glm-5.3-max",
                "1500",
                "",
                "",
                "1.1875",
                "2026-08",
                "",
                "https://openrouter.ai/z-ai/glm-5.3",
            ],
        )
    )


def test_overall_update_does_not_infer_expiry_from_absence() -> None:
    rows = [
        dict(zip(HEADERS, ["present", "1", "", "", "", "", "", ""])),
        dict(zip(HEADERS, ["absent", "2", "", "", "", "", "", ""])),
    ]

    summary = apply_updates(
        HEADERS,
        rows,
        target_column="overall",
        updates={"present": "3"},
        matcher=OpenRouterMatcher([]),
        now=datetime(2026, 8, 30, tzinfo=UTC),
    )

    assert rows[1]["end"] == ""
    assert not hasattr(summary, "ended")


@pytest.mark.parametrize("end", ["2026-08", "2026-08?", "not-a-date"])
def test_read_elo_rejects_non_exact_end_dates(tmp_path: Path, end: str) -> None:
    elo_path = tmp_path / "elo.csv"
    elo_path.write_text(
        f"model,overall,hard,coding,cpmi,launch,end,source\nmodel,1,,,,,{end},\n",
        encoding="utf-8",
    )

    with pytest.raises(UpdateEloError, match="invalid end date"):
        read_elo_rows(elo_path)


def test_write_elo_rejects_new_invalid_end(tmp_path: Path) -> None:
    row = dict(zip(HEADERS, ["model", "1", "", "", "", "", "2026-08?", ""]))

    with pytest.raises(UpdateEloError, match="invalid end date"):
        write_rows(tmp_path / "elo.csv", HEADERS, [row])


def test_openrouter_expiry_fills_blank_end_without_overwriting_existing() -> None:
    blank = dict(zip(HEADERS, ["glm-4.5", "", "", "", "", "", "", ""]))
    existing = dict(
        zip(HEADERS, ["glm-4.5-high", "", "", "", "", "", "2026-11-30", ""])
    )
    matcher = OpenRouterMatcher(
        [openrouter_model("z-ai/glm-4.5", end="2026-12-31")]
    )

    apply_updates(
        HEADERS,
        [blank, existing],
        target_column="overall",
        updates={"glm-4.5": "1400", "glm-4.5-high": "1410"},
        matcher=matcher,
        now=datetime(2026, 8, 30, tzinfo=UTC),
    )

    assert blank["end"] == "2026-12-31"
    assert existing["end"] == "2026-11-30"


def test_openrouter_sentinel_expiry_is_ignored() -> None:
    assert infer_openrouter_end_label("2098-12-31") is None
    assert infer_openrouter_end_label("invalid") is None
    assert infer_openrouter_end_label("2026-12-31") == "2026-12-31"


def test_read_arena_input_prices(tmp_path: Path) -> None:
    path = tmp_path / "arena.tsv"
    path.write_text(
        "Model\tScore\tPrice $/M\npriced\t1500\t$1.40 / $4.40\n"
        "missing\t1400\tN/A\nfree\t1300\t$0 / $1\n",
        encoding="utf-8",
    )
    assert read_arena_prices(path) == {"priced": Decimal("1.4"), "free": Decimal("0")}


@pytest.mark.parametrize("value", ["invalid", "NaN", "Infinity", "-1"])
def test_read_arena_rejects_invalid_prices(tmp_path: Path, value: str) -> None:
    path = tmp_path / "arena.tsv"
    path.write_text(f"Model\tScore\tPrice $/M\nmodel\t1500\t{value}\n", encoding="utf-8")
    with pytest.raises(UpdateEloError, match="Invalid Arena price"):
        read_arena_prices(path)


def test_arena_fills_only_missing_costs_and_warns(capsys) -> None:
    rows = [
        dict(zip(HEADERS, [name, "1", "", "", cost, "", "", "old-source"]))
        for name, cost in [("blank", ""), ("different", "2"), ("equal", "1.00"), ("unknown", "")]
    ]
    filled = apply_arena_prices(rows, {name: Decimal("1") for name in ["blank", "different", "equal"]})
    assert filled == 1
    assert [row["cpmi"] for row in rows] == ["1", "2", "1.00", ""]
    assert rows[0]["source"] == "https://arena.ai/leaderboard/text"
    assert rows[1]["source"] == "old-source"
    assert capsys.readouterr().out == "Model\telo.csv\tarena.ai\ndifferent\t2\t1\n"


def test_arena_prices_disable_openrouter_cost_fallback() -> None:
    rows = []
    summary = apply_updates(
        HEADERS, rows, target_column="overall",
        updates={"priced": "1500", "unknown": "1400", "free": "1300"},
        matcher=OpenRouterMatcher([openrouter_model(name) for name in ["priced", "unknown", "free"]]),
        now=datetime(2026, 10, 4, tzinfo=UTC),
        arena_prices={"priced": Decimal("2"), "free": Decimal("0")},
    )
    assert [row["cpmi"] for row in rows] == ["2", "", "0"]
    assert summary.priced == 2
    assert all(row["launch"] == "2026-08" for row in rows)


def test_cli_arena_write_and_dry_run(tmp_path: Path, monkeypatch) -> None:
    elo = tmp_path / "elo.csv"
    elo.write_text("model,overall,hard,coding,cpmi,launch,end,source\nmodel,1,,,2,2026-08,,old\n")
    original = elo.read_bytes()
    tsv = tmp_path / "arena.tsv"
    tsv.write_text("Model\tScore\tPrice $/M\nmodel\t1500\t$3 / $10\nnew\t1400\t$0.50 / $2\n")
    monkeypatch.setattr(update_elo, "fetch_openrouter_models", lambda: [])
    args = [str(tsv), "--column", "overall", "--elo", str(elo)]
    runner = CliRunner()
    preview = runner.invoke(update_elo.app, [*args, "--dry-run"])
    assert preview.exit_code == 0, preview.output
    assert elo.read_bytes() == original
    assert "elo.csv (dry run): 1 added, 1 changed, 0 removed, 0 unchanged" in preview.stderr
    result = runner.invoke(update_elo.app, args)
    assert result.exit_code == 0, result.output
    assert "Model\telo.csv\tarena.ai\nmodel\t2\t3\n" in result.output
    assert "1 models from Arena" in result.output
    assert "elo.csv: 1 added, 1 changed, 0 removed, 0 unchanged" in result.stderr
    assert "~ model: overall: '1' -> '1500'" in result.stderr
    assert "+ new: overall='1400'; cpmi='0.5'" in result.stderr
    _, rows = read_elo_rows(elo)
    assert [(row["model"], row["overall"], row["cpmi"]) for row in rows] == [
        ("model", "1500", "2"), ("new", "1400", "0.5")
    ]


def test_change_log_includes_cleared_fields_removals_and_excludes_unchanged(capsys):
    before = [
        {"model": "changed", "overall": "1500", "end": "2026-12-31"},
        {"model": "removed", "overall": "1400", "end": ""},
        {"model": "unchanged", "overall": "1300", "end": ""},
    ]
    after = [{**before[0], "end": ""}, before[2],
             {"model": "added", "overall": "1550", "end": ""}]
    update_elo.print_changes(before, after, elo_path=Path("elo.csv"), dry_run=False)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines() == [
        "elo.csv: 1 added, 1 changed, 1 removed, 1 unchanged",
        "  + added: overall='1550'",
        "  ~ changed: end: '2026-12-31' -> ''",
        "  - removed: overall='1400'",
    ]


@pytest.mark.parametrize("column, target", [
    ("text", "overall"), ("overall", "overall"), ("hard", "hard"),
    ("code", "coding"), ("coding", "coding"),
])
def test_cli_updates_only_selected_column_and_reports_noop(tmp_path, monkeypatch, column, target):
    elo = tmp_path / "elo.csv"
    original = dict(zip(HEADERS, ["existing", "1500", "1400", "1300", "2", "2026-08", "2026-12-31", "old"]))
    absent = dict(zip(HEADERS, ["absent", "1200", "1100", "1000", "3", "2026-07", "", "old"]))
    write_rows(elo, HEADERS, [original, absent])
    tsv = tmp_path / "arena.tsv"
    tsv.write_text("Model\tScore\tPrice $/M\nexisting\t1600\tN/A\n")
    monkeypatch.setattr(update_elo, "fetch_openrouter_models", list)
    args = [str(tsv), "--column", column, "--elo", str(elo)]
    result = CliRunner().invoke(update_elo.app, args)
    assert result.exit_code == 0, result.output
    assert read_elo_rows(elo)[1] == [{**original, target: "1600"}, absent]
    assert f"~ existing: {target}: '{original[target]}' -> '1600'" in result.stderr
    assert "0 removed, 1 unchanged" in result.stderr
    repeated = CliRunner().invoke(update_elo.app, args)
    assert repeated.exit_code == 0, repeated.output
    assert "0 added, 0 changed, 0 removed, 2 unchanged" in repeated.stderr
    assert "~ existing" not in repeated.stderr


def test_new_models_insert_by_score_without_inventing_launch():
    rows = [dict(zip(HEADERS, ["existing", "1500", "", "", "2", "2026-08", "", "old"]))]
    apply_updates(HEADERS, rows, target_column="overall",
                  updates={"lower": "1400", "higher": "1600"}, matcher=OpenRouterMatcher([]),
                  now=datetime(2026, 1, 2, tzinfo=UTC), arena_prices={})
    assert [row["model"] for row in rows] == ["higher", "existing", "lower"]
    assert rows[0]["launch"] == rows[2]["launch"] == ""
    assert rows[0]["cpmi"] == rows[2]["cpmi"] == ""


def test_arena_display_names_update_existing_slugs_without_adding_duplicates(capsys):
    rows = [
        dict(zip(HEADERS, ["glm-5.3-flash", "1475", "1501", "1525",
                           "0.15", "2026-08", "", "https://api.deepinfra.com/models/list"])),
        dict(zip(HEADERS, ["command-r", "1227", "1215", "1244",
                           "0.5", "2024-03", "", "source"])),
        dict(zip(HEADERS, ["command-r-plus", "1262", "1252", "1273",
                           "3", "2024-04", "", "source"])),
    ]
    summary = apply_updates(
        HEADERS, rows, target_column="overall",
        updates={"GLM-5.3-Flash": "1474", "Command R": "1228", "Command R+": "1263"},
        matcher=OpenRouterMatcher([]), now=datetime(2026, 10, 18, tzinfo=UTC),
        arena_prices={"GLM-5.3-Flash": Decimal("0.05"), "Command R": Decimal("0.15"),
                      "Command R+": Decimal("3")},
    )
    assert summary.added == 0
    assert len(rows) == 3
    assert [(r["model"], r["overall"]) for r in rows] == [
        ("glm-5.3-flash", "1474"), ("command-r", "1228"), ("command-r-plus", "1263")
    ]
    assert rows[0]["cpmi"] == "0.15"  # Existing audited price takes precedence.
    assert "glm-5.3-flash\t0.15\t0.05" in capsys.readouterr().out


def test_arena_qualifier_reordering_maps_to_existing_variant():
    rows = [dict(zip(HEADERS, ["claude-opus-4-5-20251101-high-32k",
                                "1474", "1501", "1531", "5", "2025-11", "", "source"]))]
    result = apply_updates(
        HEADERS, rows, target_column="overall",
        updates={"Claude Opus 4.5 (High, 32K, 20251101)": "1475"},
        matcher=OpenRouterMatcher([]), now=datetime(2026, 10, 18, tzinfo=UTC),
        arena_prices={},
    )
    assert result.added == 0
    assert rows[0]["overall"] == "1475"


def test_duplicate_normalized_identifiers_are_rejected():
    rows = [dict(zip(HEADERS, [name, "1474", "", "", "", "", "", ""]))
            for name in ("glm-5.3-flash", "GLM-5.3-Flash")]
    with pytest.raises(UpdateEloError, match="Duplicate model identifiers"):
        apply_updates(
            HEADERS, rows, target_column="overall", updates={"GLM-5.3-Flash": "1475"},
            matcher=OpenRouterMatcher([]), now=datetime(2026, 10, 18, tzinfo=UTC),
            arena_prices={},
        )


@pytest.mark.parametrize("content", ["", "Model\tScore\n", "Model\tScore\nmodel\tinvalid\n",
                                         "Model\tScore\n\t1500\n", "Model\tScore\nmodel\n"])
def test_invalid_tsv_does_not_write_csv(tmp_path, monkeypatch, content):
    elo = tmp_path / "elo.csv"
    write_rows(elo, HEADERS, [])
    original = elo.read_bytes()
    tsv = tmp_path / "arena.tsv"
    tsv.write_text(content)
    monkeypatch.setattr(update_elo, "fetch_openrouter_models", lambda: pytest.fail("must validate before fetching"))
    result = CliRunner().invoke(update_elo.app, [str(tsv), "--column", "overall", "--elo", str(elo)])
    assert result.exit_code == 1
    assert "Error:" in result.output
    assert elo.read_bytes() == original


def test_matcher_rejects_ambiguous_models():
    matcher = OpenRouterMatcher([openrouter_model("provider-a/shared"), openrouter_model("provider-b/shared")])
    assert matcher.match("shared") is None


def test_metadata_fetch_failure_does_not_write_csv(tmp_path, monkeypatch):
    elo = tmp_path / "elo.csv"
    write_rows(elo, HEADERS, [])
    original = elo.read_bytes()
    tsv = tmp_path / "arena.tsv"
    tsv.write_text("Model\tScore\tPrice $/M\nmodel\t1500\t$1 / $2\n")

    def fail():
        raise update_elo.httpx.ConnectError("offline")

    monkeypatch.setattr(update_elo, "fetch_openrouter_models", fail)
    result = CliRunner().invoke(update_elo.app, [str(tsv), "--column", "overall", "--elo", str(elo)])
    assert result.exit_code == 1
    assert "failed to fetch OpenRouter models: offline" in result.output
    assert elo.read_bytes() == original
