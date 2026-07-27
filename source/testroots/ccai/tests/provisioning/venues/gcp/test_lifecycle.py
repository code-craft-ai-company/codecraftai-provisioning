"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: End-to-end validate/plan/apply/destroy tests for the GCP venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase

from .factories import create_gcp_make_provisioner


import pytest

from ccai.interfaces.schemasemanticerror import SchemaSemanticError

from ccai.interfaces.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from ccai.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy
from ccai.provisioning.venues.google.gcpsessionfactory import (
    SERVICE_COMPUTE, SERVICE_TPU, SERVICE_STORAGE, SERVICE_DNS
)
from ccai.provisioning.venues.google.gcpspec import GcpSpec
from ccai.provisioning.venues.google.googlecloudprovisioner import (
    GoogleCloudProvisioner
)

from ._specfactory import basic_spec, gpu_compact_spec, tpu_spec


@testbase.attach.parameter(create_gcp_make_provisioner, identifier="make_provisioner")
def test_plan_then_apply_creates_resources(make_provisioner,
                                           aspects) -> None:
    """
        First plan reports CREATEs; apply produces matching resources.
    """
    provisioner, _ = make_provisioner(spec=basic_spec())

    plan = provisioner.plan(aspects=aspects)
    intents = [a.intent for a in plan.actions]
    assert PlannedActionIntent.CREATE.value in intents

    result = provisioner.apply(aspects=aspects)
    kinds = {r.kind for r in result.created}
    assert {"network", "subnet", "firewall", "instance", "volume",
            "bucket"}.issubset(kinds)
    return


@testbase.attach.parameter(create_gcp_make_provisioner, identifier="make_provisioner")
def test_apply_idempotent(make_provisioner, aspects) -> None:
    """
        Re-applying produces only SKIPs; a re-plan is all-SKIP.
    """
    provisioner, _ = make_provisioner(spec=basic_spec())
    provisioner.apply(aspects=aspects)
    second = provisioner.apply(aspects=aspects)

    skipped = set(second.skipped)
    assert "vpc-a" in skipped
    assert "sub-a" in skipped
    assert "sg-a" in skipped
    assert "inst-a" in skipped
    assert "vol-a" in skipped
    assert "bkt-a" in skipped

    plan = provisioner.plan(aspects=aspects)
    creates = [a for a in plan.actions
               if a.intent == PlannedActionIntent.CREATE.value
               and a.resource_kind not in ("dns",)]
    assert len(creates) == 0
    return


@testbase.attach.parameter(create_gcp_make_provisioner, identifier="make_provisioner")
def test_apply_idempotence_property(make_provisioner, aspects) -> None:
    """
        apply ∘ apply yields the same inventory (no new mutating calls).
    """
    provisioner, fakes = make_provisioner(spec=basic_spec())
    provisioner.apply(aspects=aspects)
    inv_after_first = provisioner.inventory(aspects=aspects)
    insert_calls_first = fakes["compute"]["instances"].insert_calls

    provisioner.apply(aspects=aspects)
    inv_after_second = provisioner.inventory(aspects=aspects)
    insert_calls_second = fakes["compute"]["instances"].insert_calls

    assert len(inv_after_first) == len(inv_after_second)
    assert insert_calls_first == insert_calls_second
    return


@testbase.attach.parameter(create_gcp_make_provisioner, identifier="make_provisioner")
def test_apply_with_vpn_join_injects_user_data(make_provisioner,
                                               aspects) -> None:
    """
        Instances with vpn_join carry cloud-init in metadata user-data.
    """
    provisioner, fakes = make_provisioner(spec=basic_spec(with_vpn=True))
    provisioner.apply(aspects=aspects)

    instances = fakes["compute"]["instances"].list()
    found = False
    for entry in instances:
        metadata = entry.metadata
        items = metadata.get("items", []) if isinstance(metadata, dict) else []
        for item in items:
            if item.get("key", "") == "user-data":
                body = item.get("value", "")
                if "tailscale" in body and "bringup" in body:
                    found = True
    assert found is True
    return


@testbase.attach.parameter(create_gcp_make_provisioner, identifier="make_provisioner")
def test_destroy_requires_confirm(make_provisioner, aspects) -> None:
    """
        destroy without aspects.confirm=True raises.
    """
    provisioner, _ = make_provisioner(spec=basic_spec())
    provisioner.apply(aspects=aspects)
    with pytest.raises(SchemaSemanticError):
        provisioner.destroy(aspects=aspects)
    return


@testbase.attach.parameter(create_gcp_make_provisioner, identifier="make_provisioner")
def test_destroy_is_inverse_of_apply(make_provisioner, aspects,
                                     confirm_aspects) -> None:
    """
        After destroy, the inventory comes back empty.
    """
    provisioner, _ = make_provisioner(spec=basic_spec())
    provisioner.apply(aspects=aspects)
    inv_before = provisioner.inventory(aspects=aspects)
    assert len(inv_before) > 0

    provisioner.destroy(aspects=confirm_aspects)

    inv_after = provisioner.inventory(aspects=aspects)
    assert len(inv_after) == 0
    return


@testbase.attach.parameter(create_gcp_make_provisioner, identifier="make_provisioner")
def test_gpu_sku_resolution(make_provisioner, aspects) -> None:
    """
        H100_SXM resolves to ``a3-highgpu-8g`` as the machine type.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    spec = basic_spec(instance_size="a3-highgpu-8g", accelerators=[accel])
    provisioner, _ = make_provisioner(spec=spec)
    result = provisioner.apply(aspects=aspects)
    inst = None
    for resource in result.created:
        if resource.kind == "instance":
            inst = resource
    assert inst is not None
    assert inst.attributes.get("machine_type", "") == "a3-highgpu-8g"
    return


@testbase.attach.parameter(create_gcp_make_provisioner, identifier="make_provisioner")
def test_compact_placement_grouping(make_provisioner, aspects) -> None:
    """
        N instances sharing a compact group produce one ResourcePolicy and
        N instances.insert calls referencing it.
    """
    provisioner, fakes = make_provisioner(spec=gpu_compact_spec(
        member_count=3
    ))
    result = provisioner.apply(aspects=aspects)

    policies = fakes["compute"]["resource_policies"].list()
    assert len(policies) == 1

    instance_resources = [r for r in result.created
                          if r.kind == "instance"]
    assert len(instance_resources) == 3
    for resource in instance_resources:
        assert "placement_policy" in resource.attributes
    assert fakes["compute"]["instances"].insert_calls == 3
    return


@testbase.attach.parameter(create_gcp_make_provisioner, identifier="make_provisioner")
def test_tpu_branch_creates_node(make_provisioner, aspects) -> None:
    """
        A TPU spec provisions a TPU node, not a Compute Engine instance.
    """
    provisioner, fakes = make_provisioner(spec=tpu_spec())
    result = provisioner.apply(aspects=aspects)

    tpu_resources = [r for r in result.created if r.kind == "tpu"]
    assert len(tpu_resources) == 1
    assert fakes["tpu"].create_calls == 1
    assert tpu_resources[0].attributes.get("accelerator_type", "") == "tpu-v5p"
    return


@testbase.attach.parameter(create_gcp_make_provisioner, identifier="make_provisioner")
def test_tpu_branch_isolation(make_provisioner, aspects) -> None:
    """
        TPU spec produces zero Compute Engine instance calls; GPU spec
        produces zero TPU API calls.
    """
    tpu_prov, tpu_fakes = make_provisioner(spec=tpu_spec())
    tpu_prov.apply(aspects=aspects)
    assert tpu_fakes["compute"]["instances"].insert_calls == 0
    assert tpu_fakes["tpu"].create_calls == 1

    gpu_prov, gpu_fakes = make_provisioner(spec=gpu_compact_spec(
        member_count=2
    ))
    gpu_prov.apply(aspects=aspects)
    assert gpu_fakes["tpu"].create_calls == 0
    assert gpu_fakes["compute"]["instances"].insert_calls == 2
    return


@testbase.attach.parameter(create_gcp_make_provisioner, identifier="make_provisioner")
def test_tpu_in_inventory(make_provisioner, aspects) -> None:
    """
        A provisioned TPU node appears in inventory with kind 'tpu'.
    """
    provisioner, _ = make_provisioner(spec=tpu_spec())
    provisioner.apply(aspects=aspects)
    inventory = provisioner.inventory(aspects=aspects)
    tpu_entries = [r for r in inventory if r.kind == "tpu"]
    assert len(tpu_entries) == 1
    assert len(tpu_entries[0].attributes.get("host_ips", [])) > 0
    return


@testbase.attach.parameter(create_gcp_make_provisioner, identifier="make_provisioner")
def test_preemption_fail_uses_standard(make_provisioner, aspects) -> None:
    """
        PreemptionPolicy.FAIL produces a STANDARD (non-spot) instance.
    """
    spec = basic_spec(preemption=PreemptionPolicy.FAIL)
    provisioner, fakes = make_provisioner(spec=spec)
    provisioner.apply(aspects=aspects)
    for entry in fakes["compute"]["instances"].list():
        scheduling = entry.scheduling
        assert scheduling.get("preemptible", False) is False
        assert scheduling.get("provisioning_model", "") == "STANDARD"
    return


@testbase.attach.parameter(create_gcp_make_provisioner, identifier="make_provisioner")
def test_preemption_reacquire_uses_spot(make_provisioner, aspects) -> None:
    """
        PreemptionPolicy.REACQUIRE produces a SPOT preemptible instance.
    """
    spec = basic_spec(preemption=PreemptionPolicy.REACQUIRE)
    provisioner, fakes = make_provisioner(spec=spec)
    provisioner.apply(aspects=aspects)
    for entry in fakes["compute"]["instances"].list():
        scheduling = entry.scheduling
        assert scheduling.get("preemptible", False) is True
        assert scheduling.get("provisioning_model", "") == "SPOT"
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

            :param device_id: Device id removed.
            :param aspects: Aspects.
        """
        self.deleted_ids.append(device_id)
        return


@testbase.attach.parameter(create_gcp_make_provisioner, identifier="make_provisioner")
def test_destroy_calls_vpn_delete_device(make_provisioner, aspects,
                                         confirm_aspects) -> None:
    """
        When vpn_join was set and a device id recorded, destroy invokes
        the control plane delete_device (Tailscale device cleanup).
    """
    vpn = _RecordingVPN()
    provisioner, _ = make_provisioner(spec=basic_spec(with_vpn=True),
                                      vpn_control_plane=vpn)
    provisioner.apply(aspects=aspects)
    provisioner.record_vpn_device(instance_name="inst-a",
                                  device_id="device-abc")

    provisioner.destroy(aspects=confirm_aspects)

    assert "device-abc" in vpn.deleted_ids
    return


@testbase.attach.parameter(create_gcp_make_provisioner, identifier="make_provisioner")
def test_plan_emits_delete_for_owned_orphan(make_provisioner, venue,
                                            credential, region_config,
                                            aspects) -> None:
    """
        An owner-tagged resource that is absent from the desired spec is
        surfaced as a DELETE action by the plan-side orphan scan.
    """
    full_spec = basic_spec()
    provisioner, fakes = make_provisioner(spec=full_spec)
    # Realise the full spec so the instance carries ccai owner labels.
    provisioner.apply(aspects=aspects)

    # Build a second provisioner over the SAME fake clients but a spec
    # from which the instance + volume have been dropped.  Those resources
    # are now owner-tagged orphans.
    spec_without_instance = GcpSpec(
        networks=list(full_spec.networks),
        subnets=list(full_spec.subnets),
        security_groups=list(full_spec.security_groups),
        instances=[],
        volumes=[],
        buckets=list(full_spec.buckets),
    )
    orphan_provisioner = GoogleCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec_without_instance,
    )
    factory = orphan_provisioner.session_factory
    factory.set_client(service_name=SERVICE_COMPUTE, client=fakes["compute"])
    factory.set_client(service_name=SERVICE_TPU, client=fakes["tpu"])
    factory.set_client(service_name=SERVICE_STORAGE, client=fakes["storage"])
    factory.set_client(service_name=SERVICE_DNS, client=fakes["dns"])

    plan = orphan_provisioner.plan(aspects=aspects)

    delete_actions = [
        a for a in plan.actions
        if a.intent == PlannedActionIntent.DELETE.value
    ]
    deleted_names = {a.resource_name for a in delete_actions}
    assert "inst-a" in deleted_names
    orphan = next(a for a in delete_actions if a.resource_name == "inst-a")
    assert orphan.resource_kind == "instance"
    return
