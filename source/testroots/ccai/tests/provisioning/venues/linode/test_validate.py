"""
    .. module:: test_validate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Validate-stage tests for the Linode venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase

from ccai.tests.provisioning.venues.linode.factories import create_linode_mock_client


from ccai.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from ccai.interfaces.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from ccai.provisioning.venues.linode.linodecloudprovisioner import (
    LinodeCloudProvisioner
)
from ccai.provisioning.venues.linode.linodeerrors import (
    LinodeValidationError
)

from ccai.tests.provisioning.venues.linode._specfactory import basic_spec


def _provisioner(*, venue, credential, region_config, spec, mock_client):
    """
        Helper: build a provisioner backed by the mock client.
    """
    rtnval = LinodeCloudProvisioner(
        venue=venue, credential=credential, region_config=region_config,
        spec=spec, client=mock_client,
    )
    return rtnval


@testbase.attach.parameter(create_linode_mock_client, identifier="mock_client")
def test_validate_happy(venue, credential, region_config, aspects,
                        mock_client) -> None:
    """
        A well-formed spec validates with ok=True.
    """
    spec = basic_spec()
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config, spec=spec,
                               mock_client=mock_client)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


@testbase.attach.parameter(create_linode_mock_client, identifier="mock_client")
def test_validate_rejects_unknown_region(venue, credential, region_config,
                                         aspects, mock_client) -> None:
    """
        A network in an unknown region is rejected.
    """
    spec = basic_spec(region="mars-central")
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config, spec=spec,
                               mock_client=mock_client)
    with testbase.raises(LinodeValidationError):
        provisioner.validate(aspects=aspects)
    return


@testbase.attach.parameter(create_linode_mock_client, identifier="mock_client")
def test_validate_rejects_interconnect(venue, credential, region_config,
                                       aspects, mock_client) -> None:
    """
        An HPC interconnect ask is a validate-error.
    """
    interconnect = CloudInterconnect(kind="INFINIBAND_NDR",
                                     bandwidth_gbps=400,
                                     topology="RAIL_OPTIMIZED")
    spec = basic_spec(interconnect=interconnect)
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config, spec=spec,
                               mock_client=mock_client)
    with testbase.raises(LinodeValidationError):
        provisioner.validate(aspects=aspects)
    return


@testbase.attach.parameter(create_linode_mock_client, identifier="mock_client")
def test_validate_rejects_shared_fs(venue, credential, region_config,
                                    aspects, mock_client) -> None:
    """
        A WEKA/Lustre-class shared filesystem is a validate-error.
    """
    sfs = CloudSharedFilesystem(name="fs-a", kind="WEKA", size_tb=10)
    spec = basic_spec(shared_filesystems=[sfs])
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config, spec=spec,
                               mock_client=mock_client)
    with testbase.raises(LinodeValidationError):
        provisioner.validate(aspects=aspects)
    return


@testbase.attach.parameter(create_linode_mock_client, identifier="mock_client")
def test_validate_rejects_unknown_image(venue, credential, region_config,
                                        aspects, mock_client) -> None:
    """
        An image family the linode venue cannot serve is rejected with a
        consistent ImageFamilyNotOfferedOnVenueError naming the venue and
        family -- a validation finding, not the BaseException-rooted
        SchemaSemanticError reserved for a family that does not exist.
    """
    from ccai.provisioning.model.cloud.cloudimage import CloudImage
    from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
    from ccai.provisioning.model.cloud.imagefamilynotofferederror import (
        ImageFamilyNotOfferedOnVenueError
    )

    spec = basic_spec()
    bad_image = CloudImage(family="windows-server", version="2022",
                           architecture="x86_64")
    spec.instances[0] = CloudInstance(
        name="inst-a", profile_ref="default", image=bad_image,
        size="medium", subnet="sub-a", security_groups=["sg-a"],
        keypair="kp-a",
    )
    provisioner = _provisioner(venue=venue, credential=credential,
                               region_config=region_config, spec=spec,
                               mock_client=mock_client)
    with testbase.raises(ImageFamilyNotOfferedOnVenueError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "windows-server" in str(excinfo.value)
    assert "linode" in str(excinfo.value)
    return
