"""
    .. module:: test_validate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Validate-stage tests for the Hyper-V venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase

from ccai.tests.provisioning.venues.hyperv.factories import create_hyperv_client


from ccai.provisioning.venues.hyperv.hverrors import HvValidationError
from ccai.provisioning.venues.hyperv.hypervcloudprovisioner import (
    HypervCloudProvisioner
)
from ccai.provisioning.venues.hyperv.hypervspec import HypervSpec

from ccai.tests.provisioning.venues.hyperv import _specfactory


def _provisioner(*, venue, client, host_config, spec):
    """
        Build a HypervCloudProvisioner for a validate test.

        :param venue: The CloudVenue.
        :param client: The MockHypervClient.
        :param host_config: The HvHostConfig.
        :param spec: The HypervSpec.

        :returns: A HypervCloudProvisioner.
    """
    rtnval = HypervCloudProvisioner(venue=venue, client=client,
                                    host_config=host_config, spec=spec)
    return rtnval


@testbase.attach.parameter(create_hyperv_client, identifier="client")
def test_validate_happy_path(venue, client, host_config, aspects):
    """
        A well-formed spec validates with ok=True.
    """
    spec = _specfactory.make_basic_spec()
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    result = provisioner.validate(aspects=aspects)

    assert result.ok is True
    assert len(result.errors) == 0
    return


@testbase.attach.parameter(create_hyperv_client, identifier="client")
def test_validate_none_spec_is_ok(venue, client, host_config, aspects):
    """
        A provisioner with no spec validates trivially.
    """
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=None)

    result = provisioner.validate(aspects=aspects)

    assert result.ok is True
    return


@testbase.attach.parameter(create_hyperv_client, identifier="client")
def test_validate_rejects_object_bucket(venue, client, host_config, aspects):
    """
        A CloudObjectBucket is rejected at validate time.
    """
    spec = HypervSpec(buckets=[_specfactory.make_bucket()])
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    with testbase.raises(HvValidationError) as excinfo:
        provisioner.validate(aspects=aspects)

    assert "object storage" in str(excinfo.value)
    return


@testbase.attach.parameter(create_hyperv_client, identifier="client")
def test_validate_rejects_load_balancer(venue, client, host_config,
                                        aspects):
    """
        A CloudLoadBalancer is rejected at validate time.
    """
    spec = HypervSpec(load_balancers=[_specfactory.make_load_balancer()])
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    with testbase.raises(HvValidationError) as excinfo:
        provisioner.validate(aspects=aspects)

    assert "load balancer" in str(excinfo.value)
    return


@testbase.attach.parameter(create_hyperv_client, identifier="client")
def test_validate_warns_on_dns_record(venue, client, host_config, aspects):
    """
        A CloudDnsRecord produces a warning, not an error.
    """
    spec = HypervSpec(dns_records=[_specfactory.make_dns_record()])
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    result = provisioner.validate(aspects=aspects)

    assert result.ok is True
    assert len(result.warnings) == 1
    return


@testbase.attach.parameter(create_hyperv_client, identifier="client")
def test_validate_rejects_unknown_image_family(venue, client, host_config,
                                               aspects):
    """
        An instance whose image family has no parent VHD is rejected.
    """
    instance = _specfactory.make_instance(image_family="rocky")
    spec = HypervSpec(networks=[_specfactory.make_network()],
                      instances=[instance])
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    with testbase.raises(HvValidationError) as excinfo:
        provisioner.validate(aspects=aspects)

    assert "Image not resolvable" in str(excinfo.value)
    return


@testbase.attach.parameter(create_hyperv_client, identifier="client")
def test_validate_rejects_unknown_size(venue, client, host_config, aspects):
    """
        An instance with an unmappable size hint is rejected.
    """
    instance = _specfactory.make_instance(size="gigantic")
    spec = HypervSpec(networks=[_specfactory.make_network()],
                      instances=[instance])
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    with testbase.raises(HvValidationError) as excinfo:
        provisioner.validate(aspects=aspects)

    assert "Size not resolvable" in str(excinfo.value)
    return


@testbase.attach.parameter(create_hyperv_client, identifier="client")
def test_validate_aspects_default_substituted(venue, client, host_config):
    """
        validate accepts an omitted aspects argument.
    """
    spec = _specfactory.make_basic_spec()
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    result = provisioner.validate()

    assert result.ok is True
    return
