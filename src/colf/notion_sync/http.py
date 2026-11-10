"""Small JSON transport with bounded retries for throttled reads."""
from decimal import Decimal
import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def json_client(base: str, headers: dict | None = None):
    def request(method: str, path: str, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        req = Request(base + path, data=data, method=method,
                      headers={'Content-Type': 'application/json', **(headers or {})})
        for attempt in range(3):
            try:
                with urlopen(req, timeout=30) as response:
                    return json.load(response, parse_float=Decimal)
            except HTTPError as error:
                if error.code != 429 or method != 'GET' or attempt == 2:
                    raise RuntimeError(f'HTTP {error.code}: {base}') from None
                delay = min(60, max(1, int(error.headers.get('Retry-After', '2'))))
                time.sleep(delay)
    return request
