"""Write the text summary into an existing gist (its first file, renamed to the title)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request


class GistError(Exception):
    pass


def _call(method, url, token, data=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "print-heatmap",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        hint = " (the token needs the gist scope)" if e.code in (401, 403, 404) else ""
        raise GistError(f"GitHub API {method} {url}: HTTP {e.code}{hint}") from e


def update(gist_id, token, title, content):
    url = f"https://api.github.com/gists/{gist_id}"
    files = _call("GET", url, token).get("files") or {}
    current = title if title in files else next(iter(files), title)
    _call("PATCH", url, token, {"files": {current: {"filename": title, "content": content}}})
