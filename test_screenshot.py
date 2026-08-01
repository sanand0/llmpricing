from pathlib import Path

import pytest

from screenshot import ScreenshotError, parse_models, screenshot_path


def test_parse_models_splits_deduplicates_and_preserves_order() -> None:
    assert parse_models("gpt, gemini,gpt") == ["gpt", "gemini"]


@pytest.mark.parametrize("value", ["", "gpt,,gemini", "../gpt", "gpt/4"])
def test_parse_models_rejects_unsafe_or_empty_values(value: str) -> None:
    with pytest.raises(ScreenshotError):
        parse_models(value)


def test_screenshot_path_zero_pads_date() -> None:
    assert screenshot_path(Path("screenshots"), "gpt", 38) == Path("screenshots/gpt-038.png")
