import logging
import time

import requests

logger = logging.getLogger(__name__)


def fetch(url: str, retries: int = 3, backoff: float = 1.0, **kwargs) -> requests.Response:
    """GET a URL with exponential-backoff retries on transient errors."""
    last_exc: Exception = RuntimeError("no attempts made")
    for attempt in range(retries):
        r = None
        try:
            r = requests.get(url, **kwargs)
            r.raise_for_status()
            return r
        except requests.HTTPError as e:
            if r is not None and r.status_code < 500:
                raise  # 4xx — no point retrying
            last_exc = e
        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
        if r is not None:
            r.close()
        if attempt < retries - 1:
            wait = backoff * (2 ** attempt)
            logger.warning("Retrying %s in %.1fs (attempt %d/%d): %s", url, wait, attempt + 1, retries, last_exc)
            time.sleep(wait)
    raise last_exc