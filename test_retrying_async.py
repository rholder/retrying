import asyncio
import unittest

from retrying import retry
from test_retrying import NoIOErrorAfterCount


def asynctest(callable_):
    callable_ = asyncio.coroutine(callable_)

    def wrapper(*a, **kw):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(callable_(*a, **kw))

    return wrapper


@retry(wait_fixed=50)
@asyncio.coroutine
def _retryable_coroutine(thing):
    thing.go()


class AsyncCase(unittest.TestCase):
    @asynctest
    def test_sleep(self):
        assert asyncio.iscoroutinefunction(_retryable_coroutine)
        thing = NoIOErrorAfterCount(5)
        yield from _retryable_coroutine(thing)
        assert thing.counter == thing.count


if __name__ == '__main__':
    unittest.main()
