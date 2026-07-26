"""
    .. module:: metalclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MetalClient — a pure-Python client for the Equinix Metal API
               v1, used directly by the venue.

    The Equinix Metal API is plain REST over HTTPS with JSON bodies and an
    ``X-Auth-Token`` header, so this client speaks it directly rather than
    depending on the ``packet-python`` SDK.

    Unlike the other migrated venues, this client stays inside the venue
    rather than moving to a ``codecraftai-restclient-*`` package.  That is
    deliberate and preserves the existing decision recorded here: the surface
    is fourteen flat, project-scoped methods returning plain JSON-shaped
    dicts, used by exactly one venue.  There is no object model or api-group
    structure to share, so a separate package would add ceremony without
    giving anything back.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import json
import os

from typing import Any, Dict, List, Optional

import requests

from ccai.provisioning.venues.equinix_metal.metalerrors import (
    MetalApiRequestError, MetalConflictError
)


METAL_API_BASE = "https://api.equinix.com/metal/v1"

DEFAULT_TIMEOUT_SECONDS = 60.0

# The API accepts up to 1000 entries per page; asking for a large page
# minimises the number of round trips when walking a collection.
MAX_PAGE_SIZE = 1000


class MetalClient:
    """
        Client for the Equinix Metal API v1, scoped to one project.

        The method surface is project-scoped and returns plain JSON-shaped
        dicts so the rest of the venue stays transport-agnostic.  Each list
        endpoint returns ``[]`` when nothing is found; create endpoints return
        the created resource dict.

        Tests inject either a fully-mocked instance (the venue's own tests) or
        a fake ``session`` (this module's tests).
    """

    def __init__(self, *, api_token: str, project_id: str,
                 base_url: str = METAL_API_BASE,
                 session: Optional[Any] = None,
                 timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        """
            Construct a MetalClient.

            :param api_token: The Equinix Metal API token.
            :param project_id: The Equinix Metal project id.
            :param base_url: The API base URL.
            :param session: Optional pre-built ``requests.Session`` — the test
                seam and the way a caller supplies custom transport adapters
                or proxies.
            :param timeout_seconds: The default per-request timeout.
        """
        if api_token is None or len(api_token) == 0:
            err_msg = "MetalClient requires a non-empty api_token."
            raise MetalConflictError(err_msg)

        if project_id is None or len(project_id) == 0:
            err_msg = "MetalClient requires a non-empty project_id."
            raise MetalConflictError(err_msg)

        self._api_token: str = api_token
        self._project_id: str = project_id
        self._base_url: str = base_url.rstrip("/")
        self._timeout_seconds: float = timeout_seconds

        if session is not None:
            self._session = session
        else:
            self._session = requests.Session()

        self._session.headers.update({
            "X-Auth-Token": api_token,
            "Accept": "application/json",
        })
        return

    @property
    def project_id(self) -> str:
        """
            Return the project id this client is scoped to.

            :returns: The project id string.
        """
        rtnval = self._project_id
        return rtnval

    # ------------------------------------------------------------------
    # transport
    # ------------------------------------------------------------------

    def _request(self, *, method: str, path: str,
                 params: Optional[Dict[str, Any]] = None,
                 body: Optional[Dict[str, Any]] = None
                 ) -> Dict[str, Any]:
        """
            Perform one API request and return the decoded body.

            :param method: The HTTP method.
            :param path: The API path, beginning with ``/``.
            :param params: Optional query parameters; ``None`` values are
                dropped.
            :param body: Optional JSON request body.

            :returns: The decoded response, or ``{}`` when the response
                carries no body (deletes answer ``204``).

            :raises: :class:`MetalApiRequestError` on a non-success status.
        """
        url = "{}{}".format(self._base_url, path)

        query: Dict[str, Any] = {}
        if params is not None:
            for key, value in params.items():
                if value is not None:
                    query[key] = value

        headers: Dict[str, str] = {}
        payload = None
        if body is not None:
            payload = json.dumps(body)
            headers["Content-Type"] = "application/json"

        response = self._session.request(method, url, params=query,
                                         data=payload, headers=headers,
                                         timeout=self._timeout_seconds)

        status = getattr(response, "status_code", 0)

        if status < 200 or status >= 300:
            text = getattr(response, "text", "")
            reason = self._extract_error_reason(
                response=response, fallback=getattr(response, "reason", ""))
            err_msg_lines = ["The Equinix Metal API request failed."]
            err_msg_lines.append("METHOD: {}".format(method))
            err_msg_lines.append("PATH: {}".format(path))
            err_msg_lines.append("STATUS: {}".format(status))
            err_msg_lines.append("REASON: {}".format(reason))
            err_msg = os.linesep.join(err_msg_lines)
            raise MetalApiRequestError(err_msg, status=status, reason=reason,
                                       body=text)

        text = getattr(response, "text", "")
        if text is None or len(text.strip()) == 0:
            rtnval: Dict[str, Any] = {}
            return rtnval

        try:
            decoded = response.json()
        except Exception:
            rtnval = {}
            return rtnval

        if isinstance(decoded, dict) is False:
            rtnval = {"data": decoded}
            return rtnval

        rtnval = decoded
        return rtnval

    def _extract_error_reason(self, *, response: Any,
                              fallback: str) -> str:
        """
            Pull a human-readable reason out of a Metal error body.

            The API reports a single failure as ``{"error": ...}`` and a
            validation failure as ``{"errors": [...]}``; either is far more
            useful than the bare HTTP phrase.

            :param response: The failed response.
            :param fallback: The reason to use when the body is unhelpful.

            :returns: The extracted reason.
        """
        try:
            decoded = response.json()
        except Exception:
            rtnval = fallback
            return rtnval

        if isinstance(decoded, dict) is False:
            rtnval = fallback
            return rtnval

        errors = decoded.get("errors", None)
        if errors is not None and len(errors) > 0:
            rtnval = "; ".join([str(entry) for entry in errors])
            return rtnval

        single = decoded.get("error", None)
        if single is not None:
            rtnval = str(single)
            return rtnval

        rtnval = fallback
        return rtnval

    def _paginate(self, *, path: str,
                  collection_key: str) -> List[Dict[str, Any]]:
        """
            Walk every page of a collection and return the concatenated
            entries.

            The API paginates with ``page`` / ``per_page`` and reports whether
            more remains via ``meta.next``.  Callers listing a collection
            expect ALL of it — a silently truncated first page would
            under-report owned resources, which on a teardown path means
            leaked infrastructure.

            :param path: The collection path.
            :param collection_key: The key the entries arrive under.

            :returns: The concatenated entries from every page.
        """
        collected: List[Dict[str, Any]] = []

        page_number = 1
        while True:
            payload = self._request(method="GET", path=path,
                                    params={"page": page_number,
                                            "per_page": MAX_PAGE_SIZE})

            entries = payload.get(collection_key, None)
            if entries is None:
                break
            collected.extend(entries)

            if self._has_next_page(payload=payload) is False:
                break
            page_number = page_number + 1

        rtnval = collected
        return rtnval

    def _has_next_page(self, *, payload: Dict[str, Any]) -> bool:
        """
            Report whether a paginated response has a following page.

            :param payload: The decoded response body.

            :returns: True when ``meta.next`` names another page.
        """
        meta = payload.get("meta", None)
        if isinstance(meta, dict) is False:
            rtnval = False
            return rtnval

        following = meta.get("next", None)
        if following is None:
            rtnval = False
            return rtnval

        rtnval = True
        return rtnval

    def _project_path(self, *, collection: str) -> str:
        """
            Build a project-scoped collection path.

            :param collection: The collection segment, e.g. ``devices``.

            :returns: The project-scoped path.
        """
        rtnval = "/projects/{}/{}".format(self._project_id, collection)
        return rtnval

    # ------------------------------------------------------------------
    # VLAN / virtual-network endpoints
    # ------------------------------------------------------------------

    def list_vlans(self) -> List[Dict[str, Any]]:
        """
            List the project's VLANs (virtual networks).

            :returns: A list of VLAN dicts.
        """
        rtnval = self._paginate(
            path=self._project_path(collection="virtual-networks"),
            collection_key="virtual_networks")
        return rtnval

    def create_vlan(self, *, metro: str, description: str,
                    tags: List[str]) -> Dict[str, Any]:
        """
            Create a project VLAN.

            :param metro: Metro slug to create the VLAN in.
            :param description: Human-readable description / name.
            :param tags: Tag string list (ownership marker).

            :returns: The created VLAN dict.
        """
        rtnval = self._request(
            method="POST",
            path=self._project_path(collection="virtual-networks"),
            body={"metro": metro, "description": description, "tags": tags})
        return rtnval

    def delete_vlan(self, *, vlan_id: str) -> None:
        """
            Delete a project VLAN.

            :param vlan_id: The VLAN id.
        """
        self._request(method="DELETE",
                      path="/virtual-networks/{}".format(vlan_id))
        return

    # ------------------------------------------------------------------
    # IP reservation endpoints
    # ------------------------------------------------------------------

    def list_ip_reservations(self) -> List[Dict[str, Any]]:
        """
            List the project's IP reservations.

            :returns: A list of IP-reservation dicts.
        """
        rtnval = self._paginate(path=self._project_path(collection="ips"),
                                collection_key="ip_addresses")
        return rtnval

    def create_ip_reservation(self, *, metro: str, quantity: int,
                              ip_type: str,
                              tags: List[str]) -> Dict[str, Any]:
        """
            Create an IP reservation.

            The wire field is ``type``; the parameter stays ``ip_type``
            because that is what the venue already passes.

            :param metro: Metro slug.
            :param quantity: Number of addresses to reserve.
            :param ip_type: ``public_ipv4`` or ``private_ipv4``.
            :param tags: Tag string list.

            :returns: The created IP-reservation dict.
        """
        rtnval = self._request(
            method="POST", path=self._project_path(collection="ips"),
            body={"metro": metro, "quantity": quantity, "type": ip_type,
                  "tags": tags})
        return rtnval

    def delete_ip_reservation(self, *, reservation_id: str) -> None:
        """
            Delete an IP reservation.

            :param reservation_id: The reservation id.
        """
        self._request(method="DELETE",
                      path="/ips/{}".format(reservation_id))
        return

    # ------------------------------------------------------------------
    # SSH-key endpoints (project-level)
    # ------------------------------------------------------------------

    def list_ssh_keys(self) -> List[Dict[str, Any]]:
        """
            List the project's SSH keys.

            :returns: A list of SSH-key dicts.
        """
        rtnval = self._paginate(
            path=self._project_path(collection="ssh-keys"),
            collection_key="ssh_keys")
        return rtnval

    def create_ssh_key(self, *, label: str, key: str) -> Dict[str, Any]:
        """
            Create a project SSH key.

            :param label: The SSH-key label.
            :param key: The OpenSSH public-key material.

            :returns: The created SSH-key dict.
        """
        rtnval = self._request(
            method="POST",
            path=self._project_path(collection="ssh-keys"),
            body={"label": label, "key": key})
        return rtnval

    def delete_ssh_key(self, *, ssh_key_id: str) -> None:
        """
            Delete a project SSH key.

            :param ssh_key_id: The SSH-key id.
        """
        self._request(method="DELETE",
                      path="/ssh-keys/{}".format(ssh_key_id))
        return

    # ------------------------------------------------------------------
    # Device endpoints
    # ------------------------------------------------------------------

    def list_devices(self) -> List[Dict[str, Any]]:
        """
            List the project's devices (bare-metal servers).

            :returns: A list of device dicts.
        """
        rtnval = self._paginate(
            path=self._project_path(collection="devices"),
            collection_key="devices")
        return rtnval

    def get_device(self, *, device_id: str) -> Dict[str, Any]:
        """
            Get a single device by id.

            :param device_id: The device id.

            :returns: The device dict.
        """
        rtnval = self._request(method="GET",
                               path="/devices/{}".format(device_id))
        return rtnval

    def create_device(self, *, hostname: str, plan: str, metro: str,
                      operating_system: str, userdata: str,
                      project_ssh_keys: List[str],
                      tags: List[str]) -> Dict[str, Any]:
        """
            Create a device (a bare-metal server).

            :param hostname: Device hostname.
            :param plan: Equinix Metal plan slug.
            :param metro: Metro slug.
            :param operating_system: OS slug.
            :param userdata: Cloud-init userdata body.
            :param project_ssh_keys: Project SSH-key ids to install.
            :param tags: Tag string list.

            :returns: The created device dict.
        """
        rtnval = self._request(
            method="POST",
            path=self._project_path(collection="devices"),
            body={"hostname": hostname, "plan": plan, "metro": metro,
                  "operating_system": operating_system, "userdata": userdata,
                  "project_ssh_keys": project_ssh_keys, "tags": tags})
        return rtnval

    def update_device_tags(self, *, device_id: str,
                           tags: List[str]) -> Dict[str, Any]:
        """
            Update the tag string list on an existing device in place.

            Equinix Metal device tags are mutable; the Metal API realises a
            tag change with ``PUT /devices/{id}`` carrying a new ``tags``
            list, with no reprovisioning of the bare-metal server.

            :param device_id: The device id.
            :param tags: The replacement tag string list.

            :returns: The updated device dict.
        """
        rtnval = self._request(method="PUT",
                               path="/devices/{}".format(device_id),
                               body={"tags": tags})
        return rtnval

    def delete_device(self, *, device_id: str) -> None:
        """
            Delete a device.

            :param device_id: The device id.
        """
        self._request(method="DELETE",
                      path="/devices/{}".format(device_id))
        return
