"""
    .. module:: vsphereops
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: VSphereOps — a thin facade over the ``automojo-interop-vsphere``
        ``VSphereClient`` exposing the exact operation surface the VSphere
        venue provisioner needs.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from automojo.credentials.basiccredential import BasicCredential
from automojo.credentials.vspherecredential import VSphereCredential


def basic_credential_from_vsphere(*, credential: VSphereCredential
                                  ) -> BasicCredential:
    """
        Adapt a :class:`VSphereCredential` to the :class:`BasicCredential`
        the ``VSphereClient`` constructor requires.

        The interop client mints its own session token; it consumes a
        username + password.  When the venue credential carries only an
        SSO token, the token is supplied as the password so the client's
        session-mint flow can still proceed.

        :param credential: The VSphereCredential.

        :returns: A BasicCredential carrying the username and secret.
        :raises: ConfigurationError
    """
    if credential.password is not None and len(credential.password) > 0:
        secret = credential.password
    else:
        secret = credential.sso_token

    rtnval = BasicCredential(
        identifier=credential.identifier,
        categories=["basic"],
        username=credential.username,
        password=secret,
        role=credential.role,
    )
    return rtnval


class VSphereOps:
    """
        Facade over :class:`VSphereClient`.

        The VSphere venue provisioner depends only on this surface, never on
        the raw client.  Production code constructs a :class:`VSphereOps`
        from a live client; tests substitute a mock object exposing the same
        methods so no real vCenter is contacted.

        Every long-running vCenter operation returns a task handle; this
        facade awaits each handle through ``handle.wait(aspects=...)`` so the
        venue receives already-completed results and stays synchronous with
        respect to the ``Aspects`` model.
    """

    def __init__(self, *, client: Any) -> None:
        """
            Construct a VSphereOps facade.

            :param client: A VSphereClient (or compatible object) exposing
                           the ``Network``, ``Content``, ``Vm``, ``Guest``,
                           ``Datastore`` and ``Inventory`` api groups.
        """
        self._client: Any = client
        return

    @staticmethod
    def _vsphere_aspects(*, aspects: Any) -> Any:
        """
            Adapt a provisioning-layer aspects object into the
            ``AspectsVSphere`` the interop client groups expect.

            The VSphere venue forwards a ``ProvisioningAspects``; the
            ``automojo-interop-vsphere`` client groups and task handles
            require an ``AspectsVSphere`` (timeout / interval field
            names differ).  When the interop package is unavailable
            (mock-backed tests substitute a plain object) the original
            aspects object is returned unchanged.

            :param aspects: A provisioning-layer aspects object.

            :returns: An ``AspectsVSphere`` or the original object.
        """
        try:
            from automojo.interop.vsphere.aspectsvsphere import AspectsVSphere
        except ImportError:
            rtnval = aspects
            return rtnval

        rtnval = AspectsVSphere.from_aspects(aspects)
        return rtnval

    @property
    def client(self) -> Any:
        """
            Return the wrapped vSphere client.

            :returns: The wrapped client object.
        """
        rtnval = self._client
        return rtnval

    @classmethod
    def from_credential(cls, *, host: str, credential: VSphereCredential,
                        port: Optional[int] = None) -> "VSphereOps":
        """
            Build a :class:`VSphereOps` from a :class:`VSphereCredential`.

            :param host: vCenter hostname or IP.
            :param credential: The VSphereCredential.
            :param port: Optional non-default vCenter port.

            :returns: A VSphereOps wrapping a freshly-constructed client.
        """
        from automojo.interop.vsphere.vsphereclient import VSphereClient

        basic = basic_credential_from_vsphere(credential=credential)
        client = VSphereClient(host=host, credential=basic, port=port)
        rtnval = cls(client=client)
        return rtnval

    # ------------------------------------------------------------------
    # Network — Distributed Virtual Switch + Port Group
    # ------------------------------------------------------------------

    def list_networks(self, *, aspects: Any) -> List[Any]:
        """
            List all networks (DVS / port groups) known to vCenter.

            :param aspects: Behaviour controls forwarded to the client.

            :returns: A list of network summary objects.
        """
        vaspects = self._vsphere_aspects(aspects=aspects)
        rtnval = self._client.Network.list(aspects=vaspects)
        return rtnval

    def create_port_group(self, *, name: str, vlan_id: int,
                          switch: str, aspects: Any) -> Dict[str, Any]:
        """
            Create a distributed port group on the named switch.

            :param name: Port group name.
            :param vlan_id: VLAN id assigned to the port group.
            :param switch: Owning distributed virtual switch name.
            :param aspects: Behaviour controls.

            :returns: A dict describing the created port group.
        """
        vaspects = self._vsphere_aspects(aspects=aspects)
        handle = self._client.Network.create_port_group(
            name=name, vlan_id=vlan_id, switch=switch, aspects=vaspects,
        )
        rtnval = self._wait(handle=handle, aspects=vaspects)
        return rtnval

    def delete_port_group(self, *, network_id: str, aspects: Any) -> None:
        """
            Delete a distributed port group.

            :param network_id: Port group identifier.
            :param aspects: Behaviour controls.
        """
        vaspects = self._vsphere_aspects(aspects=aspects)
        handle = self._client.Network.delete_port_group(
            network_id=network_id, aspects=vaspects,
        )
        self._wait(handle=handle, aspects=vaspects)
        return

    # ------------------------------------------------------------------
    # Content Library + image resolution
    # ------------------------------------------------------------------

    def find_library_item(self, *, name: str, tag: Optional[str],
                          library_ids: List[str], aspects: Any) -> Any:
        """
            Resolve a content-library item by name and optional tag.

            :param name: Library item display name.
            :param tag: Optional tag the item must carry.
            :param library_ids: Content-library search scope.
            :param aspects: Behaviour controls.

            :returns: A library item summary object.
        """
        vaspects = self._vsphere_aspects(aspects=aspects)
        rtnval = self._client.Content.find_item(
            name=name, tag=tag, all_library_ids=library_ids, aspects=vaspects,
        )
        return rtnval

    def deploy_library_item(self, *, item_id: str, target: Any,
                            deploy_spec: Any, aspects: Any) -> Dict[str, Any]:
        """
            Deploy a content-library OVF item, awaiting the deploy task.

            :param item_id: Library item identifier.
            :param target: A placement spec.
            :param deploy_spec: A content-deploy spec.
            :param aspects: Behaviour controls.

            :returns: The completed task result payload.
        """
        vaspects = self._vsphere_aspects(aspects=aspects)
        handle = self._client.Content.deploy_ovf_item(
            item_id=item_id, target=target, deploy_spec=deploy_spec,
            aspects=vaspects,
        )
        rtnval = self._wait(handle=handle, aspects=vaspects)
        return rtnval

    def find_template_vm(self, *, name: str, folder: Optional[str],
                         aspects: Any) -> Any:
        """
            Resolve a VM template by name in the configured template folder.

            :param name: Template VM name.
            :param folder: Optional folder scope (informational).
            :param aspects: Behaviour controls.

            :returns: A virtual machine summary object.
        """
        vaspects = self._vsphere_aspects(aspects=aspects)
        rtnval = self._client.Inventory.find_vm_by_name(
            name=name, aspects=vaspects,
        )
        return rtnval

    # ------------------------------------------------------------------
    # Datastore selection
    # ------------------------------------------------------------------

    def find_datastore_with_free_gb(self, *, min_free_gb: float,
                                    aspects: Any) -> Any:
        """
            Pick the least-loaded datastore meeting the free-space ask.

            :param min_free_gb: Minimum required free space in GB.
            :param aspects: Behaviour controls.

            :returns: A datastore summary object.
        """
        vaspects = self._vsphere_aspects(aspects=aspects)
        rtnval = self._client.Inventory.find_datastore_with_free_gb(
            min_free_gb=min_free_gb, aspects=vaspects,
        )
        return rtnval

    # ------------------------------------------------------------------
    # VM lifecycle
    # ------------------------------------------------------------------

    def list_vms(self, *, aspects: Any) -> List[Any]:
        """
            List VMs known to vCenter.

            :param aspects: Behaviour controls.

            :returns: A list of virtual machine summary objects.
        """
        vaspects = self._vsphere_aspects(aspects=aspects)
        rtnval = self._client.Vm.list(aspects=vaspects)
        return rtnval

    def create_vm(self, *, spec: Any, aspects: Any) -> Dict[str, Any]:
        """
            Create a VM from a ``VmCreateSpec``, awaiting the create task.

            :param spec: A VmCreateSpec.
            :param aspects: Behaviour controls.

            :returns: The completed task result payload.
        """
        vaspects = self._vsphere_aspects(aspects=aspects)
        handle = self._client.Vm.create(spec=spec, aspects=vaspects)
        rtnval = self._wait(handle=handle, aspects=vaspects)
        return rtnval

    def delete_vm(self, *, vm_id: str, aspects: Any) -> None:
        """
            Delete a VM.

            :param vm_id: VM identifier.
            :param aspects: Behaviour controls.
        """
        vaspects = self._vsphere_aspects(aspects=aspects)
        self._client.Vm.delete(id=vm_id, aspects=vaspects)
        return

    def power(self, *, vm_id: str, action: str, aspects: Any) -> Dict[str, Any]:
        """
            Apply a power action to a VM, awaiting the power task.

            :param vm_id: VM identifier.
            :param action: Power action, e.g. ``start`` or ``stop``.
            :param aspects: Behaviour controls.

            :returns: The completed task result payload.
        """
        vaspects = self._vsphere_aspects(aspects=aspects)
        handle = self._client.Vm.power(vm_id=vm_id, action=action,
                                       aspects=vaspects)
        rtnval = self._wait(handle=handle, aspects=vaspects)
        return rtnval

    def attach_disk(self, *, vm_id: str, datastore_id: str,
                    size_gb: int, aspects: Any) -> Dict[str, Any]:
        """
            Attach a virtual disk to a VM on the chosen datastore.

            :param vm_id: VM identifier.
            :param datastore_id: Datastore the disk is created on.
            :param size_gb: Disk size in gigabytes.
            :param aspects: Behaviour controls.

            :returns: A dict describing the attached disk.
        """
        vaspects = self._vsphere_aspects(aspects=aspects)
        handle = self._client.Vm.attach_disk(
            vm_id=vm_id, datastore_id=datastore_id, size_gb=size_gb,
            aspects=vaspects,
        )
        rtnval = self._wait(handle=handle, aspects=vaspects)
        return rtnval

    def apply_guest_customization(self, *, vm_id: str, spec: Any,
                                  guest_os_family: str,
                                  aspects: Any) -> Dict[str, Any]:
        """
            Apply a guest-customization spec to a VM, awaiting the task.

            :param vm_id: VM identifier.
            :param spec: A VmGuestCustomizationSpec-shaped object.
            :param guest_os_family: ``linux`` or ``windows``.
            :param aspects: Behaviour controls.

            :returns: The completed task result payload.
        """
        vaspects = self._vsphere_aspects(aspects=aspects)
        handle = self._client.Guest.apply_guest_customization_spec(
            vm=vm_id, spec=spec, guest_os_family=guest_os_family,
            aspects=vaspects,
        )
        rtnval = self._wait(handle=handle, aspects=vaspects)
        return rtnval

    # ------------------------------------------------------------------
    # Internal — task awaiting
    # ------------------------------------------------------------------

    @staticmethod
    def _wait(*, handle: Any, aspects: Any) -> Dict[str, Any]:
        """
            Await a vCenter task handle and return its result payload.

            Tolerates ``None`` handles (operations that complete
            synchronously) and handles whose ``wait`` returns either a
            dict or a result object.

            :param handle: A VSphereTaskHandle or None.
            :param aspects: Behaviour controls forwarded to ``wait``.

            :returns: A dict result payload (possibly empty).
        """
        if handle is None:
            rtnval: Dict[str, Any] = {}
            return rtnval

        result = handle.wait(aspects=aspects)
        if isinstance(result, dict):
            rtnval = result
            return rtnval

        payload = getattr(result, "result", None)
        if isinstance(payload, dict):
            rtnval = payload
            return rtnval

        resource_id = getattr(result, "resource_id", None)
        if resource_id is not None:
            rtnval = {"resource_id": resource_id}
            return rtnval

        rtnval = {}
        return rtnval
