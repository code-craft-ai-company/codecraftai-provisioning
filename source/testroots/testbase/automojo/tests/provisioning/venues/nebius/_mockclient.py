"""
    .. module:: _mockclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: In-memory stateful mock of the Nebius interop client used by
        the Nebius venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, List, Optional, Tuple

from automojo.interop.nebius.model.nebiusvpc import NebiusVpc
from automojo.interop.nebius.model.nebiussubnet import NebiusSubnet
from automojo.interop.nebius.model.nebiussecuritygroup import (
    NebiusSecurityGroup
)
from automojo.interop.nebius.model.nebiussshkey import NebiusSshKey
from automojo.interop.nebius.model.nebiusdisk import NebiusDisk
from automojo.interop.nebius.model.nebiusplacementgroup import (
    NebiusPlacementGroup
)
from automojo.interop.nebius.model.nebiusvm import NebiusVm
from automojo.interop.nebius.model.nebiusfilesystem import NebiusFilesystem
from automojo.interop.nebius.model.nebiusmounttarget import NebiusMountTarget
from automojo.interop.nebius.model.nebiustaskhandle import NebiusTaskHandle


class _State:
    """
        Shared mutable store backing every mock api group.
    """

    def __init__(self) -> None:
        """
            Construct an empty _State.
        """
        self.counter: int = 0
        self.vpcs: List[NebiusVpc] = []
        self.subnets: List[NebiusSubnet] = []
        self.security_groups: List[NebiusSecurityGroup] = []
        self.ssh_keys: List[NebiusSshKey] = []
        self.disks: List[NebiusDisk] = []
        self.placement_groups: List[NebiusPlacementGroup] = []
        self.vms: List[NebiusVm] = []
        self.filesystems: List[NebiusFilesystem] = []
        self.mount_targets: List[NebiusMountTarget] = []
        return

    def next_id(self, *, prefix: str) -> str:
        """
            Return the next monotonic identifier for a prefix.

            :param prefix: The identifier prefix.

            :returns: A unique identifier string.
        """
        self.counter = self.counter + 1
        rtnval = "{}-{}".format(prefix, self.counter)
        return rtnval


class _VpcsGroup:
    """
        Mock VPCs api group.
    """

    def __init__(self, *, state: _State) -> None:
        self._state = state
        return

    def list(self, *, project_id: str, aspects: Any = None
             ) -> List[NebiusVpc]:
        """
            List VPCs anchored to a project.

            :param project_id: The project identifier.
            :param aspects: Aspects (unused by the mock).

            :returns: The matching VPC records.
        """
        rtnval = [v for v in self._state.vpcs if v.parent_id == project_id]
        return rtnval

    def create(self, *, spec: Any, aspects: Any = None) -> NebiusVpc:
        """
            Idempotently create a VPC.

            :param spec: A NebiusVpcSpec.
            :param aspects: Aspects (unused).

            :returns: The created or pre-existing VPC record.
        """
        for existing in self._state.vpcs:
            if existing.parent_id == spec.parent_id and existing.name == spec.name:
                return existing
        record = NebiusVpc(id=self._state.next_id(prefix="vpc"),
                           name=spec.name, parent_id=spec.parent_id,
                           ipv4_cidr_block=spec.ipv4_cidr_block,
                           status="READY", labels=spec.labels)
        self._state.vpcs.append(record)
        return record

    def delete(self, *, vpc_id: str, aspects: Any = None) -> None:
        """
            Delete a VPC.

            :param vpc_id: The VPC identifier.
            :param aspects: Aspects (unused).

            :returns: ``None``.
        """
        self._state.vpcs = [v for v in self._state.vpcs if v.id != vpc_id]
        return


class _SubnetsGroup:
    """
        Mock subnets api group.
    """

    def __init__(self, *, state: _State) -> None:
        self._state = state
        return

    def list(self, *, vpc_id: str, aspects: Any = None
             ) -> List[NebiusSubnet]:
        """
            List subnets in a VPC.

            :param vpc_id: The VPC identifier.
            :param aspects: Aspects (unused).

            :returns: The matching subnet records.
        """
        rtnval = [s for s in self._state.subnets if s.vpc_id == vpc_id]
        return rtnval

    def create(self, *, spec: Any, aspects: Any = None) -> NebiusSubnet:
        """
            Idempotently create a subnet.

            :param spec: A NebiusSubnetSpec.
            :param aspects: Aspects (unused).

            :returns: The created or pre-existing subnet record.
        """
        for existing in self._state.subnets:
            if existing.vpc_id == spec.vpc_id and existing.name == spec.name:
                return existing
        record = NebiusSubnet(id=self._state.next_id(prefix="subnet"),
                              name=spec.name, vpc_id=spec.vpc_id,
                              ipv4_cidr_block=spec.ipv4_cidr_block,
                              zone_id=spec.zone_id, status="READY",
                              labels=spec.labels)
        self._state.subnets.append(record)
        return record

    def delete(self, *, subnet_id: str, aspects: Any = None) -> None:
        """
            Delete a subnet.

            :param subnet_id: The subnet identifier.
            :param aspects: Aspects (unused).

            :returns: ``None``.
        """
        self._state.subnets = [s for s in self._state.subnets
                               if s.id != subnet_id]
        return


class _SecurityGroupsGroup:
    """
        Mock security-groups api group.
    """

    def __init__(self, *, state: _State) -> None:
        self._state = state
        return

    def list(self, *, vpc_id: str, aspects: Any = None
             ) -> List[NebiusSecurityGroup]:
        """
            List security groups in a VPC.

            :param vpc_id: The VPC identifier.
            :param aspects: Aspects (unused).

            :returns: The matching security-group records.
        """
        rtnval = [g for g in self._state.security_groups
                  if g.vpc_id == vpc_id]
        return rtnval

    def create(self, *, spec: Any, aspects: Any = None
               ) -> NebiusSecurityGroup:
        """
            Idempotently create a security group.

            :param spec: A NebiusSecurityGroupSpec.
            :param aspects: Aspects (unused).

            :returns: The created or pre-existing record.
        """
        for existing in self._state.security_groups:
            if existing.vpc_id == spec.vpc_id and existing.name == spec.name:
                return existing
        record = NebiusSecurityGroup(
            id=self._state.next_id(prefix="sg"), name=spec.name,
            vpc_id=spec.vpc_id, labels=spec.labels,
        )
        self._state.security_groups.append(record)
        return record

    def delete(self, *, sg_id: str, aspects: Any = None) -> None:
        """
            Delete a security group.

            :param sg_id: The security-group identifier.
            :param aspects: Aspects (unused).

            :returns: ``None``.
        """
        self._state.security_groups = [
            g for g in self._state.security_groups if g.id != sg_id
        ]
        return


class _SshKeysGroup:
    """
        Mock ssh-keys api group.
    """

    def __init__(self, *, state: _State) -> None:
        self._state = state
        return

    def list(self, *, aspects: Any = None) -> List[NebiusSshKey]:
        """
            List registered SSH keys.

            :param aspects: Aspects (unused).

            :returns: The SSH-key records.
        """
        rtnval = list(self._state.ssh_keys)
        return rtnval

    def register(self, *, name: str, public_key: str, aspects: Any = None
                 ) -> NebiusSshKey:
        """
            Idempotently register an SSH key.

            :param name: The key name.
            :param public_key: The public-key material.
            :param aspects: Aspects (unused).

            :returns: The created or pre-existing key record.
        """
        for existing in self._state.ssh_keys:
            if existing.name == name:
                return existing
        record = NebiusSshKey(id=self._state.next_id(prefix="key"),
                              name=name, public_key=public_key,
                              fingerprint="fp-{}".format(name))
        self._state.ssh_keys.append(record)
        return record

    def delete(self, *, key_id: str, aspects: Any = None) -> None:
        """
            Delete an SSH key.

            :param key_id: The key identifier.
            :param aspects: Aspects (unused).

            :returns: ``None``.
        """
        self._state.ssh_keys = [k for k in self._state.ssh_keys
                                if k.id != key_id]
        return


class _DisksGroup:
    """
        Mock disks api group.
    """

    def __init__(self, *, state: _State) -> None:
        self._state = state
        return

    def list(self, *, project_id: str, aspects: Any = None
             ) -> List[NebiusDisk]:
        """
            List disks anchored to a project.

            :param project_id: The project identifier.
            :param aspects: Aspects (unused).

            :returns: The matching disk records.
        """
        rtnval = [d for d in self._state.disks
                  if d.parent_id == project_id]
        return rtnval

    def create(self, *, spec: Any, aspects: Any = None
               ) -> Tuple[NebiusDisk, NebiusTaskHandle]:
        """
            Idempotently create a disk.

            :param spec: A NebiusDiskSpec.
            :param aspects: Aspects (unused).

            :returns: A tuple of the disk record and a task handle.
        """
        for existing in self._state.disks:
            if existing.parent_id == spec.parent_id and existing.name == spec.name:
                handle = NebiusTaskHandle(operation_id=existing.id,
                                          client=self)
                return (existing, handle)
        record = NebiusDisk(id=self._state.next_id(prefix="disk"),
                            name=spec.name, parent_id=spec.parent_id,
                            size_bytes=spec.size_bytes, type=spec.type,
                            status="READY", labels=spec.labels)
        self._state.disks.append(record)
        handle = NebiusTaskHandle(operation_id=record.id, client=self)
        return (record, handle)

    def attach(self, *, disk_id: str, instance_id: str, aspects: Any = None
               ) -> NebiusTaskHandle:
        """
            Attach a disk to an instance.

            :param disk_id: The disk identifier.
            :param instance_id: The instance identifier.
            :param aspects: Aspects (unused).

            :returns: A task handle.
        """
        for disk in self._state.disks:
            if disk.id == disk_id:
                disk.attached_to = instance_id
        rtnval = NebiusTaskHandle(operation_id=disk_id, client=self)
        return rtnval

    def delete(self, *, disk_id: str, aspects: Any = None) -> None:
        """
            Delete a disk.

            :param disk_id: The disk identifier.
            :param aspects: Aspects (unused).

            :returns: ``None``.
        """
        self._state.disks = [d for d in self._state.disks
                             if d.id != disk_id]
        return


class _PlacementGroupsGroup:
    """
        Mock placement-groups api group.
    """

    def __init__(self, *, state: _State) -> None:
        self._state = state
        return

    def list(self, *, project_id: str, aspects: Any = None
             ) -> List[NebiusPlacementGroup]:
        """
            List placement groups anchored to a project.

            :param project_id: The project identifier.
            :param aspects: Aspects (unused).

            :returns: The matching placement-group records.
        """
        rtnval = [p for p in self._state.placement_groups
                  if p.parent_id == project_id]
        return rtnval

    def create(self, *, spec: Any, aspects: Any = None
               ) -> NebiusPlacementGroup:
        """
            Idempotently create a placement group.

            :param spec: A NebiusPlacementGroupSpec.
            :param aspects: Aspects (unused).

            :returns: The created or pre-existing record.
        """
        for existing in self._state.placement_groups:
            if existing.parent_id == spec.parent_id and existing.name == spec.name:
                return existing
        record = NebiusPlacementGroup(
            id=self._state.next_id(prefix="pg"), name=spec.name,
            parent_id=spec.parent_id, interconnect=spec.interconnect,
            status="READY", labels=spec.labels,
        )
        self._state.placement_groups.append(record)
        return record

    def delete(self, *, placement_group_id: str, aspects: Any = None
               ) -> None:
        """
            Delete a placement group.

            :param placement_group_id: The placement-group identifier.
            :param aspects: Aspects (unused).

            :returns: ``None``.
        """
        self._state.placement_groups = [
            p for p in self._state.placement_groups
            if p.id != placement_group_id
        ]
        return


class _VmsGroup:
    """
        Mock vms api group.
    """

    def __init__(self, *, state: _State) -> None:
        self._state = state
        return

    def list(self, *, project_id: str, aspects: Any = None
             ) -> List[NebiusVm]:
        """
            List VMs anchored to a project.

            :param project_id: The project identifier.
            :param aspects: Aspects (unused).

            :returns: The matching VM records.
        """
        rtnval = [v for v in self._state.vms
                  if v.parent_id == project_id]
        return rtnval

    def launch(self, *, spec: Any, aspects: Any = None
               ) -> Tuple[NebiusVm, NebiusTaskHandle]:
        """
            Idempotently launch a VM.

            :param spec: A NebiusVmSpec.
            :param aspects: Aspects (unused).

            :returns: A tuple of the VM record and a task handle.
        """
        for existing in self._state.vms:
            if existing.parent_id == spec.parent_id and existing.name == spec.name:
                handle = NebiusTaskHandle(operation_id=existing.id,
                                          client=self)
                return (existing, handle)
        record = NebiusVm(
            id=self._state.next_id(prefix="vm"), name=spec.name,
            parent_id=spec.parent_id, platform=spec.platform,
            preset=spec.preset, subnet_id=spec.subnet_id, status="RUNNING",
            placement_group_id=spec.placement_group_id,
            metadata=spec.metadata, labels=spec.labels,
        )
        self._state.vms.append(record)
        handle = NebiusTaskHandle(operation_id=record.id, client=self)
        return (record, handle)

    def terminate(self, *, vm_id: str, aspects: Any = None
                  ) -> Optional[NebiusTaskHandle]:
        """
            Terminate a VM (idempotent on a missing id).

            :param vm_id: The VM identifier.
            :param aspects: Aspects (unused).

            :returns: A task handle, or ``None`` when the VM was absent.
        """
        present = any(v.id == vm_id for v in self._state.vms)
        self._state.vms = [v for v in self._state.vms if v.id != vm_id]
        if present is False:
            rtnval: Optional[NebiusTaskHandle] = None
            return rtnval
        rtnval = NebiusTaskHandle(operation_id=vm_id, client=self)
        return rtnval


class _FilesystemsGroup:
    """
        Mock filesystems api group.
    """

    def __init__(self, *, state: _State) -> None:
        self._state = state
        return

    def get(self, *, filesystem_id: str, aspects: Any = None
            ) -> NebiusFilesystem:
        """
            Fetch a shared filesystem by identifier.

            :param filesystem_id: The filesystem identifier.
            :param aspects: Aspects (unused).

            :returns: The filesystem record (created on first access).
        """
        for fs in self._state.filesystems:
            if fs.id == filesystem_id:
                return fs
        record = NebiusFilesystem(id=filesystem_id, name=filesystem_id,
                                  status="READY")
        self._state.filesystems.append(record)
        return record


class _MountTargetsGroup:
    """
        Mock mount-targets api group.
    """

    def __init__(self, *, state: _State) -> None:
        self._state = state
        return

    def list(self, *, filesystem_id: str, aspects: Any = None
             ) -> List[NebiusMountTarget]:
        """
            List mount targets for a filesystem.

            :param filesystem_id: The filesystem identifier.
            :param aspects: Aspects (unused).

            :returns: The matching mount-target records.
        """
        rtnval = [m for m in self._state.mount_targets
                  if m.filesystem_id == filesystem_id]
        return rtnval

    def create(self, *, spec: Any, aspects: Any = None
               ) -> NebiusMountTarget:
        """
            Idempotently create a mount target.

            :param spec: A NebiusMountTargetSpec.
            :param aspects: Aspects (unused).

            :returns: The created or pre-existing record.
        """
        for existing in self._state.mount_targets:
            if existing.filesystem_id == spec.filesystem_id and existing.subnet_id == spec.subnet_id:
                return existing
        record = NebiusMountTarget(
            id=self._state.next_id(prefix="mt"),
            filesystem_id=spec.filesystem_id, subnet_id=spec.subnet_id,
            mount_path=spec.mount_path, status="READY",
        )
        self._state.mount_targets.append(record)
        return record


class MockNebiusClient:
    """
        In-memory stateful mock of the Nebius interop client.

        Mirrors the api-group surface (``vpcs``, ``subnets``,
        ``security_groups``, ``ssh_keys``, ``disks``, ``placement_groups``,
        ``vms``, ``filesystems``, ``mount_targets``) used by the
        :class:`NebiusCloudProvisioner`.  State persists across calls so
        idempotent-apply and destroy semantics can be exercised.
    """

    def __init__(self) -> None:
        """
            Construct an empty MockNebiusClient.
        """
        self._state: _State = _State()
        self.vpcs: _VpcsGroup = _VpcsGroup(state=self._state)
        self.subnets: _SubnetsGroup = _SubnetsGroup(state=self._state)
        self.security_groups: _SecurityGroupsGroup = _SecurityGroupsGroup(
            state=self._state,
        )
        self.ssh_keys: _SshKeysGroup = _SshKeysGroup(state=self._state)
        self.disks: _DisksGroup = _DisksGroup(state=self._state)
        self.placement_groups: _PlacementGroupsGroup = _PlacementGroupsGroup(
            state=self._state,
        )
        self.vms: _VmsGroup = _VmsGroup(state=self._state)
        self.filesystems: _FilesystemsGroup = _FilesystemsGroup(
            state=self._state,
        )
        self.mount_targets: _MountTargetsGroup = _MountTargetsGroup(
            state=self._state,
        )
        return

    @property
    def state(self) -> _State:
        """
            The shared mutable store backing the mock.

            :returns: The :class:`_State` instance.
        """
        rtnval = self._state
        return rtnval
