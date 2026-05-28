"""
Tests for batch/parallel_utils.py
"""

from unittest.mock import MagicMock, patch

import pytest

from batch.parallel_utils import run_indexed_parallel


class TestRunIndexedParallel:
    """Test suite for run_indexed_parallel function."""

    def test_returns_empty_list_when_inputs_empty(self):
        """Empty input should return empty output."""
        result = run_indexed_parallel(
            inputs=[],
            worker=lambda x: x * 2,
            max_workers=2,
            on_error=lambda idx, exc: None,
        )
        assert result == []

    def test_preserves_order_with_simple_worker(self):
        """Results should maintain input order even with parallel execution."""
        inputs = [1, 2, 3, 4, 5]
        result = run_indexed_parallel(
            inputs=inputs,
            worker=lambda x: x * 2,
            max_workers=2,
            on_error=lambda idx, exc: -1,
        )
        assert result == [2, 4, 6, 8, 10]

    def test_calls_on_error_when_worker_raises(self):
        """on_error callback should be called for failed workers."""
        def failing_worker(x: int) -> int:
            if x == 2:
                raise ValueError("Intentional failure")
            return x * 2

        error_handler = MagicMock(return_value=-999)

        result = run_indexed_parallel(
            inputs=[1, 2, 3],
            worker=failing_worker,
            max_workers=2,
            on_error=error_handler,
        )

        assert result == [2, -999, 6]
        error_handler.assert_called_once()
        call_args = error_handler.call_args[0]
        assert call_args[0] == 1  # index
        assert isinstance(call_args[1], ValueError)

    def test_partial_failures_preserve_successful_results(self):
        """Partial failures should not affect successful worker results."""
        def partial_failing_worker(x: int) -> int:
            if x % 2 == 0:
                raise RuntimeError("Even number")
            return x * 10

        def error_fallback(idx: int, exc: Exception) -> int:
            return 0

        result = run_indexed_parallel(
            inputs=[1, 2, 3, 4, 5],
            worker=partial_failing_worker,
            max_workers=3,
            on_error=error_fallback,
        )

        assert result == [10, 0, 30, 0, 50]

    def test_handles_different_exception_types(self):
        """on_error should receive correct exception types."""
        exception_types = []

        def mixed_failing_worker(x: int) -> int:
            if x == 0:
                raise ValueError("Value error")
            if x == 1:
                raise RuntimeError("Runtime error")
            if x == 2:
                raise KeyError("Key error")
            return x

        def error_recorder(idx: int, exc: Exception) -> int:
            exception_types.append(type(exc).__name__)
            return -1

        result = run_indexed_parallel(
            inputs=[0, 1, 2, 3],
            worker=mixed_failing_worker,
            max_workers=2,
            on_error=error_recorder,
        )

        assert result == [-1, -1, -1, 3]
        assert sorted(exception_types) == ["KeyError", "RuntimeError", "ValueError"]

    def test_max_workers_parameter_affects_execution(self):
        """Different max_workers values should work correctly."""
        inputs = list(range(10))

        # Test with different worker counts
        for max_workers in [1, 2, 4]:
            result = run_indexed_parallel(
                inputs=inputs,
                worker=lambda x: x * 2,
                max_workers=max_workers,
                on_error=lambda idx, exc: None,
            )
            assert result == [x * 2 for x in inputs]

    def test_worker_with_complex_return_types(self):
        """Worker can return complex types (dict, list, etc.)."""
        def dict_worker(x: int) -> dict:
            return {"value": x, "doubled": x * 2}

        result = run_indexed_parallel(
            inputs=[1, 2, 3],
            worker=dict_worker,
            max_workers=2,
            on_error=lambda idx, exc: {},
        )

        assert result == [
            {"value": 1, "doubled": 2},
            {"value": 2, "doubled": 4},
            {"value": 3, "doubled": 6},
        ]

    def test_on_error_receives_correct_index(self):
        """on_error should receive correct input index even with parallel execution."""
        error_indices = []

        def selective_failing_worker(x: int) -> int:
            if x in {1, 3, 5}:
                raise ValueError(f"Fail {x}")
            return x

        def index_recorder(idx: int, exc: Exception) -> int:
            error_indices.append(idx)
            return -1

        run_indexed_parallel(
            inputs=[0, 1, 2, 3, 4, 5],
            worker=selective_failing_worker,
            max_workers=3,
            on_error=index_recorder,
        )

        assert sorted(error_indices) == [1, 3, 5]

    def test_all_workers_fail(self):
        """All workers failing should still return complete result list."""
        def always_failing_worker(x: int) -> int:
            raise RuntimeError("Always fails")

        result = run_indexed_parallel(
            inputs=[1, 2, 3],
            worker=always_failing_worker,
            max_workers=2,
            on_error=lambda idx, exc: None,
        )

        assert result == [None, None, None]

    def test_large_input_set(self):
        """Should handle large input sets efficiently."""
        inputs = list(range(100))

        result = run_indexed_parallel(
            inputs=inputs,
            worker=lambda x: x ** 2,
            max_workers=10,
            on_error=lambda idx, exc: -1,
        )

        assert len(result) == 100
        assert result[0] == 0
        assert result[50] == 2500
        assert result[99] == 9801

    def test_worker_with_side_effects(self):
        """Worker functions with side effects should execute correctly."""
        call_log = []

        def logging_worker(x: int) -> int:
            call_log.append(x)
            return x * 2

        result = run_indexed_parallel(
            inputs=[1, 2, 3],
            worker=logging_worker,
            max_workers=2,
            on_error=lambda idx, exc: -1,
        )

        assert result == [2, 4, 6]
        assert sorted(call_log) == [1, 2, 3]

    def test_on_error_return_value_replaces_failed_result(self):
        """on_error return value should replace the failed worker result."""
        def failing_worker(x: int) -> str:
            if x == 1:
                raise ValueError("Fail")
            return f"success_{x}"

        def custom_error_handler(idx: int, exc: Exception) -> str:
            return f"error_at_{idx}"

        result = run_indexed_parallel(
            inputs=[0, 1, 2],
            worker=failing_worker,
            max_workers=2,
            on_error=custom_error_handler,
        )

        assert result == ["success_0", "error_at_1", "success_2"]

    def test_respects_type_annotations(self):
        """Type checking should work with generic TypeVars."""
        # This test mainly validates type annotations work correctly
        def int_to_str_worker(x: int) -> str:
            return str(x)

        result: list[str] = run_indexed_parallel(
            inputs=[1, 2, 3],
            worker=int_to_str_worker,
            max_workers=2,
            on_error=lambda idx, exc: "error",
        )

        assert all(isinstance(r, str) for r in result)
        assert result == ["1", "2", "3"]
