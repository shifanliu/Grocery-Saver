"""Product data sources: the Grocery Saver HTTP API, or an explicit offline fixture.

There is no automatic fallback between them. The caller picks one, and every
result reports which one was used.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import settings


class ServiceError(Exception):
    """The data source could not be reached, or answered with something unusable."""


class ApiSource:
    mode = "api"

    def __init__(self, base_url: str | None = None, timeout: float | None = None,
                 store_id: str | None = None):
        self.base_url = (base_url or settings.API_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.API_TIMEOUT_SECONDS
        self.store_id = store_id

    @property
    def label(self) -> str:
        return f"Grocery Saver API at {self.base_url}"

    def search(self, query: str) -> list:
        params = {"q": query}
        if self.store_id:
            params["store_id"] = self.store_id
        url = f"{self.base_url}/items/search?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise ServiceError(f"API returned HTTP {exc.code} for {url}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ServiceError(
                f"API unreachable ({type(getattr(exc, 'reason', exc)).__name__}) at {self.base_url}"
            ) from exc
        except ValueError as exc:
            raise ServiceError(f"API returned non-JSON content: {exc}") from exc
        if not isinstance(body, dict) or not isinstance(body.get("items"), list):
            raise ServiceError("API response has no 'items' list (unexpected shape)")
        return body["items"]


class FixtureSource:
    """Offline data from a JSON file: {"kind", "label", "source_date", "items": [...]}.

    kind is "snapshot" (rows copied from the real API/DB, with source_date) or
    "synthetic" (made-up sample data). Search is a case-insensitive substring
    match on the name, like the real endpoint.
    """

    mode = "fixture"

    def __init__(self, path: str | Path | None = None, data: dict | None = None):
        if data is None:
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise ServiceError(f"cannot read fixture {path}: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            raise ServiceError("fixture has no 'items' list")
        self.data = data

    @property
    def label(self) -> str:
        kind = self.data.get("kind", "synthetic")
        tag = "SAMPLE DATA (synthetic)" if kind == "synthetic" else (
            f"offline snapshot dated {self.data.get('source_date', 'unknown')}")
        return f"{tag}: {self.data.get('label', 'unnamed fixture')}"

    def search(self, query: str) -> list:
        q = query.lower()
        return [i for i in self.data["items"]
                if isinstance(i, dict) and q in str(i.get("name", "")).lower()]
