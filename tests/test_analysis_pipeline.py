"""Unit tests for AnalysisPipeline — orchestration and deduplication."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from api.analysis import AnalysisPipeline
from api.analysis.base import Finding


def _finding(resource_id: str, finding_type: str = "idle_vm") -> Finding:
    return Finding(
        resource_id=resource_id,
        resource_name="res",
        resource_type="microsoft.compute/virtualmachines",
        resource_group="rg1",
        location="eastus",
        finding_type=finding_type,
        severity="high",
        reason="test",
    )


def _make_pipeline_with_analyzers(*analyzers):
    """Build an AnalysisPipeline and inject mock analyzers."""
    mock_metrics = MagicMock()
    pipeline = AnalysisPipeline(mock_metrics)
    pipeline._analyzers = list(analyzers)
    return pipeline


class TestAnalysisPipeline:
    def test_run_aggregates_findings_from_multiple_analyzers(self):
        a1 = MagicMock()
        a1.analyze.return_value = [_finding("/sub/rg/vm1")]
        a2 = MagicMock()
        a2.analyze.return_value = [_finding("/sub/rg/vm2")]

        pipeline = _make_pipeline_with_analyzers(a1, a2)
        results = pipeline.run([], {})
        assert len(results) == 2

    def test_run_deduplicates_same_resource_and_finding_type(self):
        f = _finding("/sub/rg/vm1", "idle_vm")
        a1 = MagicMock()
        a1.analyze.return_value = [f]
        a2 = MagicMock()
        a2.analyze.return_value = [f]

        pipeline = _make_pipeline_with_analyzers(a1, a2)
        results = pipeline.run([], {})
        assert len(results) == 1

    def test_run_allows_same_resource_different_finding_types(self):
        f1 = _finding("/sub/rg/vm1", "idle_vm")
        f2 = _finding("/sub/rg/vm1", "orphan_disk")
        a1 = MagicMock()
        a1.analyze.return_value = [f1, f2]

        pipeline = _make_pipeline_with_analyzers(a1)
        results = pipeline.run([], {})
        assert len(results) == 2

    def test_run_empty_analyzers_returns_empty(self):
        pipeline = _make_pipeline_with_analyzers()
        assert pipeline.run([], {}) == []

    def test_run_all_module_function(self):
        """run_all() shim delegates to singleton pipeline."""
        with patch("api.analysis._get_pipeline") as mock_get:
            mock_pipeline = MagicMock()
            mock_pipeline.run.return_value = []
            mock_get.return_value = mock_pipeline

            from api.analysis import run_all
            run_all([], {})
            mock_pipeline.run.assert_called_once_with([], {})
