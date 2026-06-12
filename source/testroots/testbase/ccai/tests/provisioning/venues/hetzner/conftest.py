"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for Hetzner venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import pytest

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


@pytest.fixture
def credential() -> HetznerApiTokenCredential:
    """
        Return a deterministic HetznerApiTokenCredential.
    """
    rtnval = HetznerApiTokenCredential(
        identifier="hetzner-test", categories=["cloud-venue"],
        token="test-token-value")
    return rtnval


@pytest.fixture
def location_config() -> HetznerLocationConfig:
    """
        Return a deterministic HetznerLocationConfig.
    """
    rtnval = HetznerLocationConfig(
        location="nbg1",
        default_labels={"ccai.component": "test"})
    return rtnval


@pytest.fixture
def venue() -> CloudVenue:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="hetzner-test", provider="hetzner",
        region="nbg1", credential="hetzner-test")
    return rtnval


@pytest.fixture
def aspects() -> ProvisioningAspects:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="testrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    return rtnval


@pytest.fixture
def confirm_aspects() -> ProvisioningAspects:
    """
        Aspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="testrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    return rtnval


@pytest.fixture
def client() -> MockHetznerClient:
    """
        Return a fresh MockHetznerClient.
    """
    rtnval = MockHetznerClient()
    return rtnval


@pytest.fixture
def dns_client() -> MockDnsClient:
    """
        Return a fresh MockDnsClient.
    """
    rtnval = MockDnsClient()
    return rtnval


@pytest.fixture
def vpn_control_plane() -> MockVpnControlPlane:
    """
        Return a fresh MockVpnControlPlane.
    """
    rtnval = MockVpnControlPlane()
    return rtnval
