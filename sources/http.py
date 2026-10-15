"""Small, polite JSON fetching for the public job APIs."""

import time

USER_AGENT = "JobRadar/1.0 (personal job search; contact via GitHub medamin127-web/JobRadar)"


class FetchError(Exception):
    pass


def get_json(url, params=None, get=None, retries=2, wait=5, sleep=time.sleep):
    """
    GET a URL and return the decoded JSON.

    Retries a couple of times on "too many requests" (429) and server
    errors (5xx). Raises FetchError with a readable message otherwise.
    `get` can be swapped in tests (defaults to requests.get).
    """

    if get is None:
        import requests

        get = requests.get

    last_error = None

    for attempt in range(retries + 1):
        try:
            response = get(url, params=params, timeout=30, headers={"User-Agent": USER_AGENT})
        except Exception as error:  # network problems
            last_error = f"network error: {error}"
        else:
            status = getattr(response, "status_code", 200)

            if status == 404:
                raise FetchError(f"not found (404): {url}")

            if status == 429 or status >= 500:
                last_error = f"HTTP {status}"
            elif status >= 400:
                raise FetchError(f"HTTP {status}: {url}")
            else:
                try:
                    return response.json()
                except ValueError:
                    raise FetchError(f"not JSON: {url}")

        if attempt < retries:
            sleep(wait * (attempt + 1))

    raise FetchError(f"{last_error} after {retries + 1} tries: {url}")