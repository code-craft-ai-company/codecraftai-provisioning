"""
    .. module:: _mockmetalclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MockMetalClient — deterministic in-memory stand-in for the
               Equinix Metal SDK wrapper used by venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List


class MockMetalClient:
    """
        Deterministic in-memory stand-in for :class:`MetalClient`.

        Devices come up ``active`` immediately so the aspects-controlled
        polling loop completes without sleeping.  The mock honours the same
        method surface the real client exposes and records every mutating
        call for assertion.
    """

    def __init__(self, *, project_id: str = "proj-test") -> None:
        """
            Construct a MockMetalClient.

            :param project_id: The project id.
        """
        self._project_id: str = project_id
        self._vlans: List[Dict[str, Any]] = []
        self._ips: List[Dict[str, Any]] = []
        self._ssh_keys: List[Dict[str, Any]] = []
        self._devices: List[Dict[str, Any]] = []
        self._counter: int = 0
        self.calls: List[str] = []
        return

    @property
    def project_id(self) -> str:
        """
            Return the project id.

            :returns: The project id string.
        """
        rtnval = self._project_id
        return rtnval

    def _next_id(self, *, prefix: str) -> str:
        """
            Allocate a deterministic resource id.

            :param prefix: The id prefix.

            :returns: A new id string.
        """
        self._counter = self._counter + 1
        rtnval = "{}-{:04d}".format(prefix, self._counter)
        return rtnval

    # --- VLANs ---

    def list_vlans(self) -> List[Dict[str, Any]]:
        rtnval = [dict(entry) for entry in self._vlans]
        return rtnval

    def create_vlan(self, *, metro: str, description: str,
                    tags: List[str]) -> Dict[str, Any]:
        self.calls.append("create_vlan")
        vlan: Dict[str, Any] = {
            "id": self._next_id(prefix="vlan"),
            "metro": metro,
            "description": description,
            "vxlan": 1000 + self._counter,
            "tags": list(tags),
        }
        self._vlans.append(vlan)
        rtnval = dict(vlan)
        return rtnval

    def delete_vlan(self, *, vlan_id: str) -> None:
        self.calls.append("delete_vlan")
        self._vlans = [v for v in self._vlans if v.get("id") != vlan_id]
        return

    # --- IP reservations ---

    def list_ip_reservations(self) -> List[Dict[str, Any]]:
        rtnval = [dict(entry) for entry in self._ips]
        return rtnval

    def create_ip_reservation(self, *, metro: str, quantity: int,
                              ip_type: str,
                              tags: List[str]) -> Dict[str, Any]:
        self.calls.append("create_ip_reservation")
        reservation: Dict[str, Any] = {
            "id": self._next_id(prefix="ip"),
            "metro": metro,
            "quantity": quantity,
            "type": ip_type,
            "address": "10.10.{}.0".format(self._counter),
            "cidr": "10.10.{}.0/31".format(self._counter),
            "tags": list(tags),
        }
        self._ips.append(reservation)
        rtnval = dict(reservation)
        return rtnval

    def delete_ip_reservation(self, *, reservation_id: str) -> None:
        self.calls.append("delete_ip_reservation")
        self._ips = [r for r in self._ips
                     if r.get("id") != reservation_id]
        return

    # --- SSH keys ---

    def list_ssh_keys(self) -> List[Dict[str, Any]]:
        rtnval = [dict(entry) for entry in self._ssh_keys]
        return rtnval

    def create_ssh_key(self, *, label: str, key: str) -> Dict[str, Any]:
        self.calls.append("create_ssh_key")
        ssh_key: Dict[str, Any] = {
            "id": self._next_id(prefix="sshkey"),
            "label": label,
            "key": key,
            "fingerprint": "ab:cd:{:02d}".format(self._counter),
            "tags": [],
        }
        self._ssh_keys.append(ssh_key)
        rtnval = dict(ssh_key)
        return rtnval

    def delete_ssh_key(self, *, ssh_key_id: str) -> None:
        self.calls.append("delete_ssh_key")
        self._ssh_keys = [k for k in self._ssh_keys
                          if k.get("id") != ssh_key_id]
        return

    # --- Devices ---

    def list_devices(self) -> List[Dict[str, Any]]:
        rtnval = [dict(entry) for entry in self._devices]
        return rtnval

    def get_device(self, *, device_id: str) -> Dict[str, Any]:
        for device in self._devices:
            if device.get("id") == device_id:
                rtnval = dict(device)
                return rtnval
        rtnval = {"id": device_id, "state": "failed"}
        return rtnval

    def create_device(self, *, hostname: str, plan: str, metro: str,
                      operating_system: str, userdata: str,
                      project_ssh_keys: List[str],
                      tags: List[str]) -> Dict[str, Any]:
        self.calls.append("create_device")
        device: Dict[str, Any] = {
            "id": self._next_id(prefix="device"),
            "hostname": hostname,
            "plan": plan,
            "metro": metro,
            "operating_system": operating_system,
            "userdata": userdata,
            "project_ssh_keys": list(project_ssh_keys),
            "state": "active",
            "tags": list(tags),
            "ip_addresses": [
                {"address": "147.75.0.{}".format(self._counter),
                 "public": True},
                {"address": "10.0.0.{}".format(self._counter),
                 "public": False},
            ],
        }
        self._devices.append(device)
        rtnval = dict(device)
        return rtnval

    def update_device_tags(self, *, device_id: str,
                           tags: List[str]) -> Dict[str, Any]:
        self.calls.append("update_device_tags")
        for device in self._devices:
            if device.get("id") == device_id:
                device["tags"] = list(tags)
                rtnval = dict(device)
                return rtnval
        rtnval = {"id": device_id, "tags": list(tags), "state": "active"}
        return rtnval

    def delete_device(self, *, device_id: str) -> None:
        self.calls.append("delete_device")
        self._devices = [d for d in self._devices
                         if d.get("id") != device_id]
        return
