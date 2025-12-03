from app.utils.constants import (
    SIMILARITY_BANDS,
    SIMILARITY_PALETTE,
    SIMILARITY_SCALE_LABEL,
)


def test_similarity_bands_cover_full_scale() -> None:
    assert SIMILARITY_SCALE_LABEL == "0-100%"
    assert len(SIMILARITY_BANDS) == 5
    assert [band.color for band in SIMILARITY_BANDS] == list(SIMILARITY_PALETTE)
    assert SIMILARITY_BANDS[0].min_score == 0
    assert SIMILARITY_BANDS[-1].max_score == 100

    expected = [
        ("Very Low", (0, 20)),
        ("Low", (21, 40)),
        ("Medium", (41, 65)),
        ("High", (66, 85)),
        ("Very High", (86, 100)),
    ]

    for band, (label, bounds) in zip(SIMILARITY_BANDS, expected):
        assert band.label == label
        assert (band.min_score, band.max_score) == bounds
        assert band.bucket

    for current, nxt in zip(SIMILARITY_BANDS, SIMILARITY_BANDS[1:]):
        assert current.max_score < nxt.min_score
