from tools.external_smoke import percentile


def test_percentile_uses_nearest_rank() -> None:
    assert percentile([0.1, 0.2, 0.3, 0.4], 0.95) == 0.4


def test_percentile_sorts_values() -> None:
    assert percentile([0.4, 0.1, 0.3, 0.2], 0.5) == 0.2
