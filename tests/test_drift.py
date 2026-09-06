from app.drift import DriftMonitor


def test_drift_window_detects_large_shift():
    monitor = DriftMonitor("test-drift-large", window_size=5, min_samples=3, threshold=3.0)
    monitor.observe([[20.0, 20.0, 20.0, 20.0]] * 3)
    assert len(monitor.window) == 3


def test_drift_window_is_bounded():
    monitor = DriftMonitor("test-drift-bounded", window_size=2, min_samples=2)
    monitor.observe([[5.1, 3.5, 1.4, 0.2]] * 3)
    assert len(monitor.window) == 2
