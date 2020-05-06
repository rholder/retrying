from typing import TypeVar, Optional, Callable

FuncT = TypeVar('FuncT', bound=Callable)


def retry(
    stop: Optional[str] = None,
    wait: Optional[str] = None,
    stop_max_attempt_number: Optional[int] = None,
    stop_max_delay: Optional[int] = None,
    wait_fixed: Optional[int] = None,
    wait_random_min: Optional[int] = None,
    wait_random_max: Optional[int] = None,
    wait_incrementing_start: Optional[int] = None,
    wait_incrementing_increment: Optional[int] = None,
    wait_exponential_multiplier: Optional[int] = None,
    wait_exponential_max: Optional[int] = None,
    retry_on_exception: Optional[Callable[[BaseException], bool]] = None,
    retry_on_result: Optional[Callable[..., bool]] = None,
    wrap_exception: bool = False,
    stop_func: Optional[Callable[[int, int], bool]] = None,
    wait_func: Optional[Callable[[int, int], bool]] = None,
    wait_jitter_max: Optional[int] = None,
) -> Callable[[FuncT], FuncT]: ...
