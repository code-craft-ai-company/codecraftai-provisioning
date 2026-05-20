"""
    .. module:: _mockclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MockHypervClient — an in-memory stand-in for the HypervClient
               interop client used by the Hyper-V venue test suite.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.interop.hyperv.model.hypervvhdxinfo import HypervVhdxInfo
from automojo.interop.hyperv.model.hypervvirtualswitch import (
    HypervVirtualSwitch
)
from automojo.interop.hyperv.model.hypervvm import HypervVm


class _SwitchesGroup:
    """
        In-memory stand-in for the HypervClient ``switches`` API group.
    """

    def __init__(self, *, store: "MockHypervClient") -> None:
        """
            Construct a _SwitchesGroup bound to the mock store.

            :param store: The owning MockHypervClient.
        """
        self._store: "MockHypervClient" = store
        return

    def list_switches(self, *, aspects: Any = None
                      ) -> List[HypervVirtualSwitch]:
        """
            List the in-memory virtual switches.

            :param aspects: Ignored AspectsRunner.

            :returns: A list of HypervVirtualSwitch records.
        """
        rtnval = list(self._store.switches_state.values())
        return rtnval

    def get_switch(self, *, name: str, aspects: Any = None
                   ) -> Optional[HypervVirtualSwitch]:
        """
            Look up a virtual switch by name.

            :param name: The switch name.
            :param aspects: Ignored AspectsRunner.

            :returns: A HypervVirtualSwitch or None.
        """
        rtnval = self._store.switches_state.get(name, None)
        return rtnval

    def new_switch(self, *, spec: Any, aspects: Any = None
                   ) -> HypervVirtualSwitch:
        """
            Create a virtual switch (idempotent on name).

            :param spec: The HypervSwitchSpec.
            :param aspects: Ignored AspectsRunner.

            :returns: The created or pre-existing HypervVirtualSwitch.
        """
        existing = self._store.switches_state.get(spec.name, None)
        if existing is not None:
            rtnval = existing
            return rtnval

        self._store.calls["new_switch"] = self._store.calls["new_switch"] + 1
        switch_id = self._store.next_id(prefix="switch")
        record = HypervVirtualSwitch(name=spec.name,
                                     switch_type=spec.switch_type,
                                     net_adapter_interface_description=None,
                                     switch_id=switch_id)
        self._store.switches_state[spec.name] = record
        rtnval = record
        return rtnval

    def remove_switch(self, *, name: str, aspects: Any = None) -> None:
        """
            Remove a virtual switch by name.

            :param name: The switch name.
            :param aspects: Ignored AspectsRunner.

            :returns: ``None``.
        """
        if name in self._store.switches_state:
            self._store.calls["remove_switch"] = (
                self._store.calls["remove_switch"] + 1)
            del self._store.switches_state[name]
        return


class _VmsGroup:
    """
        In-memory stand-in for the HypervClient ``vms`` API group.
    """

    def __init__(self, *, store: "MockHypervClient") -> None:
        """
            Construct a _VmsGroup bound to the mock store.

            :param store: The owning MockHypervClient.
        """
        self._store: "MockHypervClient" = store
        return

    def list_vms(self, *, aspects: Any = None) -> List[HypervVm]:
        """
            List the in-memory VMs.

            :param aspects: Ignored AspectsRunner.

            :returns: A list of HypervVm records.
        """
        rtnval = list(self._store.vms_state.values())
        return rtnval

    def get_vm(self, *, name: str, aspects: Any = None
               ) -> Optional[HypervVm]:
        """
            Look up a VM by name.

            :param name: The VM name.
            :param aspects: Ignored AspectsRunner.

            :returns: A HypervVm or None.
        """
        rtnval = self._store.vms_state.get(name, None)
        return rtnval

    def new_vm(self, *, spec: Any, aspects: Any = None) -> HypervVm:
        """
            Create a VM (idempotent on name).

            :param spec: The HypervVmCreateSpec.
            :param aspects: Ignored AspectsRunner.

            :returns: The created or pre-existing HypervVm.
        """
        existing = self._store.vms_state.get(spec.name, None)
        if existing is not None:
            rtnval = existing
            return rtnval

        self._store.calls["new_vm"] = self._store.calls["new_vm"] + 1
        vm_id = self._store.next_id(prefix="vm")
        record = HypervVm(name=spec.name, vm_id=vm_id, state="Off",
                          generation=spec.generation, processor_count=1,
                          memory_startup_bytes=spec.memory_startup_bytes,
                          notes="", ip_addresses=[])
        self._store.vms_state[spec.name] = record
        rtnval = record
        return rtnval

    def start_vm(self, *, name: str, aspects: Any = None) -> None:
        """
            Start a VM.

            :param name: The VM name.
            :param aspects: Ignored AspectsRunner.

            :returns: ``None``.
        """
        record = self._store.vms_state.get(name, None)
        if record is not None:
            self._store.calls["start_vm"] = (
                self._store.calls["start_vm"] + 1)
            record.state = "Running"
            record.ip_addresses = ["10.0.0.{}".format(
                len(self._store.vms_state))]
        return

    def stop_vm(self, *, name: str, force: bool = True,
                aspects: Any = None) -> None:
        """
            Stop a VM.

            :param name: The VM name.
            :param force: Whether the stop is forced.
            :param aspects: Ignored AspectsRunner.

            :returns: ``None``.
        """
        record = self._store.vms_state.get(name, None)
        if record is not None:
            self._store.calls["stop_vm"] = self._store.calls["stop_vm"] + 1
            record.state = "Off"
        return

    def remove_vm(self, *, name: str, aspects: Any = None) -> None:
        """
            Remove a VM by name.

            :param name: The VM name.
            :param aspects: Ignored AspectsRunner.

            :returns: ``None``.
        """
        if name in self._store.vms_state:
            self._store.calls["remove_vm"] = (
                self._store.calls["remove_vm"] + 1)
            del self._store.vms_state[name]
        return

    def set_vm_notes(self, *, name: str, notes: str,
                     aspects: Any = None) -> None:
        """
            Set the Notes field of a VM.

            :param name: The VM name.
            :param notes: The notes string.
            :param aspects: Ignored AspectsRunner.

            :returns: ``None``.
        """
        record = self._store.vms_state.get(name, None)
        if record is not None:
            self._store.calls["set_vm_notes"] = (
                self._store.calls["set_vm_notes"] + 1)
            record.notes = notes
        return


class _VhdxGroup:
    """
        In-memory stand-in for the HypervClient ``vhdx`` API group.
    """

    def __init__(self, *, store: "MockHypervClient") -> None:
        """
            Construct a _VhdxGroup bound to the mock store.

            :param store: The owning MockHypervClient.
        """
        self._store: "MockHypervClient" = store
        return

    def get_vhdx(self, *, path: str, aspects: Any = None
                 ) -> Optional[HypervVhdxInfo]:
        """
            Look up a VHDX by path.

            :param path: The VHDX path.
            :param aspects: Ignored AspectsRunner.

            :returns: A HypervVhdxInfo or None.
        """
        rtnval = self._store.vhdx_state.get(path, None)
        return rtnval

    def new_vhdx(self, *, spec: Any, aspects: Any = None) -> HypervVhdxInfo:
        """
            Create a VHDX (idempotent on path).

            :param spec: The HypervVhdxSpec.
            :param aspects: Ignored AspectsRunner.

            :returns: The created or pre-existing HypervVhdxInfo.
        """
        existing = self._store.vhdx_state.get(spec.path, None)
        if existing is not None:
            rtnval = existing
            return rtnval

        self._store.calls["new_vhdx"] = self._store.calls["new_vhdx"] + 1
        vhd_type = "Dynamic" if spec.dynamic is True else "Fixed"
        if spec.parent_path is not None:
            vhd_type = "Differencing"
        record = HypervVhdxInfo(path=spec.path, size_bytes=spec.size_bytes,
                                vhd_type=vhd_type,
                                parent_path=spec.parent_path)
        self._store.vhdx_state[spec.path] = record
        rtnval = record
        return rtnval

    def delete_vhdx(self, *, path: str, aspects: Any = None) -> None:
        """
            Delete a VHDX by path.

            :param path: The VHDX path.
            :param aspects: Ignored AspectsRunner.

            :returns: ``None``.
        """
        if path in self._store.vhdx_state:
            self._store.calls["delete_vhdx"] = (
                self._store.calls["delete_vhdx"] + 1)
            del self._store.vhdx_state[path]
        return


class _HardwareGroup:
    """
        In-memory stand-in for the HypervClient ``hardware`` API group.
    """

    def __init__(self, *, store: "MockHypervClient") -> None:
        """
            Construct a _HardwareGroup bound to the mock store.

            :param store: The owning MockHypervClient.
        """
        self._store: "MockHypervClient" = store
        return

    def set_vm_processor(self, *, name: str, count: int,
                         aspects: Any = None) -> None:
        """
            Set a VM's processor count.

            :param name: The VM name.
            :param count: The processor count.
            :param aspects: Ignored AspectsRunner.

            :returns: ``None``.
        """
        record = self._store.vms_state.get(name, None)
        if record is not None:
            self._store.calls["set_vm_processor"] = (
                self._store.calls["set_vm_processor"] + 1)
            record.processor_count = count
        return

    def set_vm_memory(self, *, name: str, startup_bytes: int,
                      aspects: Any = None) -> None:
        """
            Set a VM's startup memory.

            :param name: The VM name.
            :param startup_bytes: The startup memory in bytes.
            :param aspects: Ignored AspectsRunner.

            :returns: ``None``.
        """
        record = self._store.vms_state.get(name, None)
        if record is not None:
            self._store.calls["set_vm_memory"] = (
                self._store.calls["set_vm_memory"] + 1)
            record.memory_startup_bytes = startup_bytes
        return


class _AdaptersGroup:
    """
        In-memory stand-in for the HypervClient ``adapters`` API group.
    """

    def __init__(self, *, store: "MockHypervClient") -> None:
        """
            Construct an _AdaptersGroup bound to the mock store.

            :param store: The owning MockHypervClient.
        """
        self._store: "MockHypervClient" = store
        return

    def add_vm_network_adapter(self, *, spec: Any,
                               aspects: Any = None) -> None:
        """
            Attach a network adapter to a VM.

            :param spec: The HypervAdapterSpec.
            :param aspects: Ignored AspectsRunner.

            :returns: ``None``.
        """
        self._store.calls["add_vm_network_adapter"] = (
            self._store.calls["add_vm_network_adapter"] + 1)
        return

    def add_vm_hard_disk(self, *, name: str, vhdx_path: str,
                         controller_type: str = "SCSI",
                         aspects: Any = None) -> None:
        """
            Attach a hard disk to a VM.

            :param name: The VM name.
            :param vhdx_path: The VHDX path.
            :param controller_type: SCSI or IDE.
            :param aspects: Ignored AspectsRunner.

            :returns: ``None``.
        """
        self._store.calls["add_vm_hard_disk"] = (
            self._store.calls["add_vm_hard_disk"] + 1)
        return

    def add_vm_dvd_drive(self, *, name: str, iso_path: str,
                         aspects: Any = None) -> None:
        """
            Attach a DVD drive backed by an ISO to a VM.

            :param name: The VM name.
            :param iso_path: The ISO path.
            :param aspects: Ignored AspectsRunner.

            :returns: ``None``.
        """
        self._store.calls["add_vm_dvd_drive"] = (
            self._store.calls["add_vm_dvd_drive"] + 1)
        return


class MockHypervClient:
    """
        In-memory stand-in for :class:`HypervClient`.

        Holds deterministic dictionaries for switches, VMs and VHDX disks
        keyed by name / path so the Hyper-V venue provisioner can be
        exercised without any PowerShell / WinRM traffic.  Mutating calls
        update the in-memory state so apply / destroy idempotence can be
        observed, and a ``calls`` counter exposes mutation counts.
    """

    def __init__(self) -> None:
        """
            Construct an empty MockHypervClient.
        """
        self.switches_state: Dict[str, HypervVirtualSwitch] = {}
        self.vms_state: Dict[str, HypervVm] = {}
        self.vhdx_state: Dict[str, HypervVhdxInfo] = {}
        self._counter: int = 0

        self.calls: Dict[str, int] = {
            "new_switch": 0, "remove_switch": 0, "new_vm": 0,
            "remove_vm": 0, "start_vm": 0, "stop_vm": 0,
            "set_vm_notes": 0, "new_vhdx": 0, "delete_vhdx": 0,
            "set_vm_processor": 0, "set_vm_memory": 0,
            "add_vm_network_adapter": 0, "add_vm_hard_disk": 0,
            "add_vm_dvd_drive": 0,
        }

        self.switches: _SwitchesGroup = _SwitchesGroup(store=self)
        self.vms: _VmsGroup = _VmsGroup(store=self)
        self.vhdx: _VhdxGroup = _VhdxGroup(store=self)
        self.hardware: _HardwareGroup = _HardwareGroup(store=self)
        self.adapters: _AdaptersGroup = _AdaptersGroup(store=self)
        return

    def next_id(self, *, prefix: str) -> str:
        """
            Allocate a deterministic identifier.

            :param prefix: The identifier prefix.

            :returns: A new identifier string.
        """
        self._counter = self._counter + 1
        rtnval = "{}-{:04d}".format(prefix, self._counter)
        return rtnval

    def mutation_total(self) -> int:
        """
            Return the total number of mutating calls observed.

            :returns: The summed mutation count.
        """
        rtnval = 0
        for value in self.calls.values():
            rtnval = rtnval + value
        return rtnval

    def seed_vm(self, *, name: str, notes: str = "",
                processor_count: int = 4,
                memory_startup_bytes: int = 8589934592) -> None:
        """
            Seed an existing VM into the mock state.

            :param name: The VM name.
            :param notes: The VM Notes string.
            :param processor_count: The VM processor count.
            :param memory_startup_bytes: The VM startup memory.

            :returns: ``None``.
        """
        vm_id = self.next_id(prefix="vm")
        self.vms_state[name] = HypervVm(
            name=name, vm_id=vm_id, state="Running", generation=2,
            processor_count=processor_count,
            memory_startup_bytes=memory_startup_bytes, notes=notes,
            ip_addresses=["10.0.0.250"])
        return
