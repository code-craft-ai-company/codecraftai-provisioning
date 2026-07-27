"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Plan / apply / destroy / inventory tests for the Nebius
        venue against the in-memory mock client.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase

from .factories import create_nebius_client


from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from ccai.provisioning.venues.nebius.nebiuscloudprovisioner import (
    NebiusCloudProvisioner
)

from ._specfactory import basic_spec, gpu_cluster_spec


class _RecordingControlPlane:
    """
        Minimal IVPNControlPlane stand-in recording delete_device calls.
    """

    def __init__(self) -> None:
        self.minted_authkey: str = "tskey-minted-001"
        self.deleted: list = []
        return

    def delete_device(self, *, device_id: str, aspects=None) -> None:
        """
            Record a device de-registration.

            :param device_id: The device identifier.
            :param aspects: Aspects (unused).

            :returns: ``None``.
        """
        self.deleted.append(device_id)
        return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_plan_reports_creates_first_run(client, venue, aspects) -> None:
    """
        The first plan reports CREATE actions for every resource.
    """
    spec = basic_spec()
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    plan = provisioner.plan(aspects=aspects)
    intents = [a.intent for a in plan.actions]
    assert PlannedActionIntent.CREATE.value in intents
    return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_apply_creates_resources(client, venue, aspects) -> None:
    """
        Apply produces network, subnet, sg, keypair, instance, volume
        resources.
    """
    spec = basic_spec()
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    result = provisioner.apply(aspects=aspects)
    kinds = {r.kind for r in result.created}
    assert {"network", "subnet", "sg", "keypair", "instance",
            "volume"}.issubset(kinds)
    return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_replan_after_apply_is_all_skips(client, venue, aspects) -> None:
    """
        After an apply, a fresh plan reports no CREATE/UPDATE actions.
    """
    spec = basic_spec()
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    provisioner.apply(aspects=aspects)

    plan = provisioner.plan(aspects=aspects)
    create_or_update = [
        a for a in plan.actions
        if a.intent in (PlannedActionIntent.CREATE.value,
                        PlannedActionIntent.UPDATE.value)
        and a.resource_kind in ("network", "subnet", "sg", "keypair",
                                "instance", "volume")
    ]
    assert len(create_or_update) == 0
    return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_apply_then_apply_is_idempotent(client, venue, aspects) -> None:
    """
        A second apply creates nothing and skips everything from the first.
    """
    spec = basic_spec()
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    provisioner.apply(aspects=aspects)
    vm_count_after_first = len(client.state.vms)

    second = provisioner.apply(aspects=aspects)

    created_compute = [r for r in second.created
                       if r.kind in ("network", "subnet", "sg", "keypair",
                                     "instance", "volume")]
    assert len(created_compute) == 0
    assert len(client.state.vms) == vm_count_after_first
    return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_apply_with_vpn_renders_user_data(client, venue, aspects) -> None:
    """
        An instance carrying vpn_join receives a cloud-init user-data
        document in its Nebius metadata.
    """
    spec = basic_spec(with_vpn=True)
    control_plane = _RecordingControlPlane()
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec,
                                         vpn_control_plane=control_plane)
    provisioner.apply(aspects=aspects)

    vm = client.state.vms[0]
    assert vm.metadata is not None
    user_data = vm.metadata.get("user-data", "")
    assert user_data.startswith("#cloud-config")
    assert "tailscale" in user_data
    return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_destroy_reverses_apply(client, venue, aspects,
                                confirm_aspects) -> None:
    """
        Destroy removes every resource an apply created.
    """
    spec = basic_spec()
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    provisioner.apply(aspects=aspects)
    assert len(client.state.vms) == 1

    provisioner.destroy(aspects=confirm_aspects)

    assert len(client.state.vms) == 0
    assert len(client.state.vpcs) == 0
    assert len(client.state.subnets) == 0
    assert len(client.state.security_groups) == 0
    assert len(client.state.disks) == 0
    return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_destroy_calls_control_plane_delete_device(client, venue, aspects,
                                                   confirm_aspects) -> None:
    """
        Destroying a VPN-joined deployment de-registers each device.
    """
    spec = basic_spec(with_vpn=True)
    control_plane = _RecordingControlPlane()
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec,
                                         vpn_control_plane=control_plane)
    provisioner.apply(aspects=aspects)
    provisioner.record_vpn_device(instance_name="inst-a",
                                  device_id="dev-001")

    provisioner.destroy(aspects=confirm_aspects)

    assert "dev-001" in control_plane.deleted
    return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_inventory_lists_run_resources(client, venue, aspects) -> None:
    """
        Inventory enumerates the run-id-labelled resources.
    """
    spec = basic_spec()
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    provisioner.apply(aspects=aspects)

    inventory = provisioner.inventory(aspects=aspects)
    kinds = {r.kind for r in inventory}
    assert {"network", "subnet", "sg", "instance",
            "volume"}.issubset(kinds)
    return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_gpu_cluster_grouping(client, venue, aspects) -> None:
    """
        Two instances sharing an IB interconnect group land in one GPU
        Cluster.
    """
    spec = gpu_cluster_spec()
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    provisioner.apply(aspects=aspects)

    assert len(client.state.placement_groups) == 1
    cluster_id = client.state.placement_groups[0].id
    for vm in client.state.vms:
        assert vm.placement_group_id == cluster_id
    return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_gpu_sku_resolution(client, venue, aspects) -> None:
    """
        A GPU instance resolves the H100_SXM accelerator to its Nebius SKU.
    """
    spec = gpu_cluster_spec()
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    provisioner.apply(aspects=aspects)

    vm = client.state.vms[0]
    assert vm.preset == "gpu-h100-sxm-8"
    assert vm.platform == "gpu-h100-sxm"
    return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_shared_fs_attach(client, venue, aspects) -> None:
    """
        A shared filesystem is attached (not provisioned) during apply.
    """
    spec = gpu_cluster_spec()
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    result = provisioner.apply(aspects=aspects)

    fs_resources = [r for r in result.created
                    if r.kind == "shared_filesystem"]
    assert len(fs_resources) == 1
    assert fs_resources[0].venue_id == "fs-pre-existing"
    return
