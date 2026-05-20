"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for HetznerCloudProvisioner plan / apply / destroy /
               inventory.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

import pytest

from automojo.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from automojo.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from automojo.provisioning.model.exceptions import SchemaSemanticError
from automojo.provisioning.venues.hetzner.hetznercloudprovisioner import (
    HetznerCloudProvisioner
)
from automojo.provisioning.venues.hetzner.hetznerinventory import (
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
    with pytest.raises(SchemaSemanticError):
        provisioner.destroy(aspects=aspects)
    return


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
