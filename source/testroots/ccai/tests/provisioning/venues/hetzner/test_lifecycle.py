"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for HetznerCloudProvisioner plan / apply / destroy /
               inventory.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase

from .factories import (create_client, create_dns_client, create_vpn_control_plane)


import os


from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.provisioning.venues.hetzner.hetznercloudprovisioner import (
    HetznerCloudProvisioner
)
from ccai.provisioning.venues.hetzner.hetznererrors import (
    HetznerValidationError
)
from ccai.provisioning.venues.hetzner.hetznerinventory import (
    HetznerInventory
)

from ._mockclient import MockVpnControlPlane
from ._specfactory import basic_spec


def _provisioner(*, venue, credential, location_config, client, spec,
                 dns_client=None, vpn_control_plane=None
                 ) -> HetznerCloudProvisioner:
    """
        Build a HetznerCloudProvisioner with injected mocks.
    """
    rtnval = HetznerCloudProvisioner(
        venue=venue, credential=credential,
        location_config=location_config, spec=spec, client=client,
        dns_client=dns_client, vpn_control_plane=vpn_control_plane)
    return rtnval


@testbase.attach.parameter(create_client, identifier="client")
def test_plan_all_create_on_empty_venue(venue, credential, location_config,
                                        client, aspects) -> None:
    """
        Planning against an empty venue yields all-CREATE actions.
    """
    spec = basic_spec(with_dns=True)
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=spec)
    plan = provisioner.plan(aspects=aspects)
    creates = [a for a in plan.actions
               if a.intent == PlannedActionIntent.CREATE.value]
    assert len(creates) == len(plan.actions)
    assert len(plan.actions) > 0
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_apply_creates_resources(venue, credential, location_config,
                                 client, aspects) -> None:
    """
        Apply against an empty venue creates network/firewall/server/volume.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=spec)
    result = provisioner.apply(aspects=aspects)
    kinds = sorted(r.kind for r in result.created)
    assert "network" in kinds
    assert "security_group" in kinds
    assert "instance" in kinds
    assert "volume" in kinds
    assert client.create_calls > 0
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_replan_after_apply_is_all_skip(venue, credential, location_config,
                                        client, aspects) -> None:
    """
        Re-planning after a full apply yields SKIP for every owned resource.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=spec)
    provisioner.apply(aspects=aspects)
    plan = provisioner.plan(aspects=aspects)
    non_skip = [a for a in plan.actions
                if a.intent != PlannedActionIntent.SKIP.value]
    assert len(non_skip) == 0
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_reapply_makes_no_mutating_calls(venue, credential,
                                         location_config, client,
                                         aspects) -> None:
    """
        A second apply of a fully realised spec performs no create calls.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=spec)
    provisioner.apply(aspects=aspects)
    creates_after_first = client.create_calls
    provisioner.apply(aspects=aspects)
    assert client.create_calls == creates_after_first
    return


@testbase.attach.parameter(create_client, identifier="client")
@testbase.attach.parameter(create_vpn_control_plane, identifier="vpn_control_plane")
def test_apply_renders_vpn_user_data(venue, credential, location_config,
                                     client, aspects,
                                     vpn_control_plane) -> None:
    """
        An instance with vpn_join gets cloud-init user_data on the server.
    """
    spec = basic_spec(with_vpn=True, with_volume=False)
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=spec,
                               vpn_control_plane=vpn_control_plane)
    provisioner.apply(aspects=aspects)
    server = client.servers.get_by_name(name="srv-a")
    assert server is not None
    user_data = getattr(server, "user_data", None)
    assert user_data is not None
    assert "#cloud-config" in user_data
    assert "tailscale" in user_data
    assert len(provisioner.last_vpn_records) == 1
    return


@testbase.attach.parameter(create_client, identifier="client")
@testbase.attach.parameter(create_dns_client, identifier="dns_client")
def test_apply_dns_records(venue, credential, location_config, client,
                           dns_client, aspects) -> None:
    """
        DNS records are created against the DNS client.
    """
    spec = basic_spec(with_dns=True, with_volume=False)
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=spec,
                               dns_client=dns_client)
    provisioner.apply(aspects=aspects)
    assert len(dns_client.records) == 1
    assert dns_client.records[0]["name"] == "srv-a"
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_inventory_lists_owned_resources(venue, credential,
                                         location_config, client,
                                         aspects) -> None:
    """
        Inventory enumerates every run-id-labelled resource.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=spec)
    provisioner.apply(aspects=aspects)
    records = provisioner.inventory(aspects=aspects)
    kinds = sorted(r.kind for r in records)
    assert "network" in kinds
    assert "instance" in kinds
    assert "volume" in kinds
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_inventory_persist_writes_json(venue, credential, location_config,
                                       client, aspects, tmp_path) -> None:
    """
        HetznerInventory.persist writes the inventory JSON to disk.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=spec)
    provisioner.apply(aspects=aspects)
    records = provisioner.inventory(aspects=aspects)
    path = HetznerInventory.persist(
        run_id="testrun01", resources=records,
        output_root=str(tmp_path))
    assert os.path.isfile(path)
    assert path.endswith(os.path.join("testrun01",
                                      "hetzner-inventory.json"))
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_plan_emits_inplace_update_for_volume_grow(venue, credential,
                                                   location_config,
                                                   client,
                                                   aspects) -> None:
    """
        A volume whose desired size is larger than the live size plans an
        in-place UPDATE.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=spec)
    provisioner.apply(aspects=aspects)

    grown = basic_spec()
    grown.volumes[0].size_gb = 50
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=grown)
    plan = provisioner.plan(aspects=aspects)
    volume_actions = [a for a in plan.actions
                      if a.resource_kind == "volume"]
    assert len(volume_actions) == 1
    assert volume_actions[0].intent == PlannedActionIntent.UPDATE.value
    assert volume_actions[0].diff["after"]["size_gb"] == 50
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_apply_realizes_volume_grow_in_place(venue, credential,
                                             location_config, client,
                                             aspects) -> None:
    """
        Apply grows a drifted volume in place via volume.resize and records
        it in ProvisioningResult.updated.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=spec)
    provisioner.apply(aspects=aspects)
    creates_after_first = client.create_calls

    grown = basic_spec()
    grown.volumes[0].size_gb = 50
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=grown)
    result = provisioner.apply(aspects=aspects)

    assert client.resize_calls == 1
    assert client.create_calls == creates_after_first
    updated_names = {r.name for r in result.updated}
    assert "vol-a" in updated_names
    assert "vol-a" not in set(result.skipped)
    volume = client.volumes.get_by_name(name="vol-a")
    assert getattr(volume, "size", None) == 50
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_volume_grow_preserves_the_attachment_record(venue, credential,
                                                     location_config, client,
                                                     aspects) -> None:
    """
        Growing an attached volume keeps its attachment in the recorded
        resource.

        The attachment is read off the live volume's ``server`` field, which
        is where the API reports it.  Reading a field the API never returns
        would make every grown volume look detached, losing the attachment
        from recorded state.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=spec)
    first = provisioner.apply(aspects=aspects)

    created_volume = [r for r in first.created if r.name == "vol-a"][0]
    server_id = created_volume.attributes["attached_server_id"]
    assert server_id is not None

    grown = basic_spec()
    grown.volumes[0].size_gb = 50
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=grown)
    result = provisioner.apply(aspects=aspects)

    updated_volume = [r for r in result.updated if r.name == "vol-a"][0]
    assert updated_volume.attributes["attached_server_id"] == server_id
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_reapply_after_volume_grow_is_skip(venue, credential,
                                           location_config, client,
                                           aspects) -> None:
    """
        A second apply of the grown spec emits SKIP — the in-place grow is
        idempotent.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=spec)
    provisioner.apply(aspects=aspects)

    grown = basic_spec()
    grown.volumes[0].size_gb = 50
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=grown)
    provisioner.apply(aspects=aspects)
    resize_after_grow = client.resize_calls

    second = provisioner.apply(aspects=aspects)
    assert client.resize_calls == resize_after_grow
    assert "vol-a" in set(second.skipped)
    assert len(second.updated) == 0
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_volume_shrink_is_refused(venue, credential, location_config,
                                  client, aspects) -> None:
    """
        A volume whose desired size is smaller than the live size is
        refused — Hetzner volumes cannot shrink — rather than silently
        recreated.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=spec)
    provisioner.apply(aspects=aspects)

    shrunk = basic_spec()
    shrunk.volumes[0].size_gb = 10
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=shrunk)
    with testbase.raises(HetznerValidationError):
        provisioner.plan(aspects=aspects)
    with testbase.raises(HetznerValidationError):
        provisioner.apply(aspects=aspects)
    assert client.resize_calls == 0
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_destroy_requires_confirm(venue, credential, location_config,
                                  client, aspects) -> None:
    """
        Destroy without confirm raises SchemaSemanticError.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=spec)
    provisioner.apply(aspects=aspects)
    with testbase.raises(SchemaSemanticError):
        provisioner.destroy(aspects=aspects)
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_destroy_removes_resources(venue, credential, location_config,
                                   client, confirm_aspects) -> None:
    """
        Destroy with confirm removes every owned resource.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=spec)
    provisioner.apply(aspects=confirm_aspects)
    provisioner.destroy(aspects=confirm_aspects)
    records = provisioner.inventory(aspects=confirm_aspects)
    assert len(records) == 0
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_destroy_calls_vpn_delete_device(venue, credential,
                                         location_config, client,
                                         confirm_aspects) -> None:
    """
        Destroying a VPN-joined server de-registers the VPN device.
    """
    spec = basic_spec(with_vpn=True, with_volume=False)
    vpn = MockVpnControlPlane()
    provisioner = _provisioner(venue=venue, credential=credential,
                               location_config=location_config,
                               client=client, spec=spec,
                               vpn_control_plane=vpn)
    provisioner.apply(aspects=confirm_aspects)
    provisioner.record_vpn_device(instance_name="srv-a",
                                  device_id="device-xyz")
    provisioner.destroy(aspects=confirm_aspects)
    assert "device-xyz" in vpn.deleted_devices
    return
