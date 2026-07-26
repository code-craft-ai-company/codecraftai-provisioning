"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Lifecycle + property tests for the Crusoe venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import sys

from pathlib import Path

import pytest

from ccai.interfaces.schemasemanticerror import SchemaSemanticError

from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.errors.exceptions import SemanticError

from ccai.interfaces.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from ccai.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from ccai.provisioning.model.cloud.cloudloadbalancer import (
    CloudLoadBalancer
)
from ccai.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
from ccai.interfaces.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)

from ccai.provisioning.venues.crusoe.crusoecloudprovisioner import (
    CrusoeCloudProvisioner
)
from ccai.provisioning.venues.crusoe.crusoeerrors import (
    CrusoeValidationError
)

sys.path.insert(0, str(Path(__file__).parent))

from _mockclient import MockCrusoeClient  # noqa: E402
from _specfactory import basic_spec  # noqa: E402
from conftest import make_provisioner, _Aspects  # noqa: E402


# ----------------------------------------------------------------------
# validate
# ----------------------------------------------------------------------

def test_validate_happy_path(crusoe_venue, mock_client, project_config,
                             crusoe_aspects) -> None:
    """
        A conformant CrusoeSpec validates successfully.
    """
    spec = basic_spec()
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    result = prov.validate(aspects=crusoe_aspects)
    assert result.ok is True
    return


def test_validate_rejects_bucket(crusoe_venue, mock_client, project_config,
                                 crusoe_aspects) -> None:
    """
        A CloudObjectBucket is rejected — Crusoe has no native object store.
    """
    spec = basic_spec()
    spec.buckets.append(CloudObjectBucket(name="b1", region="us-east1"))
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    with pytest.raises(CrusoeValidationError):
        prov.validate(aspects=crusoe_aspects)
    return


def test_validate_rejects_load_balancer(crusoe_venue, mock_client,
                                        project_config,
                                        crusoe_aspects) -> None:
    """
        A CloudLoadBalancer is rejected — Crusoe exposes no LB surface.
    """
    spec = basic_spec()
    spec.load_balancers.append(CloudLoadBalancer(name="lb1",
                                                 scheme="internal"))
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    with pytest.raises(CrusoeValidationError):
        prov.validate(aspects=crusoe_aspects)
    return


def test_validate_rejects_unsupported_fs(crusoe_venue, mock_client,
                                         project_config,
                                         crusoe_aspects) -> None:
    """
        A non-VENUE_NATIVE shared filesystem is rejected.
    """
    spec = basic_spec()
    spec.shared_filesystems.append(
        CloudSharedFilesystem(name="fs1", kind="WEKA", size_tb=10))
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    with pytest.raises(CrusoeValidationError):
        prov.validate(aspects=crusoe_aspects)
    return


def test_validate_rejects_native_fs_without_existing_id(
        crusoe_venue, mock_client, project_config, crusoe_aspects) -> None:
    """
        A VENUE_NATIVE shared filesystem without existing_id is rejected.
    """
    spec = basic_spec()
    spec.shared_filesystems.append(
        CloudSharedFilesystem(name="fs1", kind="VENUE_NATIVE", size_tb=10))
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    with pytest.raises(CrusoeValidationError):
        prov.validate(aspects=crusoe_aspects)
    return


def test_validate_rejects_ib_on_non_ib_instance(crusoe_venue, mock_client,
                                                project_config,
                                                crusoe_aspects) -> None:
    """
        An InfiniBand interconnect on a non-IB-eligible instance is rejected.
    """
    interconnect = CloudInterconnect(kind="INFINIBAND_NDR",
                                     bandwidth_gbps=400)
    spec = basic_spec(interconnect=interconnect, instance_size="c1.small")
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    with pytest.raises(CrusoeValidationError):
        prov.validate(aspects=crusoe_aspects)
    return


def test_validate_accepts_ib_on_gpu_sku(crusoe_venue, mock_client,
                                        project_config,
                                        crusoe_aspects) -> None:
    """
        An InfiniBand interconnect on an H100_SXM accelerator (resolves to an
        IB-eligible SKU) validates successfully.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    interconnect = CloudInterconnect(kind="INFINIBAND_NDR",
                                     bandwidth_gbps=400)
    spec = basic_spec(accelerators=[accel], interconnect=interconnect)
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    result = prov.validate(aspects=crusoe_aspects)
    assert result.ok is True
    return


# ----------------------------------------------------------------------
# plan
# ----------------------------------------------------------------------

def test_plan_all_create_on_empty_venue(crusoe_venue, mock_client,
                                        project_config,
                                        crusoe_aspects) -> None:
    """
        On an empty venue every planned action is a CREATE.
    """
    spec = basic_spec()
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    plan = prov.plan(aspects=crusoe_aspects)
    intents = {a.intent for a in plan.actions}
    assert intents == {PlannedActionIntent.CREATE.value}
    return


def test_re_plan_after_apply_is_all_skip(crusoe_venue, mock_client,
                                         project_config,
                                         crusoe_aspects) -> None:
    """
        After apply, a re-plan reports every action as SKIP.
    """
    spec = basic_spec()
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    prov.apply(aspects=crusoe_aspects)
    plan = prov.plan(aspects=crusoe_aspects)
    intents = {a.intent for a in plan.actions}
    assert intents == {PlannedActionIntent.SKIP.value}
    return


# ----------------------------------------------------------------------
# apply
# ----------------------------------------------------------------------

def test_apply_creates_resources(crusoe_venue, mock_client, project_config,
                                 crusoe_aspects) -> None:
    """
        apply on an empty venue creates the VPC, subnet, SG, key, VM, disk.
    """
    spec = basic_spec()
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    result = prov.apply(aspects=crusoe_aspects)
    kinds = {r.kind for r in result.created}
    assert "network" in kinds
    assert "subnet" in kinds
    assert "instance" in kinds
    assert "volume" in kinds
    return


def test_apply_with_vpn_join_renders_user_data(crusoe_venue, mock_client,
                                               project_config,
                                               crusoe_aspects) -> None:
    """
        An instance with vpn_join produces a cloud-init user_data payload on
        the launch spec.
    """
    spec = basic_spec(with_vpn=True)
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    prov.apply(aspects=crusoe_aspects)
    launch_spec = mock_client.vms.launch_specs[0]
    assert launch_spec.user_data is not None
    assert "#cloud-config" in launch_spec.user_data
    return


def test_apply_idempotent_second_run_makes_no_creates(
        crusoe_venue, mock_client, project_config, crusoe_aspects) -> None:
    """
        apply ∘ apply: the second apply creates nothing and skips everything.
    """
    spec = basic_spec()
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    prov.apply(aspects=crusoe_aspects)
    second = prov.apply(aspects=crusoe_aspects)
    assert len(second.created) == 0
    assert len(second.skipped) > 0
    return


def test_apply_reapply_makes_no_vpc_or_sshkey_mutations(
        crusoe_venue, mock_client, project_config, crusoe_aspects) -> None:
    """
        Regression for C9 / C10: a second ``apply`` must not call
        ``vpcs.create`` or ``ssh_keys.register`` again — re-applying an
        already-realised VPC / SSH key reuses the existing record.
    """
    spec = basic_spec()
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)

    prov.apply(aspects=crusoe_aspects)
    vpc_creates_after_first = mock_client.vpcs.create_calls
    key_registers_after_first = mock_client.ssh_keys.register_calls
    assert vpc_creates_after_first > 0
    assert key_registers_after_first > 0

    prov.apply(aspects=crusoe_aspects)
    assert mock_client.vpcs.create_calls == vpc_creates_after_first
    assert mock_client.ssh_keys.register_calls == key_registers_after_first
    return


def test_apply_resolves_gpu_sku(crusoe_venue, mock_client, project_config,
                                crusoe_aspects) -> None:
    """
        An instance carrying an H100_SXM accelerator launches on the resolved
        Crusoe GPU SKU.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    spec = basic_spec(accelerators=[accel])
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    prov.apply(aspects=crusoe_aspects)
    launch_spec = mock_client.vms.launch_specs[0]
    assert launch_spec.instance_type == "h100-80gb-sxm5.8x"
    return


def test_apply_attaches_ib_partition(crusoe_venue, mock_client,
                                     project_config, crusoe_aspects) -> None:
    """
        IB-grouped GPU instances are attached to a created IB partition.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    interconnect = CloudInterconnect(kind="INFINIBAND_NDR",
                                     bandwidth_gbps=400)
    spec = basic_spec(accelerators=[accel], interconnect=interconnect)
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    prov.apply(aspects=crusoe_aspects)
    launch_spec = mock_client.vms.launch_specs[0]
    assert launch_spec.placement_group_id is not None
    partitions = mock_client.placement_groups.list(project_id="proj-1")
    assert len(partitions) == 1
    assert partitions[0].labels.get("codecraftai-run-id") == "run-1"
    return


# ----------------------------------------------------------------------
# destroy
# ----------------------------------------------------------------------

def test_destroy_requires_confirm(crusoe_venue, mock_client, project_config,
                                  crusoe_aspects) -> None:
    """
        destroy without confirm raises before any mutation.
    """
    spec = basic_spec()
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    prov.apply(aspects=crusoe_aspects)
    with pytest.raises(SchemaSemanticError):
        prov.destroy(aspects=crusoe_aspects)
    return


def test_destroy_is_inverse_of_apply(crusoe_venue, mock_client,
                                     project_config, crusoe_aspects,
                                     crusoe_confirm_aspects) -> None:
    """
        destroy ∘ apply leaves the venue empty.
    """
    spec = basic_spec()
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    prov.apply(aspects=crusoe_aspects)
    prov.destroy(aspects=crusoe_confirm_aspects)
    assert len(mock_client.vpcs.list(project_id="proj-1")) == 0
    assert len(mock_client.vms.list(project_id="proj-1")) == 0
    assert len(mock_client.disks.list(project_id="proj-1")) == 0
    return


def test_destroy_calls_vpn_delete_device(crusoe_venue, mock_client,
                                         project_config, crusoe_aspects,
                                         crusoe_confirm_aspects) -> None:
    """
        Destroying VPN-joined instances de-registers the VPN devices.
    """
    deleted: list = []

    class _Cp:
        minted_authkey = "ts-key-xyz"

        def delete_device(self, *, device_id, aspects):
            deleted.append(device_id)
            return

    spec = basic_spec(with_vpn=True)
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec,
                            vpn_control_plane=_Cp())
    prov.apply(aspects=crusoe_aspects)
    prov.record_vpn_device(instance_name="node-0", device_id="dev-1")
    prov.destroy(aspects=crusoe_confirm_aspects)
    assert "dev-1" in deleted
    return


# ----------------------------------------------------------------------
# inventory
# ----------------------------------------------------------------------

def test_inventory_lists_run_resources(crusoe_venue, mock_client,
                                       project_config,
                                       crusoe_aspects) -> None:
    """
        inventory enumerates the run-id-labelled resources.
    """
    spec = basic_spec()
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    prov.apply(aspects=crusoe_aspects)
    items = prov.inventory(aspects=crusoe_aspects)
    kinds = {r.kind for r in items}
    assert "network" in kinds
    assert "instance" in kinds
    return


def test_persist_inventory_writes_json(crusoe_venue, mock_client,
                                       project_config, crusoe_aspects,
                                       tmp_path) -> None:
    """
        persist_inventory writes a crusoe-inventory.json under the run dir.
    """
    import json as _json

    spec = basic_spec()
    prov = make_provisioner(venue=crusoe_venue, client=mock_client,
                            project_config=project_config, spec=spec)
    prov.apply(aspects=crusoe_aspects)
    out_path = prov.persist_inventory(aspects=crusoe_aspects,
                                      output_root=str(tmp_path))
    assert out_path.endswith("crusoe-inventory.json")
    with open(out_path, "r", encoding="utf-8") as fh:
        document = _json.load(fh)
    assert document["run_id"] == "run-1"
    assert len(document["resources"]) > 0
    return


# ----------------------------------------------------------------------
# property tests
# ----------------------------------------------------------------------

def _make_venue_and_config():
    """
        Build a (CloudVenue, CrusoeProjectConfig) pair for property tests.

        :returns: A tuple of (CloudVenue, CrusoeProjectConfig).
    """
    from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
    from ccai.provisioning.venues.crusoe.crusoeprojectconfig import (
        CrusoeProjectConfig
    )
    venue = CloudVenue(name="crusoe-test", provider="crusoe",
                       region="us-east1", credential="crusoe-cred")
    config = CrusoeProjectConfig(project_id="proj-1", location="us-east1-a")
    rtnval = (venue, config)
    return rtnval


@given(volume_count=st.integers(min_value=0, max_value=3), constraints={"max_examples": 25})
def test_apply_idempotent_property(volume_count) -> None:
    """
        For any number of volumes, a second apply creates nothing.
    """
    from ccai.provisioning.model.cloud.cloudstoragevolume import (
        CloudStorageVolume
    )
    crusoe_venue, project_config = _make_venue_and_config()
    client = MockCrusoeClient()
    spec = basic_spec()
    spec.volumes = []
    for index in range(volume_count):
        spec.volumes.append(CloudStorageVolume(
            name="vol-{}".format(index), size_gb=50, storage_class="standard"))
    prov = CrusoeCloudProvisioner(venue=crusoe_venue, client=client,
                                  project_config=project_config, spec=spec)
    aspects = _Aspects(runid="run-prop")
    prov.apply(aspects=aspects)
    second = prov.apply(aspects=aspects)
    assert len(second.created) == 0
    return


@given(tags=st.lists(
    st.tuples(
        st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122),
                min_size=1, max_size=8),
        st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122),
                min_size=1, max_size=8)),
    min_size=0, max_size=6, unique_by=lambda pair: pair[0]), constraints={"max_examples": 40})
def test_label_round_trip_identity(tags) -> None:
    """
        from_crusoe(to_crusoe(tags)) is the identity for conformant inputs.
    """
    from ccai.provisioning.venues.crusoe.crusoelabeltranslator import (
        CrusoeLabelTranslator
    )
    translator = CrusoeLabelTranslator()
    neutral = {key: value for key, value in tags}

    labels = translator.to_crusoe(neutral_tags=neutral)
    recovered = translator.from_crusoe(labels=labels)

    assert recovered == neutral
    return


@given(node_count=st.integers(min_value=2, max_value=4), constraints={"max_examples": 20})
def test_ib_partition_grouping(node_count) -> None:
    """
        Multiple IB-interconnect instances sharing a group are attached to a
        single IB partition.
    """
    from ccai.provisioning.model.cloud.cloudimage import CloudImage
    from ccai.provisioning.model.cloud.cloudinstance import CloudInstance

    crusoe_venue, project_config = _make_venue_and_config()
    client = MockCrusoeClient()
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    interconnect = CloudInterconnect(kind="INFINIBAND_NDR",
                                     bandwidth_gbps=400)
    image = CloudImage(family="ubuntu", version="22.04",
                       architecture="x86_64")

    spec = basic_spec()
    spec.instances = []
    spec.volumes = []
    for index in range(node_count):
        spec.instances.append(CloudInstance(
            name="gpu-{}".format(index), profile_ref="gpu", image=image,
            size="h100", subnet="sub-a", security_groups=["sg-a"],
            keypair="kp-a", accelerators=[accel],
            interconnect=interconnect,
            placement_group="train-fabric"))

    prov = CrusoeCloudProvisioner(venue=crusoe_venue, client=client,
                                  project_config=project_config, spec=spec)
    prov.apply(aspects=_Aspects(runid="run-ib"))

    partitions = client.placement_groups.list(project_id="proj-1")
    assert len(partitions) == 1
    partition_id = partitions[0].placement_group_id
    for launch_spec in client.vms.launch_specs:
        assert launch_spec.placement_group_id == partition_id
    return
