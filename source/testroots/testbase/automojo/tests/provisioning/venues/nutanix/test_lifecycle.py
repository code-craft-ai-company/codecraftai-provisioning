"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Plan / apply / destroy / inventory tests for the Nutanix
               venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from base64 import b64decode

from automojo.provisioning.venues.nutanix.nutanixcloudprovisioner import (
    NutanixCloudProvisioner
)

from ._mockclient import MockNutanixClient, RecordingVpnControlPlane
from ._specfactory import basic_spec, make_config, volume_spec


def _provisioner(*, venue, spec, client=None, vpn_control_plane=None):
    """
        Build a NutanixCloudProvisioner over a mock client.

        :param venue: The CloudVenue fixture.
        :param spec: The NutanixSpec under test.
        :param client: Optional shared MockNutanixClient.
        :param vpn_control_plane: Optional VPN control-plane double.

        :returns: A constructed provisioner.
    """
    effective_client = client if client is not None else MockNutanixClient()
    rtnval = NutanixCloudProvisioner(venue=venue, client=effective_client,
                                     config=make_config(), spec=spec,
                                     vpn_control_plane=vpn_control_plane)
    return rtnval


def test_plan_all_create_on_empty_venue(venue, aspects):
    """
        Plan against an empty venue emits CREATE for every resource.
    """
    provisioner = _provisioner(venue=venue, spec=basic_spec())
    plan = provisioner.plan(aspects=aspects)
    intents = [action.intent for action in plan.actions]
    assert len(intents) == 3
    assert intents.count("create") == 3


def test_replan_after_apply_is_all_skip(venue, aspects):
    """
        A second plan after apply emits SKIP for every resource.
    """
    client = MockNutanixClient()
    provisioner = _provisioner(venue=venue, spec=basic_spec(),
                               client=client)
    provisioner.apply(aspects=aspects)

    plan = provisioner.plan(aspects=aspects)
    intents = [action.intent for action in plan.actions]
    assert len(intents) == 3
    for intent in intents:
        assert intent == "skip"


def test_apply_creates_vpc_subnet_and_vm(venue, aspects):
    """
        Apply creates the Flow VPC, subnet and VM.
    """
    client = MockNutanixClient()
    provisioner = _provisioner(venue=venue, spec=basic_spec(),
                               client=client)
    result = provisioner.apply(aspects=aspects)

    kinds = sorted(resource.kind for resource in result.created)
    assert kinds == ["instance", "network", "subnet"]
    assert client.create_vm_calls == 1
    assert client.create_vpc_calls == 1
    assert client.create_subnet_calls == 1


def test_apply_with_volume(venue, aspects):
    """
        Apply with a volume creates a volume group.
    """
    client = MockNutanixClient()
    provisioner = _provisioner(venue=venue, spec=volume_spec(),
                               client=client)
    result = provisioner.apply(aspects=aspects)
    assert client.create_volume_group_calls == 1
    volume_resources = [r for r in result.created if r.kind == "volume"]
    assert len(volume_resources) == 1


def test_apply_with_vpn_join_renders_base64_cloud_init(venue, aspects):
    """
        A VM carrying vpn_join gets base64 cloud-init user_data carrying
        the rendered Tailscale bring-up.
    """
    client = MockNutanixClient()
    vpn = RecordingVpnControlPlane()
    provisioner = _provisioner(venue=venue,
                               spec=basic_spec(with_vpn=True),
                               client=client, vpn_control_plane=vpn)
    provisioner.apply(aspects=aspects)

    user_data = client.vm_user_data["node-testrun0"]
    assert user_data is not None
    decoded = b64decode(user_data.encode("utf-8")).decode("utf-8")
    assert decoded.startswith("#cloud-config")
    assert "tailscale" in decoded

    records = provisioner.last_vpn_records
    assert len(records) == 1
    assert records[0]["vpn_provider"] == "tailscale"


def test_apply_re_apply_is_idempotent(venue, aspects):
    """
        Re-applying the same spec makes no fresh mutating VM calls.
    """
    client = MockNutanixClient()
    provisioner = _provisioner(venue=venue, spec=basic_spec(),
                               client=client)
    provisioner.apply(aspects=aspects)
    first_vm_calls = client.create_vm_calls

    second = provisioner.apply(aspects=aspects)
    assert client.create_vm_calls == first_vm_calls
    assert sorted(second.skipped) == ["appsubnet", "node", "vpcnet"]
    assert len(second.created) == 0


def test_destroy_removes_vm_subnet_and_vpc(venue, confirm_aspects):
    """
        Destroy reverses apply — the venue is empty afterwards.
    """
    client = MockNutanixClient()
    provisioner = _provisioner(venue=venue, spec=basic_spec(),
                               client=client)
    provisioner.apply(aspects=confirm_aspects)
    provisioner.destroy(aspects=confirm_aspects)

    assert len(client.vms_state) == 0
    assert len(client.subnets_state) == 0
    assert len(client.vpcs_state) == 0


def test_destroy_cleans_up_tailscale_device(venue, confirm_aspects):
    """
        Destroy of a VPN-joined VM de-registers the VPN device.
    """
    client = MockNutanixClient()
    vpn = RecordingVpnControlPlane()
    provisioner = _provisioner(venue=venue,
                               spec=basic_spec(with_vpn=True),
                               client=client, vpn_control_plane=vpn)
    provisioner.apply(aspects=confirm_aspects)
    provisioner.destroy(aspects=confirm_aspects)

    assert vpn.deleted_device_ids == ["node-testrun0"]


def test_inventory_lists_run_owned_vm(venue, aspects, tmp_path):
    """
        Inventory enumerates the run-id-categoried VM and persists a
        snapshot.
    """
    client = MockNutanixClient()
    provisioner = NutanixCloudProvisioner(
        venue=venue, client=client, config=make_config(),
        spec=basic_spec(), output_root=str(tmp_path),
    )
    provisioner.apply(aspects=aspects)
    resources = provisioner.inventory(aspects=aspects)

    assert len(resources) == 1
    assert resources[0].kind == "instance"
    assert resources[0].attributes["ip"] == "10.20.0.50"

    snapshot = tmp_path / "provisioning" / "testrun01" / (
        "nutanix-inventory.json"
    )
    assert snapshot.exists()
