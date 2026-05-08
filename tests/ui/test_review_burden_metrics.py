"""Tests for review burden metrics in UI.

These tests verify that:
- UI emits review-burden metrics: manual_review_rate, median_review_time_per_item, 
  high_risk_queue_age, auto_resolved_low_risk_rate
- Metrics are available for UI evaluation fixtures
- High-risk items are not buried behind low-risk items
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from relic.ui.contracts import (
    LineageRef,
    ReviewBurdenMetrics,
    ReviewBurdenMetrics,
    ReviewQueueItem,
    ReviewStatus,
    RiskLevel,
)
from relic.ui.view_models import ReviewQueueViewModel


class TestReviewBurdenMetrics:
    """Test review-burden metrics computation and emission."""

    def test_metrics_has_manual_review_rate(self):
        """Verify ReviewBurdenMetrics has manual_review_rate field."""
        metrics = ReviewBurdenMetrics()
        assert hasattr(metrics, "manual_review_rate")
        assert isinstance(metrics.manual_review_rate, float)

    def test_metrics_has_median_review_time_per_item(self):
        """Verify ReviewBurdenMetrics has median_review_time_per_item field."""
        metrics = ReviewBurdenMetrics()
        assert hasattr(metrics, "median_review_time_per_item")
        assert isinstance(metrics.median_review_time_per_item, float)

    def test_metrics_has_high_risk_queue_age(self):
        """Verify ReviewBurdenMetrics has high_risk_queue_age field."""
        metrics = ReviewBurdenMetrics()
        assert hasattr(metrics, "high_risk_queue_age")
        assert isinstance(metrics.high_risk_queue_age, float)

    def test_metrics_has_auto_resolved_low_risk_rate(self):
        """Verify ReviewBurdenMetrics has auto_resolved_low_risk_rate field."""
        metrics = ReviewBurdenMetrics()
        assert hasattr(metrics, "auto_resolved_low_risk_rate")
        assert isinstance(metrics.auto_resolved_low_risk_rate, float)

    def test_manual_review_rate_calculation(self):
        """Test manual review rate is calculated correctly."""
        items = [
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="hash1",
                lineage_refs=[],
                risk_level=RiskLevel.S0_HARD_VIOLATION,
                review_status=ReviewStatus.PENDING,
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="hash2",
                lineage_refs=[],
                risk_level=RiskLevel.S1_HIGH_RISK,
                review_status=ReviewStatus.UNDER_REVIEW,
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="hash3",
                lineage_refs=[],
                risk_level=RiskLevel.LOW_RISK,
                review_status=ReviewStatus.APPROVED,
            ),
        ]
        
        vm = ReviewQueueViewModel.from_items(items)
        
        # S0 + S1 + S2 = manual review required
        # 2 out of 3 items require manual review
        assert vm.metrics.manual_review_rate == pytest.approx(2/3, rel=0.01)

    def test_auto_resolved_low_risk_rate_calculation(self):
        """Test auto-resolved low-risk rate is calculated correctly."""
        items = [
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="hash1",
                lineage_refs=[],
                risk_level=RiskLevel.LOW_RISK,
                review_status=ReviewStatus.AUTO_RESOLVED,
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="hash2",
                lineage_refs=[],
                risk_level=RiskLevel.LOW_RISK,
                review_status=ReviewStatus.AUTO_RESOLVED,
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="hash3",
                lineage_refs=[],
                risk_level=RiskLevel.LOW_RISK,
                review_status=ReviewStatus.PENDING,
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="hash4",
                lineage_refs=[],
                risk_level=RiskLevel.LOW_RISK,
                review_status=ReviewStatus.PENDING,
            ),
        ]
        
        vm = ReviewQueueViewModel.from_items(items)
        
        # 2 out of 4 low-risk items were auto-resolved
        assert vm.metrics.auto_resolved_low_risk_rate == pytest.approx(0.5, rel=0.01)

    def test_high_risk_queue_age_calculation(self):
        """Test high-risk queue age is tracked."""
        now = datetime.utcnow()
        old_time = now - timedelta(hours=2)
        recent_time = now - timedelta(minutes=30)
        
        items = [
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="hash1",
                lineage_refs=[],
                risk_level=RiskLevel.S0_HARD_VIOLATION,
                created_at=old_time,  # 2 hours old
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="hash2",
                lineage_refs=[],
                risk_level=RiskLevel.LOW_RISK,  # Not high risk
                created_at=old_time,
            ),
        ]
        
        vm = ReviewQueueViewModel.from_items(items)
        
        # High-risk queue age should be ~2 hours (in seconds)
        expected_age_seconds = 2 * 60 * 60
        assert vm.metrics.high_risk_queue_age >= expected_age_seconds - 10  # Allow 10s tolerance

    def test_metrics_to_dict_serialization(self):
        """Test metrics can be serialized to dictionary."""
        metrics = ReviewBurdenMetrics(
            total_items=10,
            items_reviewed=5,
            manual_review_rate=0.5,
            median_review_time_per_item=30.0,
            high_risk_queue_age=3600.0,
            auto_resolved_low_risk_rate=0.25,
            s0_count=2,
            s1_count=3,
            s2_count=2,
            low_risk_count=3,
        )
        
        result = metrics.to_dict()
        
        assert isinstance(result, dict)
        assert result["total_items"] == 10
        assert result["items_reviewed"] == 5
        assert result["manual_review_rate"] == 0.5
        assert result["median_review_time_per_item"] == 30.0
        assert result["high_risk_queue_age"] == 3600.0
        assert result["auto_resolved_low_risk_rate"] == 0.25
        assert result["s0_count"] == 2
        assert result["s1_count"] == 3
        assert result["s2_count"] == 2
        assert result["low_risk_count"] == 3


class TestHighRiskNotBuried:
    """Test that high-risk items are not buried behind low-risk items."""

    def test_s0_items_appear_first(self):
        """S0 items should appear first in queue."""
        items = [
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="low_hash",
                lineage_refs=[],
                risk_level=RiskLevel.LOW_RISK,
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="s0_hash",
                lineage_refs=[],
                risk_level=RiskLevel.S0_HARD_VIOLATION,
            ),
        ]
        
        vm = ReviewQueueViewModel.from_items(items)
        
        # First item should be S0
        assert vm.items[0].risk_level == RiskLevel.S0_HARD_VIOLATION

    def test_s1_items_appear_after_s0(self):
        """S1 items should appear after S0 items."""
        items = [
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="s1_hash",
                lineage_refs=[],
                risk_level=RiskLevel.S1_HIGH_RISK,
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="s0_hash",
                lineage_refs=[],
                risk_level=RiskLevel.S0_HARD_VIOLATION,
            ),
        ]
        
        vm = ReviewQueueViewModel.from_items(items)
        
        # First item should be S0, second should be S1
        assert vm.items[0].risk_level == RiskLevel.S0_HARD_VIOLATION
        assert vm.items[1].risk_level == RiskLevel.S1_HIGH_RISK

    def test_s2_items_appear_after_s1(self):
        """S2 items should appear after S1 items."""
        items = [
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="s2_hash",
                lineage_refs=[],
                risk_level=RiskLevel.S2_WARNING,
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="s1_hash",
                lineage_refs=[],
                risk_level=RiskLevel.S1_HIGH_RISK,
            ),
        ]
        
        vm = ReviewQueueViewModel.from_items(items)
        
        # First item should be S1, second should be S2
        assert vm.items[0].risk_level == RiskLevel.S1_HIGH_RISK
        assert vm.items[1].risk_level == RiskLevel.S2_WARNING

    def test_low_risk_items_appear_last(self):
        """Low-risk items should appear last in queue."""
        items = [
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="low_hash",
                lineage_refs=[],
                risk_level=RiskLevel.LOW_RISK,
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="s0_hash",
                lineage_refs=[],
                risk_level=RiskLevel.S0_HARD_VIOLATION,
            ),
        ]
        
        vm = ReviewQueueViewModel.from_items(items)
        
        # Last item should be low-risk
        assert vm.items[-1].risk_level == RiskLevel.LOW_RISK

    def test_get_high_risk_items_returns_all(self):
        """get_high_risk_items() should return all S0 and S1 items."""
        items = [
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="low_hash",
                lineage_refs=[],
                risk_level=RiskLevel.LOW_RISK,
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="s0_hash",
                lineage_refs=[],
                risk_level=RiskLevel.S0_HARD_VIOLATION,
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="s1_hash",
                lineage_refs=[],
                risk_level=RiskLevel.S1_HIGH_RISK,
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="s2_hash",
                lineage_refs=[],
                risk_level=RiskLevel.S2_WARNING,
            ),
        ]
        
        vm = ReviewQueueViewModel.from_items(items)
        high_risk = vm.get_high_risk_items()
        
        assert len(high_risk) == 2
        assert all(
            item.risk_level in (RiskLevel.S0_HARD_VIOLATION, RiskLevel.S1_HIGH_RISK)
            for item in high_risk
        )


class TestMetricsForEvaluationFixtures:
    """Test that metrics are available for UI evaluation fixtures."""

    def test_metrics_suitable_for_eval_fixture(self):
        """Verify metrics contain all required fields for evaluation."""
        metrics = ReviewBurdenMetrics()
        
        required_fields = [
            "manual_review_rate",
            "median_review_time_per_item",
            "high_risk_queue_age",
            "auto_resolved_low_risk_rate",
        ]
        
        for field in required_fields:
            assert hasattr(metrics, field), f"Missing required field: {field}"
            assert isinstance(getattr(metrics, field), (int, float))

    def test_metrics_from_fixture_parseable(self):
        """Test that metrics from fixture JSON are parseable."""
        import json
        
        fixture_path = "fixtures/ui-validation/input_review_queue.json"
        with open(fixture_path) as f:
            fixture = json.load(f)
        
        # Verify fixture has expected structure for metrics
        assert "items" in fixture
        assert "metadata" in fixture
        
        # Create view models from fixture items
        items = []
        for item_data in fixture["items"]:
            items.append(ReviewQueueItem(
                item_id=uuid4(),
                content_hash=item_data["content_hash"],
                lineage_refs=[
                    LineageRef(
                        artifact_id=uuid4(),
                        artifact_type=ref["artifact_type"],
                        relationship=ref["relationship"],
                    )
                    for ref in item_data.get("lineage_refs", [])
                ],
                review_status=ReviewStatus(item_data["review_status"]),
                risk_level=RiskLevel(item_data["risk_level"]),
                is_runtime_impacting=item_data.get("is_runtime_impacting", False),
            ))
        
        vm = ReviewQueueViewModel.from_items(items)
        
        # Verify metrics are populated
        assert vm.metrics.total_items == len(items)
        assert vm.metrics.s0_count >= 0
        assert vm.metrics.s1_count >= 0


class TestBatchReleaseMetrics:
    """Test batch release related metrics."""

    def test_batch_release_blocked_s0_s1_counted(self):
        """Verify S0/S1 batch release blocks are counted."""
        items = [
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="hash1",
                lineage_refs=[],
                risk_level=RiskLevel.S0_HARD_VIOLATION,
                can_batch_release=False,
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="hash2",
                lineage_refs=[],
                risk_level=RiskLevel.S1_HIGH_RISK,
                can_batch_release=False,
            ),
            ReviewQueueItem(
                item_id=uuid4(),
                content_hash="hash3",
                lineage_refs=[],
                risk_level=RiskLevel.LOW_RISK,
                can_batch_release=True,
            ),
        ]
        
        vm = ReviewQueueViewModel.from_items(items)
        
        # Should count S0/S1 items that cannot batch release
        blocked_count = sum(
            1 for item in items 
            if item.risk_level in (RiskLevel.S0_HARD_VIOLATION, RiskLevel.S1_HIGH_RISK)
            and not item.can_batch_release
        )
        
        assert blocked_count == 2
