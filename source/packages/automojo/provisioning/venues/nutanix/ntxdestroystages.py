"""
    .. module:: ntxdestroystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: NtxDestroyStages — reverses apply for the Nutanix venue
               provisioner: powers off + deletes VMs, deletes volume
               groups, security policies, subnets and VPCs, and cleans up
               VPN devices.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.venues.nutanix.nutanixspec import NutanixSpec
from automojo.provisioning.venues.nutanix.nutanixvenueconfig import (
    NutanixVenueConfig
)
from automojo.provisioning.venues.nutanix.ntxcategorytranslator import (
    NtxCategoryTranslator
)
from automojo.provisioning.venues.nutanix.ntxnaming import (
    resource_name_for, run_id_short
)


class NtxDestroyStages:
    """
        The Nutanix destroy stages.

        Destroy reverses apply: each run-owned VM is powered off then
        deleted; the run's volume groups, Flow security policies, subnets
        and Flow VPCs are deleted; and — for any VPN-joined VM —
        ``IVPNControlPlane.delete_device`` is invoked so the VPN control
        plane does not accumulate stale device registrations.  Deleting
        an absent Prism entity is a no-op, so destroy is idempotent.
    """

    def __init__(self, *, client: Any, config: NutanixVenueConfig,
                 category_translator: Optional[
                     NtxCategoryTranslator] = None) -> None:
        """
            Construct an NtxDestroyStages.

            :param client: The Nutanix interop client.
            :param config: The :class:`NutanixVenueConfig`.
            :param category_translator: Optional
                :class:`NtxCategoryTranslator`.
        """
        self._client = client
        self._config = config
        if category_translator is not None:
            self._category_translator: NtxCategoryTranslator = (
                category_translator
            )
        else:
            self._category_translator = NtxCategoryTranslator(client=client)
        return

    def destroy(self, *, spec: Optional[NutanixSpec], run_id: str,
                vpn_records: List[Dict[str, Any]],
                vpn_control_plane: Optional[Any], aspects: Any) -> None:
        """
            Tear down every run-owned resource in reverse order.

            :param spec: The :class:`NutanixSpec`, or ``None`` when
                destroying from a persisted run id.
            :param run_id: The provisioning run id.
            :param vpn_records: The VPN-device records captured at apply.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        self._destroy_vms(spec=spec, run_id=run_id, aspects=aspects)
        self._destroy_volume_groups(spec=spec, run_id=run_id,
                                    aspects=aspects)
        self._destroy_security_policies(spec=spec, run_id=run_id,
                                        aspects=aspects)
        self._destroy_subnets(spec=spec, run_id=run_id, aspects=aspects)
        self._destroy_vpcs(spec=spec, run_id=run_id, aspects=aspects)
        self._cleanup_vpn_devices(vpn_records=vpn_records,
                                  vpn_control_plane=vpn_control_plane,
                                  aspects=aspects)
        return

    def _owned_suffix(self, *, run_id: str) -> str:
        """
            Return the venue-name suffix marking run ownership.

            :param run_id: The provisioning run id.

            :returns: The ``-<run-id-short>`` ownership suffix.
        """
        rtnval = "-" + run_id_short(run_id=run_id)
        return rtnval

    def _destroy_vms(self, *, spec: Optional[NutanixSpec], run_id: str,
                     aspects: Any) -> None:
        """
            Power off then delete every run-owned VM.

            Ownership is decided by the ``automojo-run-id`` Category when
            present and otherwise by the venue-name suffix.

            :param spec: The :class:`NutanixSpec` or ``None``.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        suffix = self._owned_suffix(run_id=run_id)
        owned_names = self._owned_vm_names(spec=spec, run_id=run_id)

        live = self._client.vms.list(aspects=aspects)
        for vm in live:
            embedded_run_id = self._category_translator.run_id_of(vm=vm)
            if embedded_run_id is not None and len(embedded_run_id) > 0:
                owned = embedded_run_id == run_id
            elif spec is not None:
                owned = vm.name in owned_names
            else:
                owned = vm.name.endswith(suffix)
            if not owned:
                continue

            power_handle = self._client.vms.power_off(vm_uuid=vm.uuid,
                                                      aspects=aspects)
            power_handle.wait(aspects=aspects)
            self._client.vms.delete(vm_uuid=vm.uuid, aspects=aspects)
        return

    def _destroy_volume_groups(self, *, spec: Optional[NutanixSpec],
                               run_id: str, aspects: Any) -> None:
        """
            Delete every run-owned volume group.

            :param spec: The :class:`NutanixSpec` or ``None``.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        suffix = self._owned_suffix(run_id=run_id)
        owned_names: List[str] = []
        if spec is not None:
            for volume in spec.volumes:
                owned_names.append(resource_name_for(
                    spec_name=volume.name, run_id=run_id
                ))

        live = self._client.volume_groups.list(aspects=aspects)
        for volume_group in live:
            if spec is not None:
                owned = volume_group.name in owned_names
            else:
                owned = volume_group.name.endswith(suffix)
            if not owned:
                continue
            self._client.volume_groups.delete(
                volume_group_uuid=volume_group.uuid, aspects=aspects
            )
        return

    def _destroy_security_policies(self, *, spec: Optional[NutanixSpec],
                                   run_id: str, aspects: Any) -> None:
        """
            Delete every run-owned Flow security policy.

            :param spec: The :class:`NutanixSpec` or ``None``.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        suffix = self._owned_suffix(run_id=run_id)
        owned_names: List[str] = []
        if spec is not None:
            for sg in spec.security_groups:
                owned_names.append(resource_name_for(
                    spec_name=sg.name, run_id=run_id
                ))

        live = self._client.security_policies.list(aspects=aspects)
        for policy in live:
            if spec is not None:
                owned = policy.name in owned_names
            else:
                owned = policy.name.endswith(suffix)
            if not owned:
                continue
            self._client.security_policies.delete(
                policy_uuid=policy.uuid, aspects=aspects
            )
        return

    def _destroy_subnets(self, *, spec: Optional[NutanixSpec],
                         run_id: str, aspects: Any) -> None:
        """
            Delete every run-owned subnet.

            :param spec: The :class:`NutanixSpec` or ``None``.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        suffix = self._owned_suffix(run_id=run_id)
        owned_names: List[str] = []
        if spec is not None:
            for subnet in spec.subnets:
                owned_names.append(resource_name_for(
                    spec_name=subnet.name, run_id=run_id
                ))

        live = self._client.subnets.list(aspects=aspects)
        for subnet in live:
            if spec is not None:
                owned = subnet.name in owned_names
            else:
                owned = subnet.name.endswith(suffix)
            if not owned:
                continue
            self._client.subnets.delete(subnet_uuid=subnet.uuid,
                                        aspects=aspects)
        return

    def _destroy_vpcs(self, *, spec: Optional[NutanixSpec], run_id: str,
                      aspects: Any) -> None:
        """
            Delete every run-owned Flow VPC.

            :param spec: The :class:`NutanixSpec` or ``None``.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        suffix = self._owned_suffix(run_id=run_id)
        owned_names: List[str] = []
        if spec is not None:
            for network in spec.networks:
                owned_names.append(resource_name_for(
                    spec_name=network.name, run_id=run_id
                ))

        live = self._client.vpcs.list(aspects=aspects)
        for vpc in live:
            if spec is not None:
                owned = vpc.name in owned_names
            else:
                owned = vpc.name.endswith(suffix)
            if not owned:
                continue
            self._client.vpcs.delete(vpc_uuid=vpc.uuid, aspects=aspects)
        return

    def _cleanup_vpn_devices(self, *, vpn_records: List[Dict[str, Any]],
                             vpn_control_plane: Optional[Any],
                             aspects: Any) -> None:
        """
            De-register VPN devices for VPN-joined VMs.

            :param vpn_records: The VPN-device records captured at apply.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        if vpn_control_plane is None:
            return

        for record in vpn_records:
            device_id = record.get("vpn_device_id", None)
            if device_id is None or len(str(device_id)) == 0:
                continue
            try:
                vpn_control_plane.delete_device(device_id=device_id,
                                                aspects=aspects)
            except Exception:
                # Best-effort cleanup — a missing device is acceptable.
                pass
        return

    def _owned_vm_names(self, *, spec: Optional[NutanixSpec],
                        run_id: str) -> List[str]:
        """
            Compute the venue-side VM names owned by the run.

            :param spec: The :class:`NutanixSpec` or ``None``.
            :param run_id: The provisioning run id.

            :returns: The list of run-owned venue-side VM names.
        """
        names: List[str] = []
        if spec is None:
            rtnval = names
            return rtnval

        for instance in spec.instances:
            names.append(resource_name_for(spec_name=instance.name,
                                           run_id=run_id))
        rtnval = names
        return rtnval
