"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Plan / apply / destroy / inventory lifecycle tests for the
        XCP-ng venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import base64

from automojo.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
import pytest

from automojo.provisioning.venues.xcpng.xcpngcloudprovisioner import (
    XcpngCloudProvisioner
)
from automojo.provisioning.venues.xcpng.xencloudinitrenderer import (
    XENSTORE_USERDATA_KEY
)
from automojo.provisioning.venues.xcpng.xenerrors import (
    ConfirmationRequiredError
)

from ._mockclient import MockXenClient, RecordingVpnControlPlane
from ._specfactory import basic_spec, resized_spec


def _provisioner(*, venue, spec, client=None, vpn=None):
    """
        Build an XcpngCloudProvisioner over a mock client.

        :param venue: The CloudVenue fixture.
        :param spec: The XcpngSpec under test.
        :param client: Optional MockXenClient; a fresh one is built when
                       omitted.
        :param vpn: Optional vpn-control-plane test double.

        :returns: A constructed provisioner.
    """
    effective_client = client if client is not None else MockXenClient()
    rtnval = XcpngCloudProvisioner(venue=venue, client=effective_client,
                                   spec=spec, vpn_control_plane=vpn,
                                   output_root=".output")
    return rtnval


def test_plan_creates_instance_on_empty_venue(venue, aspects):
    """
        Plan against a venue with no VMs yields CREATE for the instance and
        SKIP for the pre-existing seeded network.
    """
    provisioner = _provisioner(venue=venue, spec=basic_spec())
    plan = provisioner.plan(aspects=aspects)

    by_kind = {a.resource_kind: a.intent for a in plan.actions}
    assert by_kind["instance"] == PlannedActionIntent.CREATE.value
    assert by_kind["network"] == PlannedActionIntent.SKIP.value
    return


def test_apply_creates_vm_and_starts_it(venue, aspects):
    """
        Apply clones the VM from the Template and leaves it Running.
    """
    client = MockXenClient()
    provisioner = _provisioner(venue=venue, spec=basic_spec(), client=client)
    result = provisioner.apply(aspects=aspects)

    assert len(result.created) == 1
    vm_uuid = result.created[0].venue_id
    assert client.vms[vm_uuid].power_state == "Running"
    assert client.clone_calls == 1
    assert client.start_calls == 1
    return


def test_apply_re_plan_is_all_skip(venue, aspects):
    """
        After apply, a re-plan reports SKIP for every action.
    """
    client = MockXenClient()
    provisioner = _provisioner(venue=venue, spec=basic_spec(), client=client)
    provisioner.apply(aspects=aspects)

    plan = provisioner.plan(aspects=aspects)
    intents = set(a.intent for a in plan.actions)
    assert intents == {PlannedActionIntent.SKIP.value}
    return


def test_apply_realises_vm_drift_by_recreate(venue, confirm_aspects):
    """
        Apply over a venue carrying a size-drifted VM realises the
        UPDATE by-recreate — the stale VM is shut down + destroyed and a
        fresh VM is cloned at the desired hardware shape; the result
        carries it in ``updated``.
    """
    client = MockXenClient()
    baseline = _provisioner(venue=venue, spec=basic_spec(), client=client)
    baseline.apply(aspects=confirm_aspects)
    first_clone_calls = client.clone_calls

    drifted = _provisioner(venue=venue, spec=resized_spec(size="large"),
                           client=client)
    result = drifted.apply(aspects=confirm_aspects)

    assert client.clone_calls == first_clone_calls + 1
    updated_names = [r.name for r in result.updated]
    assert updated_names == ["worker"]
    assert result.updated[0].attributes["vcpus"] == 4

    assert len(client.vms) == 1
    live_vm = list(client.vms.values())[0]
    assert live_vm.vcpus_max == 4
    return


def test_replan_after_recreate_emits_skip(venue, confirm_aspects):
    """
        A second apply after an UPDATE-by-recreate emits SKIP — the
        idempotent contract is preserved.
    """
    client = MockXenClient()
    baseline = _provisioner(venue=venue, spec=basic_spec(), client=client)
    baseline.apply(aspects=confirm_aspects)

    drifted = _provisioner(venue=venue, spec=resized_spec(size="large"),
                           client=client)
    drifted.apply(aspects=confirm_aspects)

    plan = drifted.plan(aspects=confirm_aspects)
    instance_actions = [a for a in plan.actions
                        if a.resource_kind == "instance"]
    assert len(instance_actions) == 1
    assert instance_actions[0].intent == "skip"

    second = drifted.apply(aspects=confirm_aspects)
    assert "worker" in second.skipped
    assert len(second.updated) == 0
    return


def test_unconfirmed_drifted_apply_requires_confirm(venue, aspects):
    """
        An UPDATE-by-recreate without aspects.confirm raises
        ConfirmationRequiredError — consistent with DELETE gating.
    """
    client = MockXenClient()
    baseline = _provisioner(venue=venue, spec=basic_spec(), client=client)
    baseline.apply(aspects=aspects)

    drifted = _provisioner(venue=venue, spec=resized_spec(size="large"),
                           client=client)
    with pytest.raises(ConfirmationRequiredError):
        drifted.apply(aspects=aspects)

    assert len(client.vms) == 1
    return


def test_apply_with_vpn_join_pushes_cloud_init(venue, aspects):
    """
        An instance carrying vpn_join gets a base64 cloud-init payload
        pushed through the xenstore vm-data/cloud-init key.
    """
    client = MockXenClient()
    vpn = RecordingVpnControlPlane(minted_authkey="tskey-lifecycle")
    provisioner = _provisioner(venue=venue, spec=basic_spec(with_vpn=True),
                               client=client, vpn=vpn)
    result = provisioner.apply(aspects=aspects)

    vm_uuid = result.created[0].venue_id
    xenstore = client.xenstore[vm_uuid]
    assert XENSTORE_USERDATA_KEY in xenstore
    decoded = base64.b64decode(xenstore[XENSTORE_USERDATA_KEY]).decode(
        "utf-8")
    assert decoded.startswith("#cloud-config")
    assert "tailscale" in decoded
    return


def test_apply_attaches_volume_as_vdi(venue, aspects):
    """
        A spec volume is realised as a VDI and attached through a VBD.
    """
    client = MockXenClient()
    provisioner = _provisioner(venue=venue,
                               spec=basic_spec(with_volume=True),
                               client=client)
    result = provisioner.apply(aspects=aspects)

    vm_uuid = result.created[0].venue_id
    assert len(client.vdis) == 1
    attached_vbds = [v for v in client.vbds.values()
                     if v.vm_uuid == vm_uuid]
    assert len(attached_vbds) == 1
    return


def test_apply_attaches_vif_to_named_network(venue, aspects):
    """
        Apply attaches the VM to the network named by the instance subnet.
    """
    client = MockXenClient()
    provisioner = _provisioner(venue=venue, spec=basic_spec(), client=client)
    result = provisioner.apply(aspects=aspects)

    vm_uuid = result.created[0].venue_id
    vifs = [v for v in client.vifs.values() if v.vm_uuid == vm_uuid]
    assert len(vifs) == 1
    assert vifs[0].network_uuid == "net-lab"
    return


def test_destroy_shuts_down_and_destroys_vms(venue, aspects,
                                             confirm_aspects):
    """
        Destroy clean-shuts-down and destroys the run-owned VM.
    """
    client = MockXenClient()
    provisioner = _provisioner(venue=venue, spec=basic_spec(), client=client)
    provisioner.apply(aspects=aspects)
    assert len(client.vms) == 1

    provisioner.destroy(aspects=confirm_aspects)
    assert len(client.vms) == 0
    return


def test_destroy_without_confirm_raises(venue, aspects):
    """
        Destroy without aspects.confirm raises before any teardown.
    """
    import pytest

    from automojo.provisioning.model.exceptions import SchemaSemanticError

    client = MockXenClient()
    provisioner = _provisioner(venue=venue, spec=basic_spec(), client=client)
    provisioner.apply(aspects=aspects)
    with pytest.raises(SchemaSemanticError):
        provisioner.destroy(aspects=aspects)
    assert len(client.vms) == 1
    return


def test_destroy_invokes_tailscale_device_cleanup(venue, aspects,
                                                  confirm_aspects):
    """
        Destroy of a VPN-joined VM de-registers the VPN device.
    """
    client = MockXenClient()
    vpn = RecordingVpnControlPlane()
    provisioner = _provisioner(venue=venue, spec=basic_spec(with_vpn=True),
                               client=client, vpn=vpn)
    provisioner.apply(aspects=aspects)
    provisioner.destroy(aspects=confirm_aspects)
    assert len(vpn.deleted_device_ids) == 1
    return


def test_destroy_removes_attached_vdis(venue, aspects, confirm_aspects):
    """
        Destroy removes the run-attached VDIs along with the VM.
    """
    client = MockXenClient()
    provisioner = _provisioner(venue=venue,
                               spec=basic_spec(with_volume=True),
                               client=client)
    provisioner.apply(aspects=aspects)
    assert len(client.vdis) == 1

    provisioner.destroy(aspects=confirm_aspects)
    assert len(client.vdis) == 0
    return


def test_inventory_enumerates_run_owned_vms(venue, aspects):
    """
        Inventory enumerates the run-id-tagged VM and recovers its tags.
    """
    client = MockXenClient()
    spec = basic_spec(tags={"team": "qa"})
    provisioner = _provisioner(venue=venue, spec=spec, client=client)
    provisioner.apply(aspects=aspects)

    resources = provisioner.inventory(aspects=aspects)
    assert len(resources) == 1
    assert resources[0].kind == "instance"
    assert resources[0].tags.get("team") == "qa"
    return
