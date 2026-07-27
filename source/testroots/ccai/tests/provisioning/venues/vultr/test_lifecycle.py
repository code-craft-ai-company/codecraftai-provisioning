"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: plan/apply/destroy/inventory tests for the Vultr venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase

from .factories import create_vultr_fake_vultr


import base64

import pytest

from ccai.interfaces.schemasemanticerror import SchemaSemanticError

from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)

from ._specfactory import basic_spec


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


@testbase.attach.parameter(create_vultr_fake_vultr, identifier="fake_vultr")
def test_plan_then_apply_creates_resources(fake_vultr, provisioner_factory,
                                           aspects) -> None:
    """
        First plan reports CREATEs; apply produces matching resources.
    """
    _fake, client = fake_vultr
    spec = basic_spec()
    provisioner = provisioner_factory(client=client, spec=spec)

    plan = provisioner.plan(aspects=aspects)
    intents = [a.intent for a in plan.actions]
    assert PlannedActionIntent.CREATE.value in intents

    result = provisioner.apply(aspects=aspects)
    kinds = {r.kind for r in result.created}
    assert {"network", "sg", "keypair", "instance", "volume", "bucket",
            "dns"}.issubset(kinds)
    return


@testbase.attach.parameter(create_vultr_fake_vultr, identifier="fake_vultr")
def test_apply_idempotent(fake_vultr, provisioner_factory, aspects) -> None:
    """
        Re-applying produces only SKIPs for the read-tracked resources.
    """
    _fake, client = fake_vultr
    spec = basic_spec()
    provisioner = provisioner_factory(client=client, spec=spec)
    provisioner.apply(aspects=aspects)
    second = provisioner.apply(aspects=aspects)

    skipped = set(second.skipped)
    assert {"vpc-a", "sg-a", "kp-a", "inst-a", "vol-a",
            "bkt-a"}.issubset(skipped)

    plan = provisioner.plan(aspects=aspects)
    creates = [a for a in plan.actions
               if a.intent == PlannedActionIntent.CREATE.value
               and a.resource_kind != "dns"]
    assert len(creates) == 0
    return


@testbase.attach.parameter(create_vultr_fake_vultr, identifier="fake_vultr")
def test_apply_with_vpn_join_injects_user_data(fake_vultr,
                                               provisioner_factory,
                                               aspects) -> None:
    """
        Instances with vpn_join carry base64-encoded cloud-init user_data
        containing the tailscale bring-up reference.
    """
    fake, client = fake_vultr
    spec = basic_spec(with_vpn=True)
    vpn = _RecordingVPN()
    provisioner = provisioner_factory(client=client, spec=spec,
                                      vpn_control_plane=vpn)
    provisioner.apply(aspects=aspects)

    assert len(fake.instances) == 1
    user_data = fake.instances[0]["user_data"]
    assert len(user_data) > 0
    decoded = base64.b64decode(user_data).decode("utf-8")
    assert "tailscale" in decoded
    assert "bringup" in decoded
    assert "#cloud-config" in decoded
    return


@testbase.attach.parameter(create_vultr_fake_vultr, identifier="fake_vultr")
def test_destroy_requires_confirm(fake_vultr, provisioner_factory,
                                  aspects) -> None:
    """
        destroy without aspects.confirm=True raises.
    """
    _fake, client = fake_vultr
    spec = basic_spec()
    provisioner = provisioner_factory(client=client, spec=spec)
    provisioner.apply(aspects=aspects)
    with pytest.raises(SchemaSemanticError):
        provisioner.destroy(aspects=aspects)
    return


@testbase.attach.parameter(create_vultr_fake_vultr, identifier="fake_vultr")
def test_destroy_reverses_apply(fake_vultr, provisioner_factory, aspects,
                                confirm_aspects) -> None:
    """
        After destroy, the inventory comes back empty.
    """
    _fake, client = fake_vultr
    spec = basic_spec()
    provisioner = provisioner_factory(client=client, spec=spec)
    provisioner.apply(aspects=aspects)
    inventory_before = provisioner.inventory(aspects=aspects)
    assert len(inventory_before) > 0

    provisioner.destroy(aspects=confirm_aspects)

    inventory_after = provisioner.inventory(aspects=aspects)
    assert len(inventory_after) == 0
    return


@testbase.attach.parameter(create_vultr_fake_vultr, identifier="fake_vultr")
def test_destroy_calls_vpn_delete_device(fake_vultr, provisioner_factory,
                                         aspects, confirm_aspects) -> None:
    """
        When vpn_join was set and a device id was recorded, destroy
        invokes the control plane delete_device (Tailscale cleanup).
    """
    _fake, client = fake_vultr
    spec = basic_spec(with_vpn=True)
    vpn = _RecordingVPN()
    provisioner = provisioner_factory(client=client, spec=spec,
                                      vpn_control_plane=vpn)
    provisioner.apply(aspects=aspects)
    provisioner.record_vpn_device(instance_name="inst-a",
                                  device_id="device-abc")

    provisioner.destroy(aspects=confirm_aspects)
    assert "device-abc" in vpn.deleted_ids
    return


@testbase.attach.parameter(create_vultr_fake_vultr, identifier="fake_vultr")
def test_inventory_persists_to_output(fake_vultr, provisioner_factory,
                                      aspects) -> None:
    """
        inventory writes a run-scoped vultr-inventory.json file.
    """
    import os

    _fake, client = fake_vultr
    spec = basic_spec()
    provisioner = provisioner_factory(client=client, spec=spec)
    provisioner.apply(aspects=aspects)
    provisioner.inventory(aspects=aspects)

    out_path = os.path.join(".output", "provisioning", "testrun01",
                            "vultr-inventory.json")
    assert os.path.exists(out_path)
    return


@testbase.attach.parameter(create_vultr_fake_vultr, identifier="fake_vultr")
@given(extra_runs=st.integers(min_value=1, max_value=3), constraints={"max_examples": 6})
def test_apply_compose_apply_idempotence(fake_vultr, provisioner_factory,
                                         aspects, extra_runs) -> None:
    """
        apply ∘ apply ... is the identity: the resource count is stable
        after the first apply regardless of how many times it re-runs.
    """
    fake, client = fake_vultr
    spec = basic_spec()
    provisioner = provisioner_factory(client=client, spec=spec)
    provisioner.apply(aspects=aspects)

    baseline = (len(fake.vpcs), len(fake.firewall_groups),
                len(fake.ssh_keys), len(fake.instances), len(fake.blocks),
                len(fake.object_storages))

    for _ in range(extra_runs):
        provisioner.apply(aspects=aspects)

    after = (len(fake.vpcs), len(fake.firewall_groups), len(fake.ssh_keys),
             len(fake.instances), len(fake.blocks),
             len(fake.object_storages))
    assert after == baseline
    return
