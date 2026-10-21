import time
import urllib.error
import urllib.request
import urllib.robotparser
from pathlib import Path
from urllib.parse import urlparse

USER_AGENT = "GDC-Community-Index/0.1 (public session metadata only)"


class Fetcher:
    def __init__(self, cache: Path, refresh: bool = False, delay: float = 1.0):
        self.cache = cache
        self.refresh = refresh
        self.delay = delay
        self.last_request = 0.0
        self.robots = None

    def _read(self, url: str) -> str:
        if urlparse(url).hostname != "gdcvault.com":
            raise ValueError("The automatic collector only reads gdcvault.com public HTML")
        time.sleep(max(0.0, self.delay - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as response:
            final = urlparse(response.url)
            if final.hostname != "gdcvault.com" or final.path.startswith(("/login", "/register")):
                raise ValueError("Page requires login or registration; skipped")
            if "text/html" not in response.headers.get_content_type() and not url.endswith("robots.txt"):
                raise ValueError("Expected HTML; media downloads are disabled")
            body = response.read(4_000_001)
            if len(body) > 4_000_000:
                raise ValueError("HTML exceeds the 4 MB collector limit")
            return body.decode(response.headers.get_content_charset() or "utf-8")

    def get(self, url: str, filename: str) -> str:
        path = self.cache / filename
        # A normal run reuses a one-week snapshot. --refresh revalidates upstream.
        if path.exists() and not self.refresh and time.time() - path.stat().st_mtime < 7 * 86400:
            return path.read_text(encoding="utf-8")
        if self.robots is None:
            self.robots = urllib.robotparser.RobotFileParser()
            self.robots.parse(self._read("https://gdcvault.com/robots.txt").splitlines())
        if not self.robots.can_fetch(USER_AGENT, url):
            raise ValueError("Upstream robots.txt disallows this URL")
        for attempt in range(3):
            try:
                body = self._read(url)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8", newline="\n")
                return body
            except urllib.error.HTTPError as error:
                if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise
                time.sleep(min(30, 2 ** (attempt + 1)))
            except urllib.error.URLError:
                if attempt == 2:
                    raise
                time.sleep(2 ** (attempt + 1))
        raise RuntimeError("Failed to fetch public metadata")
