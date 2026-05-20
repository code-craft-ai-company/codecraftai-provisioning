"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: End-to-end validate/plan/apply/destroy tests against the
               in-memory ``oci`` SDK fakes.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import base64

import pytest

from automojo.provisioning.model.cloud.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from automojo.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from automojo.provisioning.model.cloud.clouddnsrecord import CloudDnsRecord
from automojo.provisioning.model.cloud.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from automojo.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from automojo.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy
from automojo.provisioning.venues.oracle.oraclecloudprovisioner import (
    OracleCloudProvisioner
)

from ._ocifakes import install_fakes
from ._specfactory import basic_spec, rdma_spec


def _new_provisioner(*, venue, credential, region_config, spec,
                     vpn_control_plane=None):
    """
        Helper: build a provisioner and install the OCI SDK fakes.
    """
    provisioner = OracleCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec, vpn_control_plane=vpn_control_plane,
    )
    fakes = install_fakes(provisioner=provisioner)
    rtnval = (provisioner, fakes)
    return rtnval


def test_plan_then_apply_creates_resources(venue, credential, region_config,
                                           aspects) -> None:
    """
        First plan reports CREATEs; apply produces matching resources.
    """
    spec = basic_spec()
    provisioner, fakes = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )

    plan = provisioner.plan(aspects=aspects)
    intents = [a.intent for a in plan.actions]
    assert PlannedActionIntent.CREATE.value in intents

    result = provisioner.apply(aspects=aspects)
    kinds = {r.kind for r in result.created}
    assert {"network", "subnet", "security_group", "instance",
            "volume", "bucket"}.issubset(kinds)
    return


def test_apply_idempotent(venue, credential, region_config,
                          aspects) -> None:
    """
        Re-applying produces only SKIPs and no new created resources.
    """
    spec = basic_spec()
    provisioner, fakes = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    provisioner.apply(aspects=aspects)
    second = provisioner.apply(aspects=aspects)

    skipped_names = set(second.skipped)
    assert "vcn-a" in skipped_names
    assert "sub-a" in skipped_names
    assert "sl-a" in skipped_names
    assert "inst-a" in skipped_names
    assert "vol-a" in skipped_names
    assert "bkt-a" in skipped_names

    plan = provisioner.plan(aspects=aspects)
    create_actions = [a for a in plan.actions
                      if a.intent == PlannedActionIntent.CREATE.value
                      and a.resource_kind not in ("dns",)]
    assert len(create_actions) == 0
    return


def test_apply_with_vpn_join_injects_user_data(venue, credential,
                                               region_config,
                                               aspects) -> None:
    """
        Instances with vpn_join carry base64-encoded cloud-init user-data
        in metadata["user_data"] containing the tailscale bring-up reference.
    """
    spec = basic_spec(with_vpn=True)
    provisioner, fakes = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    provisioner.apply(aspects=aspects)

    compute = fakes["compute"]
    found = False
    for instance in compute.instances:
        metadata = instance.metadata
        value = metadata.get("user_data", "")
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
    provisioner, fakes = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    provisioner.apply(aspects=aspects)
    with pytest.raises(Exception):
        provisioner.destroy(aspects=aspects)
    return


def test_destroy_reverses_apply(venue, credential, region_config, aspects,
                                confirm_aspects) -> None:
    """
        After destroy, the inventory comes back empty.
    """
    spec = basic_spec()
    provisioner, fakes = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    provisioner.apply(aspects=aspects)
    inventory_before = provisioner.inventory(aspects=aspects)
    assert len(inventory_before) > 0

    provisioner.destroy(aspects=confirm_aspects)

    inventory_after = provisioner.inventory(aspects=aspects)
    assert len(inventory_after) == 0
    return


def test_gpu_shape_resolution(venue, credential, region_config,
                              aspects) -> None:
    """
        H100_SXM resolves to ``BM.GPU.H100.8`` and lands as the launched
        instance's shape.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    spec = basic_spec(instance_size="BM.GPU.H100.8", accelerators=[accel])
    provisioner, fakes = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    result = provisioner.apply(aspects=aspects)
    inst_resource = None
    for resource in result.created:
        if resource.kind == "instance":
            inst_resource = resource
    assert inst_resource is not None
    assert inst_resource.attributes.get("shape", "") == "BM.GPU.H100.8"
    return


def test_rdma_cluster_network_grouping(venue, credential, region_config,
                                       aspects) -> None:
    """
        N RDMA-grouped instances yield exactly one cluster network.
    """
    spec = rdma_spec(member_count=3)
    provisioner, fakes = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    provisioner.apply(aspects=aspects)

    cluster_mgmt = fakes["compute_management"]
    assert len(cluster_mgmt.cluster_networks) == 1
    cluster = cluster_mgmt.cluster_networks[0]
    pool = cluster.instance_pools[0]
    assert pool.size == 3

    # Every launched instance carries the cluster network id.
    compute = fakes["compute"]
    cluster_ids = {i.compute_cluster_id for i in compute.instances}
    assert len(cluster_ids) == 1
    assert None not in cluster_ids
    return


def test_preemptible_instance_config(venue, credential, region_config,
                                     aspects) -> None:
    """
        PreemptionPolicy.REACQUIRE attaches a preemptible-instance config.
    """
    spec = basic_spec(preemption=PreemptionPolicy.REACQUIRE)
    provisioner, fakes = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    provisioner.apply(aspects=aspects)
    compute = fakes["compute"]
    assert len(compute.instances) == 1
    assert compute.instances[0].preemptible_instance_config is not None
    return


def test_preemption_policy_fail_is_on_demand(venue, credential,
                                             region_config,
                                             aspects) -> None:
    """
        PreemptionPolicy.FAIL produces a non-preemptible instance.
    """
    spec = basic_spec(preemption=PreemptionPolicy.FAIL)
    provisioner, fakes = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    provisioner.apply(aspects=aspects)
    compute = fakes["compute"]
    assert compute.instances[0].preemptible_instance_config is None
    return


def test_ssh_key_injected_into_metadata(venue, credential, region_config,
                                        aspects) -> None:
    """
        The CloudKeyPair public key lands in metadata["ssh_authorized_keys"].
    """
    spec = basic_spec()
    provisioner, fakes = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    provisioner.apply(aspects=aspects)
    compute = fakes["compute"]
    metadata = compute.instances[0].metadata
    assert "ssh_authorized_keys" in metadata
    assert metadata["ssh_authorized_keys"].startswith("ssh-rsa")
    return


def test_apply_dns_record_upserts(venue, credential, region_config,
                                  aspects) -> None:
    """
        A CloudDnsRecord is upserted as an OCI DNS RRSet.
    """
    spec = basic_spec()
    spec.dns_records = [CloudDnsRecord(
        zone="example.com", name="host.example.com", record_type="A",
        values=["10.0.1.5"], ttl_seconds=300,
    )]
    provisioner, fakes = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    provisioner.apply(aspects=aspects)
    dns = fakes["dns"]
    assert len(dns.rrsets) == 1
    return


def test_shared_fs_lustre_attach(venue, credential, region_config,
                                 aspects) -> None:
    """
        kind=LUSTRE with existing_id attaches a managed Lustre filesystem.
    """
    spec = basic_spec()
    spec.shared_filesystems = [CloudSharedFilesystem(
        name="lustre1", kind="LUSTRE",
        existing_id="ocid1.filesystem.oc1..managedlustre",
    )]
    provisioner, fakes = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    result = provisioner.apply(aspects=aspects)
    fs_resources = [r for r in result.created
                    if r.kind == "shared_filesystem"]
    assert len(fs_resources) == 1
    assert fs_resources[0].attributes.get("existing_id", "") == (
        "ocid1.filesystem.oc1..managedlustre"
    )
    return


class _RecordingVPN:
    """
        Minimal mock IVPNControlPlane recording delete_device calls.
    """

    def __init__(self) -> None:
        """
            Construct the recorder.
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
                                         aspects, confirm_aspects) -> None:
    """
        When vpn_join was set and a device id was recorded, destroy invokes
        the control-plane delete_device.
    """
    spec = basic_spec(with_vpn=True)
    vpn = _RecordingVPN()
    provisioner, fakes = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec, vpn_control_plane=vpn,
    )
    provisioner.apply(aspects=aspects)
    provisioner.record_vpn_device(instance_name="inst-a",
                                  device_id="device-abc")

    provisioner.destroy(aspects=confirm_aspects)

    assert "device-abc" in vpn.deleted_ids
    return


def test_inventory_lists_owned_resources(venue, credential, region_config,
                                         aspects) -> None:
    """
        Inventory enumerates run-id-tagged resources.
    """
    spec = basic_spec()
    provisioner, fakes = _new_provisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    provisioner.apply(aspects=aspects)
    inventory = provisioner.inventory(aspects=aspects)
    kinds = {r.kind for r in inventory}
    assert {"network", "subnet", "security_group", "instance",
            "volume", "bucket"}.issubset(kinds)
    return
