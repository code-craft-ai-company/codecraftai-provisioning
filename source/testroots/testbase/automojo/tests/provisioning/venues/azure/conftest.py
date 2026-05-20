"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for Azure venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import pytest

from automojo.credentials.azureserviceprincipalcredential import (
    AzureServicePrincipalCredential
)
from automojo.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
from automojo.provisioning.venues.azure.azureregionconfig import (
    AzureRegionConfig
)
from automojo.provisioning.venues.azure.azuresessionfactory import (
    AzureSessionFactory
)

from ._fakeazure import FakeAzureWorld


@pytest.fixture
def credential() -> AzureServicePrincipalCredential:
    """
        Return a deterministic AzureServicePrincipalCredential.
    """
    rtnval = AzureServicePrincipalCredential(
        identifier="azure-test", categories=["cloud-venue"],
        tenant_id="tenant-abc", client_id="client-abc",
        client_secret="secret-value",
    )
    return rtnval


@pytest.fixture
def region_config() -> AzureRegionConfig:
    """
        Return a deterministic AzureRegionConfig.
    """
    rtnval = AzureRegionConfig(
        subscription_id="sub-test-0001", location="eastus",
        resource_group="rg-testrun01",
        default_tags=[{"automojo:component": "test"}],
    )
    return rtnval


@pytest.fixture
def venue() -> CloudVenue:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="azure-test", provider="azure",
        management_url="https://management.azure.com",
        subscription="sub-test-0001",
        region="eastus", credential="azure-test",
    )
    return rtnval


@pytest.fixture
def world() -> FakeAzureWorld:
    """
        Return a fresh in-memory FakeAzureWorld.
    """
    rtnval = FakeAzureWorld(location="eastus")
    return rtnval


@pytest.fixture
def session_factory(credential, region_config,
                    world) -> AzureSessionFactory:
    """
        Return an AzureSessionFactory wired to the fake azure-mgmt clients.
    """
    factory = AzureSessionFactory(credential=credential,
                                  region_config=region_config)
    factory.override_clients(
        resource=world.resource_client(),
        network=world.network_client(),
        compute=world.compute_client(),
        storage=world.storage_client(),
        dns=world.dns_client(),
    )
    rtnval = factory
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
