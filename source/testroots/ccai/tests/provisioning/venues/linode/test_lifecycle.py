"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Plan/apply/destroy/inventory tests for the Linode venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase

from ccai.tests.provisioning.venues.linode.factories import create_linode_mock_client


import base64


from ccai.interfaces.schemasemanticerror import SchemaSemanticError

from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from ccai.provisioning.venues.linode.linodecloudprovisioner import (
    LinodeCloudProvisioner
)

from ccai.tests.provisioning.venues.linode._mocklinodeclient import MockLinodeClient
from ccai.tests.provisioning.venues.linode._specfactory import basic_spec


def _provisioner(*, venue, credential, region_config, spec, mock_client,
                 vpn_control_plane=None):
    """
        Helper: build a provisioner backed by the mock client.
    """
    rtnval = LinodeCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec, client=mock_client, vpn_control_plane=vpn_control_plane,
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
        self.minted_authkey: str = "tskey-test"
        self.minted_device_id: str = "device-abc"
        return

    def delete_device(self, *, device_id: str, aspects) -> None:
        """
            Record the deletion.

            :param device_id: The device id being deleted.
            :param aspects: Aspects.
        """
        self.deleted_ids.append(device_id)
        return


@testbase.attach.parameter(create_linode_mock_client, identifier="mock_client")
def test_plan_then_apply_creates_resources(venue, credential, region_config,
                                           aspects, mock_client) -> None:
    """
        First plan reports CREATEs; apply produces matching resources.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config, spec=spec,
                               mock_client=mock_client)

    plan = provisioner.plan(aspects=aspects)
    intents = [a.intent for a in plan.actions]
    assert PlannedActionIntent.CREATE.value in intents

    result = provisioner.apply(aspects=aspects)
    kinds = {r.kind for r in result.created}
    assert {"network", "subnet", "sg", "keypair", "instance",
            "volume", "bucket", "dns"}.issubset(kinds)
    return


@testbase.attach.parameter(create_linode_mock_client, identifier="mock_client")
def test_replan_after_apply_is_all_skip(venue, credential, region_config,
                                        aspects, mock_client) -> None:
    """
        After apply, re-planning emits no CREATE actions.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config, spec=spec,
                               mock_client=mock_client)
    provisioner.apply(aspects=aspects)

    plan = provisioner.plan(aspects=aspects)
    create_actions = [a for a in plan.actions
                      if a.intent == PlannedActionIntent.CREATE.value]
    assert len(create_actions) == 0
    return


@testbase.attach.parameter(create_linode_mock_client, identifier="mock_client")
def test_apply_idempotent(venue, credential, region_config, aspects,
                          mock_client) -> None:
    """
        Re-applying produces only SKIPs and no new created resources.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config, spec=spec,
                               mock_client=mock_client)
    provisioner.apply(aspects=aspects)
    second = provisioner.apply(aspects=aspects)

    assert len(second.created) == 0
    skipped_names = set(second.skipped)
    for name in ("vpc-a", "sub-a", "sg-a", "kp-a", "inst-a", "vol-a",
                 "bkt-a", "host"):
        assert name in skipped_names
    return


@given(size=st.sampled_from(["small", "medium", "large", "xlarge"]),
       with_vpn=st.booleans(), constraints={"max_examples": 25})
def test_apply_compose_apply_is_idempotent(venue, credential, region_config,
                                           aspects, size, with_vpn) -> None:
    """
        apply ∘ apply leaves the venue with the same resource count.
    """
    mock_client = MockLinodeClient()
    spec = basic_spec(instance_size=size, with_vpn=with_vpn)
    vpn = _RecordingVPN() if with_vpn is True else None
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config, spec=spec,
                               mock_client=mock_client,
                               vpn_control_plane=vpn)

    provisioner.apply(aspects=aspects)
    inventory_after_first = provisioner.inventory(aspects=aspects)
    provisioner.apply(aspects=aspects)
    inventory_after_second = provisioner.inventory(aspects=aspects)

    assert len(inventory_after_first) == len(inventory_after_second)
    return


@testbase.attach.parameter(create_linode_mock_client, identifier="mock_client")
def test_apply_with_vpn_join_injects_user_data(venue, credential,
                                               region_config, aspects,
                                               mock_client) -> None:
    """
        A VPN-joined instance carries base64 metadata.user_data with the
        tailscale bring-up reference.
    """
    spec = basic_spec(with_vpn=True)
    vpn = _RecordingVPN()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config, spec=spec,
                               mock_client=mock_client,
                               vpn_control_plane=vpn)
    provisioner.apply(aspects=aspects)

    instances = mock_client.linode.instances()
    assert len(instances) == 1
    user_data = instances[0].metadata.get("user_data", "")
    assert len(user_data) > 0
    decoded = base64.b64decode(user_data).decode("utf-8")
    assert "tailscale" in decoded
    assert "bringup" in decoded
    return


@testbase.attach.parameter(create_linode_mock_client, identifier="mock_client")
def test_apply_realises_instance_resize_in_place(venue, credential,
                                                 region_config,
                                                 confirm_aspects,
                                                 mock_client) -> None:
    """
        apply over a venue with a size-drifted instance realises the
        resize in place — the mock client records an instance_resize
        call and the result carries the resized instance in ``updated``.
    """
    baseline_spec = basic_spec(instance_size="small")
    baseline = _provisioner(venue=venue, credential=credential,
                            region_config=region_config, spec=baseline_spec,
                            mock_client=mock_client)
    baseline.apply(aspects=confirm_aspects)
    assert mock_client.resize_calls == 0

    drifted_spec = basic_spec(instance_size="large")
    drifted = _provisioner(venue=venue, credential=credential,
                           region_config=region_config, spec=drifted_spec,
                           mock_client=mock_client)
    result = drifted.apply(aspects=confirm_aspects)

    assert mock_client.resize_calls == 1
    updated_names = [r.name for r in result.updated]
    assert updated_names == ["inst-a"]
    assert result.updated[0].attributes["type"] == "g6-standard-6"
    return


@testbase.attach.parameter(create_linode_mock_client, identifier="mock_client")
def test_replan_after_resize_emits_skip(venue, credential, region_config,
                                        confirm_aspects,
                                        mock_client) -> None:
    """
        A second apply after an in-place resize emits no UPDATE — the
        idempotent contract is preserved.
    """
    baseline = _provisioner(venue=venue, credential=credential,
                            region_config=region_config,
                            spec=basic_spec(instance_size="small"),
                            mock_client=mock_client)
    baseline.apply(aspects=confirm_aspects)

    drifted = _provisioner(venue=venue, credential=credential,
                           region_config=region_config,
                           spec=basic_spec(instance_size="large"),
                           mock_client=mock_client)
    drifted.apply(aspects=confirm_aspects)

    plan = drifted.plan(aspects=confirm_aspects)
    instance_actions = [a for a in plan.actions
                        if a.resource_kind == "instance"]
    assert len(instance_actions) == 1
    assert instance_actions[0].intent == PlannedActionIntent.SKIP.value

    second = drifted.apply(aspects=confirm_aspects)
    assert "inst-a" in second.skipped
    assert len(second.updated) == 0
    return


@testbase.attach.parameter(create_linode_mock_client, identifier="mock_client")
def test_unconfirmed_resize_raises_semantic_error(venue, credential,
                                                  region_config, aspects,
                                                  mock_client) -> None:
    """
        An in-place instance resize without aspects.confirm raises
        SchemaSemanticError — consistent with destroy gating.
    """
    baseline = _provisioner(venue=venue, credential=credential,
                            region_config=region_config,
                            spec=basic_spec(instance_size="small"),
                            mock_client=mock_client)
    baseline.apply(aspects=aspects)

    drifted = _provisioner(venue=venue, credential=credential,
                           region_config=region_config,
                           spec=basic_spec(instance_size="large"),
                           mock_client=mock_client)
    with testbase.raises(SchemaSemanticError):
        drifted.apply(aspects=aspects)

    assert mock_client.resize_calls == 0
    return


@testbase.attach.parameter(create_linode_mock_client, identifier="mock_client")
def test_destroy_requires_confirm(venue, credential, region_config,
                                  aspects, mock_client) -> None:
    """
        destroy without aspects.confirm=True raises.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config, spec=spec,
                               mock_client=mock_client)
    provisioner.apply(aspects=aspects)
    with testbase.raises(SchemaSemanticError):
        provisioner.destroy(aspects=aspects)
    return


@testbase.attach.parameter(create_linode_mock_client, identifier="mock_client")
def test_destroy_reverses_apply(venue, credential, region_config, aspects,
                                confirm_aspects, mock_client) -> None:
    """
        After destroy, the inventory comes back empty.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config, spec=spec,
                               mock_client=mock_client)
    provisioner.apply(aspects=aspects)
    inventory_before = provisioner.inventory(aspects=aspects)
    assert len(inventory_before) > 0

    provisioner.destroy(aspects=confirm_aspects)

    inventory_after = provisioner.inventory(aspects=aspects)
    assert len(inventory_after) == 0
    return


@testbase.attach.parameter(create_linode_mock_client, identifier="mock_client")
def test_destroy_calls_vpn_delete_device(venue, credential, region_config,
                                         aspects, confirm_aspects,
                                         mock_client) -> None:
    """
        Destroying VPN-joined instances de-registers the VPN device.
    """
    spec = basic_spec(with_vpn=True)
    vpn = _RecordingVPN()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config, spec=spec,
                               mock_client=mock_client,
                               vpn_control_plane=vpn)
    provisioner.apply(aspects=aspects)
    provisioner.destroy(aspects=confirm_aspects)

    assert "device-abc" in vpn.deleted_ids
    return


@testbase.attach.parameter(create_linode_mock_client, identifier="mock_client")
def test_inventory_persist_writes_file(venue, credential, region_config,
                                       aspects, mock_client,
                                       tmp_path) -> None:
    """
        Inventory persistence writes linode-inventory.json under the run.
    """
    from ccai.provisioning.venues.linode.linodeinventory import (
        LinodeInventory
    )
    from ccai.provisioning.venues.linode.linodereader import LinodeReader
    from ccai.provisioning.venues.linode.linodetagtranslator import (
        LinodeTagTranslator
    )

    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config, spec=spec,
                               mock_client=mock_client)
    provisioner.apply(aspects=aspects)
    records = provisioner.inventory(aspects=aspects)

    translator = LinodeTagTranslator()
    reader = LinodeReader(client=mock_client, run_id="testrun01",
                          translator=translator)
    enumerator = LinodeInventory(client=mock_client, reader=reader,
                                 translator=translator)
    path = enumerator.persist(records=records, run_id="testrun01",
                              output_root=str(tmp_path))
    assert path.endswith("provisioning/testrun01/linode-inventory.json")
    import os
    assert os.path.isfile(path)
    return
