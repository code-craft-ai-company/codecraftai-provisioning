"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: End-to-end validate/plan/apply/destroy/inventory tests for the
        VSphere venue against a MockVSphereOps facade.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import pytest

from hypothesis import given, settings, strategies as st

from automojo.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from automojo.provisioning.venues.vsphere.vspherecloudprovisioner import (
    VSphereCloudProvisioner
)
from automojo.provisioning.venues.vsphere.vserrors import VsCapacityError
from automojo.provisioning.venues.vsphere.vspherevenueconfig import (
    VSphereVenueConfig
)

from ._mockvsphere import MockVSphereOps
from ._specfactory import basic_spec


def _provisioner(*, venue, credential, config, spec, ops=None,
                 vpn_control_plane=None):
    """
        Helper: build a provisioner backed by a mock ops facade.
    """
    if ops is None:
        ops = MockVSphereOps(library_items={"ubuntu-22.04": "item-ubuntu"})
    rtnval = VSphereCloudProvisioner(
        venue=venue, credential=credential, config=config, spec=spec,
        ops=ops, vpn_control_plane=vpn_control_plane,
    )
    return rtnval


class _RecordingVPN:
    """
        Minimal mock IVPNControlPlane recording delete_device calls.
    """

    def __init__(self) -> None:
        """
            Construct.
        """
        self.deleted_ids: list = []
        self.minted_authkey: str = "tskey-test-vsphere"
        return

    def delete_device(self, *, device_id: str, aspects) -> None:
        """
            Record the deletion.
        """
        self.deleted_ids.append(device_id)
        return


def test_plan_then_apply_creates_resources(venue, credential, config,
                                           aspects) -> None:
    """
        First plan reports CREATEs; apply produces matching resources.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               config=config, spec=spec)

    plan = provisioner.plan(aspects=aspects)
    intents = [a.intent for a in plan.actions]
    assert PlannedActionIntent.CREATE.value in intents

    result = provisioner.apply(aspects=aspects)
    kinds = {r.kind for r in result.created}
    assert {"subnet", "instance", "volume"}.issubset(kinds)
    return


def test_apply_idempotent_replan_all_skip(venue, credential, config,
                                          aspects) -> None:
    """
        Re-applying makes no new VM/port-group mutations; replan is all-SKIP.
    """
    spec = basic_spec()
    ops = MockVSphereOps(library_items={"ubuntu-22.04": "item-ubuntu"})
    provisioner = _provisioner(venue=venue, credential=credential,
                               config=config, spec=spec, ops=ops)

    provisioner.apply(aspects=aspects)
    create_calls_first = [c for c in ops.calls
                          if c.startswith(("create_port_group",
                                           "deploy_library_item",
                                           "create_vm"))]
    assert len(create_calls_first) > 0

    ops.calls.clear()
    second = provisioner.apply(aspects=aspects)
    create_calls_second = [c for c in ops.calls
                           if c.startswith(("create_port_group",
                                            "deploy_library_item",
                                            "create_vm"))]
    assert len(create_calls_second) == 0
    assert "pg-a" in second.skipped
    assert "inst-a" in second.skipped

    plan = provisioner.plan(aspects=aspects)
    creates = [a for a in plan.actions
               if a.intent == PlannedActionIntent.CREATE.value
               and a.resource_kind in ("subnet", "instance")]
    assert len(creates) == 0
    return


def test_apply_with_vpn_join_carries_cloud_init(venue, credential, config,
                                                aspects) -> None:
    """
        An instance with vpn_join carries the tailscale cloud-init body in
        the guest-customisation payload.
    """
    spec = basic_spec(with_vpn=True)
    ops = MockVSphereOps(library_items={"ubuntu-22.04": "item-ubuntu"})
    vpn = _RecordingVPN()
    provisioner = _provisioner(venue=venue, credential=credential,
                               config=config, spec=spec, ops=ops,
                               vpn_control_plane=vpn)
    result = provisioner.apply(aspects=aspects)

    vm_resource = None
    for resource in result.created:
        if resource.kind == "instance":
            vm_resource = resource
    assert vm_resource is not None

    customization = ops.customization_for(vm_id=vm_resource.venue_id)
    assert customization is not None
    body = customization["cloud_init_user_data"]
    assert "#cloud-config" in body
    assert "tailscale" in body
    assert "bringup" in body
    assert "vm-inst-a" == customization["hostname"]
    return


def test_destroy_requires_confirm(venue, credential, config,
                                  aspects) -> None:
    """
        destroy without aspects.confirm=True raises.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               config=config, spec=spec)
    provisioner.apply(aspects=aspects)
    with pytest.raises(Exception):
        provisioner.destroy(aspects=aspects)
    return


def test_destroy_reverses_apply(venue, credential, config, aspects,
                                confirm_aspects) -> None:
    """
        After destroy the run inventory comes back empty.
    """
    spec = basic_spec()
    ops = MockVSphereOps(library_items={"ubuntu-22.04": "item-ubuntu"})
    provisioner = _provisioner(venue=venue, credential=credential,
                               config=config, spec=spec, ops=ops)
    provisioner.apply(aspects=aspects)
    inventory_before = provisioner.inventory(aspects=aspects)
    assert len(inventory_before) > 0

    provisioner.destroy(aspects=confirm_aspects)

    inventory_after = provisioner.inventory(aspects=aspects)
    assert len(inventory_after) == 0
    return


def test_destroy_calls_vpn_delete_device(venue, credential, config, aspects,
                                         confirm_aspects) -> None:
    """
        destroy de-registers a recorded VPN device from the control plane.
    """
    spec = basic_spec(with_vpn=True)
    vpn = _RecordingVPN()
    provisioner = _provisioner(venue=venue, credential=credential,
                               config=config, spec=spec,
                               vpn_control_plane=vpn)
    provisioner.apply(aspects=aspects)
    provisioner.record_vpn_device(instance_name="inst-a",
                                  device_id="vsphere-device-1")

    provisioner.destroy(aspects=confirm_aspects)
    assert "vsphere-device-1" in vpn.deleted_ids
    return


def test_content_library_clone_path(venue, credential, config,
                                    aspects) -> None:
    """
        A library-resolvable image clones via deploy_library_item.
    """
    spec = basic_spec()
    ops = MockVSphereOps(library_items={"ubuntu-22.04": "item-ubuntu"})
    provisioner = _provisioner(venue=venue, credential=credential,
                               config=config, spec=spec, ops=ops)
    result = provisioner.apply(aspects=aspects)

    deploy_calls = [c for c in ops.calls
                    if c.startswith("deploy_library_item")]
    assert len(deploy_calls) == 1
    inst = [r for r in result.created if r.kind == "instance"][0]
    assert inst.attributes["provisioned_via"] == "content-library"
    return


def test_template_fallback_path(venue, credential, config, aspects) -> None:
    """
        When no library item matches, the folder-template fallback is used
        and the VM is built via VmCreateSpec.
    """
    spec = basic_spec()
    ops = MockVSphereOps(library_items={},
                         template_names=["ubuntu-22.04"])
    provisioner = _provisioner(venue=venue, credential=credential,
                               config=config, spec=spec, ops=ops)
    result = provisioner.apply(aspects=aspects)

    assert any(c.startswith("find_template_vm") for c in ops.calls)
    assert any(c.startswith("create_vm") for c in ops.calls)
    inst = [r for r in result.created if r.kind == "instance"][0]
    assert inst.attributes["provisioned_via"] == "vm-create-spec"
    return


def test_datastore_selection_used_for_disk(venue, credential, config,
                                           aspects) -> None:
    """
        Disk attach picks a datastore via find_datastore_with_free_gb.
    """
    spec = basic_spec()
    ops = MockVSphereOps(library_items={"ubuntu-22.04": "item-ubuntu"})
    provisioner = _provisioner(venue=venue, credential=credential,
                               config=config, spec=spec, ops=ops)
    provisioner.apply(aspects=aspects)

    assert any(c.startswith("find_datastore_with_free_gb")
               for c in ops.calls)
    assert len(ops.disks) == 1
    assert ops.disks[0]["size_gb"] == 64
    return


def test_datastore_capacity_failure(venue, credential, config,
                                    aspects) -> None:
    """
        When no datastore meets the size ask, apply fails with a capacity
        error.
    """
    spec = basic_spec()
    ops = MockVSphereOps(library_items={"ubuntu-22.04": "item-ubuntu"},
                         datastore_free_gb=1.0)
    provisioner = _provisioner(venue=venue, credential=credential,
                               config=config, spec=spec, ops=ops)
    with pytest.raises(VsCapacityError):
        provisioner.apply(aspects=aspects)
    return


@settings(max_examples=25, deadline=None)
@given(size=st.sampled_from(["tiny", "small", "medium", "large", "xlarge"]))
def test_apply_idempotence_property(size) -> None:
    """
        Property: apply ∘ apply == apply.  The second apply creates nothing
        new and skips every VM/subnet for any instance size.
    """
    from automojo.credentials.vspherecredential import VSphereCredential
    from automojo.provisioning.model.cloud.cloudvenue import CloudVenue

    venue = CloudVenue(
        name="vsphere-prop", provider="vsphere",
        endpoint="https://vcenter.lab",
        region="homelab", credential="vsphere-prop",
    )
    credential = VSphereCredential(
        identifier="vsphere-prop", categories=["vm-venue", "vsphere-basic"],
        username="administrator@vsphere.local", password="secret-value",
    )
    config = VSphereVenueConfig(
        host="vcenter.lab", datacenter="DC1", cluster="Cluster1",
        folder="/DC1/vm/automojo", content_library_ids=["lib-1"],
        subnet_vlan_ids={"pg-a": 1020},
    )
    from automojo.provisioning.aspects.provisioningaspects import (
        ProvisioningAspects
    )
    aspects = ProvisioningAspects(runid="prop01", verify_interval=0.01)

    spec = basic_spec(instance_size=size)
    ops = MockVSphereOps(library_items={"ubuntu-22.04": "item-ubuntu"})
    provisioner = VSphereCloudProvisioner(
        venue=venue, credential=credential, config=config, spec=spec,
        ops=ops,
    )

    first = provisioner.apply(aspects=aspects)
    first_created = len(first.created)
    assert first_created > 0

    second = provisioner.apply(aspects=aspects)
    assert len(second.created) == 0
    assert "inst-a" in second.skipped
    assert "pg-a" in second.skipped
    return
