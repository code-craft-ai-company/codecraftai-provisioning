"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Plan / apply / destroy / inventory lifecycle tests for the
               Lambda Labs venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import json
import os

import pytest

from automojo.provisioning.venues.lambdalabs.lambdalabscloudprovisioner import (
    LambdalabsCloudProvisioner
)
from automojo.provisioning.venues.lambdalabs.llsidecartag import LlSidecarTag

from ._mockclient import (
    MockLambdalabsClient, RecordingVpnControlPlane
)
from ._specfactory import (
    basic_spec, cluster_spec
)


def _provisioner(*, venue, credential, spec, client=None,
                 vpn_control_plane=None, output_root=".output"):
    """
        Build a LambdalabsCloudProvisioner over a mock client.

        :param venue: The CloudVenue fixture.
        :param credential: The credential fixture.
        :param spec: The LambdalabsSpec under test.
        :param client: Optional shared MockLambdalabsClient.
        :param vpn_control_plane: Optional VPN control-plane double.
        :param output_root: The sidecar/inventory output root.

        :returns: A constructed provisioner.
    """
    if client is None:
        client = MockLambdalabsClient()
    rtnval = LambdalabsCloudProvisioner(
        venue=venue, credential=credential, client=client, spec=spec,
        vpn_control_plane=vpn_control_plane, output_root=output_root,
    )
    return rtnval


def test_plan_create_then_reapply_is_skip(venue, credential, aspects):
    """
        First plan emits CREATE; after apply a re-plan emits SKIP.
    """
    client = MockLambdalabsClient()
    provisioner = _provisioner(venue=venue, credential=credential,
                               spec=basic_spec(), client=client)

    first_plan = provisioner.plan(aspects=aspects)
    creates = [a for a in first_plan.actions if a.intent == "create"]
    assert len(creates) >= 1

    provisioner.apply(aspects=aspects)

    second_plan = provisioner.plan(aspects=aspects)
    instance_actions = [a for a in second_plan.actions
                        if a.resource_kind in ("instance", "cluster")]
    for action in instance_actions:
        assert action.intent == "skip"
    return


def test_apply_launches_instance_and_ssh_key(venue, credential, aspects,
                                             tmp_path):
    """
        Apply registers the SSH key and launches the instance.
    """
    client = MockLambdalabsClient()
    provisioner = _provisioner(venue=venue, credential=credential,
                               spec=basic_spec(), client=client,
                               output_root=str(tmp_path))
    result = provisioner.apply(aspects=aspects)

    kinds = sorted(r.kind for r in result.created)
    assert "instance" in kinds
    assert "keypair" in kinds
    assert client.launch_calls == 1
    return


def test_apply_with_vpn_join_renders_user_data(venue, credential, aspects,
                                               tmp_path):
    """
        Apply with a VPNJoinSpec renders cloud-init into the launch
        user_data and records the VPN device for destroy.
    """
    client = MockLambdalabsClient()
    vpn = RecordingVpnControlPlane()
    provisioner = _provisioner(venue=venue, credential=credential,
                               spec=basic_spec(with_vpn=True), client=client,
                               vpn_control_plane=vpn,
                               output_root=str(tmp_path))
    result = provisioner.apply(aspects=aspects)

    assert len(result.created) >= 1
    records = provisioner.last_vpn_records
    assert len(records) == 1
    assert records[0]["vpn_provider"] == "tailscale"
    return


def test_apply_idempotent_no_mutation_on_reapply(venue, credential, aspects,
                                                 tmp_path):
    """
        A second apply over the same client launches nothing new.
    """
    client = MockLambdalabsClient()
    provisioner = _provisioner(venue=venue, credential=credential,
                               spec=basic_spec(), client=client,
                               output_root=str(tmp_path))
    provisioner.apply(aspects=aspects)
    first_launches = client.launch_calls

    second = provisioner.apply(aspects=aspects)
    assert client.launch_calls == first_launches
    assert "trainer" in second.skipped
    return


def test_apply_cluster_branch_uses_one_click_cluster(venue, credential,
                                                     aspects, tmp_path):
    """
        An InfiniBand instance launches via the 1-Click Cluster API.
    """
    client = MockLambdalabsClient()
    provisioner = _provisioner(venue=venue, credential=credential,
                               spec=cluster_spec(), client=client,
                               output_root=str(tmp_path))
    result = provisioner.apply(aspects=aspects)

    assert client.cluster_calls == 1
    assert client.launch_calls == 0
    cluster_resources = [r for r in result.created if r.kind == "cluster"]
    assert len(cluster_resources) == 1
    return


def test_destroy_terminates_and_cleans_vpn(venue, credential, aspects,
                                           confirm_aspects, tmp_path):
    """
        Destroy terminates the instance and de-registers the VPN device.
    """
    client = MockLambdalabsClient()
    vpn = RecordingVpnControlPlane()
    provisioner = _provisioner(venue=venue, credential=credential,
                               spec=basic_spec(with_vpn=True), client=client,
                               vpn_control_plane=vpn,
                               output_root=str(tmp_path))
    provisioner.apply(aspects=aspects)

    # Seed the captured VPN record with a device id the destroy must clean.
    records = provisioner._last_vpn_records
    records[0]["vpn_device_id"] = "device-abc"

    provisioner.destroy(aspects=confirm_aspects)
    assert len(client.list_instances(aspects=aspects)) == 0
    assert "device-abc" in vpn.deleted_device_ids
    return


def test_destroy_requires_confirm(venue, credential, aspects, tmp_path):
    """
        Destroy without confirm raises before any termination.
    """
    client = MockLambdalabsClient()
    provisioner = _provisioner(venue=venue, credential=credential,
                               spec=basic_spec(), client=client,
                               output_root=str(tmp_path))
    provisioner.apply(aspects=aspects)
    with pytest.raises(Exception):
        provisioner.destroy(aspects=aspects)
    assert len(client.list_instances(aspects=aspects)) == 1
    return


def test_inventory_lists_run_resources(venue, credential, aspects,
                                       tmp_path):
    """
        Inventory enumerates run-owned instances and persists a snapshot.
    """
    client = MockLambdalabsClient()
    provisioner = _provisioner(venue=venue, credential=credential,
                               spec=basic_spec(tags=[{"team": "ml"}]),
                               client=client, output_root=str(tmp_path))
    provisioner.apply(aspects=aspects)

    resources = provisioner.inventory(aspects=aspects)
    assert len(resources) == 1
    assert resources[0].kind == "instance"
    assert resources[0].tags == [{"team": "ml"}]

    snapshot = os.path.join(str(tmp_path), "provisioning", "testrun01",
                            "lambdalabs-inventory.json")
    assert os.path.exists(snapshot) is True
    with open(snapshot, "r", encoding="utf-8") as fh:
        document = json.load(fh)
    assert len(document) == 1
    return


def test_apply_writes_sidecar_tags(venue, credential, aspects, tmp_path):
    """
        Apply records neutral tags in the sidecar JSON keyed by instance id.
    """
    client = MockLambdalabsClient()
    provisioner = _provisioner(venue=venue, credential=credential,
                               spec=basic_spec(tags=[{"env": "test"}]),
                               client=client, output_root=str(tmp_path))
    result = provisioner.apply(aspects=aspects)

    instance_resource = [r for r in result.created
                         if r.kind == "instance"][0]
    sidecar = LlSidecarTag(runid="testrun01", output_root=str(tmp_path))
    recovered = sidecar.read(instance_id=instance_resource.venue_id)
    assert recovered == [{"env": "test"}]
    return
