"""
    .. module:: test_metalclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for MetalClient's transport behaviour.

    The venue's other tests inject a fully-mocked MetalClient, which means the
    real request building, pagination and error classification would otherwise
    have no coverage at all.  These tests drive the client through a fake
    session so those paths are really exercised.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase


import json

from typing import Any, Dict, List, Optional


from ccai.provisioning.venues.equinix_metal.metalclient import MetalClient
from ccai.provisioning.venues.equinix_metal.metalerrors import (
    MetalApiRequestError, MetalConflictError
)


PROJECT_ID = "proj-123"


class _FakeResponse:
    """
        Minimal stand-in for a ``requests.Response``.
    """

    def __init__(self, *, status_code: int = 200,
                 payload: Optional[Any] = None, text: Optional[str] = None,
                 reason: str = "OK") -> None:
        self.status_code = status_code
        self.reason = reason
        if text is not None:
            self.text = text
        elif payload is not None:
            self.text = json.dumps(payload)
        else:
            self.text = ""
        self._payload = payload

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("no json body")
        return self._payload


class _FakeSession:
    """
        Records requests and replays queued responses.
    """

    def __init__(self) -> None:
        self.headers: Dict[str, str] = {}
        self.calls: List[Dict[str, Any]] = []
        self.responses: Dict[str, List[_FakeResponse]] = {}
        self.default_response = _FakeResponse(payload={})

    def queue(self, *, method: str, path: str,
              response: _FakeResponse) -> None:
        key = "{} {}".format(method.upper(), path)
        self.responses.setdefault(key, []).append(response)
        return

    def queue_page(self, *, path: str, collection_key: str, entries,
                   has_next: bool = False) -> None:
        following = None
        if has_next is True:
            following = {"href": "/next"}
        payload = {collection_key: entries,
                   "meta": {"total": len(entries), "next": following}}
        self.queue(method="GET", path=path,
                   response=_FakeResponse(payload=payload))
        return

    def request(self, method: str, url: str, params=None, data=None,
                headers=None, timeout=None) -> _FakeResponse:
        body = None
        if data is not None:
            body = json.loads(data)

        self.calls.append({"method": method, "url": url,
                           "params": params or {}, "body": body,
                           "timeout": timeout})

        for key, queued in self.responses.items():
            wanted_method, _, wanted_path = key.partition(" ")
            if method.upper() == wanted_method and url.endswith(wanted_path):
                if len(queued) > 0:
                    rtnval = queued.pop(0)
                    return rtnval

        rtnval = self.default_response
        return rtnval


def _build_client():
    """
        Build a MetalClient over a fake session.

        :returns: A ``(client, session)`` pair.
    """
    session = _FakeSession()
    client = MetalClient(api_token="tok-abc", project_id=PROJECT_ID,
                         session=session)
    return client, session


# ----------------------------------------------------------------------
# construction
# ----------------------------------------------------------------------

def test_client_sends_the_auth_token_header():
    client, session = _build_client()

    assert session.headers["X-Auth-Token"] == "tok-abc"
    assert session.headers["Accept"] == "application/json"
    return


def test_client_exposes_its_project_id():
    client, session = _build_client()

    assert client.project_id == PROJECT_ID
    return


@testbase.parametrize("token,project", [
    ("", PROJECT_ID),
    ("tok-abc", ""),
])
def test_client_refuses_empty_credentials(token, project):
    with testbase.raises(MetalConflictError):
        MetalClient(api_token=token, project_id=project,
                    session=_FakeSession())
    return


# ----------------------------------------------------------------------
# error classification
# ----------------------------------------------------------------------

def test_error_reason_comes_from_the_errors_array():
    client, session = _build_client()
    session.queue(method="GET", path="/devices/dev-1",
                  response=_FakeResponse(
                      status_code=422, reason="Unprocessable",
                      payload={"errors": ["plan unavailable",
                                          "metro invalid"]}))

    with testbase.raises(MetalApiRequestError) as caught:
        client.get_device(device_id="dev-1")

    assert caught.value.status == 422
    assert caught.value.reason == "plan unavailable; metro invalid"
    return


def test_error_reason_comes_from_a_single_error_field():
    client, session = _build_client()
    session.queue(method="GET", path="/devices/dev-1",
                  response=_FakeResponse(
                      status_code=404, reason="Not Found",
                      payload={"error": "Not found"}))

    with testbase.raises(MetalApiRequestError) as caught:
        client.get_device(device_id="dev-1")

    assert caught.value.reason == "Not found"
    return


def test_error_falls_back_to_the_http_reason():
    client, session = _build_client()
    session.queue(method="GET", path="/devices/dev-1",
                  response=_FakeResponse(status_code=500,
                                         reason="Server Error",
                                         text="upstream failure"))

    with testbase.raises(MetalApiRequestError) as caught:
        client.get_device(device_id="dev-1")

    assert caught.value.reason == "Server Error"
    assert caught.value.body == "upstream failure"
    return


# ----------------------------------------------------------------------
# pagination
# ----------------------------------------------------------------------

def test_list_devices_walks_every_page():
    client, session = _build_client()
    path = "/projects/{}/devices".format(PROJECT_ID)
    session.queue_page(path=path, collection_key="devices",
                       entries=[{"id": "d1"}], has_next=True)
    session.queue_page(path=path, collection_key="devices",
                       entries=[{"id": "d2"}], has_next=True)
    session.queue_page(path=path, collection_key="devices",
                       entries=[{"id": "d3"}], has_next=False)

    devices = client.list_devices()

    # A truncated listing under-reports owned resources, which on a teardown
    # path means leaked infrastructure.
    assert [entry["id"] for entry in devices] == ["d1", "d2", "d3"]
    assert len(session.calls) == 3
    assert session.calls[2]["params"]["page"] == 3
    return


def test_list_returns_empty_when_the_collection_is_absent():
    client, session = _build_client()

    assert client.list_devices() == []
    return


@testbase.parametrize("method_name,collection,collection_key", [
    ("list_vlans", "virtual-networks", "virtual_networks"),
    ("list_ip_reservations", "ips", "ip_addresses"),
    ("list_ssh_keys", "ssh-keys", "ssh_keys"),
    ("list_devices", "devices", "devices"),
])
def test_list_endpoints_are_project_scoped(method_name, collection,
                                           collection_key):
    client, session = _build_client()
    path = "/projects/{}/{}".format(PROJECT_ID, collection)
    session.queue_page(path=path, collection_key=collection_key,
                       entries=[{"id": "x"}])

    found = getattr(client, method_name)()

    assert len(found) == 1
    assert session.calls[0]["url"].endswith(path)
    return


# ----------------------------------------------------------------------
# creates
# ----------------------------------------------------------------------

def test_create_vlan_posts_to_the_project_collection():
    client, session = _build_client()

    client.create_vlan(metro="da", description="net-a", tags=["owner=ccai"])

    call = session.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith(
        "/projects/{}/virtual-networks".format(PROJECT_ID))
    assert call["body"] == {"metro": "da", "description": "net-a",
                            "tags": ["owner=ccai"]}
    return


def test_create_ip_reservation_sends_ip_type_as_type():
    client, session = _build_client()

    client.create_ip_reservation(metro="da", quantity=2,
                                 ip_type="public_ipv4", tags=["t"])

    # The wire field is 'type'; the parameter stays 'ip_type' because that is
    # what the venue passes.
    body = session.calls[0]["body"]
    assert body["type"] == "public_ipv4"
    assert "ip_type" not in body
    assert body["quantity"] == 2
    return


def test_create_ssh_key_posts_label_and_key():
    client, session = _build_client()

    client.create_ssh_key(label="key-a", key="ssh-ed25519 AAA")

    call = session.calls[0]
    assert call["url"].endswith("/projects/{}/ssh-keys".format(PROJECT_ID))
    assert call["body"] == {"label": "key-a", "key": "ssh-ed25519 AAA"}
    return


def test_create_device_posts_the_full_body():
    client, session = _build_client()
    session.queue(method="POST",
                  path="/projects/{}/devices".format(PROJECT_ID),
                  response=_FakeResponse(status_code=201,
                                         payload={"id": "d1",
                                                  "hostname": "srv-a"}))

    created = client.create_device(
        hostname="srv-a", plan="m3.small.x86", metro="da",
        operating_system="ubuntu_24_04", userdata="#cloud-config",
        project_ssh_keys=["k1"], tags=["owner=ccai"])

    assert created["id"] == "d1"
    body = session.calls[0]["body"]
    assert body["hostname"] == "srv-a"
    assert body["plan"] == "m3.small.x86"
    assert body["operating_system"] == "ubuntu_24_04"
    assert body["project_ssh_keys"] == ["k1"]
    return


def test_create_returns_the_decoded_resource_dict():
    client, session = _build_client()
    session.queue(method="POST",
                  path="/projects/{}/virtual-networks".format(PROJECT_ID),
                  response=_FakeResponse(status_code=201,
                                         payload={"id": "v1", "vxlan": 1001}))

    created = client.create_vlan(metro="da", description="n", tags=[])

    assert created == {"id": "v1", "vxlan": 1001}
    return


# ----------------------------------------------------------------------
# reads, updates and deletes
# ----------------------------------------------------------------------

def test_get_device_reads_the_item_path():
    client, session = _build_client()
    session.queue(method="GET", path="/devices/d1",
                  response=_FakeResponse(payload={"id": "d1",
                                                  "state": "active"}))

    device = client.get_device(device_id="d1")

    assert device["state"] == "active"
    return


def test_update_device_tags_puts_only_the_tag_list():
    client, session = _build_client()
    session.queue(method="PUT", path="/devices/d1",
                  response=_FakeResponse(payload={"id": "d1",
                                                  "tags": ["b"]}))

    updated = client.update_device_tags(device_id="d1", tags=["b"])

    call = session.calls[0]
    assert call["method"] == "PUT"
    assert call["body"] == {"tags": ["b"]}
    assert updated["tags"] == ["b"]
    return


@testbase.parametrize("method_name,kwarg,path", [
    ("delete_vlan", "vlan_id", "/virtual-networks/x1"),
    ("delete_ip_reservation", "reservation_id", "/ips/x1"),
    ("delete_ssh_key", "ssh_key_id", "/ssh-keys/x1"),
    ("delete_device", "device_id", "/devices/x1"),
])
def test_delete_endpoints_are_not_project_scoped(method_name, kwarg, path):
    client, session = _build_client()
    session.queue(method="DELETE", path=path,
                  response=_FakeResponse(status_code=204, text=""))

    getattr(client, method_name)(**{kwarg: "x1"})

    call = session.calls[0]
    assert call["method"] == "DELETE"
    # Deletes address the resource directly, not through the project.
    assert call["url"].endswith(path)
    return


def test_delete_tolerates_a_bodiless_response():
    client, session = _build_client()
    session.queue(method="DELETE", path="/devices/d1",
                  response=_FakeResponse(status_code=204, text=""))

    assert client.delete_device(device_id="d1") is None
    return
