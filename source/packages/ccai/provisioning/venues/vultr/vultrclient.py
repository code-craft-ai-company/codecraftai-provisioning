"""
    .. module:: vultrclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Thin REST client wrapping the Vultr v2 API surface.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

import requests

from ccai.provisioning.venues.vultr.vultrerrors import VultrApiError


VULTR_API_BASE = "https://api.vultr.com/v2"


class VultrClient:
    """
        Minimal REST client for the Vultr v2 API.

        The Vultr API exposes a clean REST surface so the venue talks to it
        directly with ``requests`` and Bearer authentication.  This client is
        intentionally thin: it performs HTTP, raises :class:`VultrApiError`
        for non-2xx responses, and transparently follows the cursor-based
        paging used by Vultr list endpoints.
    """

    def __init__(self, *, token: str,
                 base_url: str = VULTR_API_BASE,
                 session: Optional[Any] = None) -> None:
        """
            Construct a VultrClient.

            :param token: The Vultr API key (Bearer credential).
            :param base_url: The API base URL (overridable for tests).
            :param session: Optional pre-built ``requests.Session``.
        """
        self._token: str = token
        self._base_url: str = base_url.rstrip("/")
        if session is not None:
            self._session: Any = session
        else:
            self._session = requests.Session()
        return

    @property
    def base_url(self) -> str:
        """
            Return the API base URL.

            :returns: The base URL string.
        """
        rtnval = self._base_url
        return rtnval

    def _headers(self) -> Dict[str, str]:
        """
            Build the request headers with Bearer authentication.

            :returns: A header dict.
        """
        rtnval = {
            "Authorization": "Bearer {}".format(self._token),
            "Content-Type": "application/json",
        }
        return rtnval

    def _request(self, *, method: str, path: str,
                 params: Optional[Dict[str, Any]] = None,
                 json_body: Optional[Dict[str, Any]] = None
                 ) -> Dict[str, Any]:
        """
            Perform an HTTP request against the Vultr API.

            :param method: HTTP verb.
            :param path: API path beginning with ``/``.
            :param params: Optional query parameters.
            :param json_body: Optional JSON request body.

            :returns: The parsed JSON response (empty dict on 204).
            :raises: VultrApiError
        """
        url = "{}{}".format(self._base_url, path)
        response = self._session.request(
            method=method, url=url, headers=self._headers(),
            params=params, json=json_body, timeout=60.0,
        )
        status = response.status_code
        if status < 200 or status >= 300:
            err_msg_lines = ["Vultr API call returned a failure status."]
            err_msg_lines.append("METHOD: {}".format(method))
            err_msg_lines.append("URL: {}".format(url))
            err_msg_lines.append("STATUS: {}".format(status))
            err_msg_lines.append("BODY: {}".format(response.text))
            err_msg = os.linesep.join(err_msg_lines)
            raise VultrApiError(err_msg)

        if status == 204 or len(response.content) == 0:
            rtnval: Dict[str, Any] = {}
            return rtnval

        rtnval = response.json()
        return rtnval

    def get(self, *, path: str,
            params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
            Perform a GET request.

            :param path: API path.
            :param params: Optional query parameters.

            :returns: The parsed JSON response.
        """
        rtnval = self._request(method="GET", path=path, params=params)
        return rtnval

    def post(self, *, path: str,
             json_body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
            Perform a POST request.

            :param path: API path.
            :param json_body: Optional JSON request body.

            :returns: The parsed JSON response.
        """
        rtnval = self._request(method="POST", path=path,
                               json_body=json_body)
        return rtnval

    def delete(self, *, path: str) -> Dict[str, Any]:
        """
            Perform a DELETE request.

            :param path: API path.

            :returns: The parsed JSON response (empty on 204).
        """
        rtnval = self._request(method="DELETE", path=path)
        return rtnval

    def list_all(self, *, path: str, collection_key: str,
                 params: Optional[Dict[str, Any]] = None
                 ) -> List[Dict[str, Any]]:
        """
            Page through a Vultr list endpoint and return every entry.

            Vultr list responses carry a ``meta.links.next`` cursor; this
            helper follows it until exhausted.

            :param path: API list path (e.g. ``/instances``).
            :param collection_key: Top-level key holding the list of items.
            :param params: Optional query parameters (e.g. tag filter).

            :returns: A flat list of item dicts.
        """
        out: List[Dict[str, Any]] = []
        effective_params: Dict[str, Any] = {}
        if params is not None:
            for key, value in params.items():
                effective_params[key] = value

        cursor: Optional[str] = None
        while True:
            if cursor is not None and len(cursor) > 0:
                effective_params["cursor"] = cursor
            response = self.get(path=path, params=effective_params)
            items = response.get(collection_key, [])
            for item in items:
                out.append(item)

            meta = response.get("meta", {})
            links = meta.get("links", {}) if isinstance(meta, dict) else {}
            next_cursor = links.get("next", "") if isinstance(links, dict) else ""
            if next_cursor is None or len(next_cursor) == 0:
                break
            cursor = next_cursor

        rtnval = out
        return rtnval
