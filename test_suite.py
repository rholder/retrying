from test_retrying import *

try:
    import asyncio
except ImportError:
    pass
else:
    from test_retrying_async import *


if __name__ == '__main__':
    unittest.main()
