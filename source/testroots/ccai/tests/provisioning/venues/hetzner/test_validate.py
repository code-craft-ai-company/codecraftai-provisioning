"""
    .. module:: test_validate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for HetznerCloudProvisioner.validate happy + rejections.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase

from ccai.tests.provisioning.venues.hetzner.factories import create_client


from ccai.credentials.basecredential import BaseCredential
from ccai.provisioning.model.cloud.cloudimage import CloudImage
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.provisioning.model.cloud.imagefamilynotofferederror import (
    ImageFamilyNotOfferedOnVenueError
)
from ccai.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from ccai.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
from ccai.interfaces.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from ccai.provisioning.venues.hetzner.hetznercloudprovisioner import (
    HetznerCloudProvisioner
)
from ccai.provisioning.venues.hetzner.hetznererrors import (
    HetznerValidationError
)
from ccai.provisioning.venues.hetzner.hetznerspec import HetznerSpec

from ccai.tests.provisioning.venues.hetzner._specfactory import basic_spec


@testbase.attach.parameter(create_client, identifier="client")
def test_validate_happy_path(venue, credential, location_config, client,
                             aspects) -> None:
    """
        A clean spec validates successfully.
    """
    spec = basic_spec()
    provisioner = HetznerCloudProvisioner(
        venue=venue, credential=credential,
        location_config=location_config, spec=spec, client=client)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_validate_rejects_non_hetzner_credential(venue, location_config,
                                                 client, aspects) -> None:
    """
        A non-HetznerApiTokenCredential is rejected at validate-time.
    """
    bogus = BaseCredential(identifier="x", categories=["other"])
    spec = basic_spec()
    provisioner = HetznerCloudProvisioner(
        venue=venue, credential=bogus, location_config=location_config,
        spec=spec, client=client)
    with testbase.raises(HetznerValidationError):
        provisioner.validate(aspects=aspects)
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_validate_rejects_object_bucket(venue, credential,
                                        location_config, client,
                                        aspects) -> None:
    """
        A spec carrying a CloudObjectBucket is rejected.
    """
    spec = basic_spec()
    spec.buckets = [CloudObjectBucket(name="bkt-a", region="nbg1")]
    provisioner = HetznerCloudProvisioner(
        venue=venue, credential=credential,
        location_config=location_config, spec=spec, client=client)
    with testbase.raises(HetznerValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "object-storage" in str(excinfo.value)
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_validate_rejects_interconnect(venue, credential, location_config,
                                       client, aspects) -> None:
    """
        A non-NONE CloudInterconnect is rejected.
    """
    spec = basic_spec()
    image = CloudImage(family="ubuntu", version="24.04",
                       architecture="x86_64")
    interconnect = CloudInterconnect(kind="INFINIBAND_NDR",
                                     bandwidth_gbps=400)
    spec.instances = [CloudInstance(
        name="srv-hpc", profile_ref="p", image=image, size="cx22",
        subnet="sub-a", interconnect=interconnect)]
    provisioner = HetznerCloudProvisioner(
        venue=venue, credential=credential,
        location_config=location_config, spec=spec, client=client)
    with testbase.raises(HetznerValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "interconnect" in str(excinfo.value)
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_validate_rejects_shared_filesystem(venue, credential,
                                            location_config, client,
                                            aspects) -> None:
    """
        A WEKA/Lustre-class CloudSharedFilesystem is rejected.
    """
    spec = basic_spec()
    spec.shared_filesystems = [CloudSharedFilesystem(
        name="fs-a", kind="WEKA", size_tb=10)]
    provisioner = HetznerCloudProvisioner(
        venue=venue, credential=credential,
        location_config=location_config, spec=spec, client=client)
    with testbase.raises(HetznerValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "shared" in str(excinfo.value).lower()
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_validate_rejects_unknown_image_family(venue, credential,
                                               location_config, client,
                                               aspects) -> None:
    """
        An image family the hetzner venue cannot serve is rejected with a
        consistent ImageFamilyNotOfferedOnVenueError naming the venue and
        family.

        The family is a real ImageFamily member; hetzner simply publishes no
        image for it.  That is a validation finding about a spec/venue
        pairing, so it is an ordinary ValueError a validator may aggregate --
        not SchemaSemanticError, which is reserved for a family that does not
        normalise at all and must halt the run.
    """
    spec = basic_spec()
    image = CloudImage(family="windows-server", version="2022",
                       architecture="x86_64")
    spec.instances = [CloudInstance(
        name="srv-win", profile_ref="p", image=image, size="cx22",
        subnet="sub-a")]
    provisioner = HetznerCloudProvisioner(
        venue=venue, credential=credential,
        location_config=location_config, spec=spec, client=client)
    with testbase.raises(ImageFamilyNotOfferedOnVenueError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "windows-server" in str(excinfo.value)
    assert "hetzner" in str(excinfo.value)
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_validate_rejects_unknown_server_type(venue, credential,
                                              location_config, client,
                                              aspects) -> None:
    """
        A size hint unknown to the resolver fails validation.
    """
    spec = basic_spec(instance_size="cx22")
    spec.instances[0] = CloudInstance(
        name="srv-a", profile_ref="p",
        image=CloudImage(family="ubuntu", version="24.04",
                         architecture="x86_64"),
        size="m5.unknown", subnet="sub-a")
    provisioner = HetznerCloudProvisioner(
        venue=venue, credential=credential,
        location_config=location_config, spec=spec, client=client)
    with testbase.raises(HetznerValidationError):
        provisioner.validate(aspects=aspects)
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_validate_none_spec_is_ok(venue, credential, location_config,
                                  client, aspects) -> None:
    """
        Validation of a None spec succeeds (inventory/destroy-only mode).
    """
    provisioner = HetznerCloudProvisioner(
        venue=venue, credential=credential,
        location_config=location_config, spec=None, client=client)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


@testbase.attach.parameter(create_client, identifier="client")
def test_validate_defaults_aspects_when_omitted(venue, credential,
                                                location_config,
                                                client) -> None:
    """
        validate may be called without aspects (default substitution).
    """
    spec = basic_spec()
    provisioner = HetznerCloudProvisioner(
        venue=venue, credential=credential,
        location_config=location_config, spec=spec, client=client)
    result = provisioner.validate()
    assert result.ok is True
    return
