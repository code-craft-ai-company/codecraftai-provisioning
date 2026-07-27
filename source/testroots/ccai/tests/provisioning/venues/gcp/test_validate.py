"""
    .. module:: test_validate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for GoogleCloudProvisioner.validate happy + rejection paths.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import pytest

from ccai.credentials.basecredential import BaseCredential
from ccai.interfaces.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from ccai.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from ccai.interfaces.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from ccai.provisioning.model.cloud.cloudsubnet import CloudSubnet
from ccai.provisioning.venues.google.gcperrors import GcpValidationError
from ccai.provisioning.venues.google.googlecloudprovisioner import (
    GoogleCloudProvisioner
)

from ._specfactory import basic_spec, tpu_spec


def test_validate_happy_path(make_provisioner, aspects) -> None:
    """
        A clean spec validates successfully.
    """
    provisioner, _ = make_provisioner(spec=basic_spec())
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


def test_validate_rejects_non_gcp_credential(venue, region_config,
                                             aspects) -> None:
    """
        A non-GCP credential is rejected at validate-time.
    """
    bogus = BaseCredential(identifier="x", categories=["other"])
    provisioner = GoogleCloudProvisioner(
        venue=venue, credential=bogus, region_config=region_config,
        spec=basic_spec(),
    )
    with pytest.raises(GcpValidationError):
        provisioner.validate(aspects=aspects)
    return


def test_validate_rejects_efa(make_provisioner, aspects) -> None:
    """
        Interconnect kind=EFA is rejected as AWS-only.
    """
    spec = basic_spec(
        interconnect=CloudInterconnect(kind="EFA", bandwidth_gbps=400),
    )
    provisioner, _ = make_provisioner(spec=spec)
    with pytest.raises(GcpValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "EFA is AWS-only" in str(excinfo.value)
    return


def test_validate_rejects_infiniband(make_provisioner, aspects) -> None:
    """
        INFINIBAND_NDR is rejected with compact-placement guidance.
    """
    spec = basic_spec(
        interconnect=CloudInterconnect(kind="INFINIBAND_NDR",
                                       bandwidth_gbps=400),
    )
    provisioner, _ = make_provisioner(spec=spec)
    with pytest.raises(GcpValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "compact placement" in str(excinfo.value)
    return


def test_validate_rejects_weka_shared_fs(make_provisioner, aspects) -> None:
    """
        Shared filesystem kind=WEKA is rejected with substitution guidance.
    """
    spec = basic_spec()
    spec.shared_filesystems = [
        CloudSharedFilesystem(name="weka1", kind="WEKA",
                              existing_id="fs-existing")
    ]
    provisioner, _ = make_provisioner(spec=spec)
    with pytest.raises(GcpValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "Parallelstore" in str(excinfo.value)
    return


def test_validate_lustre_maps_to_parallelstore(make_provisioner,
                                               aspects) -> None:
    """
        kind=LUSTRE with existing_id validates (Parallelstore attach).
    """
    spec = basic_spec()
    spec.shared_filesystems = [
        CloudSharedFilesystem(name="lus1", kind="LUSTRE",
                              existing_id="ps-existing")
    ]
    provisioner, _ = make_provisioner(spec=spec)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


def test_validate_lustre_requires_existing_id(make_provisioner,
                                              aspects) -> None:
    """
        kind=LUSTRE without existing_id is rejected (attach-only in v1).
    """
    spec = basic_spec()
    spec.shared_filesystems = [
        CloudSharedFilesystem(name="lus1", kind="LUSTRE", size_tb=4)
    ]
    provisioner, _ = make_provisioner(spec=spec)
    with pytest.raises(GcpValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "attach-only" in str(excinfo.value)
    return


def test_validate_gpu_resolves(make_provisioner, aspects) -> None:
    """
        H100_SXM resolves on GCP via the catalog.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    spec = basic_spec(instance_size="a3-highgpu-8g", accelerators=[accel])
    provisioner, _ = make_provisioner(spec=spec)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


def test_validate_gpu_size_conflict(make_provisioner, aspects) -> None:
    """
        An explicit size that disagrees with the resolved SKU is rejected.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    spec = basic_spec(instance_size="e2-standard-2", accelerators=[accel])
    provisioner, _ = make_provisioner(spec=spec)
    with pytest.raises(GcpValidationError):
        provisioner.validate(aspects=aspects)
    return


def test_validate_tpu_requires_model(make_provisioner, aspects) -> None:
    """
        A TPU spec must resolve its accelerator model on GCP.
    """
    spec = tpu_spec()
    provisioner, _ = make_provisioner(spec=spec)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


def test_validate_compact_placement_zone_unsupported(make_provisioner,
                                                     aspects) -> None:
    """
        A3 compact placement in an unsupported zone fails in validate.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    interconnect = CloudInterconnect(kind="ETHERNET", bandwidth_gbps=400,
                                     topology="RAIL_OPTIMIZED")
    spec = basic_spec(instance_size="a3-highgpu-8g", accelerators=[accel],
                      interconnect=interconnect)
    spec.subnets[0] = CloudSubnet(name="sub-a", network="vpc-a",
                                  cidr="10.0.1.0/24",
                                  zone="europe-west9-a")
    provisioner, _ = make_provisioner(spec=spec)
    with pytest.raises(GcpValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "compact placement" in str(excinfo.value)
    return


def test_validate_subnet_containment(make_provisioner, aspects) -> None:
    """
        Subnet CIDRs must be contained in their network CIDR.
    """
    spec = basic_spec()
    spec.subnets[0] = CloudSubnet(name="sub-a", network="vpc-a",
                                  cidr="192.168.1.0/24",
                                  zone="us-central1-a")
    provisioner, _ = make_provisioner(spec=spec)
    with pytest.raises(GcpValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "contained" in str(excinfo.value)
    return


def test_validate_rejects_load_balancer(make_provisioner, aspects) -> None:
    """
        Load balancers are deferred to v1.5 and rejected at validate.
    """
    from ccai.provisioning.model.cloud.cloudloadbalancer import (
        CloudLoadBalancer
    )
    spec = basic_spec()
    spec.load_balancers = [
        CloudLoadBalancer(name="lb-a", scheme="internal")
    ]
    provisioner, _ = make_provisioner(spec=spec)
    with pytest.raises(GcpValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "v1.5" in str(excinfo.value)
    return
