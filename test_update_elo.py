from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from update_elo import (
    OpenRouterMatcher,
    OpenRouterModel,
    UpdateEloError,
    apply_updates,
    infer_openrouter_end_label,
    lowest_prompt_price,
    read_elo_rows,
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
