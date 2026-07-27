"""
    .. module:: test_validate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Validate-stage tests for the Nutanix venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase


from ccai.provisioning.model.cloud.cloudimage import CloudImage
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from ccai.interfaces.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from ccai.provisioning.venues.nutanix.nutanixcloudprovisioner import (
    NutanixCloudProvisioner
)
from ccai.provisioning.venues.nutanix.nutanixspec import NutanixSpec
from ccai.provisioning.venues.nutanix.ntxerrors import NtxValidationError

from ._mockclient import MockNutanixClient
from ._specfactory import (
    basic_spec, bucket_lb_dns_spec, make_config, make_keypair,
    make_network, make_subnet
)


def _provisioner(*, venue, spec, objects_configured=False):
    """
        Build a NutanixCloudProvisioner over a mock client.

        :param venue: The CloudVenue fixture.
        :param spec: The NutanixSpec under test.
        :param objects_configured: Whether Objects is configured.

        :returns: A constructed provisioner.
    """
    rtnval = NutanixCloudProvisioner(
        venue=venue, client=MockNutanixClient(),
        config=make_config(objects_configured=objects_configured),
        spec=spec,
    )
    return rtnval


def test_validate_happy_path(venue, aspects):
    """
        A basic spec validates without errors.
    """
    provisioner = _provisioner(venue=venue, spec=basic_spec())
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True


def test_validate_rejects_bucket_without_objects(venue, aspects):
    """
        A CloudObjectBucket is rejected when Objects is not configured.
    """
    provisioner = _provisioner(venue=venue, spec=bucket_lb_dns_spec())
    with testbase.raises(NtxValidationError):
        provisioner.validate(aspects=aspects)


def test_validate_accepts_bucket_with_objects(venue, aspects):
    """
        A CloudObjectBucket warns (not errors) when Objects is configured.
    """
    spec = NutanixSpec(networks=[make_network()], subnets=[make_subnet()],
                       keypairs=[make_keypair()],
                       buckets=bucket_lb_dns_spec().buckets)
    provisioner = _provisioner(venue=venue, spec=spec,
                               objects_configured=True)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    assert len(result.warnings) >= 1


def test_validate_rejects_load_balancer(venue, aspects):
    """
        A CloudLoadBalancer is always a validate-error.
    """
    spec = bucket_lb_dns_spec()
    provisioner = _provisioner(venue=venue, spec=spec,
                               objects_configured=True)
    with testbase.raises(NtxValidationError):
        provisioner.validate(aspects=aspects)


def test_validate_rejects_interconnect(venue, aspects):
    """
        A non-NONE CloudInterconnect is a validate-error.
    """
    interconnect = CloudInterconnect(kind="INFINIBAND_HDR",
                                     bandwidth_gbps=400)
    instance = CloudInstance(name="hpc", profile_ref="vm-profile",
                             image=CloudImage(family="ubuntu",
                                              version="24.04",
                                              architecture="x86_64"),
                             size="large", subnet="appsubnet",
                             interconnect=interconnect)
    spec = NutanixSpec(networks=[make_network()], subnets=[make_subnet()],
                       keypairs=[make_keypair()], instances=[instance])
    provisioner = _provisioner(venue=venue, spec=spec)
    with testbase.raises(NtxValidationError):
        provisioner.validate(aspects=aspects)


def test_validate_rejects_unresolvable_image(venue, aspects):
    """
        An image absent from the catalog is a validate-error.
    """
    instance = CloudInstance(name="node", profile_ref="vm-profile",
                             image=CloudImage(family="windows-server",
                                              version="2022",
                                              architecture="x86_64"),
                             size="medium", subnet="appsubnet")
    spec = NutanixSpec(networks=[make_network()], subnets=[make_subnet()],
                       keypairs=[make_keypair()], instances=[instance])
    provisioner = _provisioner(venue=venue, spec=spec)
    with testbase.raises(NtxValidationError):
        provisioner.validate(aspects=aspects)


def test_validate_rejects_unsized_instance(venue, aspects):
    """
        A size token absent from the size catalog is a validate-error.
    """
    instance = CloudInstance(name="node", profile_ref="vm-profile",
                             image=CloudImage(family="ubuntu",
                                              version="24.04",
                                              architecture="x86_64"),
                             size="ginormous", subnet="appsubnet")
    spec = NutanixSpec(networks=[make_network()], subnets=[make_subnet()],
                       keypairs=[make_keypair()], instances=[instance])
    provisioner = _provisioner(venue=venue, spec=spec)
    with testbase.raises(NtxValidationError):
        provisioner.validate(aspects=aspects)


def test_validate_rejects_managed_shared_fs(venue, aspects):
    """
        A CloudSharedFilesystem without existing_id is a validate-error.
    """
    sfs = CloudSharedFilesystem(name="scratch", kind="EFS", size_tb=1)
    spec = NutanixSpec(networks=[make_network()], subnets=[make_subnet()],
                       keypairs=[make_keypair()],
                       shared_filesystems=[sfs])
    provisioner = _provisioner(venue=venue, spec=spec)
    with testbase.raises(NtxValidationError):
        provisioner.validate(aspects=aspects)


def test_validate_none_spec_is_ok(venue, aspects):
    """
        A provisioner with no spec validates trivially.
    """
    provisioner = NutanixCloudProvisioner(venue=venue,
                                          client=MockNutanixClient(),
                                          config=make_config())
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
