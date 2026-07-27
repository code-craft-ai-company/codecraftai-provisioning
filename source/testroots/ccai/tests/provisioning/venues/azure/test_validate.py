"""
    .. module:: test_validate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for AzureCloudProvisioner.validate happy + rejection
               paths.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase

from .factories import (create_azure_session_factory, create_azure_world)


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
from ccai.provisioning.venues.azure.azurecloudprovisioner import (
    AzureCloudProvisioner
)
from ccai.provisioning.venues.azure.azureerrors import (
    AzureValidationError
)

from ._specfactory import basic_spec


def _provisioner(*, venue, credential, region_config, session_factory,
                 spec):
    """
        Helper: build an AzureCloudProvisioner wired to the fake clients.
    """
    rtnval = AzureCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec, session_factory=session_factory,
    )
    return rtnval


@testbase.attach.parameter(create_azure_session_factory, identifier="session_factory")
@testbase.attach.parameter(create_azure_world, identifier="world")
def test_validate_happy_path(venue, credential, region_config,
                             world, session_factory, aspects) -> None:
    """
        A clean spec validates successfully.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


@testbase.attach.parameter(create_azure_session_factory, identifier="session_factory")
@testbase.attach.parameter(create_azure_world, identifier="world")
def test_validate_rejects_non_azure_credential(venue, region_config,
                                               world, session_factory,
                                               aspects) -> None:
    """
        A non-Azure credential is rejected at validate-time.
    """
    bogus = BaseCredential(identifier="x", categories=["other"])
    spec = basic_spec()
    provisioner = AzureCloudProvisioner(
        venue=venue, credential=bogus, region_config=region_config,
        spec=spec, session_factory=session_factory,
    )
    with pytest.raises(AzureValidationError):
        provisioner.validate(aspects=aspects)
    return


@testbase.attach.parameter(create_azure_session_factory, identifier="session_factory")
@testbase.attach.parameter(create_azure_world, identifier="world")
def test_validate_rejects_efa(venue, credential, region_config,
                              world, session_factory, aspects) -> None:
    """
        EFA is rejected — EFA is AWS-only.
    """
    spec = basic_spec(
        interconnect=CloudInterconnect(kind="EFA", bandwidth_gbps=400,
                                       topology="RAIL_OPTIMIZED"),
    )
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    with pytest.raises(AzureValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "InfiniBand" in str(excinfo.value)
    return


@testbase.attach.parameter(create_azure_session_factory, identifier="session_factory")
@testbase.attach.parameter(create_azure_world, identifier="world")
def test_validate_rejects_oci_rdma(venue, credential, region_config,
                                   world, session_factory, aspects) -> None:
    """
        OCI_RDMA is rejected — OCI_RDMA is Oracle-only.
    """
    spec = basic_spec(
        interconnect=CloudInterconnect(kind="OCI_RDMA", bandwidth_gbps=400),
    )
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    with pytest.raises(AzureValidationError):
        provisioner.validate(aspects=aspects)
    return


@testbase.attach.parameter(create_azure_session_factory, identifier="session_factory")
@testbase.attach.parameter(create_azure_world, identifier="world")
def test_validate_rejects_weka_shared_fs(venue, credential, region_config,
                                         world, session_factory, aspects) -> None:
    """
        Shared filesystem kind=WEKA is rejected with substitution guidance.
    """
    sfs = CloudSharedFilesystem(name="weka1", kind="WEKA",
                                existing_id="fs-existing")
    spec = basic_spec()
    spec.shared_filesystems = [sfs]
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    with pytest.raises(AzureValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "Lustre" in str(excinfo.value)
    return


@testbase.attach.parameter(create_azure_session_factory, identifier="session_factory")
@testbase.attach.parameter(create_azure_world, identifier="world")
def test_validate_lustre_requires_existing_id(venue, credential,
                                              region_config,
                                              world, session_factory,
                                              aspects) -> None:
    """
        Azure Managed Lustre v1 is attach-only; existing_id is required.
    """
    sfs = CloudSharedFilesystem(name="lustre1", kind="LUSTRE", size_tb=4)
    spec = basic_spec()
    spec.shared_filesystems = [sfs]
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    with pytest.raises(AzureValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "attach-only" in str(excinfo.value)
    return


@testbase.attach.parameter(create_azure_session_factory, identifier="session_factory")
@testbase.attach.parameter(create_azure_world, identifier="world")
def test_validate_accelerator_resolves(venue, credential, region_config,
                                       world, session_factory, aspects) -> None:
    """
        H100_SXM resolves on Azure via the catalog.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    spec = basic_spec(instance_size="Standard_ND96isr_H100_v5",
                      accelerators=[accel])
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


@testbase.attach.parameter(create_azure_session_factory, identifier="session_factory")
@testbase.attach.parameter(create_azure_world, identifier="world")
def test_validate_accelerator_size_conflict(venue, credential,
                                            region_config, world, session_factory,
                                            aspects) -> None:
    """
        An explicit size that disagrees with the resolved SKU is rejected.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    spec = basic_spec(instance_size="Standard_D2s_v5", accelerators=[accel])
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    with pytest.raises(AzureValidationError):
        provisioner.validate(aspects=aspects)
    return


@testbase.attach.parameter(create_azure_session_factory, identifier="session_factory")
@testbase.attach.parameter(create_azure_world, identifier="world")
def test_validate_infiniband_requires_capable_sku(venue, credential,
                                                  region_config,
                                                  world, session_factory,
                                                  aspects) -> None:
    """
        InfiniBand on a non-IB-capable VM size is rejected.
    """
    spec = basic_spec(
        instance_size="Standard_D2s_v5",
        interconnect=CloudInterconnect(kind="INFINIBAND_NDR",
                                       bandwidth_gbps=400),
    )
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    with pytest.raises(AzureValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "InfiniBand-capable" in str(excinfo.value)
    return


@testbase.attach.parameter(create_azure_session_factory, identifier="session_factory")
@testbase.attach.parameter(create_azure_world, identifier="world")
def test_validate_infiniband_no_ppg_warns(venue, credential, region_config,
                                          world, session_factory, aspects) -> None:
    """
        An IB SKU with no placement_group emits a warning (not an error).
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    spec = basic_spec(instance_size="Standard_ND96isr_H100_v5",
                      accelerators=[accel],
                      interconnect=CloudInterconnect(kind="INFINIBAND_NDR",
                                                     bandwidth_gbps=400))
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    assert len(result.warnings) >= 1
    return


@testbase.attach.parameter(create_azure_session_factory, identifier="session_factory")
@testbase.attach.parameter(create_azure_world, identifier="world")
def test_validate_subnet_containment(venue, credential, region_config,
                                     world, session_factory, aspects) -> None:
    """
        Subnet CIDRs must be contained in their VNet CIDR.
    """
    spec = basic_spec()
    spec.subnets[0] = type(spec.subnets[0])(
        name="sub-a", network="vnet-a", cidr="192.168.1.0/24",
        zone="eastus-1", public=True,
    )
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config,
                               session_factory=session_factory, spec=spec)
    with pytest.raises(AzureValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "contained" in str(excinfo.value)
    return
