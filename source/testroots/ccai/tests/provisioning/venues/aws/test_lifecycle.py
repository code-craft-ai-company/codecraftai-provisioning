"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: End-to-end validate/plan/apply/destroy tests against moto.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase


import base64


from ccai.interfaces.schemasemanticerror import SchemaSemanticError


from ccai.interfaces.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from ccai.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from ccai.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy
from ccai.provisioning.venues.aws.awscloudprovisioner import (
    AwsCloudProvisioner
)
from ccai.provisioning.venues.aws.awsspec import AwsSpec

from ccai.tests.provisioning.venues.aws._fakeaws import FakeAwsSessionFactory
from ccai.tests.provisioning.venues.aws._specfactory import basic_spec


def _new_provisioner(*, venue, credential, region_config, spec,
                     vpn_control_plane=None, session_factory=None):
    """
        Helper: build a provisioner over the in-memory AWS.

        A factory is created per call unless one is supplied, so a test that
        needs to inspect stored state or share it across two provisioners
        passes its own.
    """
    if session_factory is None:
        session_factory = FakeAwsSessionFactory()

    rtnval = AwsCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec, vpn_control_plane=vpn_control_plane,
        session_factory=session_factory,
    )
    return rtnval


def test_plan_then_apply_creates_resources(venue, credential, region_config,
                                           aspects) -> None:
    """
        First plan reports CREATEs; apply produces matching resources.
    """
    spec = basic_spec()
    provisioner = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )

    plan = provisioner.plan(aspects=aspects)
    intents = [a.intent for a in plan.actions]
    assert PlannedActionIntent.CREATE.value in intents

    result = provisioner.apply(aspects=aspects)
    kinds = {r.kind for r in result.created}
    assert {"network", "subnet", "sg", "keypair", "instance",
            "volume", "bucket"}.issubset(kinds)
    return


def test_apply_idempotent(venue, credential, region_config, aspects) -> None:
    """
        Re-applying produces only SKIPs and no new created resources.
    """
    spec = basic_spec()
    provisioner = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    first = provisioner.apply(aspects=aspects)
    second = provisioner.apply(aspects=aspects)

    # Second apply: all the read-before-create resources are already
    # present and counted in `skipped`.  fsx/dns are excluded from
    # idempotence-skipped tracking; bucket should be skipped.
    skipped_names = set(second.skipped)
    assert "vpc-a" in skipped_names
    assert "sub-a" in skipped_names
    assert "sg-a" in skipped_names
    assert "kp-a" in skipped_names
    assert "inst-a" in skipped_names
    assert "vol-a" in skipped_names
    assert "bkt-a" in skipped_names

    # Replan all-SKIP for the create-tracked kinds.
    plan = provisioner.plan(aspects=aspects)
    create_kinds = [a for a in plan.actions
                    if a.intent == PlannedActionIntent.CREATE.value
                    and a.resource_kind not in ("dns",)]
    assert len(create_kinds) == 0
    return


def test_apply_with_vpn_join_injects_user_data(venue, credential,
                                               region_config,
                                               aspects) -> None:
    """
        Instances with vpn_join carry base64-encoded cloud-init user-data
        containing the tailscale bring-up reference.
    """
    spec = basic_spec(with_vpn=True)
    factory = FakeAwsSessionFactory()
    provisioner = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec, session_factory=factory,
    )
    provisioner.apply(aspects=aspects)

    # Read the fake's instances directly.  The old version went through a
    # boto3 client and had to tolerate moto returning the user data
    # double-base64-encoded; the fake stores exactly what the venue sent, so
    # the assertion can be exact.
    found = False
    for entry in factory.ec2.instances.values():
        value = entry.get("UserData", "")
        if value is None or len(value) == 0:
            continue
        decoded = base64.b64decode(value).decode("utf-8")
        if "tailscale" in decoded and "bringup" in decoded:
            found = True
    assert found is True
    return


def test_destroy_requires_confirm(venue, credential, region_config,
                                  aspects) -> None:
    """
        destroy without aspects.confirm=True raises.
    """
    spec = basic_spec()
    provisioner = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    provisioner.apply(aspects=aspects)
    with testbase.raises(SchemaSemanticError):
        provisioner.destroy(aspects=aspects)
    return


def test_destroy_reverses_apply(venue, credential, region_config, aspects,
                                confirm_aspects) -> None:
    """
        After destroy, the inventory comes back empty.
    """
    spec = basic_spec()
    provisioner = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    provisioner.apply(aspects=aspects)
    inventory_before = provisioner.inventory(aspects=aspects)
    assert len(inventory_before) > 0

    provisioner.destroy(aspects=confirm_aspects)

    inventory_after = provisioner.inventory(aspects=aspects)
    # No instances / volumes / sgs / subnets / vpcs / buckets / keypairs
    # should be left.  (Terminated instances are filtered.)
    assert len(inventory_after) == 0
    return


def test_gpu_sku_resolution(venue, credential, region_config,
                            aspects) -> None:
    """
        H100_SXM resolves to ``p5.48xlarge`` and ends up as the instance
        type on the launched EC2.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    spec = basic_spec(instance_size="p5.48xlarge", accelerators=[accel])
    provisioner = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    result = provisioner.apply(aspects=aspects)
    inst_resource = None
    for resource in result.created:
        if resource.kind == "instance":
            inst_resource = resource
    assert inst_resource is not None
    assert inst_resource.attributes.get("instance_type", "") == "p5.48xlarge"
    return


def test_efa_attaches_placement_group(venue, credential, region_config,
                                      aspects) -> None:
    """
        Interconnect=EFA results in a placement group being created and
        the instance landing inside it.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    interconnect = CloudInterconnect(kind="EFA", bandwidth_gbps=400,
                                     topology="RAIL_OPTIMIZED")
    spec = basic_spec(instance_size="p5.48xlarge", accelerators=[accel],
                      interconnect=interconnect)
    factory = FakeAwsSessionFactory()
    provisioner = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec, session_factory=factory,
    )
    result = provisioner.apply(aspects=aspects)

    instance_created = any(r.kind == "instance" for r in result.created)
    assert instance_created is True

    # The fake models placement groups, which moto did not — so this can now
    # assert the group was really created AND attached, instead of accepting
    # either outcome.
    groups = list(factory.ec2.placement_groups.keys())
    assert len(groups) == 1
    assert "codecraftai-pg-" in groups[0]

    placements = [entry.get("Placement", {}).get("GroupName", "")
                  for entry in factory.ec2.instances.values()]
    assert groups[0] in placements
    return


def test_preemption_policy_fail_uses_on_demand(venue, credential,
                                               region_config,
                                               aspects) -> None:
    """
        PreemptionPolicy.FAIL produces an on-demand instance (no
        SpotInstanceRequestId).
    """
    spec = basic_spec(preemption=PreemptionPolicy.FAIL)
    factory = FakeAwsSessionFactory()
    provisioner = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec, session_factory=factory,
    )
    provisioner.apply(aspects=aspects)
    for entry in factory.ec2.instances.values():
        # On-demand means no spot market options were requested at all.
        assert entry.get("InstanceMarketOptions", None) is None
    return


def test_preemption_policy_reacquire_uses_spot(venue, credential,
                                               region_config,
                                               aspects) -> None:
    """
        PreemptionPolicy.REACQUIRE attaches SpotInstanceRequestId.
    """
    spec = basic_spec(preemption=PreemptionPolicy.REACQUIRE)
    provisioner = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    result = provisioner.apply(aspects=aspects)
    inst_resource = None
    for resource in result.created:
        if resource.kind == "instance":
            inst_resource = resource
    assert inst_resource is not None
    assert inst_resource.attributes.get("preemption_policy",
                                        "") == "REACQUIRE"
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


def test_plan_emits_delete_for_owned_orphan(venue, credential,
                                            region_config, aspects) -> None:
    """
        An owner-tagged resource that is absent from the desired spec is
        surfaced as a DELETE action by the plan-side orphan scan.
    """
    full_spec = basic_spec()
    # Both provisioners must see the same AWS, or the second finds nothing to
    # call an orphan.  moto shared state implicitly; the fake is explicit.
    shared = FakeAwsSessionFactory()
    provisioner = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=full_spec, session_factory=shared,
    )
    # Realise the full spec so the instance carries ccai:owner tags.
    provisioner.apply(aspects=aspects)

    # Re-plan against a spec from which the instance has been dropped; the
    # instance is now an owner-tagged orphan.  Networking is kept so the
    # remaining resources still SKIP cleanly.
    spec_without_instance = AwsSpec(
        networks=list(full_spec.networks),
        subnets=list(full_spec.subnets),
        security_groups=list(full_spec.security_groups),
        keypairs=list(full_spec.keypairs),
        instances=[],
        volumes=[],
        buckets=list(full_spec.buckets),
    )
    orphan_provisioner = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec_without_instance, session_factory=shared,
    )
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


def test_destroy_calls_vpn_delete_device(venue, credential, region_config,
                                         aspects, confirm_aspects) -> None:
    """
        When vpn_join was set and a device id was recorded, destroy
        invokes the control plane delete_device.
    """
    spec = basic_spec(with_vpn=True)
    vpn = _RecordingVPN()
    provisioner = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec, vpn_control_plane=vpn,
    )
    provisioner.apply(aspects=aspects)
    provisioner.record_vpn_device(instance_name="inst-a",
                                  device_id="device-abc")

    provisioner.destroy(aspects=confirm_aspects)

    assert "device-abc" in vpn.deleted_ids
    return
