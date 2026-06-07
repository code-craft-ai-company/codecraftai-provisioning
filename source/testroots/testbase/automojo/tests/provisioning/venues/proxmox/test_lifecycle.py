"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Plan / apply / destroy / inventory lifecycle tests for the
               Proxmox VE venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import json
import os

import pytest

from ccai.provisioning.model.exceptions import SchemaSemanticError

from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from ccai.provisioning.venues.proxmox.proxmoxcloudprovisioner import (
    ProxmoxCloudProvisioner
)
from ccai.provisioning.venues.proxmox.pveerrors import (
    ConfirmationRequiredError
)

from ._mockclient import MockProxmoxClient, RecordingVpnControlPlane
from ._specfactory import basic_spec, make_credential, make_resolver, \
    resized_spec, volume_spec


def _provisioner(*, venue, spec, client=None, vpn_control_plane=None,
                 output_root=".output"):
    """
        Build a ProxmoxCloudProvisioner over a mock client.

        :param venue: The CloudVenue fixture.
        :param spec: The ProxmoxSpec under test.
        :param client: Optional shared MockProxmoxClient.
        :param vpn_control_plane: Optional VPN control-plane double.
        :param output_root: The inventory output root.

        :returns: A constructed provisioner.
    """
    effective_client = client
    if effective_client is None:
        effective_client = MockProxmoxClient()
    rtnval = ProxmoxCloudProvisioner(
        venue=venue, credential=make_credential(),
        client=effective_client, spec=spec, resolver=make_resolver(),
        vpn_control_plane=vpn_control_plane, output_root=output_root,
    )
    return rtnval


def test_plan_all_create_then_reapply_is_skip(venue, aspects):
    """
        First plan emits CREATE for every resource; after apply a re-plan
        emits SKIP for the network and VM.
    """
    client = MockProxmoxClient()
    provisioner = _provisioner(venue=venue, spec=basic_spec(),
                               client=client)

    first_plan = provisioner.plan(aspects=aspects)
    creates = [a for a in first_plan.actions
               if a.intent == PlannedActionIntent.CREATE.value]
    assert len(creates) == len(first_plan.actions)
    assert len(creates) >= 2

    provisioner.apply(aspects=aspects)

    second_plan = provisioner.plan(aspects=aspects)
    for action in second_plan.actions:
        assert action.intent == PlannedActionIntent.SKIP.value
    return


def test_apply_creates_network_and_vm(venue, aspects, tmp_path):
    """
        Apply realises the bridge, clones the VM, attaches the disk, and
        powers the VM on.
    """
    client = MockProxmoxClient()
    provisioner = _provisioner(venue=venue, spec=volume_spec(),
                               client=client, output_root=str(tmp_path))
    result = provisioner.apply(aspects=aspects)

    kinds = sorted(r.kind for r in result.created)
    assert "network" in kinds
    assert "instance" in kinds
    assert client.clone_vm_calls == 1
    assert client.create_bridge_calls == 1
    assert client.attach_disk_calls == 1

    vms = client.all_vms()
    assert len(vms) == 1
    assert vms[0].status == "running"
    return


def test_apply_with_vpn_join_carries_cloud_init(venue, aspects, tmp_path):
    """
        Apply with a VPNJoinSpec renders the cloud-init snippet, uploads it
        as a Proxmox snippet, sets the VM cicustom reference, and records
        the VPN device for destroy.
    """
    client = MockProxmoxClient()
    vpn = RecordingVpnControlPlane()
    provisioner = _provisioner(venue=venue, spec=basic_spec(with_vpn=True),
                               client=client, vpn_control_plane=vpn,
                               output_root=str(tmp_path))
    result = provisioner.apply(aspects=aspects)

    assert len(result.created) >= 1
    records = provisioner.last_vpn_records
    assert len(records) == 1
    assert records[0]["vpn_provider"] == "tailscale"

    # A snippet was uploaded and referenced on the VM cicustom slot.
    assert client.upload_snippet_calls == 1
    assert len(client.snippets_state) == 1
    snippet_body = list(client.snippets_state.values())[0]
    assert snippet_body.startswith("#cloud-config")

    vmid = list(client.vms_state.keys())[0]
    cicustom = client.vms_state[vmid].get("cicustom", None)
    assert cicustom is not None
    assert cicustom.startswith("user=")
    return


def test_apply_idempotent_no_mutation_on_reapply(venue, aspects, tmp_path):
    """
        A second apply over the same client clones nothing new and reports
        the instance as skipped.
    """
    client = MockProxmoxClient()
    provisioner = _provisioner(venue=venue, spec=basic_spec(),
                               client=client, output_root=str(tmp_path))
    provisioner.apply(aspects=aspects)
    first_clone_calls = client.clone_vm_calls

    second = provisioner.apply(aspects=aspects)
    assert client.clone_vm_calls == first_clone_calls
    assert "node" in second.skipped
    return


def test_apply_realises_vm_drift_by_recreate(venue, confirm_aspects,
                                             tmp_path):
    """
        Apply over a venue carrying a size-drifted VM realises the
        UPDATE by-recreate — the stale VM is stopped + destroyed and a
        fresh VM is cloned at the desired hardware shape; the result
        carries it in ``updated``.
    """
    client = MockProxmoxClient()
    baseline = _provisioner(venue=venue, spec=basic_spec(), client=client,
                            output_root=str(tmp_path))
    baseline.apply(aspects=confirm_aspects)
    first_clone_calls = client.clone_vm_calls

    drifted = _provisioner(venue=venue, spec=resized_spec(size="large"),
                           client=client, output_root=str(tmp_path))
    result = drifted.apply(aspects=confirm_aspects)

    assert client.clone_vm_calls == first_clone_calls + 1
    assert client.destroy_vm_calls == 1
    updated_names = [r.name for r in result.updated]
    assert updated_names == ["node"]
    assert result.updated[0].attributes["cores"] == 8

    vms = client.all_vms()
    assert len(vms) == 1
    assert int(vms[0].cpus) == 8
    return


def test_replan_after_recreate_emits_skip(venue, confirm_aspects, tmp_path):
    """
        A second apply after an UPDATE-by-recreate emits SKIP — the
        idempotent contract is preserved.
    """
    client = MockProxmoxClient()
    baseline = _provisioner(venue=venue, spec=basic_spec(), client=client,
                            output_root=str(tmp_path))
    baseline.apply(aspects=confirm_aspects)

    drifted = _provisioner(venue=venue, spec=resized_spec(size="large"),
                           client=client, output_root=str(tmp_path))
    drifted.apply(aspects=confirm_aspects)

    plan = drifted.plan(aspects=confirm_aspects)
    instance_actions = [a for a in plan.actions
                        if a.resource_kind == "instance"]
    assert len(instance_actions) == 1
    assert instance_actions[0].intent == "skip"

    second = drifted.apply(aspects=confirm_aspects)
    assert "node" in second.skipped
    assert len(second.updated) == 0
    return


def test_unconfirmed_drifted_apply_requires_confirm(venue, aspects,
                                                    tmp_path):
    """
        An UPDATE-by-recreate without aspects.confirm raises
        ConfirmationRequiredError — consistent with the venue's DELETE /
        destroy gating.
    """
    client = MockProxmoxClient()
    baseline = _provisioner(venue=venue, spec=basic_spec(), client=client,
                            output_root=str(tmp_path))
    baseline.apply(aspects=aspects)

    drifted = _provisioner(venue=venue, spec=resized_spec(size="large"),
                           client=client, output_root=str(tmp_path))
    with pytest.raises(ConfirmationRequiredError):
        drifted.apply(aspects=aspects)

    assert client.destroy_vm_calls == 0
    return


def test_destroy_tears_down_and_cleans_vpn(venue, aspects, confirm_aspects,
                                           tmp_path):
    """
        Destroy stops and deletes the VM and de-registers the VPN device.
    """
    client = MockProxmoxClient()
    vpn = RecordingVpnControlPlane()
    provisioner = _provisioner(venue=venue, spec=basic_spec(with_vpn=True),
                               client=client, vpn_control_plane=vpn,
                               output_root=str(tmp_path))
    provisioner.apply(aspects=aspects)
    assert len(client.all_vms()) == 1

    provisioner.destroy(aspects=confirm_aspects)
    assert len(client.all_vms()) == 0
    assert client.destroy_vm_calls == 1
    assert len(vpn.deleted_device_ids) == 1
    assert vpn.deleted_device_ids[0] == "node"
    return


def test_destroy_requires_confirm(venue, aspects, tmp_path):
    """
        Destroy without confirm raises before any teardown.
    """
    client = MockProxmoxClient()
    provisioner = _provisioner(venue=venue, spec=basic_spec(),
                               client=client, output_root=str(tmp_path))
    provisioner.apply(aspects=aspects)
    with pytest.raises(SchemaSemanticError):
        provisioner.destroy(aspects=aspects)
    assert len(client.all_vms()) == 1
    return


def test_inventory_lists_run_resources(venue, aspects, tmp_path):
    """
        Inventory enumerates run-owned VMs, recovers neutral tags, and
        persists a snapshot under the run output directory.
    """
    client = MockProxmoxClient()
    provisioner = _provisioner(venue=venue,
                               spec=basic_spec(tags={"team": "ml"}),
                               client=client, output_root=str(tmp_path))
    provisioner.apply(aspects=aspects)

    resources = provisioner.inventory(aspects=aspects)
    assert len(resources) == 1
    assert resources[0].kind == "instance"
    assert resources[0].tags == {"team": "ml"}

    snapshot = os.path.join(str(tmp_path), "provisioning", "testrun01",
                            "pve-inventory.json")
    assert os.path.exists(snapshot) is True
    with open(snapshot, "r", encoding="utf-8") as fh:
        document = json.load(fh)
    assert len(document) == 1
    return


def test_apply_none_spec_is_empty_result(venue, aspects):
    """
        A provisioner with no spec yields an empty apply result.
    """
    provisioner = _provisioner(venue=venue, spec=None,
                               client=MockProxmoxClient())
    result = provisioner.apply(aspects=aspects)
    assert len(result.created) == 0
    return
