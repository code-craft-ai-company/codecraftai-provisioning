"""
    .. module:: test_validate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Validate-stage tests for the XCP-ng venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase


from ccai.provisioning.venues.xcpng.xcpngcloudprovisioner import (
    XcpngCloudProvisioner
)
from ccai.provisioning.venues.xcpng.xenerrors import XenValidationError
from ccai.provisioning.venues.xcpng.xcpngspec import XcpngSpec

from ccai.tests.provisioning.venues.xcpng._mockclient import MockXenClient
from ccai.tests.provisioning.venues.xcpng._specfactory import (
    basic_spec, bucket_lb_spec, dns_record_spec, interconnect_spec,
    make_instance
)


def _provisioner(*, venue, spec):
    """
        Build an XcpngCloudProvisioner over a mock client.

        :param venue: The CloudVenue fixture.
        :param spec: The XcpngSpec under test.

        :returns: A constructed provisioner.
    """
    rtnval = XcpngCloudProvisioner(venue=venue, client=MockXenClient(),
                                   spec=spec)
    return rtnval


def test_validate_happy_path(venue, aspects):
    """
        A spec with one network and one resolvable instance validates ok.
    """
    provisioner = _provisioner(venue=venue, spec=basic_spec())
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


def test_validate_no_spec_is_ok(venue, aspects):
    """
        A provisioner with no spec validates ok with an empty result.
    """
    provisioner = XcpngCloudProvisioner(venue=venue, client=MockXenClient())
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


def test_validate_rejects_object_bucket_and_load_balancer(venue, aspects):
    """
        Object buckets and load balancers are validate-errors.
    """
    provisioner = _provisioner(venue=venue, spec=bucket_lb_spec())
    with testbase.raises(XenValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    message = str(excinfo.value)
    assert "data-bucket" in message
    assert "api-lb" in message
    return


def test_validate_rejects_hpc_interconnect(venue, aspects):
    """
        A non-NONE HPC interconnect is a validate-error.
    """
    provisioner = _provisioner(venue=venue, spec=interconnect_spec())
    with testbase.raises(XenValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "INFINIBAND_NDR" in str(excinfo.value)
    return


def test_validate_rejects_efa_and_oci_rdma_interconnect(venue, aspects):
    """
        Cross-cutting #5: EFA and OCI_RDMA interconnect kinds — rejected by
        every sibling VM venue — are validate-errors on XCP-ng too.
    """
    for kind in ("EFA", "OCI_RDMA"):
        provisioner = _provisioner(venue=venue,
                                   spec=interconnect_spec(kind=kind))
        with testbase.raises(XenValidationError) as excinfo:
            provisioner.validate(aspects=aspects)
        assert kind in str(excinfo.value)
    return


def test_validate_rejects_unresolvable_size(venue, aspects):
    """
        An instance whose size resolves to neither a slug nor the
        <vcpus>x<gib> form is a validate-error.
    """
    instance = make_instance(name="bad-size", size="ginormous")
    spec = XcpngSpec(instances=[instance])
    provisioner = _provisioner(venue=venue, spec=spec)
    with testbase.raises(XenValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    assert "bad-size" in str(excinfo.value)
    return


def test_validate_warns_on_dns_record(venue, aspects):
    """
        DNS records produce a warning rather than an error.
    """
    provisioner = _provisioner(venue=venue, spec=dns_record_spec())
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    warned = [w["resource"] for w in result.warnings]
    assert "api" in warned
    return


def test_validate_warns_on_security_group(venue, aspects):
    """
        Security groups produce a warning recording tag-only intent.
    """
    from ccai.provisioning.model.cloud.cloudsecuritygroup import (
        CloudSecurityGroup
    )
    spec = basic_spec()
    spec.security_groups.append(CloudSecurityGroup(name="web-sg",
                                                   network="lab-net"))
    provisioner = _provisioner(venue=venue, spec=spec)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    warning_text = " ".join(w["warning"] for w in result.warnings)
    assert "tag" in warning_text.lower()
    return


def test_validate_accepts_explicit_hardware_size(venue, aspects):
    """
        An instance whose size uses the <vcpus>x<gib> form validates ok.
    """
    instance = make_instance(name="explicit", size="4x16")
    spec = XcpngSpec(instances=[instance], networks=[])
    provisioner = _provisioner(venue=venue, spec=spec)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return
