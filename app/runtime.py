from app.config import settings
from app.model import ModelManager
from app.observability.drift import DriftMonitor

manager = ModelManager(settings)
drift_monitor = DriftMonitor(
    service=settings.service_name,
    window_size=settings.drift_window_size,
    min_samples=settings.drift_min_samples,
    threshold=settings.drift_zscore_threshold,
)
