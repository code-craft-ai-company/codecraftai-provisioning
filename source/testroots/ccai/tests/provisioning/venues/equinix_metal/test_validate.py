"""
    .. module:: test_validate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Validate happy-path and rejection tests for the Equinix Metal
               venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase

from .factories import create_equinix_metal_mock_client


from ccai.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from ccai.provisioning.model.cloud.cloudloadbalancer import (
    CloudLoadBalancer
)
from ccai.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
from ccai.provisioning.model.cloud.cloudsecuritygroup import (
    CloudSecurityGroup
)
from ccai.interfaces.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from ccai.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from ccai.provisioning.venues.equinix_metal.equinixmetalcloudprovisioner import (
    EquinixMetalCloudProvisioner
)
from ccai.provisioning.venues.equinix_metal.metalerrors import (
    MetalValidationError
)

from ._specfactory import basic_spec


def _provisioner(*, venue, credential, project_config, spec, mock_client):
    """
        Helper: construct an EquinixMetalCloudProvisioner with a mock client.
    """
    rtnval = EquinixMetalCloudProvisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, client=mock_client,
    )
    return rtnval


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_validate_happy_path(venue, credential, project_config,
                             mock_client) -> None:
    """
        A baseline bare-metal spec validates with ok=True.
    """
    spec = basic_spec()
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    result = provisioner.validate(aspects=None)
    assert result.ok is True
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_validate_rejects_object_bucket(venue, credential, project_config,
                                        mock_client) -> None:
    """
        CloudObjectBucket is rejected — Metal has no native object storage.
    """
    spec = basic_spec()
    spec.buckets.append(CloudObjectBucket(name="bkt-a", region="sv"))
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    with testbase.raises(MetalValidationError) as excinfo:
        provisioner.validate(aspects=None)
    assert "object storage" in str(excinfo.value)
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_validate_rejects_interconnect(venue, credential, project_config,
                                       mock_client) -> None:
    """
        A non-NONE HPC interconnect is rejected on bare metal.
    """
    interconnect = CloudInterconnect(kind="INFINIBAND_NDR",
                                     bandwidth_gbps=400)
    spec = basic_spec(interconnect=interconnect)
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    with testbase.raises(MetalValidationError) as excinfo:
        provisioner.validate(aspects=None)
    assert "RDMA" in str(excinfo.value)
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_validate_rejects_load_balancer(venue, credential, project_config,
                                        mock_client) -> None:
    """
        CloudLoadBalancer is rejected in the v1 bare-metal venue.
    """
    spec = basic_spec()
    spec.load_balancers.append(
        CloudLoadBalancer(name="lb-a", scheme="internet-facing")
    )
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    with testbase.raises(MetalValidationError) as excinfo:
        provisioner.validate(aspects=None)
    assert "load balancer" in str(excinfo.value)
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_validate_rejects_shared_filesystem(venue, credential,
                                            project_config,
                                            mock_client) -> None:
    """
        CloudSharedFilesystem is rejected — Metal has no managed shared FS.
    """
    spec = basic_spec()
    spec.shared_filesystems.append(
        CloudSharedFilesystem(name="fs-a", kind="LUSTRE", size_tb=10)
    )
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    with testbase.raises(MetalValidationError) as excinfo:
        provisioner.validate(aspects=None)
    assert "shared filesystem" in str(excinfo.value)
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_validate_rejects_block_volume_without_existing_id(
        venue, credential, project_config, mock_client) -> None:
    """
        A CloudStorageVolume without an existing_id is rejected — Metal block
        storage is a separate product not provisioned in v1.
    """
    spec = basic_spec()
    spec.volumes.append(
        CloudStorageVolume(name="vol-a", size_gb=100, storage_class="performance")
    )
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    with testbase.raises(MetalValidationError) as excinfo:
        provisioner.validate(aspects=None)
    assert "block storage" in str(excinfo.value)
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_validate_rejects_unknown_plan(venue, credential, project_config,
                                       mock_client) -> None:
    """
        An unknown Metal SKU / size hint fails validation.
    """
    spec = basic_spec(size="z9.gigantic.x86")
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    with testbase.raises(MetalValidationError) as excinfo:
        provisioner.validate(aspects=None)
    assert "Plan does not resolve" in str(excinfo.value)
    return


@testbase.attach.parameter(create_equinix_metal_mock_client, identifier="mock_client")
def test_validate_security_group_is_warning_not_error(
        venue, credential, project_config, mock_client) -> None:
    """
        A CloudSecurityGroup produces a warning, not a hard error — bare
        metal records it in tags but cannot realise a cloud security group.
    """
    spec = basic_spec()
    spec.security_groups.append(
        CloudSecurityGroup(name="sg-a", network="net-a")
    )
    provisioner = _provisioner(
        venue=venue, credential=credential, project_config=project_config,
        spec=spec, mock_client=mock_client,
    )
    result = provisioner.validate(aspects=None)
    assert result.ok is True
    assert len(result.warnings) == 1
    return
