"""Small, polite fetching for the job APIs (JSON) and job boards (HTML)."""

import time

USER_AGENT = "JobRadar/1.0 (personal job search; contact via GitHub medamin127-web/JobRadar)"

# Job boards without an API serve their pages to browsers.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


class FetchError(Exception):
    pass


def _fetch(url, params, get, retries, wait, sleep, headers):
    """
    GET with retries on "too many requests" (429) and server errors (5xx).
    Returns the response; raises FetchError with a readable message.
    `get` can be swapped in tests (defaults to requests.get).
    """

    if get is None:
        import requests

        get = requests.get

    last_error = None

    for attempt in range(retries + 1):
        try:
            response = get(url, params=params, timeout=30, headers=headers)
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
                return response

        if attempt < retries:
            sleep(wait * (attempt + 1))

    raise FetchError(f"{last_error} after {retries + 1} tries: {url}")


def get_json(url, params=None, get=None, retries=2, wait=5, sleep=time.sleep):
    """GET a URL and return the decoded JSON."""

    response = _fetch(url, params, get, retries, wait, sleep, {"User-Agent": USER_AGENT})

    try:
        return response.json()
    except ValueError:
        raise FetchError(f"not JSON: {url}")


def browser_get():
    """
    curl_cffi's get, which copies Chrome's network fingerprint (some sites,
    StepStone for one, refuse plain Python requests). None when curl_cffi
    is not installed:  pip install curl_cffi
    """

    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        return None

    def get(url, params=None, timeout=30, headers=None):
        return curl_requests.get(url, params=params, timeout=timeout, headers=headers,
                                 impersonate="chrome")

    return get


def get_html(url, params=None, get=None, retries=2, wait=5, sleep=time.sleep,
             browser_like=False) -> str:
    """
    GET a web page and return its HTML. browser_like: use curl_cffi when it
    is installed (looks like Chrome), else plain requests.
    """

    if get is None and browser_like:
        get = browser_get()

    response = _fetch(url, params, get, retries, wait, sleep, BROWSER_HEADERS)

    return response.text