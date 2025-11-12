"""Vision metrics tracking system.

Tracks OCR accuracy, MAE for amounts, card recognition accuracy,
with configurable thresholds and alert system.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import numpy as np
from holdem.utils.logging import get_logger

logger = get_logger("vision.metrics")


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class Alert:
    """Represents a metric alert."""
    level: AlertLevel
    metric_name: str
    message: str
    timestamp: float
    current_value: float
    threshold: float


@dataclass
class VisionMetricsConfig:
    """Configuration for vision metrics thresholds."""
    # OCR thresholds
    ocr_accuracy_warning: float = 0.90  # 90%
    ocr_accuracy_critical: float = 0.80  # 80%
    
    # Amount MAE thresholds (in big blinds)
    amount_mae_warning: float = 1.0  # 1 BB
    amount_mae_critical: float = 2.0  # 2 BB
    
    # Card recognition thresholds
    card_accuracy_warning: float = 0.95  # 95%
    card_accuracy_critical: float = 0.90  # 90%
    
    # Minimum samples before alerting
    min_samples_for_alert: int = 10


@dataclass
class OCRResult:
    """Represents an OCR reading with ground truth for validation."""
    detected_text: str
    expected_text: Optional[str] = None
    is_correct: Optional[bool] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class AmountResult:
    """Represents an amount reading (stack, pot, bet) with ground truth."""
    detected_amount: Optional[float]
    expected_amount: Optional[float] = None
    absolute_error: Optional[float] = None
    timestamp: float = field(default_factory=time.time)
    category: str = "unknown"  # "stack", "pot", "bet"


@dataclass
class CardRecognitionResult:
    """Represents a card recognition result."""
    detected_card: Optional[str]  # e.g., "Ah", "Kd"
    expected_card: Optional[str] = None
    is_correct: Optional[bool] = None
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)


class VisionMetrics:
    """Central metrics tracking for vision system.
    
    Tracks:
    - OCR accuracy percentage
    - MAE (Mean Absolute Error) for amounts
    - Card recognition accuracy
    - Performance metrics (latency)
    - Alerts when metrics fall below thresholds
    """
    
    def __init__(self, config: Optional[VisionMetricsConfig] = None):
        """Initialize metrics tracker.
        
        Args:
            config: Configuration with thresholds, or None for defaults
        """
        self.config = config or VisionMetricsConfig()
        
        # OCR tracking
        self.ocr_results: List[OCRResult] = []
        
        # Amount tracking
        self.amount_results: List[AmountResult] = []
        
        # Card recognition tracking
        self.card_results: List[CardRecognitionResult] = []
        
        # Performance tracking
        self.ocr_latencies: List[float] = []
        self.card_recognition_latencies: List[float] = []
        self.parse_latencies: List[float] = []
        
        # Alert tracking
        self.alerts: List[Alert] = []
        
        # Session tracking
        self.session_start = time.time()
    
    def record_ocr(
        self,
        detected_text: str,
        expected_text: Optional[str] = None,
        latency_ms: Optional[float] = None
    ):
        """Record an OCR reading.
        
        Args:
            detected_text: Text detected by OCR
            expected_text: Ground truth text (if known)
            latency_ms: Time taken for OCR (milliseconds)
        """
        is_correct = None
        if expected_text is not None:
            is_correct = detected_text.strip().lower() == expected_text.strip().lower()
        
        result = OCRResult(
            detected_text=detected_text,
            expected_text=expected_text,
            is_correct=is_correct
        )
        self.ocr_results.append(result)
        
        if latency_ms is not None:
            self.ocr_latencies.append(latency_ms)
        
        # Check for alerts
        self._check_ocr_alerts()
    
    def record_amount(
        self,
        detected_amount: Optional[float],
        expected_amount: Optional[float] = None,
        category: str = "unknown"
    ):
        """Record an amount reading (stack, pot, bet).
        
        Args:
            detected_amount: Amount detected by OCR
            expected_amount: Ground truth amount (if known)
            category: Type of amount ("stack", "pot", "bet")
        """
        absolute_error = None
        if expected_amount is not None and detected_amount is not None:
            absolute_error = abs(detected_amount - expected_amount)
        
        result = AmountResult(
            detected_amount=detected_amount,
            expected_amount=expected_amount,
            absolute_error=absolute_error,
            category=category
        )
        self.amount_results.append(result)
        
        # Check for alerts
        self._check_amount_alerts()
    
    def record_card_recognition(
        self,
        detected_card: Optional[str],
        expected_card: Optional[str] = None,
        confidence: float = 0.0,
        latency_ms: Optional[float] = None
    ):
        """Record a card recognition result.
        
        Args:
            detected_card: Card detected (e.g., "Ah")
            expected_card: Ground truth card (if known)
            confidence: Recognition confidence score
            latency_ms: Time taken for recognition (milliseconds)
        """
        is_correct = None
        if expected_card is not None and detected_card is not None:
            is_correct = detected_card.lower() == expected_card.lower()
        
        result = CardRecognitionResult(
            detected_card=detected_card,
            expected_card=expected_card,
            is_correct=is_correct,
            confidence=confidence
        )
        self.card_results.append(result)
        
        if latency_ms is not None:
            self.card_recognition_latencies.append(latency_ms)
        
        # Check for alerts
        self._check_card_alerts()
    
    def record_parse_latency(self, latency_ms: float):
        """Record full state parse latency.
        
        Args:
            latency_ms: Time taken for full state parse (milliseconds)
        """
        self.parse_latencies.append(latency_ms)
    
    def _check_ocr_alerts(self):
        """Check OCR accuracy and generate alerts if needed."""
        if len(self.ocr_results) < self.config.min_samples_for_alert:
            return
        
        # Calculate recent accuracy (last N samples)
        recent_results = self.ocr_results[-self.config.min_samples_for_alert:]
        correct_results = [r for r in recent_results if r.is_correct is True]
        accuracy = len(correct_results) / len(recent_results)
        
        if accuracy < self.config.ocr_accuracy_critical:
            alert = Alert(
                level=AlertLevel.CRITICAL,
                metric_name="ocr_accuracy",
                message=f"OCR accuracy critically low: {accuracy:.1%}",
                timestamp=time.time(),
                current_value=accuracy,
                threshold=self.config.ocr_accuracy_critical
            )
            self.alerts.append(alert)
            logger.error(alert.message)
        elif accuracy < self.config.ocr_accuracy_warning:
            alert = Alert(
                level=AlertLevel.WARNING,
                metric_name="ocr_accuracy",
                message=f"OCR accuracy below warning threshold: {accuracy:.1%}",
                timestamp=time.time(),
                current_value=accuracy,
                threshold=self.config.ocr_accuracy_warning
            )
            self.alerts.append(alert)
            logger.warning(alert.message)
    
    def _check_amount_alerts(self):
        """Check amount MAE and generate alerts if needed."""
        # Only check amounts with ground truth
        results_with_error = [r for r in self.amount_results if r.absolute_error is not None]
        
        if len(results_with_error) < self.config.min_samples_for_alert:
            return
        
        # Calculate recent MAE (last N samples)
        recent_results = results_with_error[-self.config.min_samples_for_alert:]
        errors = [r.absolute_error for r in recent_results]
        mae = np.mean(errors)
        
        if mae > self.config.amount_mae_critical:
            alert = Alert(
                level=AlertLevel.CRITICAL,
                metric_name="amount_mae",
                message=f"Amount MAE critically high: {mae:.2f}",
                timestamp=time.time(),
                current_value=mae,
                threshold=self.config.amount_mae_critical
            )
            self.alerts.append(alert)
            logger.error(alert.message)
        elif mae > self.config.amount_mae_warning:
            alert = Alert(
                level=AlertLevel.WARNING,
                metric_name="amount_mae",
                message=f"Amount MAE above warning threshold: {mae:.2f}",
                timestamp=time.time(),
                current_value=mae,
                threshold=self.config.amount_mae_warning
            )
            self.alerts.append(alert)
            logger.warning(alert.message)
    
    def _check_card_alerts(self):
        """Check card recognition accuracy and generate alerts if needed."""
        if len(self.card_results) < self.config.min_samples_for_alert:
            return
        
        # Calculate recent accuracy (last N samples)
        recent_results = self.card_results[-self.config.min_samples_for_alert:]
        results_with_truth = [r for r in recent_results if r.is_correct is not None]
        
        if len(results_with_truth) < self.config.min_samples_for_alert:
            return
        
        correct_results = [r for r in results_with_truth if r.is_correct is True]
        accuracy = len(correct_results) / len(results_with_truth)
        
        if accuracy < self.config.card_accuracy_critical:
            alert = Alert(
                level=AlertLevel.CRITICAL,
                metric_name="card_accuracy",
                message=f"Card recognition accuracy critically low: {accuracy:.1%}",
                timestamp=time.time(),
                current_value=accuracy,
                threshold=self.config.card_accuracy_critical
            )
            self.alerts.append(alert)
            logger.error(alert.message)
        elif accuracy < self.config.card_accuracy_warning:
            alert = Alert(
                level=AlertLevel.WARNING,
                metric_name="card_accuracy",
                message=f"Card recognition accuracy below warning threshold: {accuracy:.1%}",
                timestamp=time.time(),
                current_value=accuracy,
                threshold=self.config.card_accuracy_warning
            )
            self.alerts.append(alert)
            logger.warning(alert.message)
    
    def get_ocr_accuracy(self) -> Optional[float]:
        """Get overall OCR accuracy percentage.
        
        Returns:
            Accuracy as a float (0.0 to 1.0), or None if no data
        """
        results_with_truth = [r for r in self.ocr_results if r.is_correct is not None]
        if not results_with_truth:
            return None
        
        correct = sum(1 for r in results_with_truth if r.is_correct)
        return correct / len(results_with_truth)
    
    def get_amount_mae(self, category: Optional[str] = None) -> Optional[float]:
        """Get Mean Absolute Error for amount readings.
        
        Args:
            category: Filter by category ("stack", "pot", "bet"), or None for all
        
        Returns:
            MAE as a float, or None if no data
        """
        results = self.amount_results
        if category:
            results = [r for r in results if r.category == category]
        
        results_with_error = [r for r in results if r.absolute_error is not None]
        if not results_with_error:
            return None
        
        errors = [r.absolute_error for r in results_with_error]
        return float(np.mean(errors))
    
    def get_card_accuracy(self) -> Optional[float]:
        """Get card recognition accuracy percentage.
        
        Returns:
            Accuracy as a float (0.0 to 1.0), or None if no data
        """
        results_with_truth = [r for r in self.card_results if r.is_correct is not None]
        if not results_with_truth:
            return None
        
        correct = sum(1 for r in results_with_truth if r.is_correct)
        return correct / len(results_with_truth)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary.
        
        Returns:
            Dictionary with all metrics and statistics
        """
        summary = {
            "session_duration_seconds": time.time() - self.session_start,
            "ocr": {
                "total_readings": len(self.ocr_results),
                "with_ground_truth": len([r for r in self.ocr_results if r.is_correct is not None]),
                "accuracy": self.get_ocr_accuracy(),
                "mean_latency_ms": float(np.mean(self.ocr_latencies)) if self.ocr_latencies else None,
                "p50_latency_ms": float(np.percentile(self.ocr_latencies, 50)) if self.ocr_latencies else None,
                "p95_latency_ms": float(np.percentile(self.ocr_latencies, 95)) if self.ocr_latencies else None,
            },
            "amounts": {
                "total_readings": len(self.amount_results),
                "with_ground_truth": len([r for r in self.amount_results if r.absolute_error is not None]),
                "mae_all": self.get_amount_mae(),
                "mae_stack": self.get_amount_mae("stack"),
                "mae_pot": self.get_amount_mae("pot"),
                "mae_bet": self.get_amount_mae("bet"),
            },
            "cards": {
                "total_recognitions": len(self.card_results),
                "with_ground_truth": len([r for r in self.card_results if r.is_correct is not None]),
                "accuracy": self.get_card_accuracy(),
                "mean_confidence": float(np.mean([r.confidence for r in self.card_results])) if self.card_results else None,
                "mean_latency_ms": float(np.mean(self.card_recognition_latencies)) if self.card_recognition_latencies else None,
            },
            "performance": {
                "mean_parse_latency_ms": float(np.mean(self.parse_latencies)) if self.parse_latencies else None,
                "p50_parse_latency_ms": float(np.percentile(self.parse_latencies, 50)) if self.parse_latencies else None,
                "p95_parse_latency_ms": float(np.percentile(self.parse_latencies, 95)) if self.parse_latencies else None,
            },
            "alerts": {
                "total": len(self.alerts),
                "critical": len([a for a in self.alerts if a.level == AlertLevel.CRITICAL]),
                "warning": len([a for a in self.alerts if a.level == AlertLevel.WARNING]),
                "info": len([a for a in self.alerts if a.level == AlertLevel.INFO]),
            }
        }
        
        return summary
    
    def get_alerts(
        self,
        level: Optional[AlertLevel] = None,
        since: Optional[float] = None
    ) -> List[Alert]:
        """Get alerts, optionally filtered.
        
        Args:
            level: Filter by alert level
            since: Filter by timestamp (unix time)
        
        Returns:
            List of alerts matching filters
        """
        alerts = self.alerts
        
        if level is not None:
            alerts = [a for a in alerts if a.level == level]
        
        if since is not None:
            alerts = [a for a in alerts if a.timestamp >= since]
        
        return alerts
    
    def generate_report(self, format: str = "text") -> str:
        """Generate a comprehensive metrics report.
        
        Args:
            format: Report format ("text" or "json")
        
        Returns:
            Formatted report string
        """
        summary = self.get_summary()
        
        if format == "json":
            import json
            return json.dumps(summary, indent=2)
        
        # Text format
        lines = []
        lines.append("=" * 80)
        lines.append("VISION METRICS REPORT")
        lines.append("=" * 80)
        lines.append(f"Session Duration: {summary['session_duration_seconds']:.1f} seconds")
        lines.append("")
        
        # OCR Metrics
        lines.append("OCR METRICS:")
        lines.append(f"  Total Readings: {summary['ocr']['total_readings']}")
        lines.append(f"  With Ground Truth: {summary['ocr']['with_ground_truth']}")
        if summary['ocr']['accuracy'] is not None:
            lines.append(f"  Accuracy: {summary['ocr']['accuracy']:.1%}")
        if summary['ocr']['mean_latency_ms'] is not None:
            lines.append(f"  Mean Latency: {summary['ocr']['mean_latency_ms']:.1f}ms")
            lines.append(f"  P50 Latency: {summary['ocr']['p50_latency_ms']:.1f}ms")
            lines.append(f"  P95 Latency: {summary['ocr']['p95_latency_ms']:.1f}ms")
        lines.append("")
        
        # Amount Metrics
        lines.append("AMOUNT METRICS:")
        lines.append(f"  Total Readings: {summary['amounts']['total_readings']}")
        lines.append(f"  With Ground Truth: {summary['amounts']['with_ground_truth']}")
        if summary['amounts']['mae_all'] is not None:
            lines.append(f"  MAE (All): {summary['amounts']['mae_all']:.2f}")
        if summary['amounts']['mae_stack'] is not None:
            lines.append(f"  MAE (Stacks): {summary['amounts']['mae_stack']:.2f}")
        if summary['amounts']['mae_pot'] is not None:
            lines.append(f"  MAE (Pot): {summary['amounts']['mae_pot']:.2f}")
        if summary['amounts']['mae_bet'] is not None:
            lines.append(f"  MAE (Bets): {summary['amounts']['mae_bet']:.2f}")
        lines.append("")
        
        # Card Recognition Metrics
        lines.append("CARD RECOGNITION METRICS:")
        lines.append(f"  Total Recognitions: {summary['cards']['total_recognitions']}")
        lines.append(f"  With Ground Truth: {summary['cards']['with_ground_truth']}")
        if summary['cards']['accuracy'] is not None:
            lines.append(f"  Accuracy: {summary['cards']['accuracy']:.1%}")
        if summary['cards']['mean_confidence'] is not None:
            lines.append(f"  Mean Confidence: {summary['cards']['mean_confidence']:.2f}")
        if summary['cards']['mean_latency_ms'] is not None:
            lines.append(f"  Mean Latency: {summary['cards']['mean_latency_ms']:.1f}ms")
        lines.append("")
        
        # Performance Metrics
        lines.append("PERFORMANCE METRICS:")
        if summary['performance']['mean_parse_latency_ms'] is not None:
            lines.append(f"  Mean Parse Latency: {summary['performance']['mean_parse_latency_ms']:.1f}ms")
            lines.append(f"  P50 Parse Latency: {summary['performance']['p50_parse_latency_ms']:.1f}ms")
            lines.append(f"  P95 Parse Latency: {summary['performance']['p95_parse_latency_ms']:.1f}ms")
        lines.append("")
        
        # Alert Summary
        lines.append("ALERTS:")
        lines.append(f"  Total: {summary['alerts']['total']}")
        lines.append(f"  Critical: {summary['alerts']['critical']}")
        lines.append(f"  Warning: {summary['alerts']['warning']}")
        lines.append(f"  Info: {summary['alerts']['info']}")
        
        # List recent alerts
        recent_alerts = self.get_alerts(since=time.time() - 3600)  # Last hour
        if recent_alerts:
            lines.append("")
            lines.append("RECENT ALERTS (Last Hour):")
            for alert in recent_alerts[-10:]:  # Last 10
                lines.append(f"  [{alert.level.value}] {alert.message}")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def reset(self):
        """Reset all metrics and alerts."""
        self.ocr_results.clear()
        self.amount_results.clear()
        self.card_results.clear()
        self.ocr_latencies.clear()
        self.card_recognition_latencies.clear()
        self.parse_latencies.clear()
        self.alerts.clear()
        self.session_start = time.time()


# Global metrics tracker instance
_global_vision_metrics: Optional[VisionMetrics] = None


def get_vision_metrics() -> VisionMetrics:
    """Get the global vision metrics tracker instance.
    
    Returns:
        Global VisionMetrics instance
    """
    global _global_vision_metrics
    if _global_vision_metrics is None:
        _global_vision_metrics = VisionMetrics()
    return _global_vision_metrics


def reset_vision_metrics():
    """Reset the global vision metrics tracker."""
    global _global_vision_metrics
    if _global_vision_metrics is not None:
        _global_vision_metrics.reset()
