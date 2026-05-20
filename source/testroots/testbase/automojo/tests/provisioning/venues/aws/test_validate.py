"""
    .. module:: test_validate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for AwsCloudProvisioner.validate happy + rejection paths.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import pytest

from automojo.credentials.basecredential import BaseCredential
from automojo.provisioning.model.cloud.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from automojo.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from automojo.provisioning.model.cloud.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from automojo.provisioning.venues.aws.awscloudprovisioner import (
    AwsCloudProvisioner
)
from automojo.provisioning.venues.aws.awserrors import AwsValidationError
from automojo.provisioning.venues.aws.awsspec import AwsSpec

from ._specfactory import basic_spec


def test_validate_happy_path(venue, credential, region_config,
                             aspects) -> None:
    """
        A clean spec validates successfully.
    """
    spec = basic_spec()
    provisioner = AwsCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


def test_validate_rejects_non_aws_credential(venue, region_config,
                                             aspects) -> None:
    """
        A non-AwsAccessKeyCredential is rejected at validate-time.
    """
    bogus = BaseCredential(identifier="x", categories=["other"])
    spec = basic_spec()
    provisioner = AwsCloudProvisioner(
        venue=venue, credential=bogus, region_config=region_config,
        spec=spec,
    )
    with pytest.raises(AwsValidationError):
        provisioner.validate(aspects=aspects)
    return


def test_validate_rejects_infiniband(venue, credential, region_config,
                                     aspects) -> None:
    """
        INFINIBAND_NDR is rejected with substitution guidance.
    """
    spec = basic_spec(
        interconnect=CloudInterconnect(kind="INFINIBAND_NDR",
                                       bandwidth_gbps=400),
    )
    provisioner = AwsCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    with pytest.raises(AwsValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "EFA" in str(excinfo.value)
    return


def test_validate_rejects_weka_shared_fs(venue, credential, region_config,
                                         aspects) -> None:
    """
        Shared filesystem kind=WEKA is rejected.
    """
    sfs = CloudSharedFilesystem(name="weka1", kind="WEKA",
                                existing_id="fs-existing")
    spec = basic_spec()
    spec.shared_filesystems = [sfs]
    provisioner = AwsCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    with pytest.raises(AwsValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "LUSTRE" in str(excinfo.value)
    return


def test_validate_accelerator_resolves(venue, credential, region_config,
                                       aspects) -> None:
    """
        H100_SXM resolves on AWS via the catalog.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    spec = basic_spec(instance_size="p5.48xlarge", accelerators=[accel])
    provisioner = AwsCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


def test_validate_accelerator_size_conflict(venue, credential, region_config,
                                            aspects) -> None:
    """
        An explicit size that disagrees with the resolved SKU is rejected.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    spec = basic_spec(instance_size="m5.large", accelerators=[accel])
    provisioner = AwsCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    with pytest.raises(AwsValidationError):
        provisioner.validate(aspects=aspects)
    return


def test_validate_efa_requires_capable_family(venue, credential,
                                              region_config, aspects) -> None:
    """
        EFA on a non-EFA family is rejected.
    """
    spec = basic_spec(
        instance_size="t3.micro",
        interconnect=CloudInterconnect(kind="EFA", bandwidth_gbps=400,
                                       topology="RAIL_OPTIMIZED"),
    )
    provisioner = AwsCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    with pytest.raises(AwsValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "EFA" in str(excinfo.value)
    return


def test_validate_subnet_containment(venue, credential, region_config,
                                     aspects) -> None:
    """
        Subnet CIDRs must be contained in their network CIDR.
    """
    spec = basic_spec()
    spec.subnets[0] = type(spec.subnets[0])(
        name="sub-a", network="vpc-a", cidr="192.168.1.0/24",
        zone="us-east-1a", public=True,
    )
    provisioner = AwsCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    with pytest.raises(AwsValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "contained" in str(excinfo.value)
    return
