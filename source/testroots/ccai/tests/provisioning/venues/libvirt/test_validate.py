"""
    .. module:: test_validate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Validate-stage tests for the libvirt venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase


from ccai.provisioning.model.cloud.cloudimage import CloudImage
from ccai.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from ccai.provisioning.model.cloud.cloudsecuritygroup import (
    CloudSecurityGroup
)
from ccai.interfaces.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from ccai.provisioning.venues.libvirt.libvirtcloudprovisioner import (
    LibvirtCloudProvisioner
)
from ccai.provisioning.venues.libvirt.libvirtspec import LibvirtSpec
from ccai.provisioning.venues.libvirt.lverrors import LvValidationError

from ._mockclient import MockLibvirtClient
from ._specfactory import (
    basic_spec, bucket_lb_dns_spec, make_config, make_instance,
    make_keypair, make_network
)


def _provisioner(*, venue, spec):
    """
        Build a LibvirtCloudProvisioner over a mock client.

        :param venue: The CloudVenue fixture.
        :param spec: The LibvirtSpec under test.

        :returns: A constructed provisioner.
    """
    rtnval = LibvirtCloudProvisioner(venue=venue,
                                     client=MockLibvirtClient(),
                                     config=make_config(), spec=spec)
    return rtnval


def test_validate_happy_path(venue, aspects):
    """
        A spec with one network, keypair, and resolvable instance is ok.
    """
    provisioner = _provisioner(venue=venue, spec=basic_spec())
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


def test_validate_rejects_bucket_lb_dns(venue, aspects):
    """
        Object buckets, load balancers, and DNS records are errors.
    """
    provisioner = _provisioner(venue=venue, spec=bucket_lb_dns_spec())
    with testbase.raises(LvValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    message = str(excinfo.value)
    assert "data-bucket" in message
    assert "api-lb" in message
    assert "api" in message
    return


def test_validate_rejects_interconnect(venue, aspects):
    """
        A non-NONE HPC interconnect is a validate-error.
    """
    interconnect = CloudInterconnect(kind="INFINIBAND_NDR",
                                     bandwidth_gbps=400,
                                     topology="RAIL_OPTIMIZED")
    instance = make_instance()
    instance.interconnect = interconnect
    spec = LibvirtSpec(networks=[make_network()],
                       keypairs=[make_keypair()], instances=[instance])
    provisioner = _provisioner(venue=venue, spec=spec)
    with testbase.raises(LvValidationError):
        provisioner.validate(aspects=aspects)
    return


def test_validate_rejects_unmanaged_shared_filesystem(venue, aspects):
    """
        A CloudSharedFilesystem with no existing_id is a validate-error.
    """
    sfs = CloudSharedFilesystem(name="scratch", kind="LUSTRE", size_tb=1)
    spec = LibvirtSpec(networks=[make_network()],
                       keypairs=[make_keypair()],
                       instances=[make_instance()],
                       shared_filesystems=[sfs])
    provisioner = _provisioner(venue=venue, spec=spec)
    with testbase.raises(LvValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "scratch" in str(excinfo.value)
    return


def test_validate_rejects_unknown_image(venue, aspects):
    """
        An image not in the base-image catalog is a validate-error
        naming the lookup attempted.
    """
    instance = make_instance()
    instance.image = CloudImage(family="rhel", version="9",
                                architecture="x86_64")
    spec = LibvirtSpec(networks=[make_network()],
                       keypairs=[make_keypair()], instances=[instance])
    provisioner = _provisioner(venue=venue, spec=spec)
    with testbase.raises(LvValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "rhel/9" in str(excinfo.value)
    return


def test_validate_warns_on_security_group(venue, aspects):
    """
        Security groups produce a warning rather than an error.
    """
    spec = basic_spec()
    spec.security_groups.append(CloudSecurityGroup(name="web-sg",
                                                   network="vmnet"))
    provisioner = _provisioner(venue=venue, spec=spec)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    warned = [w["resource"] for w in result.warnings]
    assert "web-sg" in warned
    return


def test_validate_none_spec_is_ok(venue, aspects):
    """
        A provisioner with no spec validates ok.
    """
    provisioner = LibvirtCloudProvisioner(venue=venue,
                                          client=MockLibvirtClient(),
                                          config=make_config(), spec=None)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return
