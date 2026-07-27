"""
    .. module:: test_validate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Validate-stage tests for the Proxmox VE venue provisioner.

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
from ccai.interfaces.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from ccai.provisioning.venues.proxmox.proxmoxcloudprovisioner import (
    ProxmoxCloudProvisioner
)
from ccai.provisioning.venues.proxmox.proxmoxspec import ProxmoxSpec
from ccai.provisioning.venues.proxmox.pveerrors import PveValidationError

from ccai.tests.provisioning.venues.proxmox._mockclient import MockProxmoxClient
from ccai.tests.provisioning.venues.proxmox._specfactory import (
    basic_spec, bucket_lb_dns_spec, make_credential, make_instance,
    make_keypair, make_network, make_resolver
)


def _provisioner(*, venue, spec):
    """
        Build a ProxmoxCloudProvisioner over a mock client.

        :param venue: The CloudVenue fixture.
        :param spec: The ProxmoxSpec under test.

        :returns: A constructed provisioner.
    """
    rtnval = ProxmoxCloudProvisioner(venue=venue,
                                     credential=make_credential(),
                                     client=MockProxmoxClient(),
                                     spec=spec, resolver=make_resolver())
    return rtnval


def test_validate_happy_path(venue, aspects):
    """
        A spec with one network, keypair, and resolvable instance is ok.
    """
    provisioner = _provisioner(venue=venue, spec=basic_spec())
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


def test_validate_rejects_bucket_lb(venue, aspects):
    """
        Object buckets and load balancers surface as validate-errors.
    """
    provisioner = _provisioner(venue=venue, spec=bucket_lb_dns_spec())
    with testbase.raises(PveValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    message = str(excinfo.value)
    assert "data-bucket" in message
    assert "api-lb" in message
    return


def test_validate_dns_record_is_warning(venue, aspects):
    """
        DNS records produce a warning rather than an error.
    """
    from ccai.provisioning.model.cloud.clouddnsrecord import (
        CloudDnsRecord
    )

    record = CloudDnsRecord(zone="example.com", name="api",
                            record_type="A", values=["203.0.113.1"],
                            ttl_seconds=300)
    spec = ProxmoxSpec(networks=[make_network()],
                       keypairs=[make_keypair()],
                       instances=[make_instance()],
                       dns_records=[record])
    provisioner = _provisioner(venue=venue, spec=spec)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    warned = [w["resource"] for w in result.warnings]
    assert "api" in warned
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
    spec = ProxmoxSpec(networks=[make_network()],
                       keypairs=[make_keypair()], instances=[instance])
    provisioner = _provisioner(venue=venue, spec=spec)
    with testbase.raises(PveValidationError):
        provisioner.validate(aspects=aspects)
    return


def test_validate_rejects_unmanaged_shared_filesystem(venue, aspects):
    """
        A CloudSharedFilesystem of an unsupported kind with no existing_id
        is a validate-error.
    """
    sfs = CloudSharedFilesystem(name="scratch", kind="LUSTRE", size_tb=1)
    spec = ProxmoxSpec(networks=[make_network()],
                       keypairs=[make_keypair()],
                       instances=[make_instance()],
                       shared_filesystems=[sfs])
    provisioner = _provisioner(venue=venue, spec=spec)
    with testbase.raises(PveValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "scratch" in str(excinfo.value)
    return


def test_validate_rejects_unknown_image(venue, aspects):
    """
        An image not in the template catalog is a validate-error naming
        the lookup key attempted.
    """
    instance = make_instance()
    instance.image = CloudImage(family="rhel", version="9",
                                architecture="x86_64")
    spec = ProxmoxSpec(networks=[make_network()],
                       keypairs=[make_keypair()], instances=[instance])
    provisioner = _provisioner(venue=venue, spec=spec)
    with testbase.raises(PveValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "rhel/9" in str(excinfo.value)
    return


def test_validate_rejects_unknown_size(venue, aspects):
    """
        An unrecognised size hint is a validate-error.
    """
    instance = make_instance(size="ginormous")
    spec = ProxmoxSpec(networks=[make_network()],
                       keypairs=[make_keypair()], instances=[instance])
    provisioner = _provisioner(venue=venue, spec=spec)
    with testbase.raises(PveValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "ginormous" in str(excinfo.value)
    return


def test_validate_none_spec_is_ok(venue, aspects):
    """
        A provisioner with no spec validates ok.
    """
    provisioner = _provisioner(venue=venue, spec=None)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return
