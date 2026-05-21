"""
    .. module:: _mockclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: In-memory MockCrusoeClient + api-group fakes used by the
        Crusoe venue tests in place of live HTTP.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional, Tuple

from automojo.restclient.crusoe.model.crusoedisk import CrusoeDisk
from automojo.restclient.crusoe.model.crusoeplacementgroup import (
    CrusoePlacementGroup
)
from automojo.restclient.crusoe.model.crusoesecuritygroup import (
    CrusoeSecurityGroup
)
from automojo.restclient.crusoe.model.crusoesshkey import CrusoeSshKey
from automojo.restclient.crusoe.model.crusoesubnet import CrusoeSubnet
from automojo.restclient.crusoe.model.crusoevm import CrusoeVm
from automojo.restclient.crusoe.model.crusoevpc import CrusoeVpc


class _Counter:
    """
        Monotonic id generator shared across the mock api groups.
    """

    def __init__(self) -> None:
        """
            Construct the counter.
        """
        self._value = 0
        return

    def next(self, *, prefix: str) -> str:
        """
            Return the next identifier with a prefix.

            :param prefix: The id prefix.

            :returns: A unique identifier string.
        """
        self._value = self._value + 1
        rtnval = "{0}-{1}".format(prefix, self._value)
        return rtnval


class _MockVpcs:
    """
        In-memory VPCs api group.
    """

    def __init__(self, *, store: Dict[str, CrusoeVpc],
                 counter: _Counter) -> None:
        self._store = store
        self._counter = counter
        self.create_calls = 0
        return

    def create(self, *, spec: Any) -> CrusoeVpc:
        self.create_calls = self.create_calls + 1
        for record in self._store.values():
            if record.name == spec.name:
                return record
        vpc_id = self._counter.next(prefix="vpc")
        record = CrusoeVpc(vpc_id=vpc_id, name=spec.name, cidr=spec.cidr,
                           project_id=spec.project_id, state="ready",
                           labels=dict(spec.labels))
        self._store[vpc_id] = record
        return record

    def list(self, *, project_id: str) -> List[CrusoeVpc]:
        return list(self._store.values())

    def delete(self, *, project_id: str, vpc_id: str) -> None:
        self._store.pop(vpc_id, None)
        return


class _MockSubnets:
    """
        In-memory subnets api group.
    """

    def __init__(self, *, store: Dict[str, CrusoeSubnet],
                 counter: _Counter) -> None:
        self._store = store
        self._counter = counter
        return

    def create(self, *, spec: Any) -> CrusoeSubnet:
        subnet_id = self._counter.next(prefix="sn")
        record = CrusoeSubnet(subnet_id=subnet_id, name=spec.name,
                              cidr=spec.cidr, vpc_id=spec.vpc_id,
                              location=spec.location, state="ready",
                              labels=dict(spec.labels))
        self._store[subnet_id] = record
        return record

    def list(self, *, vpc_id: str) -> List[CrusoeSubnet]:
        rtnval = [r for r in self._store.values() if r.vpc_id == vpc_id]
        return rtnval

    def delete(self, *, vpc_id: str, subnet_id: str) -> None:
        self._store.pop(subnet_id, None)
        return


class _MockSecurityGroups:
    """
        In-memory security groups api group.
    """

    def __init__(self, *, store: Dict[str, CrusoeSecurityGroup],
                 counter: _Counter) -> None:
        self._store = store
        self._counter = counter
        return

    def create(self, *, spec: Any) -> CrusoeSecurityGroup:
        for record in self._store.values():
            if record.name == spec.name and record.vpc_id == spec.vpc_id:
                return record
        sg_id = self._counter.next(prefix="sg")
        record = CrusoeSecurityGroup(security_group_id=sg_id, name=spec.name,
                                     vpc_id=spec.vpc_id,
                                     ingress_rules=list(spec.ingress_rules),
                                     egress_rules=list(spec.egress_rules),
                                     state="ready", labels=dict(spec.labels))
        self._store[sg_id] = record
        return record

    def list(self, *, vpc_id: str) -> List[CrusoeSecurityGroup]:
        rtnval = [r for r in self._store.values() if r.vpc_id == vpc_id]
        return rtnval

    def delete(self, *, vpc_id: str, security_group_id: str) -> None:
        self._store.pop(security_group_id, None)
        return


class _MockSshKeys:
    """
        In-memory SSH keys api group.
    """

    def __init__(self, *, store: Dict[str, CrusoeSshKey],
                 counter: _Counter) -> None:
        self._store = store
        self._counter = counter
        self.register_calls = 0
        return

    def register(self, *, project_id: str, name: str,
                 public_key: str) -> CrusoeSshKey:
        self.register_calls = self.register_calls + 1
        for record in self._store.values():
            if record.name == name:
                return record
        key_id = self._counter.next(prefix="key")
        record = CrusoeSshKey(ssh_key_id=key_id, name=name,
                              public_key=public_key, project_id=project_id)
        self._store[key_id] = record
        return record

    def list(self, *, project_id: str) -> List[CrusoeSshKey]:
        return list(self._store.values())

    def delete(self, *, project_id: str, ssh_key_id: str) -> None:
        self._store.pop(ssh_key_id, None)
        return


class _MockPlacementGroups:
    """
        In-memory placement groups (IB partitions) api group.
    """

    def __init__(self, *, store: Dict[str, CrusoePlacementGroup],
                 counter: _Counter) -> None:
        self._store = store
        self._counter = counter
        return

    def create(self, *, spec: Any) -> CrusoePlacementGroup:
        for record in self._store.values():
            if record.name == spec.name:
                return record
        pg_id = self._counter.next(prefix="ib")
        record = CrusoePlacementGroup(placement_group_id=pg_id,
                                      name=spec.name,
                                      interconnect=spec.interconnect,
                                      project_id=spec.project_id,
                                      state="ready",
                                      labels=dict(spec.labels))
        self._store[pg_id] = record
        return record

    def list(self, *, project_id: str) -> List[CrusoePlacementGroup]:
        return list(self._store.values())

    def delete(self, *, project_id: str, placement_group_id: str) -> None:
        self._store.pop(placement_group_id, None)
        return


class _MockDisks:
    """
        In-memory disks api group.
    """

    def __init__(self, *, store: Dict[str, CrusoeDisk],
                 counter: _Counter) -> None:
        self._store = store
        self._counter = counter
        self.attach_calls: List[Tuple[str, str]] = []
        return

    def create(self, *, project_id: str,
               spec: Any) -> Tuple[CrusoeDisk, Optional[Any]]:
        disk_id = self._counter.next(prefix="disk")
        record = CrusoeDisk(disk_id=disk_id, name=spec.name,
                            size_gib=spec.size_gib, disk_type=spec.disk_type,
                            location=spec.location, state="ready",
                            labels=dict(spec.labels))
        self._store[disk_id] = record
        rtnval = (record, None)
        return rtnval

    def attach(self, *, project_id: str, disk_id: str,
               instance_id: str) -> Optional[Any]:
        self.attach_calls.append((disk_id, instance_id))
        record = self._store.get(disk_id, None)
        if record is not None:
            record.attached_to = instance_id
        return None

    def detach(self, *, project_id: str, disk_id: str,
               instance_id: str) -> Optional[Any]:
        record = self._store.get(disk_id, None)
        if record is not None:
            record.attached_to = None
        return None

    def list(self, *, project_id: str) -> List[CrusoeDisk]:
        return list(self._store.values())

    def delete(self, *, project_id: str, disk_id: str) -> None:
        self._store.pop(disk_id, None)
        return


class _MockVms:
    """
        In-memory virtual machines api group.
    """

    def __init__(self, *, store: Dict[str, CrusoeVm],
                 counter: _Counter) -> None:
        self._store = store
        self._counter = counter
        self.launch_specs: List[Any] = []
        return

    def launch(self, *, project_id: str,
               spec: Any) -> Tuple[CrusoeVm, Optional[Any]]:
        self.launch_specs.append(spec)
        vm_id = self._counter.next(prefix="vm")
        record = CrusoeVm(vm_id=vm_id, name=spec.name,
                          instance_type=spec.instance_type,
                          location=spec.location, state="running",
                          project_id=project_id, subnet_id=spec.subnet_id,
                          placement_group_id=spec.placement_group_id,
                          labels=dict(spec.labels))
        self._store[vm_id] = record
        rtnval = (record, None)
        return rtnval

    def get(self, *, project_id: str, vm_id: str) -> CrusoeVm:
        rtnval = self._store[vm_id]
        return rtnval

    def list(self, *, project_id: str) -> List[CrusoeVm]:
        return list(self._store.values())

    def terminate(self, *, project_id: str, vm_id: str) -> Optional[Any]:
        self._store.pop(vm_id, None)
        return None


class MockCrusoeClient:
    """
        In-memory stand-in for :class:`CrusoeClient` used by the Crusoe venue
        tests.  Every api group keeps a deterministic dictionary store so
        repeated apply / destroy cycles behave like a real venue.
    """

    def __init__(self) -> None:
        """
            Construct a fresh MockCrusoeClient with empty stores.
        """
        counter = _Counter()
        self._vpcs = _MockVpcs(store={}, counter=counter)
        self._subnets = _MockSubnets(store={}, counter=counter)
        self._security_groups = _MockSecurityGroups(store={}, counter=counter)
        self._ssh_keys = _MockSshKeys(store={}, counter=counter)
        self._placement_groups = _MockPlacementGroups(store={},
                                                      counter=counter)
        self._disks = _MockDisks(store={}, counter=counter)
        self._vms = _MockVms(store={}, counter=counter)
        return

    @property
    def vpcs(self) -> _MockVpcs:
        return self._vpcs

    @property
    def subnets(self) -> _MockSubnets:
        return self._subnets

    @property
    def security_groups(self) -> _MockSecurityGroups:
        return self._security_groups

    @property
    def ssh_keys(self) -> _MockSshKeys:
        return self._ssh_keys

    @property
    def placement_groups(self) -> _MockPlacementGroups:
        return self._placement_groups

    @property
    def disks(self) -> _MockDisks:
        return self._disks

    @property
    def vms(self) -> _MockVms:
        return self._vms
