"""
    .. module:: _fakevultr
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: In-memory stateful fake Vultr v2 API backed by requests-mock.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import json
import re

from typing import Any, Dict, List

from urllib.parse import parse_qs, urlparse


_OS_CATALOG = [
    {"id": 1743, "name": "Ubuntu 22.04 LTS x64", "arch": "x64",
     "family": "ubuntu"},
    {"id": 2104, "name": "Debian 12 x64 (bookworm)", "arch": "x64",
     "family": "debian"},
]

_REGION_CATALOG = [
    {"id": "ewr", "city": "New Jersey", "country": "US"},
    {"id": "ord", "city": "Chicago", "country": "US"},
]


class FakeVultrApi:
    """
        Stateful in-memory model of the Vultr v2 API surface.

        Registered against a ``requests_mock`` adapter, this fake records
        created resources and answers list / get / delete calls so the venue
        provisioner exercises a realistic create-read-destroy cycle without
        ever calling the real Vultr API.
    """

    def __init__(self) -> None:
        """
            Construct an empty FakeVultrApi.
        """
        self.vpcs: List[Dict[str, Any]] = []
        self.firewall_groups: List[Dict[str, Any]] = []
        self.firewall_rules: Dict[str, List[Dict[str, Any]]] = {}
        self.ssh_keys: List[Dict[str, Any]] = []
        self.instances: List[Dict[str, Any]] = []
        self.blocks: List[Dict[str, Any]] = []
        self.object_storages: List[Dict[str, Any]] = []
        self.domain_records: Dict[str, List[Dict[str, Any]]] = {}
        self._counter: int = 0
        return

    def _next_id(self, *, prefix: str) -> str:
        """
            Return a deterministic monotonically-increasing id.

            :param prefix: An id prefix.

            :returns: A unique id string.
        """
        self._counter = self._counter + 1
        rtnval = "{}-{:04d}".format(prefix, self._counter)
        return rtnval

    def install(self, *, adapter: Any, base_url: str) -> None:
        """
            Register every endpoint matcher against a requests-mock adapter.

            :param adapter: A ``requests_mock.Mocker`` instance.
            :param base_url: The API base URL.
        """
        pattern = re.compile(re.escape(base_url) + r"/.*")
        adapter.register_uri("GET", pattern, json=self._handle_get)
        adapter.register_uri("POST", pattern, json=self._handle_post)
        adapter.register_uri("DELETE", pattern, json=self._handle_delete)
        return

    # ------------------------------------------------------------------
    # Request handlers
    # ------------------------------------------------------------------

    def _handle_get(self, request: Any, context: Any) -> Dict[str, Any]:
        """
            Dispatch a GET request.

            :param request: The requests-mock request.
            :param context: The requests-mock response context.

            :returns: A JSON-serialisable response dict.
        """
        path = urlparse(request.url).path
        path = path.split("/v2", 1)[1] if "/v2" in path else path

        if path == "/os":
            return {"os": list(_OS_CATALOG), "meta": {}}
        if path == "/regions":
            return {"regions": list(_REGION_CATALOG), "meta": {}}
        if path == "/vpc2":
            return {"vpcs": list(self.vpcs), "meta": {}}
        if path == "/firewalls":
            return {"firewall_groups": list(self.firewall_groups),
                    "meta": {}}
        if path == "/ssh-keys":
            return {"ssh_keys": list(self.ssh_keys), "meta": {}}
        if path == "/instances":
            return {"instances": list(self.instances), "meta": {}}
        if path == "/blocks":
            return {"blocks": list(self.blocks), "meta": {}}
        if path == "/object-storage":
            return {"object_storages": list(self.object_storages),
                    "meta": {}}

        records_match = re.match(r"^/domains/([^/]+)/records$", path)
        if records_match is not None:
            zone = records_match.group(1)
            return {"records": list(self.domain_records.get(zone, [])),
                    "meta": {}}

        context.status_code = 404
        return {"error": "unknown path {}".format(path)}

    def _handle_post(self, request: Any, context: Any) -> Dict[str, Any]:
        """
            Dispatch a POST request.

            :param request: The requests-mock request.
            :param context: The requests-mock response context.

            :returns: A JSON-serialisable response dict.
        """
        path = urlparse(request.url).path
        path = path.split("/v2", 1)[1] if "/v2" in path else path
        body = json.loads(request.body) if request.body else {}
        context.status_code = 201

        if path == "/vpc2":
            entry = {
                "id": self._next_id(prefix="vpc"),
                "region": body.get("region", ""),
                "description": body.get("description", ""),
                "v4_subnet": body.get("v4_subnet", ""),
                "v4_subnet_mask": body.get("v4_subnet_mask", 0),
                "tags": body.get("tags", []),
            }
            self.vpcs.append(entry)
            return {"vpc": entry}

        if path == "/firewalls":
            entry = {
                "id": self._next_id(prefix="fw"),
                "description": body.get("description", ""),
            }
            self.firewall_groups.append(entry)
            self.firewall_rules[entry["id"]] = []
            return {"firewall_group": entry}

        rule_match = re.match(r"^/firewalls/([^/]+)/rules$", path)
        if rule_match is not None:
            group_id = rule_match.group(1)
            rule = dict(body)
            rule["id"] = self._counter + 1
            self._counter = self._counter + 1
            self.firewall_rules.setdefault(group_id, []).append(rule)
            return {"firewall_rule": rule}

        if path == "/ssh-keys":
            entry = {
                "id": self._next_id(prefix="ssh"),
                "name": body.get("name", ""),
                "ssh_key": body.get("ssh_key", ""),
            }
            self.ssh_keys.append(entry)
            return {"ssh_key": entry}

        if path == "/instances":
            entry = {
                "id": self._next_id(prefix="inst"),
                "label": body.get("label", ""),
                "region": body.get("region", ""),
                "plan": body.get("plan", ""),
                "os_id": body.get("os_id", 0),
                "main_ip": "192.0.2.10",
                "tags": body.get("tags", []),
                "user_data": body.get("user_data", ""),
            }
            self.instances.append(entry)
            return {"instance": entry}

        if path == "/blocks":
            entry = {
                "id": self._next_id(prefix="blk"),
                "label": body.get("label", ""),
                "region": body.get("region", ""),
                "size_gb": body.get("size_gb", 0),
                "attached_to_instance": "",
            }
            self.blocks.append(entry)
            return {"block": entry}

        attach_match = re.match(r"^/blocks/([^/]+)/attach$", path)
        if attach_match is not None:
            block_id = attach_match.group(1)
            for block in self.blocks:
                if block["id"] == block_id:
                    block["attached_to_instance"] = body.get(
                        "instance_id", ""
                    )
            context.status_code = 204
            return {}

        detach_match = re.match(r"^/blocks/([^/]+)/detach$", path)
        if detach_match is not None:
            block_id = detach_match.group(1)
            for block in self.blocks:
                if block["id"] == block_id:
                    block["attached_to_instance"] = ""
            context.status_code = 204
            return {}

        if path == "/object-storage":
            entry = {
                "id": self._next_id(prefix="obj"),
                "label": body.get("label", ""),
                "cluster_id": body.get("cluster_id", 0),
            }
            self.object_storages.append(entry)
            return {"object_storage": entry}

        records_match = re.match(r"^/domains/([^/]+)/records$", path)
        if records_match is not None:
            zone = records_match.group(1)
            entry = {
                "id": self._next_id(prefix="rec"),
                "name": body.get("name", ""),
                "type": body.get("type", ""),
                "data": body.get("data", ""),
                "ttl": body.get("ttl", 300),
            }
            self.domain_records.setdefault(zone, []).append(entry)
            return {"record": entry}

        context.status_code = 404
        return {"error": "unknown post path {}".format(path)}

    def _handle_delete(self, request: Any, context: Any) -> Dict[str, Any]:
        """
            Dispatch a DELETE request.

            :param request: The requests-mock request.
            :param context: The requests-mock response context.

            :returns: An empty dict.
        """
        path = urlparse(request.url).path
        path = path.split("/v2", 1)[1] if "/v2" in path else path
        context.status_code = 204

        collections = {
            "vpc2": self.vpcs,
            "firewalls": self.firewall_groups,
            "ssh-keys": self.ssh_keys,
            "instances": self.instances,
            "blocks": self.blocks,
            "object-storage": self.object_storages,
        }
        simple_match = re.match(r"^/([^/]+)/([^/]+)$", path)
        if simple_match is not None:
            collection_name = simple_match.group(1)
            entry_id = simple_match.group(2)
            if collection_name in collections:
                target = collections[collection_name]
                remaining = [e for e in target if e.get("id") != entry_id]
                target[:] = remaining
                return {}

        record_match = re.match(r"^/domains/([^/]+)/records/([^/]+)$", path)
        if record_match is not None:
            zone = record_match.group(1)
            record_id = record_match.group(2)
            existing = self.domain_records.get(zone, [])
            self.domain_records[zone] = [
                e for e in existing if e.get("id") != record_id
            ]
            return {}

        return {}
