"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: plan/apply/destroy/inventory tests for the DigitalOcean venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import pytest

from ccai.interfaces.schemasemanticerror import SchemaSemanticError

from hypothesis import HealthCheck, given, settings, strategies as st

from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from ccai.provisioning.venues.digitalocean.digitaloceancloudprovisioner import (
    DigitalOceanCloudProvisioner
)
from ccai.provisioning.venues.digitalocean.doclient import (
    DigitalOceanClient
)

from ._mockclient import MockDigitalOceanRawClient
from ._specfactory import basic_spec


def _provisioner(*, venue, credential, region_config, do_client, spec,
                 vpn_control_plane=None, output_root=None):
    """
        Helper: build a provisioner.
    """
    rtnval = DigitalOceanCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec, client=do_client, vpn_control_plane=vpn_control_plane,
        output_root=output_root,
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
        return

    def delete_device(self, *, device_id: str, aspects) -> None:
        """
            Record the deletion.
        """
        self.deleted_ids.append(device_id)
        return


def test_plan_then_apply_creates_resources(venue, credential, region_config,
                                           do_client, aspects) -> None:
    """
        First plan reports CREATEs; apply produces matching resources.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, region_config=region_config,
        do_client=do_client, spec=spec,
    )
    plan = provisioner.plan(aspects=aspects)
    intents = [a.intent for a in plan.actions]
    assert PlannedActionIntent.CREATE.value in intents

    result = provisioner.apply(aspects=aspects)
    kinds = {r.kind for r in result.created}
    assert {"network", "sg", "keypair", "instance", "volume",
            "bucket"}.issubset(kinds)
    return


def test_replan_after_apply_is_all_skip(venue, credential, region_config,
                                        do_client, aspects) -> None:
    """
        After apply, a re-plan emits no CREATE actions.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, region_config=region_config,
        do_client=do_client, spec=spec,
    )
    provisioner.apply(aspects=aspects)

    plan = provisioner.plan(aspects=aspects)
    creates = [a for a in plan.actions
               if a.intent == PlannedActionIntent.CREATE.value]
    assert len(creates) == 0
    return


def test_apply_with_vpn_join_injects_user_data(venue, credential,
                                               region_config, do_client,
                                               raw_client, aspects) -> None:
    """
        A Droplet with vpn_join carries cloud-init user_data referencing the
        tailscale bring-up.
    """
    spec = basic_spec(with_vpn=True)
    vpn = _RecordingVPN()
    provisioner = _provisioner(
        venue=venue, credential=credential, region_config=region_config,
        do_client=do_client, spec=spec, vpn_control_plane=vpn,
    )
    provisioner.apply(aspects=aspects)

    found = False
    for droplet in raw_client.store["droplets"].values():
        user_data = droplet.get("user_data", "")
        if "tailscale" in user_data and "bringup" in user_data:
            found = True
    assert found is True
    return


def test_destroy_requires_confirm(venue, credential, region_config,
                                  do_client, aspects) -> None:
    """
        destroy without aspects.confirm=True raises.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, region_config=region_config,
        do_client=do_client, spec=spec,
    )
    provisioner.apply(aspects=aspects)
    with pytest.raises(SchemaSemanticError):
        provisioner.destroy(aspects=aspects)
    return


def test_destroy_reverses_apply(venue, credential, region_config, do_client,
                                aspects, confirm_aspects) -> None:
    """
        After destroy, the inventory comes back empty.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, region_config=region_config,
        do_client=do_client, spec=spec,
    )
    provisioner.apply(aspects=aspects)
    inventory_before = provisioner.inventory(aspects=aspects)
    assert len(inventory_before) > 0

    provisioner.destroy(aspects=confirm_aspects)

    inventory_after = provisioner.inventory(aspects=aspects)
    assert len(inventory_after) == 0
    return


def test_destroy_calls_vpn_delete_device(venue, credential, region_config,
                                         do_client, aspects,
                                         confirm_aspects) -> None:
    """
        destroy de-registers the Tailscale device via the control plane.
    """
    spec = basic_spec(with_vpn=True)
    vpn = _RecordingVPN()
    provisioner = _provisioner(
        venue=venue, credential=credential, region_config=region_config,
        do_client=do_client, spec=spec, vpn_control_plane=vpn,
    )
    provisioner.apply(aspects=aspects)
    provisioner.record_vpn_device(instance_name="droplet-a",
                                  device_id="device-do-1")

    provisioner.destroy(aspects=confirm_aspects)
    assert "device-do-1" in vpn.deleted_ids
    return


def test_inventory_is_persisted(venue, credential, region_config, do_client,
                                aspects, tmp_path) -> None:
    """
        inventory writes a do-inventory.json under the output root.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, region_config=region_config,
        do_client=do_client, spec=spec, output_root=str(tmp_path),
    )
    provisioner.apply(aspects=aspects)
    provisioner.inventory(aspects=aspects)

    out_file = tmp_path / "provisioning" / "dotestrun01" / "do-inventory.json"
    assert out_file.exists()
    return


def test_spaces_bucket_created_and_skipped(venue, credential, region_config,
                                           do_client, raw_client,
                                           aspects) -> None:
    """
        A Spaces bucket is created on first apply and SKIPped on re-apply.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, region_config=region_config,
        do_client=do_client, spec=spec,
    )
    first = provisioner.apply(aspects=aspects)
    assert any(r.kind == "bucket" for r in first.created)
    assert len(raw_client.store["spaces"]) == 1

    second = provisioner.apply(aspects=aspects)
    assert "bkt-a" in second.skipped
    return


def test_dns_record_created_and_skipped(venue, credential, region_config,
                                        do_client, aspects) -> None:
    """
        A DNS record is created on first apply and SKIPped on re-apply.
    """
    spec = basic_spec(with_dns=True)
    provisioner = _provisioner(
        venue=venue, credential=credential, region_config=region_config,
        do_client=do_client, spec=spec,
    )
    first = provisioner.apply(aspects=aspects)
    assert any(r.kind == "dns" for r in first.created)

    second = provisioner.apply(aspects=aspects)
    assert "api" in second.skipped
    return


@settings(max_examples=25, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(with_vpn=st.booleans(), with_dns=st.booleans())
def test_apply_idempotent(venue, credential, region_config, with_vpn,
                          with_dns) -> None:
    """
        apply ∘ apply is idempotent: a second apply creates nothing.
    """
    raw = MockDigitalOceanRawClient()
    client = DigitalOceanClient(credential=credential, raw_client=raw,
                                spaces_client=raw.spaces)
    aspects = ProvisioningAspects(runid="idem01", verify_timeout=5.0,
                                  verify_interval=0.01)
    spec = basic_spec(with_vpn=with_vpn, with_dns=with_dns)
    provisioner = _provisioner(
        venue=venue, credential=credential, region_config=region_config,
        do_client=client, spec=spec,
    )
    provisioner.apply(aspects=aspects)
    second = provisioner.apply(aspects=aspects)

    assert len(second.created) == 0
    assert len(second.skipped) > 0
    return


@settings(max_examples=25, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(with_vpn=st.booleans(), with_dns=st.booleans())
def test_destroy_is_inverse_of_apply(venue, credential, region_config,
                                     with_vpn, with_dns) -> None:
    """
        destroy ∘ apply leaves no owned resources behind.
    """
    raw = MockDigitalOceanRawClient()
    client = DigitalOceanClient(credential=credential, raw_client=raw,
                                spaces_client=raw.spaces)
    aspects = ProvisioningAspects(runid="inv01", verify_timeout=5.0,
                                  verify_interval=0.01)
    confirm = ProvisioningAspects(runid="inv01", confirm=True,
                                  verify_timeout=5.0, verify_interval=0.01)
    spec = basic_spec(with_vpn=with_vpn, with_dns=with_dns)
    provisioner = _provisioner(
        venue=venue, credential=credential, region_config=region_config,
        do_client=client, spec=spec,
    )
    provisioner.apply(aspects=aspects)
    provisioner.destroy(aspects=confirm)

    assert len(provisioner.inventory(aspects=aspects)) == 0
    assert len(raw.store["droplets"]) == 0
    assert len(raw.store["vpcs"]) == 0
    assert len(raw.store["volumes"]) == 0
    assert len(raw.store["firewalls"]) == 0
    return
