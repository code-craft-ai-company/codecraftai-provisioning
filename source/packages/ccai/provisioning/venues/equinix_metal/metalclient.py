"""
    .. module:: metalclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MetalClient — thin wrapper over the Equinix Metal SDK
               (packet-python / metal-python) used directly by the venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from ccai.provisioning.venues.equinix_metal.metalerrors import (
    MetalConflictError
)


class MetalClient:
    """
        Thin wrapper over the Equinix Metal SDK.

        Equinix Metal is a bare-metal venue; following the same pattern as the
        AWS venue (boto3 directly), the SDK is used inside the venue with no
        separate interop package.  The SDK import is lazy so tests can mock
        the whole client surface without ever importing ``packet-python``.

        The method surface is project-scoped and returns plain JSON-shaped
        dicts so the rest of the venue stays SDK-agnostic.  Each list endpoint
        returns ``[]`` when nothing is found; create endpoints return the
        created resource dict.

        Tests inject a fully-mocked instance; this implementation is used only
        against the real API behind ``RUN_LIVE_METAL=1``.
    """

    def __init__(self, *, api_token: str, project_id: str) -> None:
        """
            Construct a MetalClient.

            :param api_token: The Equinix Metal API token.
            :param project_id: The Equinix Metal project id.
        """
        if api_token is None or len(api_token) == 0:
            err_msg = "MetalClient requires a non-empty api_token."
            raise MetalConflictError(err_msg)

        if project_id is None or len(project_id) == 0:
            err_msg = "MetalClient requires a non-empty project_id."
            raise MetalConflictError(err_msg)

        self._api_token: str = api_token
        self._project_id: str = project_id
        self._sdk: Optional[Any] = None
        return

    def _manager(self) -> Any:
        """
            Lazily import and construct the Equinix Metal SDK manager.

            :returns: The SDK manager object.
            :raises: MetalConflictError
        """
        if self._sdk is not None:
            rtnval = self._sdk
            return rtnval

        try:
            import packet

            manager = packet.Manager(auth_token=self._api_token)
        except ImportError:
            err_msg_lines = [
                "The Equinix Metal SDK (packet-python) is not installed."
            ]
            err_msg_lines.append(
                "INSTALL: python -m pip install packet-python"
            )
            err_msg = os.linesep.join(err_msg_lines)
            raise MetalConflictError(err_msg) from None

        self._sdk = manager
        rtnval = manager
        return rtnval

    @property
    def project_id(self) -> str:
        """
            Return the project id this client is scoped to.

            :returns: The project id string.
        """
        rtnval = self._project_id
        return rtnval

    # ------------------------------------------------------------------
    # VLAN / virtual-network endpoints
    # ------------------------------------------------------------------

    def list_vlans(self) -> List[Dict[str, Any]]:
        """
            List the project's VLANs (virtual networks).

            :returns: A list of VLAN dicts.
        """
        manager = self._manager()
        rtnval = manager.list_vlans(project_id=self._project_id)
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
        manager = self._manager()
        rtnval = manager.create_vlan(
            project_id=self._project_id, metro=metro,
            description=description, tags=tags,
        )
        return rtnval

    def delete_vlan(self, *, vlan_id: str) -> None:
        """
            Delete a project VLAN.

            :param vlan_id: The VLAN id.
        """
        manager = self._manager()
        manager.delete_vlan(vlan_id=vlan_id)
        return

    # ------------------------------------------------------------------
    # IP reservation endpoints
    # ------------------------------------------------------------------

    def list_ip_reservations(self) -> List[Dict[str, Any]]:
        """
            List the project's IP reservations.

            :returns: A list of IP-reservation dicts.
        """
        manager = self._manager()
        rtnval = manager.list_ip_reservations(project_id=self._project_id)
        return rtnval

    def create_ip_reservation(self, *, metro: str, quantity: int,
                              ip_type: str,
                              tags: List[str]) -> Dict[str, Any]:
        """
            Create an IP reservation.

            :param metro: Metro slug.
            :param quantity: Number of addresses to reserve.
            :param ip_type: ``public_ipv4`` or ``private_ipv4``.
            :param tags: Tag string list.

            :returns: The created IP-reservation dict.
        """
        manager = self._manager()
        rtnval = manager.create_ip_reservation(
            project_id=self._project_id, metro=metro, quantity=quantity,
            ip_type=ip_type, tags=tags,
        )
        return rtnval

    def delete_ip_reservation(self, *, reservation_id: str) -> None:
        """
            Delete an IP reservation.

            :param reservation_id: The reservation id.
        """
        manager = self._manager()
        manager.delete_ip_reservation(reservation_id=reservation_id)
        return

    # ------------------------------------------------------------------
    # SSH-key endpoints (project-level)
    # ------------------------------------------------------------------

    def list_ssh_keys(self) -> List[Dict[str, Any]]:
        """
            List the project's SSH keys.

            :returns: A list of SSH-key dicts.
        """
        manager = self._manager()
        rtnval = manager.list_ssh_keys(project_id=self._project_id)
        return rtnval

    def create_ssh_key(self, *, label: str, key: str) -> Dict[str, Any]:
        """
            Create a project SSH key.

            :param label: The SSH-key label.
            :param key: The OpenSSH public-key material.

            :returns: The created SSH-key dict.
        """
        manager = self._manager()
        rtnval = manager.create_ssh_key(
            project_id=self._project_id, label=label, key=key,
        )
        return rtnval

    def delete_ssh_key(self, *, ssh_key_id: str) -> None:
        """
            Delete a project SSH key.

            :param ssh_key_id: The SSH-key id.
        """
        manager = self._manager()
        manager.delete_ssh_key(ssh_key_id=ssh_key_id)
        return

    # ------------------------------------------------------------------
    # Device endpoints
    # ------------------------------------------------------------------

    def list_devices(self) -> List[Dict[str, Any]]:
        """
            List the project's devices (bare-metal servers).

            :returns: A list of device dicts.
        """
        manager = self._manager()
        rtnval = manager.list_devices(project_id=self._project_id)
        return rtnval

    def get_device(self, *, device_id: str) -> Dict[str, Any]:
        """
            Get a single device by id.

            :param device_id: The device id.

            :returns: The device dict.
        """
        manager = self._manager()
        rtnval = manager.get_device(device_id=device_id)
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
        manager = self._manager()
        rtnval = manager.create_device(
            project_id=self._project_id, hostname=hostname, plan=plan,
            metro=metro, operating_system=operating_system,
            userdata=userdata, project_ssh_keys=project_ssh_keys,
            tags=tags,
        )
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
        manager = self._manager()
        rtnval = manager.update_device(device_id=device_id, tags=tags)
        return rtnval

    def delete_device(self, *, device_id: str) -> None:
        """
            Delete a device.

            :param device_id: The device id.
        """
        manager = self._manager()
        manager.delete_device(device_id=device_id)
        return
