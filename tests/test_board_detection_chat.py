"""Tests for board card detection via chat OCR with vision fusion."""

import pytest
import numpy as np
from datetime import datetime
from unittest.mock import Mock, MagicMock

from holdem.types import Card, Street
from holdem.vision.chat_parser import ChatParser, ChatLine, GameEvent, EventSource
from holdem.vision.event_fusion import EventFuser, FusedEvent
from holdem.vision.ocr import OCREngine


class TestBoardDetectionChat:
    """Test board card detection from chat."""
    
    @pytest.fixture
    def mock_ocr_engine(self):
        """Create a mock OCR engine."""
        mock = Mock(spec=OCREngine)
        return mock
    
    @pytest.fixture
    def chat_parser(self, mock_ocr_engine):
        """Create a chat parser instance."""
        return ChatParser(mock_ocr_engine)
    
    @pytest.fixture
    def event_fuser(self):
        """Create an event fuser instance."""
        return EventFuser(time_window_seconds=5.0, confidence_threshold=0.7)
    
    def test_parse_flop_dealing_format(self, chat_parser):
        """Test parsing flop from 'Dealing Flop' format."""
        chat_line = ChatLine(
            text="Dealing Flop: [Ah Kd Qs]",
            timestamp=datetime.now()
        )
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "board_update"
        assert event.street == "FLOP"
        assert len(event.cards) == 3
        assert str(event.cards[0]) == "Ah"
        assert str(event.cards[1]) == "Kd"
        assert str(event.cards[2]) == "Qs"
        assert EventSource.CHAT_OCR in event.sources
        assert event.confidence == 0.9
    
    def test_parse_turn_dealing_format(self, chat_parser):
        """Test parsing turn from 'Dealing Turn' format."""
        chat_line = ChatLine(
            text="Dealing Turn: [2c]",
            timestamp=datetime.now()
        )
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "board_update"
        assert event.street == "TURN"
        assert len(event.cards) == 1
        assert str(event.cards[0]) == "2c"
        assert EventSource.CHAT_OCR in event.sources
        assert event.confidence == 0.9
    
    def test_parse_river_dealing_format(self, chat_parser):
        """Test parsing river from 'Dealing River' format."""
        chat_line = ChatLine(
            text="Dealing River: [Jh]",
            timestamp=datetime.now()
        )
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "board_update"
        assert event.street == "RIVER"
        assert len(event.cards) == 1
        assert str(event.cards[0]) == "Jh"
        assert EventSource.CHAT_OCR in event.sources
    
    def test_parse_flop_street_marker_format(self, chat_parser):
        """Test parsing flop from '*** FLOP ***' format."""
        chat_line = ChatLine(
            text="*** FLOP *** [9s 8h 7d]",
            timestamp=datetime.now()
        )
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "board_update"
        assert event.street == "FLOP"
        assert len(event.cards) == 3
    
    def test_parse_turn_street_marker_format(self, chat_parser):
        """Test parsing turn from '*** TURN ***' format."""
        chat_line = ChatLine(
            text="*** TURN *** [Tc]",
            timestamp=datetime.now()
        )
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "board_update"
        assert event.street == "TURN"
        assert len(event.cards) == 1
        assert str(event.cards[0]) == "Tc"
    
    def test_ocr_error_correction_rank(self, chat_parser):
        """Test OCR error correction for card ranks."""
        # Test 0 -> T correction
        chat_line = ChatLine(text="Dealing Flop: [0h Kd Qs]", timestamp=datetime.now())
        events = chat_parser.parse_chat_line_multi(chat_line)
        assert len(events) == 1
        assert str(events[0].cards[0]) == "Th"  # 0h corrected to Th
        
        # Test O -> Q correction
        chat_line = ChatLine(text="Dealing Turn: [Od]", timestamp=datetime.now())
        events = chat_parser.parse_chat_line_multi(chat_line)
        assert len(events) == 1
        assert str(events[0].cards[0]) == "Qd"  # Od corrected to Qd
        
        # Test I -> T correction
        chat_line = ChatLine(text="Dealing River: [Is]", timestamp=datetime.now())
        events = chat_parser.parse_chat_line_multi(chat_line)
        assert len(events) == 1
        assert str(events[0].cards[0]) == "Ts"  # Is corrected to Ts
    
    def test_ocr_error_correction_suit(self, chat_parser):
        """Test OCR error correction for card suits."""
        # Test n -> h correction
        chat_line = ChatLine(text="Dealing Flop: [An Kd Qs]", timestamp=datetime.now())
        events = chat_parser.parse_chat_line_multi(chat_line)
        assert len(events) == 1
        assert str(events[0].cards[0]) == "Ah"  # An corrected to Ah
    
    def test_board_event_fusion_chat_only(self, event_fuser):
        """Test fusion with chat board event only."""
        chat_event = GameEvent(
            event_type="board_update",
            street="FLOP",
            cards=[Card(rank="A", suit="h"), Card(rank="K", suit="d"), Card(rank="Q", suit="s")],
            sources=[EventSource.CHAT_OCR],
            confidence=0.9,
            timestamp=datetime.now()
        )
        
        fused_events = event_fuser.fuse_events([chat_event], [])
        
        assert len(fused_events) == 1
        fused = fused_events[0]
        assert fused.event_type == "board_update"
        assert fused.street == "FLOP"
        assert len(fused.cards) == 3
        assert EventSource.CHAT_OCR in fused.sources
        assert fused.confidence >= 0.85  # High confidence for chat
    
    def test_board_event_fusion_vision_only(self, event_fuser):
        """Test fusion with vision board event only."""
        vision_event = GameEvent(
            event_type="board_update",
            street="TURN",
            cards=[Card(rank="2", suit="c")],
            sources=[EventSource.VISION],
            confidence=0.7,
            timestamp=datetime.now()
        )
        
        fused_events = event_fuser.fuse_events([], [vision_event])
        
        assert len(fused_events) == 1
        fused = fused_events[0]
        assert fused.event_type == "board_update"
        assert fused.street == "TURN"
        assert len(fused.cards) == 1
        assert EventSource.VISION in fused.sources
    
    def test_board_event_fusion_agree(self, event_fuser):
        """Test fusion when chat and vision agree on board cards."""
        cards = [Card(rank="A", suit="h"), Card(rank="K", suit="d"), Card(rank="Q", suit="s")]
        
        chat_event = GameEvent(
            event_type="board_update",
            street="FLOP",
            cards=cards,
            sources=[EventSource.CHAT_OCR],
            confidence=0.9,
            timestamp=datetime.now()
        )
        
        vision_event = GameEvent(
            event_type="board_update",
            street="FLOP",
            cards=cards,  # Same cards
            sources=[EventSource.VISION],
            confidence=0.7,
            timestamp=datetime.now()
        )
        
        fused_events = event_fuser.fuse_events([chat_event], [vision_event])
        
        assert len(fused_events) == 1
        fused = fused_events[0]
        assert fused.event_type == "board_update"
        assert fused.street == "FLOP"
        assert len(fused.cards) == 3
        assert EventSource.CHAT_OCR in fused.sources
        assert EventSource.VISION in fused.sources
        assert fused.is_multi_source()
        assert fused.confidence >= 0.90  # Very high confidence for agreement
        assert not fused.has_source_conflict
    
    def test_board_event_fusion_conflict(self, event_fuser):
        """Test fusion when chat and vision disagree on board cards.
        
        When cards differ significantly (< 80% overlap), events should NOT fuse,
        resulting in separate events. The chat event should have higher priority
        in downstream processing due to higher confidence.
        """
        chat_event = GameEvent(
            event_type="board_update",
            street="FLOP",
            cards=[Card(rank="A", suit="h"), Card(rank="K", suit="d"), Card(rank="Q", suit="s")],
            sources=[EventSource.CHAT_OCR],
            confidence=0.9,
            timestamp=datetime.now()
        )
        
        vision_event = GameEvent(
            event_type="board_update",
            street="FLOP",
            cards=[Card(rank="A", suit="h"), Card(rank="K", suit="d"), Card(rank="J", suit="s")],  # Different 3rd card
            sources=[EventSource.VISION],
            confidence=0.7,
            timestamp=datetime.now()
        )
        
        fused_events = event_fuser.fuse_events([chat_event], [vision_event])
        
        # Events with significantly different cards should NOT fuse (< 80% overlap)
        # Results in 2 separate events
        assert len(fused_events) == 2
        
        # Find chat and vision events
        chat_fused = next((e for e in fused_events if EventSource.CHAT_OCR in e.sources), None)
        vision_fused = next((e for e in fused_events if EventSource.VISION in e.sources), None)
        
        assert chat_fused is not None
        assert vision_fused is not None
        
        # Chat should have higher confidence
        assert chat_fused.confidence > vision_fused.confidence
        
        # Chat cards should be preserved
        assert str(chat_fused.cards[2]) == "Qs"
        
        # Vision cards should be preserved
        assert str(vision_fused.cards[2]) == "Js"
    
    def test_board_event_matching_same_street(self, event_fuser):
        """Test that board events match by street."""
        event1 = GameEvent(
            event_type="board_update",
            street="FLOP",
            cards=[Card(rank="A", suit="h"), Card(rank="K", suit="d"), Card(rank="Q", suit="s")],
            sources=[EventSource.CHAT_OCR],
            timestamp=datetime.now()
        )
        
        event2 = GameEvent(
            event_type="board_update",
            street="FLOP",
            cards=[Card(rank="A", suit="h"), Card(rank="K", suit="d"), Card(rank="Q", suit="s")],
            sources=[EventSource.VISION],
            timestamp=datetime.now()
        )
        
        assert event_fuser._events_match(event1, event2)
    
    def test_board_event_not_matching_different_street(self, event_fuser):
        """Test that board events don't match if streets differ."""
        event1 = GameEvent(
            event_type="board_update",
            street="FLOP",
            cards=[Card(rank="A", suit="h"), Card(rank="K", suit="d"), Card(rank="Q", suit="s")],
            sources=[EventSource.CHAT_OCR],
            timestamp=datetime.now()
        )
        
        event2 = GameEvent(
            event_type="board_update",
            street="TURN",
            cards=[Card(rank="2", suit="c")],
            sources=[EventSource.VISION],
            timestamp=datetime.now()
        )
        
        assert not event_fuser._events_match(event1, event2)
    
    def test_parse_multiple_formats_in_single_session(self, chat_parser):
        """Test parsing different board formats in the same session."""
        # Flop with dealing format
        line1 = ChatLine(text="Dealing Flop: [Ah Kd Qs]", timestamp=datetime.now())
        events1 = chat_parser.parse_chat_line_multi(line1)
        assert len(events1) == 1
        assert events1[0].street == "FLOP"
        assert len(events1[0].cards) == 3
        
        # Turn with street marker format
        line2 = ChatLine(text="*** TURN *** [2c]", timestamp=datetime.now())
        events2 = chat_parser.parse_chat_line_multi(line2)
        assert len(events2) == 1
        assert events2[0].street == "TURN"
        assert len(events2[0].cards) == 1
        
        # River with dealing format
        line3 = ChatLine(text="Dealing River: [Jh]", timestamp=datetime.now())
        events3 = chat_parser.parse_chat_line_multi(line3)
        assert len(events3) == 1
        assert events3[0].street == "RIVER"
        assert len(events3[0].cards) == 1


class TestBoardMetrics:
    """Test board detection metrics tracking."""
    
    def test_record_board_detection_chat(self):
        """Test recording board detection from chat."""
        from holdem.vision.vision_metrics import VisionMetrics, VisionMetricsConfig
        
        metrics = VisionMetrics(VisionMetricsConfig())
        
        # Record chat board detection
        metrics.record_board_detection(
            source="chat",
            street="FLOP",
            confidence=0.9,
            cards=["Ah", "Kd", "Qs"]
        )
        
        assert metrics.board_from_chat_count == 1
        assert metrics.board_from_vision_count == 0
        assert len(metrics.chat_board_confidences) == 1
        assert metrics.chat_board_confidences[0] == 0.9
    
    def test_record_board_detection_vision(self):
        """Test recording board detection from vision."""
        from holdem.vision.vision_metrics import VisionMetrics, VisionMetricsConfig
        
        metrics = VisionMetrics(VisionMetricsConfig())
        
        # Record vision board detection
        metrics.record_board_detection(
            source="vision",
            street="TURN",
            confidence=0.7,
            latency_ms=15.5
        )
        
        assert metrics.board_from_vision_count == 1
        assert metrics.board_from_chat_count == 0
        assert len(metrics.vision_board_confidences) == 1
        assert metrics.vision_board_confidences[0] == 0.7
        assert len(metrics.board_vision_latencies) == 1
        assert metrics.board_vision_latencies[0] == 15.5
    
    def test_record_board_detection_fusion_agree(self):
        """Test recording fusion agreement."""
        from holdem.vision.vision_metrics import VisionMetrics, VisionMetricsConfig
        
        metrics = VisionMetrics(VisionMetricsConfig())
        
        # Record fusion agreement
        metrics.record_board_detection(
            source="fusion_agree",
            street="FLOP",
            confidence=0.95
        )
        
        assert metrics.board_from_fusion_agree_count == 1
    
    def test_record_board_detection_conflict(self):
        """Test recording board detection conflict."""
        from holdem.vision.vision_metrics import VisionMetrics, VisionMetricsConfig
        
        metrics = VisionMetrics(VisionMetricsConfig())
        
        # Record conflict
        metrics.record_board_detection(
            source="conflict",
            street="RIVER",
            cards=["Jh"]
        )
        
        assert metrics.board_source_conflict_count == 1
    
    def test_board_metrics_in_summary(self):
        """Test that board metrics appear in summary."""
        from holdem.vision.vision_metrics import VisionMetrics, VisionMetricsConfig
        
        metrics = VisionMetrics(VisionMetricsConfig())
        
        # Record some board detections
        metrics.record_board_detection(source="chat", street="FLOP", confidence=0.9)
        metrics.record_board_detection(source="vision", street="FLOP", confidence=0.7)
        metrics.record_board_detection(source="fusion_agree", street="FLOP")
        
        summary = metrics.get_summary()
        
        assert "board" in summary
        assert summary["board"]["total_detections"] == 2
        assert summary["board"]["from_chat"] == 1
        assert summary["board"]["from_vision"] == 1
        assert summary["board"]["fusion_agree"] == 1
        assert summary["board"]["conflicts"] == 0
        assert summary["board"]["chat_mean_confidence"] == 0.9
        assert summary["board"]["vision_mean_confidence"] == 0.7
    
    def test_board_metrics_in_report(self):
        """Test that board metrics appear in text report."""
        from holdem.vision.vision_metrics import VisionMetrics, VisionMetricsConfig
        
        metrics = VisionMetrics(VisionMetricsConfig())
        
        # Record some board detections
        metrics.record_board_detection(source="chat", street="FLOP", confidence=0.9)
        metrics.record_board_detection(source="vision", street="TURN", confidence=0.7)
        
        report = metrics.generate_report(format="text")
        
        assert "BOARD DETECTION METRICS:" in report
        assert "Total Detections: 2" in report
        assert "From Vision: 1" in report
        assert "From Chat: 1" in report
    
    def test_parse_turn_full_board_format(self, chat_parser):
        """Test parsing turn with full board (4 cards)."""
        chat_line = ChatLine(
            text="*** TURN *** [Ah Kd Qs 7c]",
            timestamp=datetime.now()
        )
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "board_update"
        assert event.street == "TURN"
        assert len(event.cards) == 4
        # Verify all 4 cards are present
        card_strs = [str(c) for c in event.cards]
        assert "Ah" in card_strs
        assert "Kd" in card_strs
        assert "Qs" in card_strs
        assert "7c" in card_strs
    
    def test_parse_river_full_board_format(self, chat_parser):
        """Test parsing river with full board (5 cards)."""
        chat_line = ChatLine(
            text="*** RIVER *** [Ah Kd Qs 7c 2d]",
            timestamp=datetime.now()
        )
        events = chat_parser.parse_chat_line_multi(chat_line)
        
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "board_update"
        assert event.street == "RIVER"
        assert len(event.cards) == 5
        # Verify all 5 cards are present
        card_strs = [str(c) for c in event.cards]
        assert "Ah" in card_strs
        assert "Kd" in card_strs
        assert "Qs" in card_strs
        assert "7c" in card_strs
        assert "2d" in card_strs
    
    def test_board_fusion_turn_incremental_vs_full(self, event_fuser):
        """Test fusion when vision sends [7c] and chat sends [Ah Kd Qs 7c]."""
        # Vision sends only the new turn card
        vision_event = GameEvent(
            event_type="board_update",
            street="TURN",
            cards=[Card(rank='7', suit='c')],
            sources=[EventSource.VISION],
            confidence=0.7,
            timestamp=datetime.now()
        )
        
        # Chat sends all 4 cards
        chat_event = GameEvent(
            event_type="board_update",
            street="TURN",
            cards=[
                Card(rank='A', suit='h'),
                Card(rank='K', suit='d'),
                Card(rank='Q', suit='s'),
                Card(rank='7', suit='c')
            ],
            sources=[EventSource.CHAT_OCR],
            confidence=0.9,
            timestamp=datetime.now()
        )
        
        fused_events = event_fuser.fuse_events([chat_event], [vision_event])
        
        # Should fuse successfully (vision card [7c] is subset of chat cards)
        assert len(fused_events) == 1
        fused = fused_events[0]
        assert fused.street == "TURN"
        # Should prefer chat cards (more complete)
        assert len(fused.cards) == 4
        assert EventSource.CHAT_OCR in fused.sources
        assert EventSource.VISION in fused.sources
        assert not fused.has_source_conflict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
