from __future__ import annotations

import importlib

from app.utils.constants import SIMILARITY_BANDS


def _load_search_page():
    return importlib.import_module("app.pages.2_search")


def test_similarity_legend_table_matches_bands() -> None:
    page = _load_search_page()
    legend_df = page.build_similarity_legend_table()

    assert not legend_df.empty
    assert {"Label", "Range", "Color"} <= set(legend_df.columns)
    assert len(legend_df) == len(SIMILARITY_BANDS)
    assert legend_df.iloc[0]["Label"] == SIMILARITY_BANDS[0].label


def test_guidance_mentions_defaults_when_no_preferences() -> None:
    page = _load_search_page()
    defaults = [
        {
            "dataset_id": "ds-1",
            "dataset_name": "Dataset One",
            "source": "dataset",
            "columns": [
                {"name": "question", "display_label": "question"},
                {"name": "response", "display_label": "Response"},
            ],
        }
    ]

    message = page.build_contextual_guidance(defaults=defaults, has_preferences=False)
    assert message, "Expected guidance message when no preferences are saved"
    assert "Dataset One" in message
    assert "question" in message.lower()
