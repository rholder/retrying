## Copyright 2013-2014 Ray Holder
##
## Licensed under the Apache License, Version 2.0 (the "License");
## you may not use this file except in compliance with the License.
## You may obtain a copy of the License at
##
## http://www.apache.org/licenses/LICENSE-2.0
##
## Unless required by applicable law or agreed to in writing, software
## distributed under the License is distributed on an "AS IS" BASIS,
## WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
## See the License for the specific language governing permissions and
## limitations under the License.
import inspect
import random
import sys
import time
import traceback

import six


if sys.version_info >= (3, 5):
    def _is_async(fn):
        return inspect.isasyncgenfunction(fn) or inspect.isgeneratorfunction(fn)
else:
    def _is_async(fn):
        return inspect.isgeneratorfunction(fn)


# sys.maxint / 2, since Python 3.2 doesn't have a sys.maxint...
MAX_WAIT = 1073741823


def _retry_if_exception_of_type(retryable_types):
    def _retry_if_exception_these_types(exception):
        return isinstance(exception, retryable_types)
    return _retry_if_exception_these_types


def retry(*dargs, **dkw):
    """
    Decorator function that instantiates the Retrying object
    @param *dargs: positional arguments passed to Retrying object
    @param **dkw: keyword arguments passed to the Retrying object
    """
    # support both @retry and @retry() as valid syntax
    if len(dargs) == 1 and callable(dargs[0]):
        def wrap_simple(f):

            @six.wraps(f)
            def wrapped_f(*args, **kw):
                if dkw.get('deterministic_generators') and _is_async(f):
                    return Retrying().call_async(f, *args, **kw)
                return Retrying().call(f, *args, **kw)
            return wrapped_f

        return wrap_simple(dargs[0])

    else:
        def wrap(f):

            @six.wraps(f)
            def wrapped_f(*args, **kw):
                if dkw.get('deterministic_generators') and _is_async(f):
                    return Retrying(*dargs, **dkw).call_async(f, *args, **kw)
                return Retrying(*dargs, **dkw).call(f, *args, **kw)

            return wrapped_f

        return wrap


class Retrying(object):

    def __init__(self,
                 stop=None, wait=None,
                 stop_max_attempt_number=None,
                 stop_max_delay=None,
                 wait_fixed=None,
                 wait_random_min=None, wait_random_max=None,
                 wait_incrementing_start=None, wait_incrementing_increment=None,
                 wait_incrementing_max=None,
                 wait_exponential_multiplier=None, wait_exponential_max=None,
                 retry_on_exception=None,
                 retry_on_result=None,
                 wrap_exception=False,
                 stop_func=None,
                 wait_func=None,
                 wait_jitter_max=None,
                 before_attempts=None,
                 after_attempts=None,
                 deterministic_generators=False):

        self._stop_max_attempt_number = 5 if stop_max_attempt_number is None else stop_max_attempt_number
        self._stop_max_delay = 100 if stop_max_delay is None else stop_max_delay
        self._wait_fixed = 1000 if wait_fixed is None else wait_fixed
        self._wait_random_min = 0 if wait_random_min is None else wait_random_min
        self._wait_random_max = 1000 if wait_random_max is None else wait_random_max
        self._wait_incrementing_start = 0 if wait_incrementing_start is None else wait_incrementing_start
        self._wait_incrementing_increment = 100 if wait_incrementing_increment is None else wait_incrementing_increment
        self._wait_exponential_multiplier = 1 if wait_exponential_multiplier is None else wait_exponential_multiplier
        self._wait_exponential_max = MAX_WAIT if wait_exponential_max is None else wait_exponential_max
        self._wait_incrementing_max = MAX_WAIT if wait_incrementing_max is None else wait_incrementing_max
        self._wait_jitter_max = 0 if wait_jitter_max is None else wait_jitter_max
        self._before_attempts = before_attempts
        self._after_attempts = after_attempts
        self._deterministic_generators = deterministic_generators
        self._deterministic_offset = -1
        # TODO add chaining of stop behaviors
        # stop behavior
        stop_funcs = []
        if stop_max_attempt_number is not None:
            stop_funcs.append(self.stop_after_attempt)

        if stop_max_delay is not None:
            stop_funcs.append(self.stop_after_delay)

        if stop_func is not None:
            self.stop = stop_func

        elif stop is None:
            self.stop = lambda attempts, delay: any(f(attempts, delay) for f in stop_funcs)

        else:
            self.stop = getattr(self, stop)

        # TODO add chaining of wait behaviors
        # wait behavior
        wait_funcs = [lambda *args, **kwargs: 0]
        if wait_fixed is not None:
            wait_funcs.append(self.fixed_sleep)

        if wait_random_min is not None or wait_random_max is not None:
            wait_funcs.append(self.random_sleep)

        if wait_incrementing_start is not None or wait_incrementing_increment is not None:
            wait_funcs.append(self.incrementing_sleep)

        if wait_exponential_multiplier is not None or wait_exponential_max is not None:
            wait_funcs.append(self.exponential_sleep)

        if wait_func is not None:
            self.wait = wait_func

        elif wait is None:
            self.wait = lambda attempts, delay: max(f(attempts, delay) for f in wait_funcs)

        else:
            self.wait = getattr(self, wait)

        # retry on exception filter
        if retry_on_exception is None:
            self._retry_on_exception = self.always_reject
        else:
            # this allows for providing a tuple of exception types that
            # should be allowed to retry on, and avoids having to create
            # a callback that does the same thing
            if isinstance(retry_on_exception, (tuple)):
                retry_on_exception = _retry_if_exception_of_type(
                    retry_on_exception)
            self._retry_on_exception = retry_on_exception

        # retry on result filter
        if retry_on_result is None:
            self._retry_on_result = self.never_reject
        else:
            self._retry_on_result = retry_on_result

        self._wrap_exception = wrap_exception

    def stop_after_attempt(self, previous_attempt_number, delay_since_first_attempt_ms):
        """Stop after the previous attempt >= stop_max_attempt_number."""
        return previous_attempt_number >= self._stop_max_attempt_number

    def stop_after_delay(self, previous_attempt_number, delay_since_first_attempt_ms):
        """Stop after the time from the first attempt >= stop_max_delay."""
        return delay_since_first_attempt_ms >= self._stop_max_delay

    @staticmethod
    def no_sleep(previous_attempt_number, delay_since_first_attempt_ms):
        """Don't sleep at all before retrying."""
        return 0

    def fixed_sleep(self, previous_attempt_number, delay_since_first_attempt_ms):
        """Sleep a fixed amount of time between each retry."""
        return self._wait_fixed

    def random_sleep(self, previous_attempt_number, delay_since_first_attempt_ms):
        """Sleep a random amount of time between wait_random_min and wait_random_max"""
        return random.randint(self._wait_random_min, self._wait_random_max)

    def incrementing_sleep(self, previous_attempt_number, delay_since_first_attempt_ms):
        """
        Sleep an incremental amount of time after each attempt, starting at
        wait_incrementing_start and incrementing by wait_incrementing_increment
        """
        result = self._wait_incrementing_start + (self._wait_incrementing_increment * (previous_attempt_number - 1))
        if result > self._wait_incrementing_max:
            result = self._wait_incrementing_max
        if result < 0:
            result = 0
        return result

    def exponential_sleep(self, previous_attempt_number, delay_since_first_attempt_ms):
        exp = 2 ** previous_attempt_number
        result = self._wait_exponential_multiplier * exp
        if result > self._wait_exponential_max:
            result = self._wait_exponential_max
        if result < 0:
            result = 0
        return result

    @staticmethod
    def never_reject(result):
        return False

    @staticmethod
    def always_reject(result):
        return True

    def should_reject(self, attempt):
        reject = False
        if attempt.has_exception:
            reject |= self._retry_on_exception(attempt.value[1])
        else:
            reject |= self._retry_on_result(attempt.value)

        return reject

    def call(self, fn, *args, **kwargs):
        self._deterministic_offset = -1
        assert not self._deterministic_generators

        is_generator = _is_async(fn)

        start_time = int(round(time.time() * 1000))
        attempt_number = 1
        while True:
            if self._before_attempts:
                self._before_attempts(attempt_number)

            try:
                if is_generator:
                    # Here we do not know if the generator will fail.
                    # In order to avoid partial yield to the caller, which would
                    # produce partial data and then start from scratch upon error,
                    # we have to fetch the whole data and, in case of failures, we
                    # just recreate the result from scratch.
                    # We could also yield data incrementally and, when retrying,
                    # skip what we have already produced.
                    # This would require deterministic order of element production, though.
                    result = list(fn(*args, **kwargs))
                else:
                    result = fn(*args, **kwargs)
                attempt = Attempt(result, attempt_number, False)
            except:
                tb = sys.exc_info()
                attempt = Attempt(tb, attempt_number, True)
            
            if not self.should_reject(attempt):
                if is_generator:
                    return self._yelded_data(attempt)
                return attempt.get(self._wrap_exception)

            if self._after_attempts:
                self._after_attempts(attempt_number)

            delay_since_first_attempt_ms = int(round(time.time() * 1000)) - start_time
            if self.stop(attempt_number, delay_since_first_attempt_ms):
                if not self._wrap_exception and attempt.has_exception:
                    # get() on an attempt with an exception should cause it to be raised, but raise just in case
                    raise attempt.get()
                else:
                    raise RetryError(attempt)
            else:
                sleep = self.wait(attempt_number, delay_since_first_attempt_ms)
                if self._wait_jitter_max:
                    jitter = random.random() * self._wait_jitter_max
                    sleep = sleep + max(0, jitter)
                time.sleep(sleep / 1000.0)

            attempt_number += 1

    def call_async(self, fn, *args, **kwargs):
        self._deterministic_offset = -1
        assert self._deterministic_generators
        assert _is_async(fn)

        start_time = int(round(time.time() * 1000))
        attempt_number = 1
        while True:
            if self._before_attempts:
                self._before_attempts(attempt_number)

            try:
                for d in self._deterministic_generation(fn, *args, **kwargs):
                    yield d
                attempt = Attempt(None, attempt_number, False)
            except:
                tb = sys.exc_info()
                attempt = Attempt(tb, attempt_number, True)

            if not self.should_reject(attempt):
                self._yelded_data(attempt)
                return
            if self._after_attempts:
                self._after_attempts(attempt_number)

            delay_since_first_attempt_ms = int(round(time.time() * 1000)) - start_time
            if self.stop(attempt_number, delay_since_first_attempt_ms):
                if not self._wrap_exception and attempt.has_exception:
                    # get() on an attempt with an exception should cause it to be raised, but raise just in case
                    raise attempt.get()
                else:
                    raise RetryError(attempt)
            else:
                sleep = self.wait(attempt_number, delay_since_first_attempt_ms)
                if self._wait_jitter_max:
                    jitter = random.random() * self._wait_jitter_max
                    sleep = sleep + max(0, jitter)
                time.sleep(sleep / 1000.0)

            attempt_number += 1

    def _yelded_data(self, attempt):
        for d in attempt.get(self._wrap_exception):
            yield d

    def _deterministic_generation(self, fn, *args, **kwargs):
        for i, v in enumerate(fn(*args, **kwargs)):
            if i <= self._deterministic_offset:
                continue
            yield v
            self._deterministic_offset = i


class Attempt(object):
    """
    An Attempt encapsulates a call to a target function that may end as a
    normal return value from the function or an Exception depending on what
    occurred during the execution.
    """

    def __init__(self, value, attempt_number, has_exception):
        self.value = value
        self.attempt_number = attempt_number
        self.has_exception = has_exception

    def get(self, wrap_exception=False):
        """
        Return the return value of this Attempt instance or raise an Exception.
        If wrap_exception is true, this Attempt is wrapped inside of a
        RetryError before being raised.
        """
        if self.has_exception:
            if wrap_exception:
                raise RetryError(self)
            else:
                six.reraise(self.value[0], self.value[1], self.value[2])
        else:
            return self.value

    def __repr__(self):
        if self.has_exception:
            return "Attempts: {0}, Error:\n{1}".format(self.attempt_number, "".join(traceback.format_tb(self.value[2])))
        else:
            return "Attempts: {0}, Value: {1}".format(self.attempt_number, self.value)


class RetryError(Exception):
    """
    A RetryError encapsulates the last Attempt instance right before giving up.
    """

    def __init__(self, last_attempt):
        self.last_attempt = last_attempt

    def __str__(self):
        return "RetryError[{0}]".format(self.last_attempt)
