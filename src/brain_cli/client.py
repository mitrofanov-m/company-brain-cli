"""Standard-library HTTP client bundled with the standalone CLI."""
from __future__ import annotations

import json
import ipaddress
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class _NoRedirect(HTTPRedirectHandler):
    """Do not let urllib forward Bearer credentials to a redirect target."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER=build_opener(_NoRedirect())


class APIError(RuntimeError):
    def __init__(self, status: int, message: str, payload=None):
        super().__init__(message)
        self.status = status
        self.payload = payload


class BrainAPIClient:
    def __init__(self, base_url: str, token: str, timeout: float = 30.0, *, connection="api", admin_session=None):
        parts=urlsplit(base_url)
        if parts.scheme not in ("http","https") or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path not in ("","/"):
            raise ValueError("API URL must be an HTTP(S) origin without embedded credentials")
        loopback=parts.hostname.lower()=="localhost"
        try: loopback=loopback or ipaddress.ip_address(parts.hostname).is_loopback
        except ValueError: pass
        if parts.scheme!="https" and not loopback:
            raise ValueError("API tokens may be sent over HTTP only to localhost or a loopback IP")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.connection = connection
        self.admin_session = os.environ.get('BRAIN_ADMIN_SESSION','') if admin_session is None else admin_session

    def request(self, method: str, path: str, payload=None):
        url = self.base_url + "/" + path.lstrip("/")
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if data is not None and len(data)>48*1024*1024:
            raise APIError(413,"API request exceeds 48 MiB")
        headers = {"Accept": "application/json", "X-Brain-Client":self.connection}
        if self.token: headers["Authorization"] = "Bearer " + self.token
        if self.admin_session: headers['X-Brain-Admin-Session']=self.admin_session
        if data is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        req = Request(url, data=data, headers=headers, method=method.upper())
        try:
            with _OPENER.open(req, timeout=self.timeout) as response:
                raw = response.read(32 * 1024 * 1024 + 1)
                if len(raw) > 32 * 1024 * 1024:
                    raise APIError(response.status, "API response exceeds 32 MiB")
                return json.loads(raw) if raw else None
        except HTTPError as exc:
            try: raw = exc.read(1024 * 1024)
            finally: exc.close()
            try:
                payload = json.loads(raw)
                message = payload.get("error", str(exc)) if isinstance(payload, dict) else str(exc)
            except (ValueError, UnicodeDecodeError):
                payload = None
                message = str(exc)
            raise APIError(exc.code, message, payload) from None
        except URLError as exc:
            raise APIError(503, f"Company Brain API unavailable: {exc.reason}") from None

    @staticmethod
    def segment(value: str) -> str:
        return quote(str(value), safe="")

    def workspaces(self): return self.request("GET", "/v1/workspaces").get("workspaces", [])
    def workspace(self, workspace_id): return self.request("GET", f"/v1/workspaces/{self.segment(workspace_id)}")
    def resource(self, workspace_id, path):
        parts = "/".join(quote(part, safe="") for part in path.split("/"))
        return self.request("GET", f"/v1/workspaces/{self.segment(workspace_id)}/resources/{parts}")
    def session_resource(self, session_id, path):
        parts = "/".join(quote(part, safe="") for part in path.split("/"))
        return self.request("GET", f"/v1/sessions/{self.segment(session_id)}/resources/{parts}")
    def search(self, workspace_id, query):
        return self.request("GET", f"/v1/workspaces/{self.segment(workspace_id)}/search?q={quote(query, safe='')}").get("results", [])
    def changesets(self, workspace_id):
        return self.request("GET", f"/v1/workspaces/{self.segment(workspace_id)}/changesets").get("changesets", [])
    def subscribe_document(self, workspace_id, path, after_id=None):
        payload={"path":path}
        if after_id is not None: payload["after_id"]=after_id
        return self.request("POST",f"/v1/workspaces/{self.segment(workspace_id)}/subscriptions",payload)
    def subscriptions(self, workspace_id):
        return self.request("GET",f"/v1/workspaces/{self.segment(workspace_id)}/subscriptions").get("subscriptions",[])
    def poll_subscription(self, workspace_id, subscription_id, limit=100):
        return self.request("GET",f"/v1/workspaces/{self.segment(workspace_id)}/subscriptions/{self.segment(subscription_id)}/events?limit={int(limit)}")
    def unsubscribe_document(self, workspace_id, subscription_id):
        return self.request("DELETE",f"/v1/workspaces/{self.segment(workspace_id)}/subscriptions/{self.segment(subscription_id)}")
    def session_history(self, session_id):
        return self.request("GET", f"/v1/sessions/{self.segment(session_id)}/history").get("events", [])
    def start_session(self, workspace_id, agent="cli"):
        return self.request("POST", f"/v1/workspaces/{self.segment(workspace_id)}/sessions", {"agent": agent})
    def session_call(self, session_id, name, arguments=None):
        return self.request("POST", f"/v1/sessions/{self.segment(session_id)}/tools/{self.segment(name)}", {"arguments": arguments or {}})
