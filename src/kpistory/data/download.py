"""Download a public file once into data/raw, with a clear error when the network fails."""

from __future__ import annotations

import urllib.request
from pathlib import Path

from ..paths import RAW_DIR

USER_AGENT = "kpistory/1.0 (portfolio project; https://github.com)"


class DownloadError(RuntimeError):
    pass


def fetch(url: str, filename: str, timeout: int = 120) -> Path:
    """Return the cached file in data/raw, downloading it first if needed."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    target = RAW_DIR / filename
    if target.exists() and target.stat().st_size > 0:
        return target
    tmp = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, open(tmp, "wb") as fh:
            while chunk := response.read(1 << 20):
                fh.write(chunk)
    except Exception as exc:  # network errors come in many shapes; all mean "use plan B"
        tmp.unlink(missing_ok=True)
        raise DownloadError(f"{type(exc).__name__}: {exc}") from exc
    tmp.rename(target)
    return target
