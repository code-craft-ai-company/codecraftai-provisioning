"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Plan / apply / destroy / inventory lifecycle tests for the
               libvirt venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase


import json
import os


from ccai.interfaces.schemasemanticerror import SchemaSemanticError

from ccai.provisioning.venues.libvirt.libvirtcloudprovisioner import (
    LibvirtCloudProvisioner
)
from ccai.provisioning.venues.libvirt.lverrors import (
    ConfirmationRequiredError
)

from ._mockclient import MockLibvirtClient, RecordingVpnControlPlane
from ._specfactory import (
    BASE_IMAGE_VOLUME, basic_spec, make_config, resized_spec, volume_spec
)


def _provisioner(*, venue, spec, client=None, vpn_control_plane=None,
                 output_root=".output"):
    """
        Build a LibvirtCloudProvisioner over a mock client.

        :param venue: The CloudVenue fixture.
        :param spec: The LibvirtSpec under test.
        :param client: Optional shared MockLibvirtClient (base image
            seeded by the caller).
        :param vpn_control_plane: Optional VPN control-plane double.
        :param output_root: The inventory output root.

        :returns: A constructed provisioner.
    """
    config = make_config()
    if client is None:
        client = MockLibvirtClient()
        client.seed_base_image(pool=config.base_image_pool,
                               volume_name=BASE_IMAGE_VOLUME)
    rtnval = LibvirtCloudProvisioner(
        venue=venue, client=client, config=config, spec=spec,
        vpn_control_plane=vpn_control_plane, output_root=output_root,
    )
    return rtnval


def _seeded_client():
    """
        Build a MockLibvirtClient with the base image seeded.

        :returns: A seeded MockLibvirtClient.
    """
    config = make_config()
    client = MockLibvirtClient()
    client.seed_base_image(pool=config.base_image_pool,
                           volume_name=BASE_IMAGE_VOLUME)
    rtnval = client
    return rtnval


def test_plan_create_then_reapply_is_skip(venue, aspects):
    """
        First plan emits CREATE; after apply a re-plan emits SKIP.
    """
    client = _seeded_client()
    provisioner = _provisioner(venue=venue, spec=basic_spec(),
                               client=client)

    first_plan = provisioner.plan(aspects=aspects)
    creates = [a for a in first_plan.actions if a.intent == "create"]
    assert len(creates) >= 1

    provisioner.apply(aspects=aspects)

    second_plan = provisioner.plan(aspects=aspects)
    for action in second_plan.actions:
        assert action.intent == "skip"
    return


def test_apply_creates_network_volume_and_domain(venue, aspects, tmp_path):
    """
        Apply defines the network, clones the boot disk, and starts the
        domain.
    """
    client = _seeded_client()
    provisioner = _provisioner(venue=venue, spec=volume_spec(),
                               client=client, output_root=str(tmp_path))
    result = provisioner.apply(aspects=aspects)

    kinds = sorted(r.kind for r in result.created)
    assert "network" in kinds
    assert "instance" in kinds
    assert "volume" in kinds
    assert client.define_domain_calls == 1
    return


def test_apply_with_vpn_join_renders_seed_iso(venue, aspects, tmp_path):
    """
        Apply with a VPNJoinSpec renders cloud-init into the seed ISO and
        records the VPN device for destroy.
    """
    client = _seeded_client()
    vpn = RecordingVpnControlPlane()
    provisioner = _provisioner(venue=venue, spec=basic_spec(with_vpn=True),
                               client=client, vpn_control_plane=vpn,
                               output_root=str(tmp_path))
    result = provisioner.apply(aspects=aspects)

    assert len(result.created) >= 1
    records = provisioner.last_vpn_records
    assert len(records) == 1
    assert records[0]["vpn_provider"] == "tailscale"

    # The seed staging directory should have been written with a
    # user-data document mentioning the tailscale bring-up.
    staged = os.path.join(str(tmp_path), "cidata")
    assert os.path.exists(staged) is True
    return


def test_apply_idempotent_no_mutation_on_reapply(venue, aspects, tmp_path):
    """
        A second apply over the same client defines nothing new.
    """
    client = _seeded_client()
    provisioner = _provisioner(venue=venue, spec=basic_spec(),
                               client=client, output_root=str(tmp_path))
    provisioner.apply(aspects=aspects)
    first_domain_calls = client.define_domain_calls

    second = provisioner.apply(aspects=aspects)
    assert client.define_domain_calls == first_domain_calls
    assert "node" in second.skipped
    return


def test_apply_realises_domain_drift_by_recreate(venue, confirm_aspects,
                                                 tmp_path):
    """
        Apply over a venue carrying a size-drifted domain realises the
        UPDATE by undefining the stale domain and redefining it with the
        desired hardware shape; the result carries it in ``updated``.
    """
    client = _seeded_client()
    baseline = _provisioner(venue=venue, spec=basic_spec(), client=client,
                            output_root=str(tmp_path))
    baseline.apply(aspects=confirm_aspects)
    first_domain_calls = client.define_domain_calls

    drifted = _provisioner(venue=venue, spec=resized_spec(size="large"),
                           client=client, output_root=str(tmp_path))
    result = drifted.apply(aspects=confirm_aspects)

    assert client.define_domain_calls == first_domain_calls + 1
    updated_names = [r.name for r in result.updated]
    assert updated_names == ["node"]
    assert result.updated[0].attributes["vcpus"] == 4

    live = client.domains.list_domains(aspects=confirm_aspects)
    assert len(live) == 1
    assert live[0].vcpus == 4
    return


def test_replan_after_recreate_emits_skip(venue, confirm_aspects, tmp_path):
    """
        A second apply after an UPDATE-by-recreate emits SKIP — the
        idempotent contract is preserved.
    """
    client = _seeded_client()
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
        ConfirmationRequiredError — consistent with DELETE / destroy
        gating.
    """
    client = _seeded_client()
    baseline = _provisioner(venue=venue, spec=basic_spec(), client=client,
                            output_root=str(tmp_path))
    baseline.apply(aspects=aspects)

    drifted = _provisioner(venue=venue, spec=resized_spec(size="large"),
                           client=client, output_root=str(tmp_path))
    with testbase.raises(ConfirmationRequiredError):
        drifted.apply(aspects=aspects)

    live = client.domains.list_domains(aspects=aspects)
    assert live[0].vcpus == 2
    return


def test_destroy_tears_down_and_cleans_vpn(venue, aspects, confirm_aspects,
                                           tmp_path):
    """
        Destroy undefines the domain and de-registers the VPN device.
    """
    client = _seeded_client()
    vpn = RecordingVpnControlPlane()
    provisioner = _provisioner(venue=venue, spec=basic_spec(with_vpn=True),
                               client=client, vpn_control_plane=vpn,
                               output_root=str(tmp_path))
    provisioner.apply(aspects=aspects)

    assert len(client.domains.list_domains(aspects=aspects)) == 1

    provisioner.destroy(aspects=confirm_aspects)
    assert len(client.domains.list_domains(aspects=aspects)) == 0
    assert len(client.networks.list_networks(aspects=aspects)) == 0
    assert len(vpn.deleted_device_ids) == 1
    return


def test_destroy_requires_confirm(venue, aspects, tmp_path):
    """
        Destroy without confirm raises before any teardown.
    """
    client = _seeded_client()
    provisioner = _provisioner(venue=venue, spec=basic_spec(),
                               client=client, output_root=str(tmp_path))
    provisioner.apply(aspects=aspects)
    with testbase.raises(SchemaSemanticError):
        provisioner.destroy(aspects=aspects)
    assert len(client.domains.list_domains(aspects=aspects)) == 1
    return


def test_inventory_lists_run_resources(venue, aspects, tmp_path):
    """
        Inventory enumerates run-owned domains and persists a snapshot.
    """
    client = _seeded_client()
    provisioner = _provisioner(venue=venue,
                               spec=basic_spec(tags={"team": "ml"}),
                               client=client, output_root=str(tmp_path))
    provisioner.apply(aspects=aspects)

    resources = provisioner.inventory(aspects=aspects)
    assert len(resources) == 1
    assert resources[0].kind == "instance"
    assert resources[0].tags == {"team": "ml"}

    snapshot = os.path.join(str(tmp_path), "provisioning", "testrun01",
                            "libvirt-inventory.json")
    assert os.path.exists(snapshot) is True
    with open(snapshot, "r", encoding="utf-8") as fh:
        document = json.load(fh)
    assert len(document) == 1
    return
