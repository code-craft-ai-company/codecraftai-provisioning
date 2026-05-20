"""
    .. module:: hvapplystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: HvApplyStages — the staged, idempotent apply implementation
        for the Hyper-V venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.interop.hyperv.specs.hypervadapterspec import HypervAdapterSpec
from automojo.interop.hyperv.specs.hypervswitchspec import HypervSwitchSpec
from automojo.interop.hyperv.specs.hypervvhdxspec import HypervVhdxSpec
from automojo.interop.hyperv.specs.hypervvmcreatespec import (
    HypervVmCreateSpec
)

from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)

from automojo.provisioning.venues.hyperv.hvcloudinitrenderer import (
    HvCloudInitRenderer
)
from automojo.provisioning.venues.hyperv.hvhostconfig import HvHostConfig
from automojo.provisioning.venues.hyperv.hvnotestranslator import (
    HvNotesTranslator
)
from automojo.provisioning.venues.hyperv.hvresolver import HvResolver


class HvApplyStages:
    """
        Staged, idempotent apply for the Hyper-V venue.

        Stages run in dependency order: ``apply_switches`` ensures the
        VMSwitches a run needs, then ``apply_vms`` verifies the parent VHD,
        creates a differencing boot VHDX, runs ``New-VM``, sizes the VM with
        ``Set-VMProcessor`` / ``Set-VMMemory``, attaches data VHDX disks,
        connects a network adapter, encodes ownership into ``VM.Notes``,
        mounts the config-drive ISO and starts the VM.
    """

    def __init__(self, *, client: Any, host_config: HvHostConfig,
                 resolver: HvResolver, notes: HvNotesTranslator,
                 cloud_init: HvCloudInitRenderer) -> None:
        """
            Construct an HvApplyStages.

            :param client: The HypervClient interop client.
            :param host_config: The HvHostConfig for the run.
            :param resolver: The HvResolver.
            :param notes: The HvNotesTranslator.
            :param cloud_init: The HvCloudInitRenderer.
        """
        self._client: Any = client
        self._host_config: HvHostConfig = host_config
        self._resolver: HvResolver = resolver
        self._notes: HvNotesTranslator = notes
        self._cloud_init: HvCloudInitRenderer = cloud_init
        return

    def apply_switches(self, *, spec: Any, run_id: str,
                       created: List[ProvisionedResource],
                       skipped: List[str], aspects: Any
                       ) -> Dict[str, Any]:
        """
            Ensure every VMSwitch the spec's networks require.

            :param spec: The HypervSpec.
            :param run_id: The provisioning run identifier.
            :param created: The accumulating created-resource list.
            :param skipped: The accumulating skipped-name list.
            :param aspects: The AspectsRunner.

            :returns: A map of network name -> HypervVirtualSwitch record.
        """
        existing_switches: Dict[str, Any] = {}
        for switch in self._client.switches.list_switches(aspects=aspects):
            existing_switches[switch.name] = switch

        switch_state: Dict[str, Any] = {}
        for net in spec.networks:
            existed = net.name in existing_switches
            switch_type, adapter_name = self._switch_shape_for(net=net)
            switch_spec = HypervSwitchSpec(name=net.name,
                                           switch_type=switch_type,
                                           net_adapter_name=adapter_name)
            record = self._client.switches.new_switch(spec=switch_spec,
                                                      aspects=aspects)
            switch_state[net.name] = record
            if existed is True:
                skipped.append(net.name)
            else:
                created.append(ProvisionedResource(
                    kind="network", name=net.name,
                    venue_id=record.switch_id, attributes={}, tags=[]))

        rtnval = switch_state
        return rtnval

    def apply_vms(self, *, spec: Any, run_id: str,
                  switch_state: Dict[str, Any],
                  created: List[ProvisionedResource],
                  skipped: List[str],
                  vpn_records: List[Dict[str, Any]],
                  vpn_authkeys: Dict[str, str], aspects: Any) -> None:
        """
            Realise every VM and additional data volume in the spec.

            :param spec: The HypervSpec.
            :param run_id: The provisioning run identifier.
            :param switch_state: Map of network name -> switch record.
            :param created: The accumulating created-resource list.
            :param skipped: The accumulating skipped-name list.
            :param vpn_records: The accumulating VPN device-record list.
            :param vpn_authkeys: Map of instance name -> minted auth key.
            :param aspects: The AspectsRunner.

            :returns: ``None``.
        """
        existing_vms: Dict[str, Any] = {}
        for vm in self._client.vms.list_vms(aspects=aspects):
            existing_vms[vm.name] = vm

        keypair_index: Dict[str, Any] = {}
        for keypair in spec.keypairs:
            keypair_index[keypair.name] = keypair

        for inst in spec.instances:
            if inst.name in existing_vms:
                skipped.append(inst.name)
                self._record_vpn(instance=inst, vpn_records=vpn_records)
                continue

            self._create_vm(inst=inst, run_id=run_id,
                            switch_state=switch_state,
                            keypair_index=keypair_index,
                            vpn_authkeys=vpn_authkeys, aspects=aspects)
            created.append(ProvisionedResource(
                kind="instance", name=inst.name, venue_id=inst.name,
                attributes={}, tags=[]))
            self._record_vpn(instance=inst, vpn_records=vpn_records)

        for vol in spec.volumes:
            vhdx_path = self._volume_path(volume_name=vol.name)
            existing_vhdx = self._client.vhdx.get_vhdx(path=vhdx_path,
                                                       aspects=aspects)
            if existing_vhdx is not None:
                skipped.append(vol.name)
                continue

            vhdx_spec = HypervVhdxSpec(path=vhdx_path,
                                       size_bytes=vol.size_gb
                                       * 1024 * 1024 * 1024,
                                       dynamic=True)
            self._client.vhdx.new_vhdx(spec=vhdx_spec, aspects=aspects)
            created.append(ProvisionedResource(
                kind="volume", name=vol.name, venue_id=vhdx_path,
                attributes={}, tags=[]))

            if vol.attached_to is not None and len(vol.attached_to) > 0:
                self._client.adapters.add_vm_hard_disk(
                    name=vol.attached_to, vhdx_path=vhdx_path,
                    aspects=aspects)
        return

    def _create_vm(self, *, inst: Any, run_id: str,
                   switch_state: Dict[str, Any],
                   keypair_index: Dict[str, Any],
                   vpn_authkeys: Dict[str, str], aspects: Any) -> None:
        """
            Create and bring up a single VM.

            :param inst: The neutral CloudInstance.
            :param run_id: The provisioning run identifier.
            :param switch_state: Map of network name -> switch record.
            :param keypair_index: Map of keypair name -> CloudKeyPair.
            :param vpn_authkeys: Map of instance name -> minted auth key.
            :param aspects: The AspectsRunner.

            :returns: ``None``.
        """
        hardware = self._resolver.size_to_hardware(size_hint=inst.size)
        parent_vhd = self._resolver.image_to_parent_vhd(
            family=inst.image.family, version=inst.image.version,
            arch=inst.image.architecture)
        is_windows = self._resolver.is_windows_family(
            family=inst.image.family)

        boot_vhdx = self._resolver._join(root=self._host_config.vhd_root,
                                         leaf="{}-boot.vhdx".format(
                                             inst.name))
        boot_spec = HypervVhdxSpec(path=boot_vhdx,
                                   size_bytes=hardware.disk_bytes,
                                   dynamic=True, parent_path=parent_vhd)
        self._client.vhdx.new_vhdx(spec=boot_spec, aspects=aspects)

        vm_path = self._resolver._join(root=self._host_config.vm_root,
                                       leaf=inst.name)
        generation = 2
        create_spec = HypervVmCreateSpec(
            name=inst.name,
            memory_startup_bytes=hardware.memory_startup_bytes,
            generation=generation, vhd_path=boot_vhdx, path=vm_path)
        self._client.vms.new_vm(spec=create_spec, aspects=aspects)

        self._client.hardware.set_vm_processor(
            name=inst.name, count=hardware.processor_count, aspects=aspects)
        self._client.hardware.set_vm_memory(
            name=inst.name, startup_bytes=hardware.memory_startup_bytes,
            aspects=aspects)

        switch_record = switch_state.get(inst.subnet, None)
        if switch_record is None and len(switch_state) > 0:
            first_key = sorted(switch_state.keys())[0]
            switch_record = switch_state[first_key]
        if switch_record is not None:
            adapter_spec = HypervAdapterSpec(vm_name=inst.name,
                                             switch_name=switch_record.name)
            self._client.adapters.add_vm_network_adapter(spec=adapter_spec,
                                                         aspects=aspects)

        notes = self._notes.encode(neutral_tags=inst.tags, run_id=run_id)
        self._client.vms.set_vm_notes(name=inst.name, notes=notes,
                                      aspects=aspects)

        self._deliver_cloud_init(inst=inst, is_windows=is_windows,
                                 keypair_index=keypair_index,
                                 vpn_authkeys=vpn_authkeys, aspects=aspects)

        self._client.vms.start_vm(name=inst.name, aspects=aspects)
        return

    def _deliver_cloud_init(self, *, inst: Any, is_windows: bool,
                            keypair_index: Dict[str, Any],
                            vpn_authkeys: Dict[str, str],
                            aspects: Any) -> None:
        """
            Render and mount the cloud-init delivery payload for a VM.

            :param inst: The neutral CloudInstance.
            :param is_windows: Whether the guest is a Windows family.
            :param keypair_index: Map of keypair name -> CloudKeyPair.
            :param vpn_authkeys: Map of instance name -> minted auth key.
            :param aspects: The AspectsRunner.

            :returns: ``None``.
        """
        authkey = vpn_authkeys.get(inst.name, "")
        rendered_hostname = inst.name
        if inst.vpn_join is not None:
            rendered_hostname = inst.vpn_join.hostname_template

        if is_windows is True:
            self._cloud_init.build_setupcomplete(
                instance_name=inst.name, image_family=inst.image.family,
                vpn_join=inst.vpn_join, vpn_authkey=authkey,
                rendered_hostname=rendered_hostname)
            return

        ssh_keys: List[str] = []
        if inst.keypair is not None:
            keypair = keypair_index.get(inst.keypair, None)
            if keypair is not None:
                ssh_keys.append(keypair.public_key_material)

        self._cloud_init.build_iso(
            instance_name=inst.name, image_family=inst.image.family,
            ssh_keys=ssh_keys, user_data=inst.user_data_script,
            vpn_join=inst.vpn_join, vpn_authkey=authkey,
            rendered_hostname=rendered_hostname)

        iso_path = self._resolver._join(root=self._host_config.iso_root,
                                        leaf="{}-cidata.iso".format(
                                            inst.name))
        self._client.adapters.add_vm_dvd_drive(name=inst.name,
                                               iso_path=iso_path,
                                               aspects=aspects)
        return

    def _record_vpn(self, *, instance: Any,
                    vpn_records: List[Dict[str, Any]]) -> None:
        """
            Append a VPN device record when an instance carries vpn_join.

            :param instance: The neutral CloudInstance.
            :param vpn_records: The accumulating VPN device-record list.

            :returns: ``None``.
        """
        if instance.vpn_join is None:
            return
        vpn_records.append({
            "instance_name": instance.name,
            "vpn_provider": instance.vpn_join.provider,
            "vpn_device_id": None,
        })
        return

    def _switch_shape_for(self, *, net: Any) -> Any:
        """
            Resolve the VMSwitch type and physical adapter for a network.

            A network with a host external adapter configured maps to an
            External switch; otherwise an Internal switch is used.

            :param net: The neutral CloudNetwork.

            :returns: A (switch_type, net_adapter_name) tuple.
        """
        adapter_name = self._host_config.external_adapter_name
        if adapter_name is not None and len(adapter_name) > 0:
            rtnval = ("External", adapter_name)
            return rtnval
        rtnval = ("Internal", None)
        return rtnval

    def _volume_path(self, *, volume_name: str) -> str:
        """
            Resolve the host VHDX path for an additional data volume.

            :param volume_name: The neutral volume name.

            :returns: The host VHDX path string.
        """
        rtnval = self._resolver._join(root=self._host_config.vhd_root,
                                      leaf="{}-data.vhdx".format(volume_name))
        return rtnval
