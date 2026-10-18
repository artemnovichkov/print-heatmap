"""Bambu Cloud: sign-in and print history.

The API is unofficial; endpoints follow OpenBambuAPI and the Home Assistant
Bambu Lab integration. The cloud keeps only the last ~3 months of tasks.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from http.cookies import SimpleCookie

HOSTS = {
    "global": ("https://api.bambulab.com", "https://bambulab.com"),
    "china": ("https://api.bambulab.cn", "https://bambulab.cn"),
}
HEADERS = {
    "User-Agent": "bambu_network_agent/01.09.05.01",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
PAGE = 50  # a limit above the server's cap (200..500) silently falls back to 20


class CloudError(Exception):
    pass


class AuthError(CloudError):
    pass


class Response:
    def __init__(self, status, body, headers):
        self.status, self.body, self.headers = status, body, headers

    def cookie(self, name):
        jar = SimpleCookie()
        for header in self.headers.get_all("Set-Cookie") or []:
            jar.load(header)
        return jar[name].value if name in jar else None


def _request(url, data=None, token=None, headers=None):
    h = dict(HEADERS, **(headers or {}))
    if token:
        h["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return Response(resp.status, json.loads(raw) if raw.strip() else {}, resp.headers)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = {"message": raw.decode(errors="replace")[:200]}
        return Response(e.code, payload, e.headers)


def _message(resp):
    body = resp.body if isinstance(resp.body, dict) else {}
    return body.get("message") or body.get("error") or f"HTTP {resp.status}"


def send_code(email, region="global"):
    """Email a one-time sign-in code."""
    api, _ = HOSTS[region]
    resp = _request(f"{api}/v1/user-service/user/sendemail/code", {"email": email, "type": "codeLogin"})
    if resp.status != 200:
        raise CloudError(f"could not send the code: {_message(resp)}")


def login_with_code(email, code, region="global"):
    """Returns {"token", "expires_in"} or {"tfa_key"} when two-factor auth is on."""
    api, _ = HOSTS[region]
    resp = _request(f"{api}/v1/user-service/user/login", {"account": email, "code": code})
    body = resp.body if isinstance(resp.body, dict) else {}
    if resp.status == 400 and body.get("code") == 1:
        raise AuthError("the code has expired, request a new one")
    if resp.status == 400 and body.get("code") == 2:
        raise AuthError("wrong code")
    if resp.status != 200:
        raise AuthError(f"sign-in failed: {_message(resp)}")
    if body.get("accessToken"):
        return {"token": body["accessToken"], "expires_in": body.get("expiresIn")}
    if body.get("loginType") == "tfa" and body.get("tfaKey"):
        return {"tfa_key": body["tfaKey"]}
    raise AuthError(f"unexpected sign-in response: loginType={body.get('loginType')!r}")


def login_tfa(tfa_key, code, region="global"):
    """Second step for accounts with two-factor auth; the token comes back as a cookie."""
    _, web = HOSTS[region]
    csrf = _request(f"{web}/api/csrf").cookie("bbl_csrf_token")
    if not csrf:
        raise AuthError("could not get a CSRF token for two-factor sign-in")
    resp = _request(
        f"{web}/api/sign-in/tfa",
        {"tfaKey": tfa_key, "tfaCode": code},
        headers={"x-bbl-csrf-token": csrf, "Cookie": f"bbl_csrf_token={csrf}"},
    )
    token = resp.cookie("token")
    if not token:
        raise AuthError(f"two-factor sign-in failed: {_message(resp)}")
    return {"token": token, "expires_in": None}


def fetch_tasks(token, region="global", limit=None):
    """All print tasks the cloud still has, newest first (raw API objects)."""
    api, _ = HOSTS[region]
    hits, total = [], None
    while (total is None or len(hits) < total) and (limit is None or len(hits) < limit):
        resp = _request(f"{api}/v1/user-service/my/tasks?limit={PAGE}&offset={len(hits)}", token=token)
        if resp.status == 401:
            raise AuthError("BAMBU_TOKEN is invalid or expired: run `print-heatmap login` for a new one")
        if resp.status != 200:
            raise CloudError(f"print history request failed: {_message(resp)}")
        total = resp.body.get("total", 0)
        page = resp.body.get("hits") or []
        if not page:
            break
        hits += page
    return hits[:limit] if limit else hits
