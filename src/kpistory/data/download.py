"""Robust downloads: one-off files (cached in data/raw) and paginated public APIs."""

from __future__ import annotations

import io
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from ..paths import RAW_DIR

USER_AGENT = "kpistory/1.0 (portfolio project; open data)"


class DownloadError(RuntimeError):
    pass


def _get(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def with_retries(
    func: Callable[[], bytes], retries: int, wait: float = 2.0, sleep=time.sleep
) -> bytes:
    """Call func, retrying with exponential back-off (2 s, 4 s, 8 s, ...)."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return func()
        except Exception as exc:  # network errors come in many shapes
            last = exc
            if attempt < retries:
                sleep(wait * 2**attempt)
    raise DownloadError(f"{type(last).__name__}: {last}") from last


def fetch(url: str, filename: str, timeout: int = 120, retries: int = 2) -> Path:
    """Return the cached file in data/raw, downloading it first if needed."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    target = RAW_DIR / filename
    if target.exists() and target.stat().st_size > 0:
        return target
    data = with_retries(lambda: _get(url, timeout), retries)
    tmp = target.with_suffix(target.suffix + ".part")
    tmp.write_bytes(data)
    tmp.rename(target)
    return target


def fetch_paged_csv(
    base_url: str,
    params: dict[str, str],
    page_size: int,
    max_rows: int,
    min_rows: int,
    retries: int = 4,
    timeout: int = 180,
    get: Callable[[str, int], bytes] = _get,
    log: Callable[[str], None] = print,
) -> pd.DataFrame:
    """Download a Socrata-style CSV API page by page ($limit / $offset).

    Logs the rows of every page and raises DownloadError when fewer than `min_rows`
    arrive, so a truncated download never reaches the site.
    """
    pages, offset = [], 0
    while offset < max_rows:
        query = {**params, "$limit": str(page_size), "$offset": str(offset)}
        url = f"{base_url}?{urllib.parse.urlencode(query)}"
        raw = with_retries(lambda u=url: get(u, timeout), retries)
        page = pd.read_csv(io.BytesIO(raw), dtype=str)
        log(f"    página {len(pages) + 1}: {len(page)} filas (desde la fila {offset})")
        if page.empty:
            break
        pages.append(page)
        if len(page) < page_size:
            break
        offset += page_size
    df = pd.concat(pages, ignore_index=True) if pages else pd.DataFrame()
    log(f"    total descargado: {len(df)} filas")
    if len(df) < min_rows:
        raise DownloadError(f"solo llegaron {len(df)} filas (mínimo esperado: {min_rows})")
    return df
