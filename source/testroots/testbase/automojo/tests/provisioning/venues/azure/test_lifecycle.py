"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: End-to-end validate/plan/apply/destroy tests against the
               in-memory fake azure-mgmt clients.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import base64

import pytest

from automojo.provisioning.model.exceptions import SchemaSemanticError

from hypothesis import given, HealthCheck, settings
from hypothesis import strategies as st

from automojo.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from automojo.provisioning.model.cloud.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from automojo.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from automojo.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy
from automojo.provisioning.venues.azure.azurecloudprovisioner import (
    AzureCloudProvisioner
)
from automojo.provisioning.venues.azure.azuresessionfactory import (
    AzureSessionFactory
)
from automojo.provisioning.venues.azure.azurespec import AzureSpec

from ._fakeazure import FakeAzureWorld
from ._specfactory import basic_spec, ib_instance


def _provisioner(*, venue, credential, region_config, session_factory,
                 spec, vpn_control_plane=None):
    """
        Helper: build an AzureCloudProvisioner wired to the fake clients.
    """
    rtnval = AzureCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec, session_factory=session_factory,
        vpn_control_plane=vpn_control_plane,
    )
    return rtnval


def test_plan_then_apply_creates_resources(venue, credential,
                                           region_config, session_factory,
                                           aspects) -> None:
    """
        First plan reports CREATEs; apply produces matching resources.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)

    plan = provisioner.plan(aspects=aspects)
    intents = [a.intent for a in plan.actions]
    assert PlannedActionIntent.CREATE.value in intents

    result = provisioner.apply(aspects=aspects)
    kinds = {r.kind for r in result.created}
    assert {"resource_group", "network", "sg", "subnet", "nic", "instance",
            "volume", "bucket"}.issubset(kinds)
    return


def test_resource_group_created_first(venue, credential, region_config,
                                      session_factory, world,
                                      aspects) -> None:
    """
        The apex ResourceGroup exists in the world after apply.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    provisioner.apply(aspects=aspects)
    assert "rg-testrun01" in world.resource_groups
    return


def test_apply_idempotent(venue, credential, region_config,
                          session_factory, aspects) -> None:
    """
        Re-applying produces only SKIPs and no new created resources.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    provisioner.apply(aspects=aspects)
    second = provisioner.apply(aspects=aspects)

    skipped_names = set(second.skipped)
    assert "rg-testrun01" in skipped_names
    assert "vnet-a" in skipped_names
    assert "nsg-a" in skipped_names
    assert "sub-a" in skipped_names
    assert "inst-a" in skipped_names
    assert "vol-a" in skipped_names
    assert "bkta" in skipped_names

    # Re-plan: every create-tracked kind is now SKIP.
    plan = provisioner.plan(aspects=aspects)
    create_kinds = [a for a in plan.actions
                    if a.intent == PlannedActionIntent.CREATE.value
                    and a.resource_kind not in ("dns",)]
    assert len(create_kinds) == 0
    return


@settings(max_examples=15, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(runid=st.text(min_size=4, max_size=12,
                     alphabet=st.characters(min_codepoint=0x61,
                                            max_codepoint=0x7a)))
def test_apply_apply_idempotence_property(venue, credential,
                                          region_config, runid) -> None:
    """
        Property: apply ∘ apply has the same inventory as apply.

        A fresh world is built per example so the run identifier varies.
    """
    world = FakeAzureWorld(location="eastus")
    factory = AzureSessionFactory(credential=credential,
                                  region_config=region_config)
    factory.override_clients(
        resource=world.resource_client(),
        network=world.network_client(),
        compute=world.compute_client(),
        storage=world.storage_client(),
        dns=world.dns_client(),
    )
    aspects = ProvisioningAspects(runid=runid, verify_timeout=30.0,
                                  verify_interval=0.05)
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=factory, spec=spec)
    provisioner.apply(aspects=aspects)
    inv_one = provisioner.inventory(aspects=aspects)
    provisioner.apply(aspects=aspects)
    inv_two = provisioner.inventory(aspects=aspects)
    names_one = sorted(r.name for r in inv_one)
    names_two = sorted(r.name for r in inv_two)
    assert names_one == names_two
    return


def test_apply_with_vpn_join_injects_custom_data(venue, credential,
                                                 region_config,
                                                 session_factory, world,
                                                 aspects) -> None:
    """
        Linux VMs with vpn_join carry base64-encoded cloud-init in
        ``os_profile.custom_data`` containing the tailscale bring-up.
    """
    spec = basic_spec(with_vpn=True)
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    provisioner.apply(aspects=aspects)

    vm = world.vms["rg-testrun01/inst-a"]
    os_profile = vm.os_profile
    encoded = getattr(os_profile, "custom_data", "")
    assert encoded is not None and len(encoded) > 0
    decoded = base64.b64decode(encoded).decode("utf-8")
    assert "tailscale" in decoded
    assert "bringup" in decoded
    return


def test_apply_vpn_join_records_device(venue, credential, region_config,
                                       session_factory, aspects) -> None:
    """
        Applying a VPN-joined spec records a VPN device entry.
    """
    spec = basic_spec(with_vpn=True)
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    provisioner.apply(aspects=aspects)
    records = provisioner.last_vpn_records
    assert len(records) == 1
    assert records[0]["instance_name"] == "inst-a"
    return


def test_inventory_enumerates_subnets_and_nics(venue, credential,
                                               region_config,
                                               session_factory,
                                               aspects) -> None:
    """
        Regression for PV-H1: ``inventory`` enumerates the subnets and NICs
        that ``apply`` creates — not just the top-level resources — so an
        inventory-driven destroy does not leak them.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    provisioner.apply(aspects=aspects)

    kinds = {resource.kind
             for resource in provisioner.inventory(aspects=aspects)}
    assert "subnet" in kinds
    assert "nic" in kinds
    return


def test_destroy_requires_confirm(venue, credential, region_config,
                                  session_factory, aspects) -> None:
    """
        destroy without aspects.confirm=True raises.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    provisioner.apply(aspects=aspects)
    with pytest.raises(SchemaSemanticError):
        provisioner.destroy(aspects=aspects)
    return


def test_destroy_reverses_apply(venue, credential, region_config,
                                session_factory, aspects,
                                confirm_aspects) -> None:
    """
        After destroy, the inventory comes back empty and the
        ResourceGroup is removed.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    provisioner.apply(aspects=aspects)
    inventory_before = provisioner.inventory(aspects=aspects)
    assert len(inventory_before) > 0

    provisioner.destroy(aspects=confirm_aspects)

    inventory_after = provisioner.inventory(aspects=aspects)
    assert len(inventory_after) == 0
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


def test_destroy_calls_vpn_delete_device(venue, credential, region_config,
                                         session_factory, aspects,
                                         confirm_aspects) -> None:
    """
        When vpn_join was set and a device id was recorded, destroy
        invokes the control plane delete_device.
    """
    spec = basic_spec(with_vpn=True)
    vpn = _RecordingVPN()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec,
                               vpn_control_plane=vpn)
    provisioner.apply(aspects=aspects)
    provisioner.record_vpn_device(instance_name="inst-a",
                                  device_id="device-abc")

    provisioner.destroy(aspects=confirm_aspects)

    assert "device-abc" in vpn.deleted_ids
    return


def test_gpu_sku_resolution(venue, credential, region_config,
                            session_factory, aspects) -> None:
    """
        H100_SXM resolves to ``Standard_ND96isr_H100_v5`` and ends up as the
        VM size on the launched VM.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    spec = basic_spec(instance_size="Standard_ND96isr_H100_v5",
                      accelerators=[accel])
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    result = provisioner.apply(aspects=aspects)
    inst_resource = None
    for resource in result.created:
        if resource.kind == "instance":
            inst_resource = resource
    assert inst_resource is not None
    assert inst_resource.attributes.get("vm_size",
                                        "") == "Standard_ND96isr_H100_v5"
    return


def test_ib_sku_creates_proximity_placement_group(venue, credential,
                                                  region_config,
                                                  session_factory, world,
                                                  aspects) -> None:
    """
        An InfiniBand SKU lands the VM into a Proximity Placement Group.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    spec = basic_spec(instance_size="Standard_ND96isr_H100_v5",
                      accelerators=[accel], placement_group="ib-cluster")
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    provisioner.apply(aspects=aspects)

    assert "rg-testrun01/ib-cluster-ppg" in world.ppgs
    vm = world.vms["rg-testrun01/inst-a"]
    ppg = getattr(vm, "proximity_placement_group", None)
    assert ppg is not None
    return


def test_ndv5_ppg_grouping(venue, credential, region_config,
                           session_factory, world, aspects) -> None:
    """
        Two InfiniBand VMs sharing an interconnect_group land in the same
        Proximity Placement Group.
    """
    spec = basic_spec()
    spec.instances = [
        ib_instance(name="ib-a", interconnect_group="cluster-x"),
        ib_instance(name="ib-b", interconnect_group="cluster-x"),
    ]
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    provisioner.apply(aspects=aspects)

    vm_a = world.vms["rg-testrun01/ib-a"]
    vm_b = world.vms["rg-testrun01/ib-b"]
    ppg_a = vm_a.proximity_placement_group.id
    ppg_b = vm_b.proximity_placement_group.id
    assert ppg_a == ppg_b
    # Exactly one PPG was created for the shared group.
    assert len([k for k in world.ppgs if "cluster-x-ppg" in k]) == 1
    return


def test_preemption_policy_fail_uses_regular_vm(venue, credential,
                                                region_config,
                                                session_factory, world,
                                                aspects) -> None:
    """
        PreemptionPolicy.FAIL produces a regular (non-spot) VM.
    """
    spec = basic_spec(preemption=PreemptionPolicy.FAIL)
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    provisioner.apply(aspects=aspects)
    vm = world.vms["rg-testrun01/inst-a"]
    assert getattr(vm, "priority", None) != "Spot"
    return


def test_preemption_policy_reacquire_uses_spot(venue, credential,
                                               region_config,
                                               session_factory, world,
                                               aspects) -> None:
    """
        PreemptionPolicy.REACQUIRE produces a Spot VM with an eviction
        policy.
    """
    spec = basic_spec(preemption=PreemptionPolicy.REACQUIRE)
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    result = provisioner.apply(aspects=aspects)
    vm = world.vms["rg-testrun01/inst-a"]
    assert getattr(vm, "priority", None) == "Spot"
    assert getattr(vm, "eviction_policy", None) == "Deallocate"

    inst_resource = None
    for resource in result.created:
        if resource.kind == "instance":
            inst_resource = resource
    assert inst_resource is not None
    assert inst_resource.attributes.get("preemption_policy",
                                        "") == "REACQUIRE"
    return


def test_apply_disk_uses_standard_ssd_lrs(venue, credential, region_config,
                                          session_factory, world,
                                          aspects) -> None:
    """
        A ``standard`` neutral StorageClass maps to a StandardSSD_LRS disk.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    provisioner.apply(aspects=aspects)
    disk = world.disks["rg-testrun01/vol-a"]
    assert disk.sku.name == "StandardSSD_LRS"
    return


def test_apply_keypair_injected_into_vm(venue, credential, region_config,
                                        session_factory, world,
                                        aspects) -> None:
    """
        The CloudKeyPair public key lands in the VM's linux_configuration
        SSH block (Azure has no native key-pair resource).
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    provisioner.apply(aspects=aspects)
    vm = world.vms["rg-testrun01/inst-a"]
    linux_cfg = vm.os_profile.linux_configuration
    ssh_block = getattr(linux_cfg, "ssh", None)
    assert ssh_block is not None
    return


def test_destroy_preserves_foreign_resource_group(venue, credential,
                                                  region_config,
                                                  session_factory, world,
                                                  aspects,
                                                  confirm_aspects) -> None:
    """
        A ResourceGroup containing a resource not tagged with the run-id is
        left intact by destroy.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    provisioner.apply(aspects=aspects)

    # Inject a foreign (un-owned) resource into the group.
    from ._fakeazure import FakeResource
    world.vnets["rg-testrun01/foreign-vnet"] = FakeResource(
        name="foreign-vnet", location="eastus",
        id="/fake/eastus/foreign-vnet", tags={"owner": "someone-else"},
    )

    provisioner.destroy(aspects=confirm_aspects)
    # The foreign resource keeps the group alive.
    assert "rg-testrun01" in world.resource_groups
    return


def test_plan_emits_delete_for_owned_orphan(venue, credential,
                                            region_config, session_factory,
                                            aspects) -> None:
    """
        An owner-tagged resource that is absent from the desired spec is
        surfaced as a DELETE action by the plan-side orphan scan.
    """
    full_spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory,
                               spec=full_spec)
    # Realise the full spec so the instance carries automojo owner tags.
    provisioner.apply(aspects=aspects)

    # Re-plan against a spec from which the instance + volume have been
    # dropped; those resources are now owner-tagged orphans.
    spec_without_instance = AzureSpec(
        networks=list(full_spec.networks),
        subnets=list(full_spec.subnets),
        security_groups=list(full_spec.security_groups),
        keypairs=list(full_spec.keypairs),
        instances=[],
        volumes=[],
        buckets=list(full_spec.buckets),
    )
    orphan_provisioner = _provisioner(venue=venue, credential=credential,
                                      region_config=region_config,
                                      session_factory=session_factory,
                                      spec=spec_without_instance)
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
