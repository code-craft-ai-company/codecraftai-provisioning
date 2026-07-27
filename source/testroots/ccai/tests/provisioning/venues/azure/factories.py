"""
    .. module:: factories
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for Azure venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from collections.abc import Generator

from ccai import testbase

from ccai.credentials.azureserviceprincipalcredential import (
    AzureServicePrincipalCredential
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.azure.azureregionconfig import (
    AzureRegionConfig
)
from ccai.provisioning.venues.azure.azuresessionfactory import (
    AzureSessionFactory
)

from ccai.tests.provisioning.venues.azure._fakeazure import FakeAzureWorld

@testbase.register.resource_factory()
def create_azure_credential(constraints=None) -> Generator[AzureServicePrincipalCredential, None, None]:
    """
        Return a deterministic AzureServicePrincipalCredential.
    """
    rtnval = AzureServicePrincipalCredential(
        identifier="azure-test", categories=["cloud-venue"],
        tenant_id="tenant-abc", client_id="client-abc",
        client_secret="secret-value",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_azure_region_config(constraints=None) -> Generator[AzureRegionConfig, None, None]:
    """
        Return a deterministic AzureRegionConfig.
    """
    rtnval = AzureRegionConfig(
        subscription_id="sub-test-0001", location="eastus",
        resource_group="rg-testrun01",
        default_tags={"ccai:component": "test"},
    )
    yield rtnval


@testbase.register.resource_factory()
def create_azure_venue(constraints=None) -> Generator[CloudVenue, None, None]:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="azure-test", provider="azure",
        account="sub-test-0001",
        region="eastus", credential="azure-test",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_azure_world(constraints=None) -> Generator[FakeAzureWorld, None, None]:
    """
        Return a fresh in-memory FakeAzureWorld.
    """
    rtnval = FakeAzureWorld(location="eastus")
    yield rtnval


@testbase.register.resource_factory()
def create_azure_session_factory(credential, region_config,
                    world, constraints=None) -> Generator[AzureSessionFactory, None, None]:
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
    yield rtnval


@testbase.register.resource_factory()
def create_azure_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="testrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    yield rtnval


@testbase.register.resource_factory()
def create_azure_confirm_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Aspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="testrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    yield rtnval
