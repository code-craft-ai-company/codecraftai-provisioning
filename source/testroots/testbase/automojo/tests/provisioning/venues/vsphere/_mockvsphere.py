"""
    .. module:: _mockvsphere
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MockVSphereOps — an in-memory stand-in for the VSphereOps
        facade, recording calls and returning deterministic responses so the
        VSphere venue can be exercised without a live vCenter.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional


class _Record:
    """
        Tiny attribute-bag used for network / vm / datastore summaries.
    """

    def __init__(self, **fields: Any) -> None:
        """
            Construct a _Record.

            :param fields: Arbitrary keyword fields exposed as attributes.
        """
        for key, value in fields.items():
            setattr(self, key, value)
        return


class MockTaskHandle:
    """
        Fake VSphereTaskHandle whose ``wait`` returns immediately.
    """

    def __init__(self, *, resource_id: str) -> None:
        """
            Construct a MockTaskHandle.

            :param resource_id: The resource id surfaced in the result.
        """
        self._resource_id: str = resource_id
        return

    def wait(self, *, aspects: Any) -> Dict[str, Any]:
        """
            Return the completed task result immediately.

            :param aspects: Behaviour controls (ignored).

            :returns: A dict carrying the resource id.
        """
        rtnval = {"resource_id": self._resource_id}
        return rtnval


class MockVSphereOps:
    """
        In-memory MockVSphereOps mirroring the :class:`VSphereOps` surface.

        Tracks created port groups, VMs and disks in dicts keyed by name so
        re-apply observes them and reports SKIPs.  Every call is appended to
        ``calls`` for assertion.
    """

    def __init__(self, *, library_items: Optional[Dict[str, str]] = None,
                 template_names: Optional[List[str]] = None,
                 datastore_free_gb: float = 4096.0) -> None:
        """
            Construct a MockVSphereOps.

            :param library_items: Mapping ``item_name -> item_id`` of
                                   content-library items that resolve.
            :param template_names: List of VM-template names that resolve via
                                   the folder fallback.
            :param datastore_free_gb: Free space reported by the datastore.
        """
        self._library_items: Dict[str, str] = library_items if library_items is not None else {}
        self._template_names: List[str] = template_names if template_names is not None else []
        self._datastore_free_gb: float = datastore_free_gb

        self.port_groups: Dict[str, Dict[str, Any]] = {}
        self.vms: Dict[str, Dict[str, Any]] = {}
        self.disks: List[Dict[str, Any]] = []
        self.calls: List[str] = []
        self._next_id: int = 0
        return

    def _alloc_id(self, *, prefix: str) -> str:
        """
            Allocate a deterministic resource id.

            :param prefix: Id prefix.

            :returns: A unique id string.
        """
        self._next_id = self._next_id + 1
        rtnval = "{}-{}".format(prefix, self._next_id)
        return rtnval

    # -- Network ------------------------------------------------------

    def list_networks(self, *, aspects: Any) -> List[Any]:
        """
            Return the current port groups as summary records.

            :param aspects: Behaviour controls.

            :returns: A list of network summary records.
        """
        self.calls.append("list_networks")
        out: List[Any] = []
        for name, info in self.port_groups.items():
            out.append(_Record(name=name, network=info["network_id"]))
        return out

    def create_port_group(self, *, name: str, vlan_id: int, switch: str,
                           aspects: Any) -> Dict[str, Any]:
        """
            Create and record a port group.

            :param name: Port group name.
            :param vlan_id: VLAN id.
            :param switch: Owning switch.
            :param aspects: Behaviour controls.

            :returns: A dict describing the port group.
        """
        self.calls.append("create_port_group:{}".format(name))
        network_id = self._alloc_id(prefix="dvportgroup")
        self.port_groups[name] = {"network_id": network_id,
                                  "vlan_id": vlan_id, "switch": switch}
        rtnval = {"network": network_id}
        return rtnval

    def delete_port_group(self, *, network_id: str, aspects: Any) -> None:
        """
            Delete a port group by network id.

            :param network_id: Port group id.
            :param aspects: Behaviour controls.
        """
        self.calls.append("delete_port_group:{}".format(network_id))
        for name, info in list(self.port_groups.items()):
            if info["network_id"] == network_id:
                del self.port_groups[name]
        return

    # -- Content library / image resolution ---------------------------

    def find_library_item(self, *, name: str, tag: Optional[str],
                           library_ids: List[str], aspects: Any) -> Any:
        """
            Resolve a content-library item by name.

            :param name: Item name.
            :param tag: Optional tag (ignored by the mock).
            :param library_ids: Search scope.
            :param aspects: Behaviour controls.

            :returns: A library item summary record.
            :raises: KeyError
        """
        self.calls.append("find_library_item:{}".format(name))
        if name not in self._library_items:
            raise KeyError("no library item named {}".format(name))
        rtnval = _Record(item_id=self._library_items[name],
                         library_id=library_ids[0], name=name)
        return rtnval

    def deploy_library_item(self, *, item_id: str, target: Any,
                             deploy_spec: Any, aspects: Any) -> Dict[str, Any]:
        """
            Deploy a content-library item, recording a new VM.

            :param item_id: Library item id.
            :param target: Placement spec.
            :param deploy_spec: Deploy spec carrying the VM name.
            :param aspects: Behaviour controls.

            :returns: The completed task result payload.
        """
        self.calls.append("deploy_library_item:{}".format(item_id))
        vm_name = deploy_spec["name"]
        vm_id = self._alloc_id(prefix="vm")
        self.vms[vm_name] = {"vm_id": vm_id, "power_state": "POWERED_OFF",
                             "ip_addresses": ["10.20.0.50"]}
        rtnval = {"resource_id": vm_id}
        return rtnval

    def find_template_vm(self, *, name: str, folder: Optional[str],
                          aspects: Any) -> Any:
        """
            Resolve a VM template by name.

            :param name: Template name.
            :param folder: Folder scope (ignored).
            :param aspects: Behaviour controls.

            :returns: A virtual machine summary record.
            :raises: KeyError
        """
        self.calls.append("find_template_vm:{}".format(name))
        if name not in self._template_names:
            raise KeyError("no template named {}".format(name))
        rtnval = _Record(vm=self._alloc_id(prefix="template"), name=name)
        return rtnval

    # -- Datastore ----------------------------------------------------

    def find_datastore_with_free_gb(self, *, min_free_gb: float,
                                     aspects: Any) -> Any:
        """
            Return the single mock datastore when it satisfies the ask.

            :param min_free_gb: Required free space in GB.
            :param aspects: Behaviour controls.

            :returns: A datastore summary record.
            :raises: ValueError
        """
        self.calls.append("find_datastore_with_free_gb:{}".format(
            min_free_gb
        ))
        if min_free_gb > self._datastore_free_gb:
            raise ValueError("no datastore with {} GB free".format(
                min_free_gb
            ))
        rtnval = _Record(datastore="datastore-1", name="ds-mock",
                         free_space=int(self._datastore_free_gb) * 1024 ** 3)
        return rtnval

    # -- VM lifecycle -------------------------------------------------

    def list_vms(self, *, aspects: Any) -> List[Any]:
        """
            Return the current VMs as summary records.

            :param aspects: Behaviour controls.

            :returns: A list of VM summary records.
        """
        self.calls.append("list_vms")
        out: List[Any] = []
        for name, info in self.vms.items():
            out.append(_Record(name=name, vm=info["vm_id"],
                                power_state=info["power_state"],
                                ip_addresses=info["ip_addresses"]))
        return out

    def create_vm(self, *, spec: Any, aspects: Any) -> Dict[str, Any]:
        """
            Create a VM from a VmCreateSpec-shaped dict.

            :param spec: The create spec dict.
            :param aspects: Behaviour controls.

            :returns: The completed task result payload.
        """
        self.calls.append("create_vm:{}".format(spec["name"]))
        vm_name = spec["name"]
        vm_id = self._alloc_id(prefix="vm")
        self.vms[vm_name] = {"vm_id": vm_id, "power_state": "POWERED_OFF",
                             "ip_addresses": ["10.20.0.51"]}
        rtnval = {"resource_id": vm_id}
        return rtnval

    def delete_vm(self, *, vm_id: str, aspects: Any) -> None:
        """
            Delete a VM by id.

            :param vm_id: VM id.
            :param aspects: Behaviour controls.
        """
        self.calls.append("delete_vm:{}".format(vm_id))
        for name, info in list(self.vms.items()):
            if info["vm_id"] == vm_id:
                del self.vms[name]
        return

    def power(self, *, vm_id: str, action: str, aspects: Any
              ) -> Dict[str, Any]:
        """
            Apply a power action to a VM.

            :param vm_id: VM id.
            :param action: ``start`` or ``stop``.
            :param aspects: Behaviour controls.

            :returns: The completed task result payload.
        """
        self.calls.append("power:{}:{}".format(action, vm_id))
        for info in self.vms.values():
            if info["vm_id"] == vm_id:
                info["power_state"] = ("POWERED_ON" if action == "start"
                                       else "POWERED_OFF")
        rtnval = {"resource_id": vm_id}
        return rtnval

    def attach_disk(self, *, vm_id: str, datastore_id: str, size_gb: int,
                    aspects: Any) -> Dict[str, Any]:
        """
            Attach a virtual disk to a VM.

            :param vm_id: VM id.
            :param datastore_id: Datastore id.
            :param size_gb: Disk size in GB.
            :param aspects: Behaviour controls.

            :returns: The completed task result payload.
        """
        self.calls.append("attach_disk:{}".format(vm_id))
        disk_id = self._alloc_id(prefix="disk")
        self.disks.append({"disk_id": disk_id, "vm_id": vm_id,
                           "size_gb": size_gb})
        rtnval = {"resource_id": disk_id}
        return rtnval

    def apply_guest_customization(self, *, vm_id: str, spec: Any,
                                   guest_os_family: str,
                                   aspects: Any) -> Dict[str, Any]:
        """
            Record the guest-customisation payload applied to a VM.

            :param vm_id: VM id.
            :param spec: The customisation spec dict.
            :param guest_os_family: ``linux`` or ``windows``.
            :param aspects: Behaviour controls.

            :returns: The completed task result payload.
        """
        self.calls.append("apply_guest_customization:{}".format(vm_id))
        for info in self.vms.values():
            if info["vm_id"] == vm_id:
                info["guest_customization"] = spec
                info["guest_os_family"] = guest_os_family
        rtnval = {"resource_id": vm_id}
        return rtnval

    # -- Test helpers -------------------------------------------------

    def customization_for(self, *, vm_id: str) -> Optional[Dict[str, Any]]:
        """
            Return the guest-customisation payload applied to a VM.

            :param vm_id: VM id.

            :returns: The customisation spec dict, or None.
        """
        for info in self.vms.values():
            if info["vm_id"] == vm_id:
                rtnval = info.get("guest_customization", None)
                return rtnval
        rtnval = None
        return rtnval
