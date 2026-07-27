"""
    .. module:: test_validate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Validate-stage tests for the Lambda Labs venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase


from ccai.interfaces.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from ccai.provisioning.model.cloud.cloudnetwork import CloudNetwork
from ccai.provisioning.venues.lambdalabs.lambdalabscloudprovisioner import (
    LambdalabsCloudProvisioner
)
from ccai.provisioning.venues.lambdalabs.llerrors import LlValidationError
from ccai.provisioning.venues.lambdalabs.lambdalabsspec import (
    LambdalabsSpec
)

from ._mockclient import (
    MockLambdalabsClient
)
from ._specfactory import (
    basic_spec, bucket_lb_dns_spec, cluster_spec, make_instance
)


def _provisioner(*, venue, credential, spec):
    """
        Build a LambdalabsCloudProvisioner over a mock client.

        :param venue: The CloudVenue fixture.
        :param credential: The credential fixture.
        :param spec: The LambdalabsSpec under test.

        :returns: A constructed provisioner.
    """
    rtnval = LambdalabsCloudProvisioner(venue=venue, credential=credential,
                                        client=MockLambdalabsClient(),
                                        spec=spec)
    return rtnval


def test_validate_happy_path(venue, credential, aspects):
    """
        A spec with one keypair and one resolvable instance validates ok.
    """
    provisioner = _provisioner(venue=venue, credential=credential,
                               spec=basic_spec())
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    return


def test_validate_rejects_bucket_lb_dns(venue, credential, aspects):
    """
        Object buckets, load balancers, and DNS records are validate-errors.
    """
    provisioner = _provisioner(venue=venue, credential=credential,
                               spec=bucket_lb_dns_spec())
    with testbase.raises(LlValidationError) as excinfo:
        provisioner.validate(aspects=aspects)
    message = str(excinfo.value)
    assert "data-bucket" in message
    assert "api-lb" in message
    assert "api" in message
    return


def test_validate_warns_on_network_resources(venue, credential, aspects):
    """
        Networks produce a warning rather than an error.
    """
    spec = basic_spec()
    spec.networks.append(CloudNetwork(name="vpc-a", cidr="10.0.0.0/16",
                                      region="us-east-1"))
    provisioner = _provisioner(venue=venue, credential=credential, spec=spec)
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    warned = [w["resource"] for w in result.warnings]
    assert "vpc-a" in warned
    return


def test_validate_rejects_unknown_accelerator(venue, credential, aspects):
    """
        An accelerator with no Lambda Labs SKU is a validate-error.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="MI300X", count=8,
                                 interconnect="INFINITY_FABRIC",
                                 memory_gb=192)
    instance = make_instance(accelerators=[accel])
    spec = LambdalabsSpec(instances=[instance])
    provisioner = _provisioner(venue=venue, credential=credential, spec=spec)
    with testbase.raises(LlValidationError):
        provisioner.validate(aspects=aspects)
    return


def test_validate_notes_one_click_cluster_path(venue, credential, aspects):
    """
        An InfiniBand instance produces a 1-Click Cluster warning.
    """
    provisioner = _provisioner(venue=venue, credential=credential,
                               spec=cluster_spec())
    result = provisioner.validate(aspects=aspects)
    assert result.ok is True
    warning_text = " ".join(w["warning"] for w in result.warnings)
    assert "1-Click Cluster" in warning_text
    return


def test_validate_rejects_instance_without_region(venue, credential,
                                                  aspects):
    """
        An instance carrying no region is a validate-error.
    """
    instance = make_instance(region="x")
    instance.subnet = ""
    spec = LambdalabsSpec(instances=[instance])
    provisioner = _provisioner(venue=venue, credential=credential, spec=spec)
    with testbase.raises(LlValidationError):
        provisioner.validate(aspects=aspects)
    return
