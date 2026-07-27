"""
    .. module:: test_validate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for NebiusCloudProvisioner.validate happy + rejection
        paths.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase

from .factories import create_nebius_client


import pytest

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
from ccai.interfaces.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from ccai.provisioning.venues.nebius.nebiuscloudprovisioner import (
    NebiusCloudProvisioner
)
from ccai.provisioning.venues.nebius.nebiuserrors import (
    NebiusValidationError
)

from ._specfactory import basic_spec, gpu_cluster_spec


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_validate_happy_path(client, venue, aspects) -> None:
    """
        A clean spec validates successfully.
    """
    spec = basic_spec()
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_validate_gpu_cluster_spec(client, venue, aspects) -> None:
    """
        A GPU-cluster spec with an IB-eligible platform validates.
    """
    spec = gpu_cluster_spec()
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_validate_rejects_load_balancer(client, venue, aspects) -> None:
    """
        CloudLoadBalancer is rejected at validate-time.
    """
    spec = basic_spec()
    spec.load_balancers = [CloudLoadBalancer(name="lb-a",
                                             scheme="internet-facing",
                                             listeners=[])]
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    with pytest.raises(NebiusValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "LoadBalancer" in str(excinfo.value)
    return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_validate_rejects_object_bucket(client, venue, aspects) -> None:
    """
        CloudObjectBucket is rejected — v1 client has no object storage.
    """
    spec = basic_spec()
    spec.buckets = [CloudObjectBucket(name="bkt-a", region="eu-north1")]
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    with pytest.raises(NebiusValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "Object Storage" in str(excinfo.value)
    return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_validate_rejects_shared_fs_without_existing_id(client, venue,
                                                        aspects) -> None:
    """
        A CloudSharedFilesystem with no existing_id is rejected.
    """
    spec = basic_spec()
    # A filesystem requesting provisioning (size_tb set, no existing_id)
    # must be rejected — Nebius shared FS is attach-only in v1.
    spec.shared_filesystems = [
        CloudSharedFilesystem(name="fs-a", kind="VENUE_NATIVE",
                              size_tb=10),
    ]
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    with pytest.raises(NebiusValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "existing_id" in str(excinfo.value)
    return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_validate_rejects_uncontained_subnet(client, venue, aspects) -> None:
    """
        A subnet CIDR not contained in its network CIDR is rejected.
    """
    spec = basic_spec()
    spec.subnets[0] = type(spec.subnets[0])(
        name="sub-a", network="vpc-a", cidr="192.168.1.0/24",
        zone="eu-north1-a", public=True,
    )
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    with pytest.raises(NebiusValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "contained" in str(excinfo.value)
    return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_validate_rejects_ib_on_non_eligible_platform(client, venue,
                                                      aspects) -> None:
    """
        An InfiniBand interconnect on a CPU platform is rejected.
    """
    spec = basic_spec(
        instance_size="cpu-16vcpu-64gb",
        interconnect=CloudInterconnect(kind="INFINIBAND_NDR",
                                       bandwidth_gbps=400),
        placement_group="cpu-cluster",
    )
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    with pytest.raises(NebiusValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "IB-eligible" in str(excinfo.value)
    return


@testbase.attach.parameter(create_nebius_client, identifier="client")
def test_validate_rejects_unknown_accelerator(client, venue,
                                              aspects) -> None:
    """
        An accelerator model not in the catalog is rejected.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="NOT_A_REAL_GPU",
                                 count=8, interconnect="NVSWITCH",
                                 memory_gb=80)
    spec = basic_spec(instance_size="gpu", accelerators=[accel])
    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    with pytest.raises(NebiusValidationError):
        provisioner.validate(aspects=aspects)
    return
