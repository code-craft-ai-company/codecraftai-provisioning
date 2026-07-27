"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: End-to-end plan/apply/destroy/inventory tests for the Equinix
               Metal venue against the mock client.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase

from .factories import create_equinix_metal_mock_client


import pytest

from ccai.interfaces.schemasemanticerror import SchemaSemanticError

from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from ccai.provisioning.venues.equinix_metal.equinixmetalcloudprovisioner import (
    EquinixMetalCloudProvisioner
)

from ._specfactory import basic_spec


def _provisioner(*, venue, credential, project_config, spec, mock_client,
                 vpn_control_plane=None):
    """
        Helper: construct an EquinixMetalCloudProvisioner with a mock client.
    """
    rtnval = EquinixMetalCloudProvisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, client=mock_client, vpn_control_plane=vpn_control_plane,
    )
    return rtnval


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_plan_then_apply_creates_resources(venue, credential,
                                           project_config, mock_client,
                                           aspects) -> None:
    """
        First plan reports CREATEs; apply produces matching resources.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    plan = provisioner.plan(aspects=aspects)
    intents = [a.intent for a in plan.actions]
    assert PlannedActionIntent.CREATE.value in intents

    result = provisioner.apply(aspects=aspects)
    kinds = {r.kind for r in result.created}
    assert {"network", "subnet", "keypair", "instance"}.issubset(kinds)
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_replan_after_apply_is_all_skip(venue, credential, project_config,
                                        mock_client, aspects) -> None:
    """
        Re-planning after a successful apply yields no CREATE actions.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    provisioner.apply(aspects=aspects)

    plan = provisioner.plan(aspects=aspects)
    creates = [a for a in plan.actions
               if a.intent == PlannedActionIntent.CREATE.value]
    assert len(creates) == 0
    skips = [a for a in plan.actions
             if a.intent == PlannedActionIntent.SKIP.value]
    assert len(skips) == len(plan.actions)
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_apply_idempotent_skips_on_reapply(venue, credential,
                                           project_config, mock_client,
                                           aspects) -> None:
    """
        A second apply skips every resource and makes no mutating calls.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    provisioner.apply(aspects=aspects)
    mock_client.calls.clear()

    second = provisioner.apply(aspects=aspects)
    skipped = set(second.skipped)
    assert {"net-a", "sub-a", "kp-a", "dev-a"}.issubset(skipped)
    assert len(second.created) == 0
    # No mutating calls were made on the second apply.
    assert len(mock_client.calls) == 0
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_apply_with_vpn_join_injects_userdata(venue, credential,
                                              project_config, mock_client,
                                              aspects) -> None:
    """
        An instance with vpn_join carries cloud-init userdata containing the
        tailscale bring-up reference.
    """
    spec = basic_spec(with_vpn=True)
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    provisioner.apply(aspects=aspects)

    devices = mock_client.list_devices()
    assert len(devices) == 1
    userdata = devices[0].get("userdata", "")
    assert "tailscale" in userdata
    assert "bringup" in userdata
    assert userdata.startswith("#cloud-config")
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_device_uses_resolved_plan_and_os_slug(venue, credential,
                                               project_config, mock_client,
                                               aspects) -> None:
    """
        The created device carries the resolved Metal plan and OS slug.
    """
    spec = basic_spec(size="medium")
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    result = provisioner.apply(aspects=aspects)
    device_resource = None
    for resource in result.created:
        if resource.kind == "instance":
            device_resource = resource
    assert device_resource is not None
    assert device_resource.attributes.get("plan", "") == "c3.medium.x86"
    assert device_resource.attributes.get(
        "operating_system", ""
    ) == "ubuntu_24_04"
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_inventory_lists_owned_resources(venue, credential, project_config,
                                         mock_client, aspects) -> None:
    """
        Inventory enumerates every owned resource after apply.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    provisioner.apply(aspects=aspects)
    inventory = provisioner.inventory(aspects=aspects)
    kinds = {r.kind for r in inventory}
    assert {"network", "subnet", "keypair", "instance"}.issubset(kinds)
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_destroy_requires_confirm(venue, credential, project_config,
                                  mock_client, aspects) -> None:
    """
        destroy without aspects.confirm=True raises.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    provisioner.apply(aspects=aspects)
    with pytest.raises(SchemaSemanticError):
        provisioner.destroy(aspects=aspects)
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_destroy_reverses_apply(venue, credential, project_config,
                                mock_client, aspects,
                                confirm_aspects) -> None:
    """
        After destroy the inventory comes back empty.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    provisioner.apply(aspects=aspects)
    assert len(provisioner.inventory(aspects=aspects)) > 0

    provisioner.destroy(aspects=confirm_aspects)
    assert len(provisioner.inventory(aspects=aspects)) == 0
    return


class _RecordingVPN:
    """
        Minimal mock IVPNControlPlane recording delete_device calls.
    """

    def __init__(self) -> None:
        """
            Construct.
        """
        self.deleted_ids: list = []
        self.minted_authkey: str = "tskey-test"
        return

    def delete_device(self, *, device_id: str, aspects) -> None:
        """
            Record the deletion.
        """
        self.deleted_ids.append(device_id)
        return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_destroy_calls_vpn_delete_device(venue, credential, project_config,
                                         mock_client, aspects,
                                         confirm_aspects) -> None:
    """
        When vpn_join was set and a device id was recorded, destroy invokes
        the control-plane delete_device.
    """
    spec = basic_spec(with_vpn=True)
    vpn = _RecordingVPN()
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client, vpn_control_plane=vpn,
    )
    provisioner.apply(aspects=aspects)
    provisioner.record_vpn_device(instance_name="dev-a",
                                  device_id="ts-device-1")

    provisioner.destroy(aspects=confirm_aspects)
    assert "ts-device-1" in vpn.deleted_ids
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_plan_emits_inplace_update_for_tag_drift(venue, credential,
                                                 project_config,
                                                 mock_client,
                                                 aspects) -> None:
    """
        A tag-only drift on an existing device plans an in-place UPDATE
        carrying an ``update_kind="tags"`` diff.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    provisioner.apply(aspects=aspects)

    drifted = basic_spec()
    drifted.instances[0].tags["ccai:purpose"] = "production"
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=drifted, mock_client=mock_client,
    )
    plan = provisioner.plan(aspects=aspects)
    device_actions = [a for a in plan.actions
                      if a.resource_kind == "instance"]
    assert len(device_actions) == 1
    assert device_actions[0].intent == PlannedActionIntent.UPDATE.value
    assert device_actions[0].diff.get("update_kind") == "tags"
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_apply_realizes_tag_drift_in_place(venue, credential,
                                           project_config, mock_client,
                                           aspects) -> None:
    """
        Apply realises a tag-only drift in place via update_device_tags and
        records the device in ProvisioningResult.updated.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    provisioner.apply(aspects=aspects)
    mock_client.calls.clear()

    drifted = basic_spec()
    drifted.instances[0].tags["ccai:purpose"] = "production"
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=drifted, mock_client=mock_client,
    )
    result = provisioner.apply(aspects=aspects)

    assert "update_device_tags" in mock_client.calls
    assert "create_device" not in mock_client.calls
    assert "delete_device" not in mock_client.calls
    updated_names = {r.name for r in result.updated}
    assert "dev-a" in updated_names
    assert "dev-a" not in set(result.skipped)

    device = mock_client.list_devices()[0]
    observed = dict(
        entry.split("=", 1) for entry in device.get("tags", [])
        if "=" in entry
    )
    assert observed.get("ccai:purpose") == "production"
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_reapply_after_tag_drift_is_skip(venue, credential, project_config,
                                         mock_client, aspects) -> None:
    """
        A second apply of the tag-reconciled spec emits SKIP — the in-place
        tag update is idempotent.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    provisioner.apply(aspects=aspects)

    drifted = basic_spec()
    drifted.instances[0].tags["ccai:purpose"] = "production"
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=drifted, mock_client=mock_client,
    )
    provisioner.apply(aspects=aspects)
    mock_client.calls.clear()

    second = provisioner.apply(aspects=aspects)
    assert "dev-a" in set(second.skipped)
    assert len(second.updated) == 0
    assert len(mock_client.calls) == 0
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_default_aspects_substituted_when_omitted(venue, credential,
                                                  project_config,
                                                  mock_client) -> None:
    """
        Methods accept aspects=None and substitute a default run identifier.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    result = provisioner.apply(aspects=None)
    assert len(result.created) > 0
    return
