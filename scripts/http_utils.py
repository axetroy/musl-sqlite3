import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def urlopen_with_retry(request, timeout):
    for attempt in range(3):
        try:
            return urlopen(request, timeout=timeout)
        except HTTPError as error:
            if error.code not in (408, 429) and not 500 <= error.code < 600:
                raise
            if attempt == 2:
                raise
            error.close()
        except (URLError, TimeoutError):
            if attempt == 2:
                raise

        time.sleep(2**attempt)
