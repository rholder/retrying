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

import asyncio
import sys


@asyncio.coroutine
def call_async(self, fn, *args, **kwargs):
    from retrying import GeneratorReturn

    retry_generator = self.retry_main_loop()
    next(retry_generator)
    while True:
        try:
            try_result = yield from fn(*args, **kwargs)
            try_result = (try_result,)
            send = retry_generator.send
        except:
            try_result = sys.exc_info()
            send = retry_generator.throw

        try:
            send(*try_result)
        except GeneratorReturn as e:
            return e.value
