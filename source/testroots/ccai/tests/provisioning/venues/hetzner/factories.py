"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for Hetzner venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from collections.abc import Generator

from ccai import testbase

from ccai.credentials.hetznerapitokencredential import (
    HetznerApiTokenCredential
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.hetzner.hetznerlocationconfig import (
    HetznerLocationConfig
)

from ._mockclient import MockDnsClient, MockHetznerClient, MockVpnControlPlane

@testbase.register.resource_factory()
def create_credential(constraints=None) -> Generator[HetznerApiTokenCredential, None, None]:
    """
        Return a deterministic HetznerApiTokenCredential.
    """
    rtnval = HetznerApiTokenCredential(
        identifier="hetzner-test", categories=["cloud-venue"],
        token="test-token-value")
    yield rtnval


@testbase.register.resource_factory()
def create_location_config(constraints=None) -> Generator[HetznerLocationConfig, None, None]:
    """
        Return a deterministic HetznerLocationConfig.
    """
    rtnval = HetznerLocationConfig(
        location="nbg1",
        default_labels={"ccai.component": "test"})
    yield rtnval


@testbase.register.resource_factory()
def create_venue(constraints=None) -> Generator[CloudVenue, None, None]:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="hetzner-test", provider="hetzner",
        region="nbg1", credential="hetzner-test")
    yield rtnval


@testbase.register.resource_factory()
def create_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="testrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    yield rtnval


@testbase.register.resource_factory()
def create_confirm_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Aspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="testrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    yield rtnval


@testbase.register.resource_factory()
def create_client(constraints=None) -> Generator[MockHetznerClient, None, None]:
    """
        Return a fresh MockHetznerClient.
    """
    rtnval = MockHetznerClient()
    yield rtnval


@testbase.register.resource_factory()
def create_dns_client(constraints=None) -> Generator[MockDnsClient, None, None]:
    """
        Return a fresh MockDnsClient.
    """
    rtnval = MockDnsClient()
    yield rtnval


@testbase.register.resource_factory()
def create_vpn_control_plane(constraints=None) -> Generator[MockVpnControlPlane, None, None]:
    """
        Return a fresh MockVpnControlPlane.
    """
    rtnval = MockVpnControlPlane()
    yield rtnval
