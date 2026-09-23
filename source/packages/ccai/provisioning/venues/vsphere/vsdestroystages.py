"""
    .. module:: vsdestroystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: VsDestroyStages — reverse-order teardown for the VSphere venue
        (power-off -> delete VM -> delete port group), with VPN device
        de-registration.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List

from ccai.provisioning.venues.vpncleanup import delete_vpn_device


class VsDestroyStages:
    """
        Reverse-dependency-order teardown for the VSphere venue.

        VMs are powered off then deleted before the distributed port groups
        they were attached to.  VPN-joined VMs trigger an
        ``IVPNControlPlane.delete_device`` call after the VM is deleted so
        the device record does not leak in the control plane.
    """

    def __init__(self, *, ops: Any) -> None:
        """
            Construct a VsDestroyStages.

            :param ops: A VSphereOps facade.
        """
        self._ops: Any = ops
        return

    def destroy(self, *, spec: Any, run_id: str, aspects: Any,
                vpn_control_plane: Any,
                vpn_records: List[Dict[str, Any]]) -> List[str]:
        """
            Tear down every owned resource for the run.

            :param spec: The VSphereSpec.
            :param run_id: Run identifier.
            :param aspects: Behaviour controls.
            :param vpn_control_plane: Optional IVPNControlPlane impl.
            :param vpn_records: The VPN device records captured by apply.

            :returns: A list of deleted VM identifiers.
        """
        deleted_vm_ids: List[str] = []

        if spec is None:
            rtnval = deleted_vm_ids
            return rtnval

        # 1. Power-off + delete VMs.
        existing_vms = self._ops.list_vms(aspects=aspects)
        vm_by_name: Dict[str, Any] = {}
        for vm in existing_vms:
            vm_name = getattr(vm, "name", None)
            if vm_name is not None:
                vm_by_name[vm_name] = vm

        vm_name_to_instance: Dict[str, str] = {}
        for instance in spec.instances:
            vm_name = "{}-{}".format(run_id, instance.name)
            vm_name_to_instance[vm_name] = instance.name

        for vm_name, instance_name in vm_name_to_instance.items():
            vm = vm_by_name.get(vm_name, None)
            if vm is None:
                continue
            vm_id = getattr(vm, "vm", vm_name)
            try:
                self._ops.power(vm_id=vm_id, action="stop", aspects=aspects)
            except Exception:
                # Best-effort power-off; the VM may already be stopped, and delete_vm
                # below raises if the VM cannot be removed.
                pass
            self._ops.delete_vm(vm_id=vm_id, aspects=aspects)
            deleted_vm_ids.append(vm_id)

        # 2. VPN control-plane device cleanup.
        if vpn_control_plane is not None:
            for record in vpn_records:
                device_id = record.get("vpn_device_id", None)
                if device_id is None or len(str(device_id)) == 0:
                    continue
                delete_vpn_device(vpn_control_plane=vpn_control_plane,
                                  device_id=device_id, aspects=aspects)

        # 3. Delete distributed port groups created by the run.
        existing_networks = self._ops.list_networks(aspects=aspects)
        run_pg_names = set()
        for subnet in spec.subnets:
            run_pg_names.add("{}-{}".format(run_id, subnet.name))

        for net in existing_networks:
            net_name = getattr(net, "name", None)
            if net_name is None or net_name not in run_pg_names:
                continue
            net_id = getattr(net, "network", net_name)
            try:
                self._ops.delete_port_group(network_id=net_id,
                                            aspects=aspects)
            except Exception:
                # Best-effort teardown; a failed delete must not stop the remaining
                # resources of the run from being torn down.
                pass

        rtnval = deleted_vm_ids
        return rtnval
