"""
    .. module:: factories
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for Vultr venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from collections.abc import Generator
from typing import Any

from ccai import testbase

import requests_mock as requests_mock_lib

from ccai.credentials.vultrapikeycredential import VultrApiKeyCredential
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.vultr.vultrclient import VultrClient
from ccai.provisioning.venues.vultr.vultrcloudprovisioner import (
    VultrCloudProvisioner
)

from ._fakevultr import FakeVultrApi

@testbase.register.resource_factory()
def create_vultr_credential(constraints=None) -> Generator[VultrApiKeyCredential, None, None]:
    """
        Return a deterministic VultrApiKeyCredential.
    """
    rtnval = VultrApiKeyCredential(
        identifier="vultr-test", categories=["cloud-venue"],
        token="test-api-key",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_vultr_venue(constraints=None) -> Generator[CloudVenue, None, None]:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="vultr-test", provider="vultr",
        region="ewr", credential="vultr-test",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_vultr_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="testrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    yield rtnval


@testbase.register.resource_factory()
def create_vultr_confirm_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Aspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="testrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    yield rtnval


@testbase.register.resource_factory()
def create_vultr_fake_vultr(constraints=None) -> Generator[Any, None, None]:
    """
        Yield a (FakeVultrApi, VultrClient) bound through requests-mock.
    """
    fake = FakeVultrApi()
    base_url = "https://api.vultr.com/v2"
    with requests_mock_lib.Mocker() as mocker:
        fake.install(adapter=mocker, base_url=base_url)
        client = VultrClient(token="test-api-key", base_url=base_url)
        yield fake, client


@testbase.register.resource_factory()
def create_vultr_provisioner_factory(venue, credential, constraints=None) -> Generator[Any, None, None]:
    """
        Return a factory building a VultrCloudProvisioner bound to a client.
    """
    def _make(*, client, spec, vpn_control_plane=None):
        rtnval = VultrCloudProvisioner(
            venue=venue, credential=credential, spec=spec, client=client,
            default_tags={"ccai:component": "test"},
            vpn_control_plane=vpn_control_plane,
        )
        return rtnval

    yield _make
