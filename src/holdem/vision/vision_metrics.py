"""Vision metrics tracking system.

Tracks OCR accuracy, MAE for amounts, card recognition accuracy,
with configurable thresholds and alert system.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from collections import defaultdict, deque
import hashlib
import json
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
    
    # Amount MAE thresholds (in currency units, e.g., cents)
    amount_mae_warning: float = 0.02  # 2 cents
    amount_mae_critical: float = 0.05  # 5 cents
    
    # Amount MAPE (Mean Absolute Percentage Error) thresholds
    amount_mape_warning: float = 0.002  # 0.2%
    amount_mape_critical: float = 0.01  # 1.0%
    amount_mape_alert_threshold: float = 0.005  # 0.5% (intermediate alert)
    
    # Card recognition thresholds
    card_accuracy_warning: float = 0.95  # 95%
    card_accuracy_critical: float = 0.90  # 90%
    
    # Latency thresholds (milliseconds)
    latency_p95_threshold: float = 50.0  # 50ms
    latency_p99_threshold: float = 80.0  # 80ms
    
    # Flicker detection
    flicker_window_seconds: float = 10.0  # Time window for flicker detection
    flicker_threshold_count: int = 5  # Number of value changes to trigger alert
    
    # Hysteresis for alerts (consecutive windows before alerting)
    alert_hysteresis_windows: int = 3
    
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
    percentage_error: Optional[float] = None  # MAPE component
    timestamp: float = field(default_factory=time.time)
    category: str = "unknown"  # "stack", "pot", "bet"
    field_name: Optional[str] = None  # Specific field name for granular tracking
    seat_position: Optional[int] = None  # Seat position (0-8 for 9-max, 0-5 for 6-max)


@dataclass
class CardRecognitionResult:
    """Represents a card recognition result."""
    detected_card: Optional[str]  # e.g., "Ah", "Kd"
    expected_card: Optional[str] = None
    is_correct: Optional[bool] = None
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)
    street: Optional[str] = None  # "preflop", "flop", "turn", "river"
    seat_position: Optional[int] = None  # Seat position for hole cards


@dataclass
class VisionContext:
    """Captures UI context for drift detection."""
    ui_theme: Optional[str] = None  # "light", "dark"
    resolution: Optional[tuple] = None  # (width, height)
    zoom_level: Optional[float] = None  # Zoom percentage
    profile_version: Optional[str] = None  # Profile version/hash
    template_hash: Optional[str] = None  # Template hash for reproducibility


@dataclass
class FlickerEvent:
    """Represents a value oscillation event."""
    field_name: str
    timestamp: float
    old_value: Any
    new_value: Any
    change_count: int  # Number of changes in window


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
        
        # Board detection tracking
        self.board_from_vision_count: int = 0
        self.board_from_chat_count: int = 0
        self.board_from_fusion_agree_count: int = 0  # Both sources agree
        self.board_source_conflict_count: int = 0  # Sources disagree
        self.board_updates_per_hand: List[int] = []  # Track updates per hand
        
        # Board confidence tracking
        self.vision_board_confidences: List[float] = []
        self.chat_board_confidences: List[float] = []
        
        # Board detection timing
        self.board_vision_latencies: List[float] = []
        self.board_chat_latencies: List[float] = []
        
        # Performance tracking
        self.ocr_latencies: List[float] = []
        self.card_recognition_latencies: List[float] = []
        self.parse_latencies: List[float] = []
        
        # Parse mode tracking (full vs light)
        self.full_parse_count: int = 0
        self.light_parse_count: int = 0
        
        # Alert tracking
        self.alerts: List[Alert] = []
        
        # Flicker detection
        self.flicker_events: List[FlickerEvent] = []
        self.value_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Confusion matrix for cards (rank x suit)
        self.card_confusion_matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        
        # Context tracking
        self.context: VisionContext = VisionContext()
        
        # Hysteresis tracking for alerts
        self.alert_windows: Dict[str, int] = defaultdict(int)
        
        # Session tracking
        self.session_start = time.time()
        
        # Ground truth data
        self.ground_truth_data: List[Dict[str, Any]] = []
    
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
        category: str = "unknown",
        field_name: Optional[str] = None,
        seat_position: Optional[int] = None
    ):
        """Record an amount reading (stack, pot, bet).
        
        Args:
            detected_amount: Amount detected by OCR
            expected_amount: Ground truth amount (if known)
            category: Type of amount ("stack", "pot", "bet")
            field_name: Specific field name for granular tracking
            seat_position: Seat position (0-8 for 9-max, 0-5 for 6-max)
        """
        absolute_error = None
        percentage_error = None
        
        if expected_amount is not None and detected_amount is not None:
            absolute_error = abs(detected_amount - expected_amount)
            # Calculate MAPE component (avoid division by zero)
            if expected_amount > 0:
                percentage_error = absolute_error / expected_amount
        
        result = AmountResult(
            detected_amount=detected_amount,
            expected_amount=expected_amount,
            absolute_error=absolute_error,
            percentage_error=percentage_error,
            category=category,
            field_name=field_name,
            seat_position=seat_position
        )
        self.amount_results.append(result)
        
        # Track value changes for flicker detection
        if field_name and detected_amount is not None:
            self._track_value_change(field_name, detected_amount)
        
        # Check for alerts
        self._check_amount_alerts()
    
    def record_card_recognition(
        self,
        detected_card: Optional[str],
        expected_card: Optional[str] = None,
        confidence: float = 0.0,
        latency_ms: Optional[float] = None,
        street: Optional[str] = None,
        seat_position: Optional[int] = None
    ):
        """Record a card recognition result.
        
        Args:
            detected_card: Card detected (e.g., "Ah")
            expected_card: Ground truth card (if known)
            confidence: Recognition confidence score
            latency_ms: Time taken for recognition (milliseconds)
            street: Poker street ("preflop", "flop", "turn", "river")
            seat_position: Seat position for hole cards
        """
        is_correct = None
        if expected_card is not None and detected_card is not None:
            is_correct = detected_card.lower() == expected_card.lower()
            
            # Update confusion matrix
            self._update_card_confusion_matrix(detected_card, expected_card)
        
        result = CardRecognitionResult(
            detected_card=detected_card,
            expected_card=expected_card,
            is_correct=is_correct,
            confidence=confidence,
            street=street,
            seat_position=seat_position
        )
        self.card_results.append(result)
        
        if latency_ms is not None:
            self.card_recognition_latencies.append(latency_ms)
        
        # Check for alerts
        self._check_card_alerts()
    
    def record_board_detection(
        self,
        source: str,  # "vision", "chat", "fusion_agree", "conflict"
        street: Optional[str] = None,  # "FLOP", "TURN", "RIVER"
        confidence: Optional[float] = None,
        latency_ms: Optional[float] = None,
        cards: Optional[List[str]] = None
    ):
        """Record a board detection event.
        
        Args:
            source: Detection source ("vision", "chat", "fusion_agree", "conflict")
            street: Poker street where board was detected
            confidence: Confidence score for the detection
            latency_ms: Time taken for detection (milliseconds)
            cards: Detected cards (for logging)
        """
        # Update counters by source
        if source == "vision":
            self.board_from_vision_count += 1
            if confidence is not None:
                self.vision_board_confidences.append(confidence)
            if latency_ms is not None:
                self.board_vision_latencies.append(latency_ms)
        
        elif source == "chat":
            self.board_from_chat_count += 1
            if confidence is not None:
                self.chat_board_confidences.append(confidence)
            if latency_ms is not None:
                self.board_chat_latencies.append(latency_ms)
        
        elif source == "fusion_agree":
            self.board_from_fusion_agree_count += 1
        
        elif source == "conflict":
            self.board_source_conflict_count += 1
            logger.warning(
                f"[BOARD METRICS] Source conflict detected: "
                f"street={street}, cards={cards}"
            )
    
    def record_parse_latency(self, latency_ms: float, is_full_parse: bool = True):
        """Record full state parse latency.
        
        Args:
            latency_ms: Time taken for full state parse (milliseconds)
            is_full_parse: Whether this was a full parse or light parse
        """
        self.parse_latencies.append(latency_ms)
        
        # Track parse mode
        if is_full_parse:
            self.full_parse_count += 1
        else:
            self.light_parse_count += 1
        
        # Check for latency alerts
        self._check_latency_alerts()
    
    def _check_latency_alerts(self):
        """Check parse latency and generate alerts if thresholds are exceeded."""
        if len(self.parse_latencies) < self.config.min_samples_for_alert:
            return
        
        # Calculate recent metrics (last N samples)
        recent_latencies = self.parse_latencies[-self.config.min_samples_for_alert:]
        mean_latency = float(np.mean(recent_latencies))
        p95_latency = float(np.percentile(recent_latencies, 95))
        p99_latency = float(np.percentile(recent_latencies, 99))
        
        # Check P99 threshold (most critical)
        if p99_latency > self.config.latency_p99_threshold:
            alert = Alert(
                level=AlertLevel.CRITICAL,
                metric_name="parse_latency_p99",
                message=f"Parse latency P99 critically high: {p99_latency:.1f}ms (threshold: {self.config.latency_p99_threshold}ms)",
                timestamp=time.time(),
                current_value=p99_latency,
                threshold=self.config.latency_p99_threshold
            )
            self.alerts.append(alert)
            logger.error(alert.message)
        
        # Check P95 threshold
        if p95_latency > self.config.latency_p95_threshold:
            alert = Alert(
                level=AlertLevel.WARNING,
                metric_name="parse_latency_p95",
                message=f"Parse latency P95 above threshold: {p95_latency:.1f}ms (threshold: {self.config.latency_p95_threshold}ms)",
                timestamp=time.time(),
                current_value=p95_latency,
                threshold=self.config.latency_p95_threshold
            )
            self.alerts.append(alert)
            logger.warning(alert.message)
        
        # Check mean latency (if it's very high, alert even if percentiles pass)
        if mean_latency > self.config.latency_p99_threshold * 2:
            alert = Alert(
                level=AlertLevel.CRITICAL,
                metric_name="parse_latency_mean",
                message=f"Mean parse latency critically high: {mean_latency:.1f}ms",
                timestamp=time.time(),
                current_value=mean_latency,
                threshold=self.config.latency_p99_threshold * 2
            )
            self.alerts.append(alert)
            logger.error(alert.message)
    
    def set_context(
        self,
        ui_theme: Optional[str] = None,
        resolution: Optional[Tuple[int, int]] = None,
        zoom_level: Optional[float] = None,
        profile_version: Optional[str] = None,
        template_hash: Optional[str] = None
    ):
        """Set vision context for drift detection.
        
        Args:
            ui_theme: UI theme ("light", "dark")
            resolution: Screen resolution (width, height)
            zoom_level: Zoom percentage
            profile_version: Profile version/hash
            template_hash: Template hash
        """
        if ui_theme is not None:
            self.context.ui_theme = ui_theme
        if resolution is not None:
            self.context.resolution = resolution
        if zoom_level is not None:
            self.context.zoom_level = zoom_level
        if profile_version is not None:
            self.context.profile_version = profile_version
        if template_hash is not None:
            self.context.template_hash = template_hash
    
    def ingest_ground_truth(self, data: Dict[str, Any]):
        """Ingest ground truth data for validation.
        
        Args:
            data: Ground truth data dictionary
        """
        self.ground_truth_data.append(data)
    
    def _track_value_change(self, field_name: str, value: Any):
        """Track value changes for flicker detection.
        
        Args:
            field_name: Name of the field
            value: New value
        """
        history = self.value_history[field_name]
        current_time = time.time()
        
        # Add value with timestamp
        history.append((current_time, value))
        
        # Check for flicker in the time window
        window_start = current_time - self.config.flicker_window_seconds
        recent_values = [(t, v) for t, v in history if t >= window_start]
        
        if len(recent_values) >= 2:
            # Count value changes
            changes = 0
            for i in range(1, len(recent_values)):
                if recent_values[i][1] != recent_values[i-1][1]:
                    changes += 1
            
            # Alert if threshold exceeded
            if changes >= self.config.flicker_threshold_count:
                flicker_event = FlickerEvent(
                    field_name=field_name,
                    timestamp=current_time,
                    old_value=recent_values[-2][1] if len(recent_values) >= 2 else None,
                    new_value=value,
                    change_count=changes
                )
                self.flicker_events.append(flicker_event)
                
                # Generate alert with hysteresis
                self._check_flicker_alert(field_name, changes)
    
    def _update_card_confusion_matrix(self, detected: str, expected: str):
        """Update confusion matrix for card recognition.
        
        Args:
            detected: Detected card (e.g., "Ah")
            expected: Expected card (e.g., "Ah")
        """
        if not detected or not expected or len(detected) < 2 or len(expected) < 2:
            return
        
        detected_rank = detected[0].upper()
        detected_suit = detected[1].lower()
        expected_rank = expected[0].upper()
        expected_suit = expected[1].lower()
        
        # Track rank confusion
        rank_key = f"rank_{expected_rank}"
        self.card_confusion_matrix[rank_key][detected_rank] += 1
        
        # Track suit confusion
        suit_key = f"suit_{expected_suit}"
        self.card_confusion_matrix[suit_key][detected_suit] += 1
    
    def _check_flicker_alert(self, field_name: str, change_count: int):
        """Check and generate flicker alert with hysteresis.
        
        Args:
            field_name: Field name
            change_count: Number of changes in window
        """
        alert_key = f"flicker_{field_name}"
        
        # Increment alert window counter
        self.alert_windows[alert_key] += 1
        
        # Only alert if threshold exceeded for consecutive windows
        if self.alert_windows[alert_key] >= self.config.alert_hysteresis_windows:
            alert = Alert(
                level=AlertLevel.WARNING,
                metric_name="flicker",
                message=f"Flicker detected in {field_name}: {change_count} changes in {self.config.flicker_window_seconds}s",
                timestamp=time.time(),
                current_value=float(change_count),
                threshold=float(self.config.flicker_threshold_count)
            )
            self.alerts.append(alert)
            logger.warning(alert.message)
            
            # Reset counter after alerting
            self.alert_windows[alert_key] = 0
    
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
        """Check amount MAE and MAPE, generate alerts if needed."""
        # Only check amounts with ground truth
        results_with_error = [r for r in self.amount_results if r.absolute_error is not None]
        
        if len(results_with_error) < self.config.min_samples_for_alert:
            return
        
        # Calculate recent MAE (last N samples)
        recent_results = results_with_error[-self.config.min_samples_for_alert:]
        errors = [r.absolute_error for r in recent_results]
        mae = np.mean(errors)
        
        # Check MAE thresholds
        if mae > self.config.amount_mae_critical:
            alert = Alert(
                level=AlertLevel.CRITICAL,
                metric_name="amount_mae",
                message=f"Amount MAE critically high: {mae:.4f} units",
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
                message=f"Amount MAE above warning threshold: {mae:.4f} units",
                timestamp=time.time(),
                current_value=mae,
                threshold=self.config.amount_mae_warning
            )
            self.alerts.append(alert)
            logger.warning(alert.message)
        
        # Check MAPE thresholds
        results_with_percentage = [r for r in recent_results if r.percentage_error is not None]
        if results_with_percentage:
            percentage_errors = [r.percentage_error for r in results_with_percentage]
            mape = np.mean(percentage_errors)
            
            if mape > self.config.amount_mape_critical:
                alert = Alert(
                    level=AlertLevel.CRITICAL,
                    metric_name="amount_mape",
                    message=f"Amount MAPE critically high: {mape:.2%}",
                    timestamp=time.time(),
                    current_value=mape,
                    threshold=self.config.amount_mape_critical
                )
                self.alerts.append(alert)
                logger.error(alert.message)
            elif mape > self.config.amount_mape_alert_threshold:
                alert = Alert(
                    level=AlertLevel.WARNING,
                    metric_name="amount_mape",
                    message=f"Amount MAPE above alert threshold: {mape:.2%}",
                    timestamp=time.time(),
                    current_value=mape,
                    threshold=self.config.amount_mape_alert_threshold
                )
                self.alerts.append(alert)
                logger.warning(alert.message)
            elif mape > self.config.amount_mape_warning:
                alert = Alert(
                    level=AlertLevel.INFO,
                    metric_name="amount_mape",
                    message=f"Amount MAPE above warning threshold: {mape:.2%}",
                    timestamp=time.time(),
                    current_value=mape,
                    threshold=self.config.amount_mape_warning
                )
                self.alerts.append(alert)
                logger.info(alert.message)
    
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
    
    def get_amount_mae(self, category: Optional[str] = None, seat_position: Optional[int] = None) -> Optional[float]:
        """Get Mean Absolute Error for amount readings.
        
        Args:
            category: Filter by category ("stack", "pot", "bet"), or None for all
            seat_position: Filter by seat position, or None for all
        
        Returns:
            MAE as a float, or None if no data
        """
        results = self.amount_results
        if category:
            results = [r for r in results if r.category == category]
        if seat_position is not None:
            results = [r for r in results if r.seat_position == seat_position]
        
        results_with_error = [r for r in results if r.absolute_error is not None]
        if not results_with_error:
            return None
        
        errors = [r.absolute_error for r in results_with_error]
        return float(np.mean(errors))
    
    def get_amount_mape(self, category: Optional[str] = None, seat_position: Optional[int] = None) -> Optional[float]:
        """Get Mean Absolute Percentage Error for amount readings.
        
        Args:
            category: Filter by category ("stack", "pot", "bet"), or None for all
            seat_position: Filter by seat position, or None for all
        
        Returns:
            MAPE as a float (0.0 to 1.0), or None if no data
        """
        results = self.amount_results
        if category:
            results = [r for r in results if r.category == category]
        if seat_position is not None:
            results = [r for r in results if r.seat_position == seat_position]
        
        results_with_percentage = [r for r in results if r.percentage_error is not None]
        if not results_with_percentage:
            return None
        
        percentage_errors = [r.percentage_error for r in results_with_percentage]
        return float(np.mean(percentage_errors))
    
    def get_card_accuracy(self, street: Optional[str] = None, seat_position: Optional[int] = None) -> Optional[float]:
        """Get card recognition accuracy percentage.
        
        Args:
            street: Filter by street ("preflop", "flop", "turn", "river"), or None for all
            seat_position: Filter by seat position, or None for all
        
        Returns:
            Accuracy as a float (0.0 to 1.0), or None if no data
        """
        results = self.card_results
        if street:
            results = [r for r in results if r.street == street]
        if seat_position is not None:
            results = [r for r in results if r.seat_position == seat_position]
        
        results_with_truth = [r for r in results if r.is_correct is not None]
        if not results_with_truth:
            return None
        
        correct = sum(1 for r in results_with_truth if r.is_correct)
        return correct / len(results_with_truth)
    
    def get_card_confusion_matrix(self) -> Dict[str, Dict[str, int]]:
        """Get card confusion matrix.
        
        Returns:
            Dictionary with rank and suit confusion matrices
        """
        return dict(self.card_confusion_matrix)
    
    def get_latency_percentile(self, latency_type: str, percentile: int) -> Optional[float]:
        """Get latency percentile.
        
        Args:
            latency_type: Type of latency ("ocr", "card", "parse")
            percentile: Percentile to calculate (0-100)
        
        Returns:
            Latency in milliseconds, or None if no data
        """
        if latency_type == "ocr":
            latencies = self.ocr_latencies
        elif latency_type == "card":
            latencies = self.card_recognition_latencies
        elif latency_type == "parse":
            latencies = self.parse_latencies
        else:
            return None
        
        if not latencies:
            return None
        
        return float(np.percentile(latencies, percentile))
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary.
        
        Returns:
            Dictionary with all metrics and statistics
        """
        summary = {
            "session_duration_seconds": time.time() - self.session_start,
            "context": {
                "ui_theme": self.context.ui_theme,
                "resolution": self.context.resolution,
                "zoom_level": self.context.zoom_level,
                "profile_version": self.context.profile_version,
                "template_hash": self.context.template_hash,
            },
            "ocr": {
                "total_readings": len(self.ocr_results),
                "with_ground_truth": len([r for r in self.ocr_results if r.is_correct is not None]),
                "accuracy": self.get_ocr_accuracy(),
                "mean_latency_ms": float(np.mean(self.ocr_latencies)) if self.ocr_latencies else None,
                "p50_latency_ms": self.get_latency_percentile("ocr", 50),
                "p95_latency_ms": self.get_latency_percentile("ocr", 95),
                "p99_latency_ms": self.get_latency_percentile("ocr", 99),
            },
            "amounts": {
                "total_readings": len(self.amount_results),
                "with_ground_truth": len([r for r in self.amount_results if r.absolute_error is not None]),
                "mae_all": self.get_amount_mae(),
                "mae_stack": self.get_amount_mae("stack"),
                "mae_pot": self.get_amount_mae("pot"),
                "mae_bet": self.get_amount_mae("bet"),
                "mape_all": self.get_amount_mape(),
                "mape_stack": self.get_amount_mape("stack"),
                "mape_pot": self.get_amount_mape("pot"),
                "mape_bet": self.get_amount_mape("bet"),
            },
            "cards": {
                "total_recognitions": len(self.card_results),
                "with_ground_truth": len([r for r in self.card_results if r.is_correct is not None]),
                "accuracy_all": self.get_card_accuracy(),
                "accuracy_preflop": self.get_card_accuracy("preflop"),
                "accuracy_flop": self.get_card_accuracy("flop"),
                "accuracy_turn": self.get_card_accuracy("turn"),
                "accuracy_river": self.get_card_accuracy("river"),
                "mean_confidence": float(np.mean([r.confidence for r in self.card_results])) if self.card_results else None,
                "mean_latency_ms": float(np.mean(self.card_recognition_latencies)) if self.card_recognition_latencies else None,
                "confusion_matrix": self.get_card_confusion_matrix(),
            },
            "board": {
                "total_detections": self.board_from_vision_count + self.board_from_chat_count,
                "from_vision": self.board_from_vision_count,
                "from_chat": self.board_from_chat_count,
                "fusion_agree": self.board_from_fusion_agree_count,
                "conflicts": self.board_source_conflict_count,
                "vision_mean_confidence": float(np.mean(self.vision_board_confidences)) if self.vision_board_confidences else None,
                "chat_mean_confidence": float(np.mean(self.chat_board_confidences)) if self.chat_board_confidences else None,
                "vision_mean_latency_ms": float(np.mean(self.board_vision_latencies)) if self.board_vision_latencies else None,
                "chat_mean_latency_ms": float(np.mean(self.board_chat_latencies)) if self.board_chat_latencies else None,
                "updates_per_hand_mean": float(np.mean(self.board_updates_per_hand)) if self.board_updates_per_hand else None,
            },
            "performance": {
                "mean_parse_latency_ms": float(np.mean(self.parse_latencies)) if self.parse_latencies else None,
                "p50_parse_latency_ms": self.get_latency_percentile("parse", 50),
                "p95_parse_latency_ms": self.get_latency_percentile("parse", 95),
                "p99_parse_latency_ms": self.get_latency_percentile("parse", 99),
                "p95_threshold_met": self.get_latency_percentile("parse", 95) <= self.config.latency_p95_threshold if self.parse_latencies else None,
                "p99_threshold_met": self.get_latency_percentile("parse", 99) <= self.config.latency_p99_threshold if self.parse_latencies else None,
            },
            "flicker": {
                "total_events": len(self.flicker_events),
                "recent_events": [
                    {
                        "field": e.field_name,
                        "timestamp": e.timestamp,
                        "change_count": e.change_count
                    }
                    for e in self.flicker_events[-10:]  # Last 10 events
                ],
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
            lines.append(f"  MAE (All): {summary['amounts']['mae_all']:.4f} units")
        if summary['amounts']['mae_stack'] is not None:
            lines.append(f"  MAE (Stacks): {summary['amounts']['mae_stack']:.4f} units")
        if summary['amounts']['mae_pot'] is not None:
            lines.append(f"  MAE (Pot): {summary['amounts']['mae_pot']:.4f} units")
        if summary['amounts']['mae_bet'] is not None:
            lines.append(f"  MAE (Bets): {summary['amounts']['mae_bet']:.4f} units")
        if summary['amounts']['mape_all'] is not None:
            lines.append(f"  MAPE (All): {summary['amounts']['mape_all']:.2%}")
        if summary['amounts']['mape_stack'] is not None:
            lines.append(f"  MAPE (Stacks): {summary['amounts']['mape_stack']:.2%}")
        if summary['amounts']['mape_pot'] is not None:
            lines.append(f"  MAPE (Pot): {summary['amounts']['mape_pot']:.2%}")
        if summary['amounts']['mape_bet'] is not None:
            lines.append(f"  MAPE (Bets): {summary['amounts']['mape_bet']:.2%}")
        lines.append("")
        
        # Card Recognition Metrics
        lines.append("CARD RECOGNITION METRICS:")
        lines.append(f"  Total Recognitions: {summary['cards']['total_recognitions']}")
        lines.append(f"  With Ground Truth: {summary['cards']['with_ground_truth']}")
        if summary['cards']['accuracy_all'] is not None:
            lines.append(f"  Accuracy (All): {summary['cards']['accuracy_all']:.1%}")
        if summary['cards']['accuracy_preflop'] is not None:
            lines.append(f"  Accuracy (Preflop): {summary['cards']['accuracy_preflop']:.1%}")
        if summary['cards']['accuracy_flop'] is not None:
            lines.append(f"  Accuracy (Flop): {summary['cards']['accuracy_flop']:.1%}")
        if summary['cards']['accuracy_turn'] is not None:
            lines.append(f"  Accuracy (Turn): {summary['cards']['accuracy_turn']:.1%}")
        if summary['cards']['accuracy_river'] is not None:
            lines.append(f"  Accuracy (River): {summary['cards']['accuracy_river']:.1%}")
        if summary['cards']['mean_confidence'] is not None:
            lines.append(f"  Mean Confidence: {summary['cards']['mean_confidence']:.2f}")
        if summary['cards']['mean_latency_ms'] is not None:
            lines.append(f"  Mean Latency: {summary['cards']['mean_latency_ms']:.1f}ms")
        lines.append("")
        
        # Board Detection Metrics
        lines.append("BOARD DETECTION METRICS:")
        lines.append(f"  Total Detections: {summary['board']['total_detections']}")
        lines.append(f"  From Vision: {summary['board']['from_vision']}")
        lines.append(f"  From Chat: {summary['board']['from_chat']}")
        lines.append(f"  Fusion Agreement: {summary['board']['fusion_agree']}")
        lines.append(f"  Source Conflicts: {summary['board']['conflicts']}")
        if summary['board']['vision_mean_confidence'] is not None:
            lines.append(f"  Vision Mean Confidence: {summary['board']['vision_mean_confidence']:.2f}")
        if summary['board']['chat_mean_confidence'] is not None:
            lines.append(f"  Chat Mean Confidence: {summary['board']['chat_mean_confidence']:.2f}")
        if summary['board']['vision_mean_latency_ms'] is not None:
            lines.append(f"  Vision Mean Latency: {summary['board']['vision_mean_latency_ms']:.1f}ms")
        if summary['board']['chat_mean_latency_ms'] is not None:
            lines.append(f"  Chat Mean Latency: {summary['board']['chat_mean_latency_ms']:.1f}ms")
        if summary['board']['updates_per_hand_mean'] is not None:
            lines.append(f"  Updates Per Hand (Avg): {summary['board']['updates_per_hand_mean']:.1f}")
        lines.append("")
        
        # Performance Metrics
        lines.append("PERFORMANCE METRICS:")
        if summary['performance']['mean_parse_latency_ms'] is not None:
            lines.append(f"  Mean Parse Latency: {summary['performance']['mean_parse_latency_ms']:.1f}ms")
            lines.append(f"  P50 Parse Latency: {summary['performance']['p50_parse_latency_ms']:.1f}ms")
            lines.append(f"  P95 Parse Latency: {summary['performance']['p95_parse_latency_ms']:.1f}ms")
            lines.append(f"  P99 Parse Latency: {summary['performance']['p99_parse_latency_ms']:.1f}ms")
            if summary['performance']['p95_threshold_met'] is not None:
                p95_status = "✓" if summary['performance']['p95_threshold_met'] else "✗"
                lines.append(f"  P95 Threshold Met ({self.config.latency_p95_threshold}ms): {p95_status}")
            if summary['performance']['p99_threshold_met'] is not None:
                p99_status = "✓" if summary['performance']['p99_threshold_met'] else "✗"
                lines.append(f"  P99 Threshold Met ({self.config.latency_p99_threshold}ms): {p99_status}")
        
        # Parse mode statistics
        total_parses = self.full_parse_count + self.light_parse_count
        if total_parses > 0:
            lines.append(f"  Full Parses: {self.full_parse_count} ({self.full_parse_count/total_parses:.1%})")
            lines.append(f"  Light Parses: {self.light_parse_count} ({self.light_parse_count/total_parses:.1%})")
        lines.append("")
        
        # Flicker Metrics
        if summary['flicker']['total_events'] > 0:
            lines.append("FLICKER DETECTION:")
            lines.append(f"  Total Events: {summary['flicker']['total_events']}")
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
    
    def export_jsonlines(self, filepath: str):
        """Export metrics to JSON Lines format.
        
        Args:
            filepath: Path to output file
        """
        with open(filepath, 'a') as f:
            # Export context
            context_line = {
                "type": "context",
                "timestamp": time.time(),
                "data": {
                    "ui_theme": self.context.ui_theme,
                    "resolution": self.context.resolution,
                    "zoom_level": self.context.zoom_level,
                    "profile_version": self.context.profile_version,
                    "template_hash": self.context.template_hash,
                }
            }
            f.write(json.dumps(context_line) + '\n')
            
            # Export summary
            summary_line = {
                "type": "summary",
                "timestamp": time.time(),
                "data": self.get_summary()
            }
            f.write(json.dumps(summary_line) + '\n')
    
    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus text format.
        
        Returns:
            Metrics in Prometheus text format
        """
        lines = []
        summary = self.get_summary()
        
        # OCR metrics
        if summary['ocr']['accuracy'] is not None:
            lines.append('# HELP vision_ocr_accuracy OCR accuracy percentage')
            lines.append('# TYPE vision_ocr_accuracy gauge')
            lines.append(f"vision_ocr_accuracy {summary['ocr']['accuracy']}")
        
        # Amount MAE metrics
        if summary['amounts']['mae_all'] is not None:
            lines.append('# HELP vision_amount_mae_units Amount Mean Absolute Error in units')
            lines.append('# TYPE vision_amount_mae_units gauge')
            lines.append(f"vision_amount_mae_units{{category=\"all\"}} {summary['amounts']['mae_all']}")
            if summary['amounts']['mae_stack'] is not None:
                lines.append(f"vision_amount_mae_units{{category=\"stack\"}} {summary['amounts']['mae_stack']}")
            if summary['amounts']['mae_pot'] is not None:
                lines.append(f"vision_amount_mae_units{{category=\"pot\"}} {summary['amounts']['mae_pot']}")
            if summary['amounts']['mae_bet'] is not None:
                lines.append(f"vision_amount_mae_units{{category=\"bet\"}} {summary['amounts']['mae_bet']}")
        
        # Amount MAPE metrics
        if summary['amounts']['mape_all'] is not None:
            lines.append('# HELP vision_amount_mape Amount Mean Absolute Percentage Error')
            lines.append('# TYPE vision_amount_mape gauge')
            lines.append(f"vision_amount_mape{{category=\"all\"}} {summary['amounts']['mape_all']}")
            if summary['amounts']['mape_stack'] is not None:
                lines.append(f"vision_amount_mape{{category=\"stack\"}} {summary['amounts']['mape_stack']}")
            if summary['amounts']['mape_pot'] is not None:
                lines.append(f"vision_amount_mape{{category=\"pot\"}} {summary['amounts']['mape_pot']}")
            if summary['amounts']['mape_bet'] is not None:
                lines.append(f"vision_amount_mape{{category=\"bet\"}} {summary['amounts']['mape_bet']}")
        
        # Card accuracy metrics
        if summary['cards']['accuracy_all'] is not None:
            lines.append('# HELP vision_card_accuracy Card recognition accuracy percentage')
            lines.append('# TYPE vision_card_accuracy gauge')
            lines.append(f"vision_card_accuracy{{street=\"all\"}} {summary['cards']['accuracy_all']}")
            if summary['cards']['accuracy_preflop'] is not None:
                lines.append(f"vision_card_accuracy{{street=\"preflop\"}} {summary['cards']['accuracy_preflop']}")
            if summary['cards']['accuracy_flop'] is not None:
                lines.append(f"vision_card_accuracy{{street=\"flop\"}} {summary['cards']['accuracy_flop']}")
            if summary['cards']['accuracy_turn'] is not None:
                lines.append(f"vision_card_accuracy{{street=\"turn\"}} {summary['cards']['accuracy_turn']}")
            if summary['cards']['accuracy_river'] is not None:
                lines.append(f"vision_card_accuracy{{street=\"river\"}} {summary['cards']['accuracy_river']}")
        
        # Latency metrics (as histogram)
        if summary['performance']['p95_parse_latency_ms'] is not None:
            lines.append('# HELP vision_parse_latency_ms Parse latency in milliseconds')
            lines.append('# TYPE vision_parse_latency_ms summary')
            lines.append(f"vision_parse_latency_ms{{quantile=\"0.5\"}} {summary['performance']['p50_parse_latency_ms']}")
            lines.append(f"vision_parse_latency_ms{{quantile=\"0.95\"}} {summary['performance']['p95_parse_latency_ms']}")
            lines.append(f"vision_parse_latency_ms{{quantile=\"0.99\"}} {summary['performance']['p99_parse_latency_ms']}")
            lines.append(f"vision_parse_latency_ms_count {len(self.parse_latencies)}")
            lines.append(f"vision_parse_latency_ms_sum {sum(self.parse_latencies)}")
        
        # Alert counters
        lines.append('# HELP vision_alerts_total Total number of alerts')
        lines.append('# TYPE vision_alerts_total counter')
        lines.append(f"vision_alerts_total{{level=\"critical\"}} {summary['alerts']['critical']}")
        lines.append(f"vision_alerts_total{{level=\"warning\"}} {summary['alerts']['warning']}")
        lines.append(f"vision_alerts_total{{level=\"info\"}} {summary['alerts']['info']}")
        
        # Flicker events
        lines.append('# HELP vision_flicker_events_total Total number of flicker events')
        lines.append('# TYPE vision_flicker_events_total counter')
        lines.append(f"vision_flicker_events_total {summary['flicker']['total_events']}")
        
        return '\n'.join(lines) + '\n'
    
    def reset(self):
        """Reset all metrics and alerts."""
        self.ocr_results.clear()
        self.amount_results.clear()
        self.card_results.clear()
        self.ocr_latencies.clear()
        self.card_recognition_latencies.clear()
        self.parse_latencies.clear()
        self.alerts.clear()
        self.flicker_events.clear()
        self.value_history.clear()
        self.card_confusion_matrix.clear()
        self.alert_windows.clear()
        self.ground_truth_data.clear()
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
