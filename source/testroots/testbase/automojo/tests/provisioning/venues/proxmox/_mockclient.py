"""
    .. module:: _mockclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MockProxmoxClient — an in-memory stand-in for the Proxmox
               interop client used by the venue test suite.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List

from ccai.restclient.proxmox.model.proxmoxnetworkinterface import (
    ProxmoxNetworkInterface
)
from ccai.restclient.proxmox.model.proxmoxnode import ProxmoxNode
from ccai.restclient.proxmox.model.proxmoxvmstatus import ProxmoxVmStatus


class _MockTaskHandle:
    """
        In-memory stand-in for a Proxmox task handle.

        The venue calls ``wait`` after every mutating clone / power
        operation; this double records the call and returns immediately.
    """

    def __init__(self, *, upid: str) -> None:
        """
            Construct a _MockTaskHandle.

            :param upid: The fabricated unique process id.
        """
        self.upid: str = upid
        self.wait_calls: int = 0
        return

    def wait(self, *, aspects: Any,
             raise_on_failure: bool = True) -> None:
        """
            Record a wait on the task and return.

            :param aspects: Behaviour control (unused).
            :param raise_on_failure: Whether failure raises (unused).

            :returns: ``None``.
        """
        # `aspects` and `raise_on_failure` are accepted for interface
        # uniformity; the mock task always completes successfully.
        _ = (aspects, raise_on_failure)
        self.wait_calls = self.wait_calls + 1
        return


class _MockNodesGroup:
    """
        In-memory stand-in for the interop ``NodesGroup``.
    """

    def __init__(self, *, owner: "MockProxmoxClient") -> None:
        """
            Construct a _MockNodesGroup.

            :param owner: The owning :class:`MockProxmoxClient`.
        """
        self._owner = owner
        return

    def list(self, *, aspects: Any) -> List[ProxmoxNode]:
        """
            List the cluster nodes.

            :param aspects: Behaviour control (unused).

            :returns: The node list.
        """
        _ = aspects
        rtnval = list(self._owner.nodes_state)
        return rtnval


class _MockNetworksGroup:
    """
        In-memory stand-in for the interop ``NetworkGroup``.
    """

    def __init__(self, *, owner: "MockProxmoxClient") -> None:
        """
            Construct a _MockNetworksGroup.

            :param owner: The owning :class:`MockProxmoxClient`.
        """
        self._owner = owner
        return

    def list_node_networks(self, *, node_name: str,
                           aspects: Any) -> List[ProxmoxNetworkInterface]:
        """
            List the network interfaces on a node.

            :param node_name: The node name.
            :param aspects: Behaviour control (unused).

            :returns: The interface list for the node.
        """
        _ = aspects
        pool = self._owner.bridges_state.get(node_name, {})
        rtnval = list(pool.values())
        return rtnval

    def create_bridge(self, *, node_name: str, bridge: str, cidr: str,
                      comments: str, aspects: Any) -> bool:
        """
            Create a Linux bridge, idempotently by name.

            :param node_name: The node name.
            :param bridge: The bridge interface name.
            :param cidr: The bridge CIDR.
            :param comments: The bridge comment string.
            :param aspects: Behaviour control (unused).

            :returns: ``True`` when a bridge was created, ``False`` when an
                identically-named bridge already existed.
        """
        _ = (cidr, comments, aspects)
        pool = self._owner.bridges_state.setdefault(node_name, {})
        if bridge in pool:
            rtnval = False
            return rtnval
        self._owner.create_bridge_calls = (
            self._owner.create_bridge_calls + 1
        )
        pool[bridge] = ProxmoxNetworkInterface(
            iface=bridge, iface_type="bridge", active=True, cidr=cidr,
        )
        rtnval = True
        return rtnval

    def delete_bridge(self, *, node_name: str, bridge: str,
                      aspects: Any) -> None:
        """
            Delete a Linux bridge by name (idempotent).

            :param node_name: The node name.
            :param bridge: The bridge interface name.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        _ = aspects
        pool = self._owner.bridges_state.get(node_name, {})
        if bridge in pool:
            del pool[bridge]
        return


class _MockQemuGroup:
    """
        In-memory stand-in for the interop ``QemuGroup``.
    """

    def __init__(self, *, owner: "MockProxmoxClient") -> None:
        """
            Construct a _MockQemuGroup.

            :param owner: The owning :class:`MockProxmoxClient`.
        """
        self._owner = owner
        return

    def list_vms(self, *, node_name: str,
                 aspects: Any) -> List[ProxmoxVmStatus]:
        """
            List the VMs on a node.

            :param node_name: The node name.
            :param aspects: Behaviour control (unused).

            :returns: The VM-status list for the node.
        """
        _ = aspects
        out: List[ProxmoxVmStatus] = []
        for record in self._owner.vms_state.values():
            if record["node"] == node_name:
                out.append(record["status"])
        rtnval = out
        return rtnval

    def clone_vm(self, *, node_name: str, source_vmid: int,
                 spec: Any, aspects: Any) -> _MockTaskHandle:
        """
            Clone a VM from a template, idempotently by VMID.

            :param node_name: The target node name.
            :param source_vmid: The source template VMID.
            :param spec: The :class:`ProxmoxVmCloneSpec`.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`_MockTaskHandle`.
        """
        _ = (source_vmid, aspects)
        if spec.newid not in self._owner.vms_state:
            self._owner.clone_vm_calls = self._owner.clone_vm_calls + 1
            extra = spec.extra if spec.extra is not None else {}
            cores = extra.get("cores", 1)
            memory_mb = extra.get("memory", 512)
            status = ProxmoxVmStatus(
                vmid=spec.newid, name=spec.name, status="stopped",
                template=False, cpus=cores,
                maxmem=memory_mb * 1024 * 1024, tags=[],
            )
            self._owner.vms_state[spec.newid] = {"node": node_name,
                                                 "status": status}
        rtnval = _MockTaskHandle(upid=self._owner.next_upid())
        return rtnval

    def set_tags(self, *, node_name: str, vmid: int, tags: List[str],
                 aspects: Any) -> None:
        """
            Replace the tag list on a VM.

            :param node_name: The node name.
            :param vmid: The numeric VM identifier.
            :param tags: The tag-string list.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        _ = (node_name, aspects)
        record = self._owner.vms_state.get(vmid, None)
        if record is not None:
            record["status"].tags = list(tags)
        return

    def attach_disk(self, *, node_name: str, vmid: int, spec: Any,
                    aspects: Any) -> None:
        """
            Attach a virtual disk to a VM.

            :param node_name: The node name.
            :param vmid: The numeric VM identifier.
            :param spec: The :class:`ProxmoxDiskSpec`.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        _ = (node_name, aspects)
        self._owner.attach_disk_calls = self._owner.attach_disk_calls + 1
        record = self._owner.vms_state.get(vmid, None)
        if record is not None:
            record.setdefault("disks", []).append(spec.slot)
        return

    def set_cloud_init_user_data(self, *, node_name: str, vmid: int,
                                 user_data: str, aspects: Any) -> None:
        """
            Set the ``cicustom`` cloud-init user-data reference on a VM.

            :param node_name: The node name.
            :param vmid: The numeric VM identifier.
            :param user_data: The ``cicustom`` config value.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        _ = (node_name, aspects)
        record = self._owner.vms_state.get(vmid, None)
        if record is not None:
            record["cicustom"] = user_data
        return

    def set_ip_config(self, *, node_name: str, vmid: int, slot: str,
                      value: str, aspects: Any) -> None:
        """
            Set an ``ipconfig`` slot on a VM.

            :param node_name: The node name.
            :param vmid: The numeric VM identifier.
            :param slot: The ``ipconfigN`` slot name.
            :param value: The ip-config value.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        _ = (node_name, aspects)
        record = self._owner.vms_state.get(vmid, None)
        if record is not None:
            record.setdefault("ipconfig", {})[slot] = value
        return

    def start_vm(self, *, node_name: str, vmid: int,
                 aspects: Any) -> _MockTaskHandle:
        """
            Start a VM (idempotent).

            :param node_name: The node name.
            :param vmid: The numeric VM identifier.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`_MockTaskHandle`.
        """
        _ = (node_name, aspects)
        record = self._owner.vms_state.get(vmid, None)
        if record is not None:
            record["status"].status = "running"
        rtnval = _MockTaskHandle(upid=self._owner.next_upid())
        return rtnval

    def stop_vm(self, *, node_name: str, vmid: int,
                aspects: Any) -> _MockTaskHandle:
        """
            Stop a VM (idempotent).

            :param node_name: The node name.
            :param vmid: The numeric VM identifier.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`_MockTaskHandle`.
        """
        _ = (node_name, aspects)
        record = self._owner.vms_state.get(vmid, None)
        if record is not None:
            record["status"].status = "stopped"
        rtnval = _MockTaskHandle(upid=self._owner.next_upid())
        return rtnval

    def destroy_vm(self, *, node_name: str, vmid: int,
                   aspects: Any) -> _MockTaskHandle:
        """
            Destroy a VM by VMID (idempotent).

            :param node_name: The node name.
            :param vmid: The numeric VM identifier.
            :param aspects: Behaviour control (unused).

            :returns: A :class:`_MockTaskHandle`.
        """
        _ = (node_name, aspects)
        if vmid in self._owner.vms_state:
            self._owner.destroy_vm_calls = (
                self._owner.destroy_vm_calls + 1
            )
            del self._owner.vms_state[vmid]
        rtnval = _MockTaskHandle(upid=self._owner.next_upid())
        return rtnval


class _MockFirewallGroup:
    """
        In-memory stand-in for the interop ``FirewallGroup``.
    """

    def __init__(self, *, owner: "MockProxmoxClient") -> None:
        """
            Construct a _MockFirewallGroup.

            :param owner: The owning :class:`MockProxmoxClient`.
        """
        self._owner = owner
        return

    def add_vm_firewall_rule(self, *, node_name: str, vmid: int,
                             spec: Any, aspects: Any) -> None:
        """
            Add a firewall rule to a VM.

            :param node_name: The node name.
            :param vmid: The numeric VM identifier.
            :param spec: The :class:`ProxmoxFirewallRuleSpec`.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        _ = (node_name, aspects)
        self._owner.firewall_rules.setdefault(vmid, []).append(spec)
        return


class _MockStorageGroup:
    """
        In-memory stand-in for the interop ``StorageGroup``.
    """

    def __init__(self, *, owner: "MockProxmoxClient") -> None:
        """
            Construct a _MockStorageGroup.

            :param owner: The owning :class:`MockProxmoxClient`.
        """
        self._owner = owner
        return

    def has_snippet(self, *, node_name: str, storage: str, filename: str,
                    aspects: Any) -> bool:
        """
            Return whether a snippet is already present on a storage.

            :param node_name: The node name.
            :param storage: The storage name.
            :param filename: The snippet filename.
            :param aspects: Behaviour control (unused).

            :returns: ``True`` when the snippet exists.
        """
        _ = (node_name, aspects)
        key = "{}/{}".format(storage, filename)
        rtnval = key in self._owner.snippets_state
        return rtnval

    def upload_snippet(self, *, node_name: str, storage: str,
                       filename: str, content: str, aspects: Any) -> None:
        """
            Upload a snippet to a storage, content-addressed by filename.

            :param node_name: The node name.
            :param storage: The storage name.
            :param filename: The snippet filename.
            :param content: The snippet body.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        _ = (node_name, aspects)
        key = "{}/{}".format(storage, filename)
        self._owner.upload_snippet_calls = (
            self._owner.upload_snippet_calls + 1
        )
        self._owner.snippets_state[key] = content
        return


class MockProxmoxClient:
    """
        In-memory stand-in for :class:`ProxmoxClient`.

        Holds deterministic state for cluster nodes, per-node bridges, VMs
        (keyed by VMID), firewall rules, and uploaded cloud-init snippets so
        the venue provisioner can be exercised without a live Proxmox
        cluster.  Mutating calls update the in-memory state so apply /
        destroy idempotence can be observed.  The api groups are reachable
        through the same public attributes as the real client.
    """

    def __init__(self, *, node_names: List[str] = None) -> None:
        """
            Construct a MockProxmoxClient with one or more cluster nodes.

            :param node_names: The cluster node names; a single default
                node is used when omitted.
        """
        effective_nodes = node_names
        if effective_nodes is None:
            effective_nodes = ["pve-node-1"]

        self.nodes_state: List[ProxmoxNode] = []
        for node_name in effective_nodes:
            self.nodes_state.append(ProxmoxNode(name=node_name,
                                                status="online",
                                                online=True))

        self.bridges_state: Dict[str, Dict[str, Any]] = {}
        self.vms_state: Dict[int, Dict[str, Any]] = {}
        self.firewall_rules: Dict[int, List[Any]] = {}
        self.snippets_state: Dict[str, str] = {}

        self._upid_counter = 0
        self.create_bridge_calls = 0
        self.clone_vm_calls = 0
        self.attach_disk_calls = 0
        self.destroy_vm_calls = 0
        self.upload_snippet_calls = 0

        self.nodes = _MockNodesGroup(owner=self)
        self.networks = _MockNetworksGroup(owner=self)
        self.qemu = _MockQemuGroup(owner=self)
        self.firewall = _MockFirewallGroup(owner=self)
        self.storage = _MockStorageGroup(owner=self)
        return

    def next_upid(self) -> str:
        """
            Allocate a deterministic unique process id.

            :returns: A new UPID string.
        """
        self._upid_counter = self._upid_counter + 1
        rtnval = "UPID:mock:{:08d}".format(self._upid_counter)
        return rtnval

    def all_vms(self) -> List[ProxmoxVmStatus]:
        """
            Return every VM record across every node.

            :returns: A list of VM-status records.
        """
        out: List[ProxmoxVmStatus] = []
        for record in self.vms_state.values():
            out.append(record["status"])
        rtnval = out
        return rtnval


class RecordingVpnControlPlane:
    """
        Minimal ``IVPNControlPlane`` test double recording the device ids
        passed to :meth:`delete_device` and the auth key handed to apply.
    """

    def __init__(self, *, minted_authkey: str = "tskey-mock-0001") -> None:
        """
            Construct a RecordingVpnControlPlane.

            :param minted_authkey: The auth key handed to the apply stage.
        """
        self.minted_authkey: str = minted_authkey
        self.deleted_device_ids: List[str] = []
        return

    def delete_device(self, *, device_id: str, aspects: Any) -> None:
        """
            Record a device-id de-registration.

            :param device_id: The device id to de-register.
            :param aspects: Behaviour control (unused).

            :returns: ``None``.
        """
        _ = aspects
        self.deleted_device_ids.append(device_id)
        return
