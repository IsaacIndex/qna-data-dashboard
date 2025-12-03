from __future__ import annotations

import math

from app.services.search import (
    build_similarity_legend,
    describe_similarity_score,
    similarity_to_percent,
)
from app.utils.constants import SIMILARITY_BANDS, SIMILARITY_SCALE_LABEL


def test_similarity_to_percent_clamps_range() -> None:
    assert similarity_to_percent(0.5) == 50.0
    assert similarity_to_percent(1.2) == 100.0
    assert similarity_to_percent(-0.25) == 0.0
    assert math.isclose(similarity_to_percent(0.7564), 75.64, rel_tol=1e-6)


def test_describe_similarity_maps_to_band() -> None:
    label, color = describe_similarity_score(87.0)
    assert label == "Very High"
    assert color == SIMILARITY_BANDS[-1].color

    label_low, color_low = describe_similarity_score(10.0)
    assert label_low == "Very Low"
    assert color_low == SIMILARITY_BANDS[0].color


def test_build_similarity_legend_returns_palette() -> None:
    legend = build_similarity_legend()
    assert legend["scale"] == SIMILARITY_SCALE_LABEL
    assert len(legend["palette"]) == len(SIMILARITY_BANDS)
    assert legend["palette"][0]["label"] == SIMILARITY_BANDS[0].label
    assert legend["palette"][-1]["max"] == SIMILARITY_BANDS[-1].max_score
