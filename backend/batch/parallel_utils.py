from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def run_indexed_parallel(
    inputs: list[T],
    worker: Callable[[T], R],
    *,
    max_workers: int,
    on_error: Callable[[int, Exception], R],
) -> list[R]:
    """Run worker over inputs in parallel and preserve original order."""
    if not inputs:
        return []

    results: list[R] = [None] * len(inputs)  # type: ignore[list-item]
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker, item): idx for idx, item in enumerate(inputs)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as exc:  # noqa: BLE001 - centralized boundary
                results[idx] = on_error(idx, exc)
    return results
