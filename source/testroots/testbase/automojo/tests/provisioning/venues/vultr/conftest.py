"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for Vultr venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import pytest

import requests_mock as requests_mock_lib

from automojo.credentials.vultrapikeycredential import VultrApiKeyCredential
from automojo.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
from automojo.provisioning.venues.vultr.vultrclient import VultrClient
from automojo.provisioning.venues.vultr.vultrcloudprovisioner import (
    VultrCloudProvisioner
)

from ._fakevultr import FakeVultrApi


@pytest.fixture
def credential() -> VultrApiKeyCredential:
    """
        Return a deterministic VultrApiKeyCredential.
    """
    rtnval = VultrApiKeyCredential(
        identifier="vultr-test", categories=["cloud-venue"],
        token="test-api-key",
    )
    return rtnval


@pytest.fixture
def venue() -> CloudVenue:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="vultr-test", provider="vultr",
        region="ewr", credential="vultr-test",
    )
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
def fake_vultr():
    """
        Yield a (FakeVultrApi, VultrClient) bound through requests-mock.
    """
    fake = FakeVultrApi()
    base_url = "https://api.vultr.com/v2"
    with requests_mock_lib.Mocker() as mocker:
        fake.install(adapter=mocker, base_url=base_url)
        client = VultrClient(token="test-api-key", base_url=base_url)
        yield fake, client


@pytest.fixture
def provisioner_factory(venue, credential):
    """
        Return a factory building a VultrCloudProvisioner bound to a client.
    """
    def _make(*, client, spec, vpn_control_plane=None):
        rtnval = VultrCloudProvisioner(
            venue=venue, credential=credential, spec=spec, client=client,
            default_tags={"automojo:component": "test"},
            vpn_control_plane=vpn_control_plane,
        )
        return rtnval

    return _make
