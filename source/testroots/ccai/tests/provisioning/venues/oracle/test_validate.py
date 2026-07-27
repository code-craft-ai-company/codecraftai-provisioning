"""
    .. module:: test_validate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for OracleCloudProvisioner.validate happy + rejection
               paths.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase


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
from ccai.provisioning.venues.oracle.ocierrors import OciValidationError
from ccai.provisioning.venues.oracle.oraclecloudprovisioner import (
    OracleCloudProvisioner
)

from ccai.tests.provisioning.venues.oracle._specfactory import basic_spec


def test_validate_happy_path(venue, credential, region_config,
                             aspects) -> None:
    """
        A clean spec validates successfully.
    """
    spec = basic_spec()
    provisioner = OracleCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


def test_validate_rejects_non_oracle_credential(venue, region_config,
                                                aspects) -> None:
    """
        A non-OracleCloudApiKeyCredential is rejected at validate-time.
    """
    bogus = BaseCredential(identifier="x", categories=["other"])
    spec = basic_spec()
    provisioner = OracleCloudProvisioner(
        venue=venue, credential=bogus, region_config=region_config,
        spec=spec,
    )
    with testbase.raises(OciValidationError):
        provisioner.validate(aspects=aspects)
    return


def test_validate_rejects_efa_interconnect(venue, credential, region_config,
                                           aspects) -> None:
    """
        EFA is rejected — OCI exposes RDMA only via OCI_RDMA.
    """
    spec = basic_spec(
        interconnect=CloudInterconnect(kind="EFA", bandwidth_gbps=400,
                                       topology="RAIL_OPTIMIZED"),
    )
    provisioner = OracleCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    with testbase.raises(OciValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "OCI_RDMA" in str(excinfo.value)
    return


def test_validate_rejects_infiniband_interconnect(venue, credential,
                                                  region_config,
                                                  aspects) -> None:
    """
        INFINIBAND_NDR is rejected with OCI_RDMA substitution guidance.
    """
    spec = basic_spec(
        interconnect=CloudInterconnect(kind="INFINIBAND_NDR",
                                       bandwidth_gbps=400),
    )
    provisioner = OracleCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    with testbase.raises(OciValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "OCI_RDMA" in str(excinfo.value)
    return


def test_validate_rejects_weka_shared_fs(venue, credential, region_config,
                                         aspects) -> None:
    """
        Shared filesystem kind=WEKA is rejected with a substitution hint.
    """
    sfs = CloudSharedFilesystem(name="weka1", kind="WEKA",
                                existing_id="fs-existing")
    spec = basic_spec()
    spec.shared_filesystems = [sfs]
    provisioner = OracleCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    with testbase.raises(OciValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "VENUE_NATIVE" in str(excinfo.value)
    return


def test_validate_rejects_lustre_without_existing_id(venue, credential,
                                                     region_config,
                                                     aspects) -> None:
    """
        kind=LUSTRE without existing_id is rejected (attach-only in v1).
    """
    sfs = CloudSharedFilesystem(name="lustre1", kind="LUSTRE", size_tb=10)
    spec = basic_spec()
    spec.shared_filesystems = [sfs]
    provisioner = OracleCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    with testbase.raises(OciValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "existing_id" in str(excinfo.value)
    return


def test_validate_rdma_requires_bm_gpu_shape(venue, credential,
                                             region_config,
                                             aspects) -> None:
    """
        An OCI_RDMA interconnect on a non-BM.GPU shape fails in validate.
    """
    spec = basic_spec(
        instance_size="VM.Standard.E4.Flex",
        interconnect=CloudInterconnect(kind="OCI_RDMA", bandwidth_gbps=3200,
                                       topology="RAIL_OPTIMIZED"),
    )
    provisioner = OracleCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    with testbase.raises(OciValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "BM.GPU" in str(excinfo.value)
    return


def test_validate_accelerator_resolves(venue, credential, region_config,
                                       aspects) -> None:
    """
        H100_SXM resolves on OCI via the catalog to a BM.GPU shape.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    spec = basic_spec(instance_size="BM.GPU.H100.8", accelerators=[accel])
    provisioner = OracleCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


def test_validate_accelerator_size_conflict(venue, credential,
                                            region_config, aspects) -> None:
    """
        An explicit size that disagrees with the resolved shape is rejected.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    spec = basic_spec(instance_size="VM.Standard.E4.Flex",
                      accelerators=[accel])
    provisioner = OracleCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    with testbase.raises(OciValidationError):
        provisioner.validate(aspects=aspects)
    return


def test_validate_subnet_containment(venue, credential, region_config,
                                     aspects) -> None:
    """
        Subnet CIDRs must be contained in their network CIDR.
    """
    spec = basic_spec()
    spec.subnets[0] = type(spec.subnets[0])(
        name="sub-a", network="vcn-a", cidr="192.168.1.0/24",
        zone="Uocm:US-ASHBURN-AD-1", public=True,
    )
    provisioner = OracleCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    with testbase.raises(OciValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "contained" in str(excinfo.value)
    return


def test_validate_accepts_oci_rdma_on_bm_gpu(venue, credential,
                                             region_config, aspects) -> None:
    """
        OCI_RDMA on a BM.GPU shape validates successfully.
    """
    spec = basic_spec(
        instance_size="BM.GPU.H100.8",
        interconnect=CloudInterconnect(kind="OCI_RDMA", bandwidth_gbps=3200,
                                       topology="FAT_TREE"),
    )
    provisioner = OracleCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec,
    )
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return
