"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for Equinix Metal venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from collections.abc import Generator

from ccai import testbase

from ccai.credentials.equinixmetalapitokencredential import (
    EquinixMetalApiTokenCredential
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.equinix_metal.metalprojectconfig import (
    MetalProjectConfig
)

from ._mockmetalclient import MockMetalClient

@testbase.register.resource_factory()
def create_equinix_metal_credential(constraints=None) -> Generator[EquinixMetalApiTokenCredential, None, None]:
    """
        Return a deterministic EquinixMetalApiTokenCredential.
    """
    rtnval = EquinixMetalApiTokenCredential(
        identifier="equinix-test", categories=["cloud-venue"],
        token="metal-test-token",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_equinix_metal_project_config(constraints=None) -> Generator[MetalProjectConfig, None, None]:
    """
        Return a deterministic MetalProjectConfig.
    """
    rtnval = MetalProjectConfig(
        project_id="proj-test", metro="sv",
        default_tags={"ccai:component": "test"},
    )
    yield rtnval


@testbase.register.resource_factory()
def create_equinix_metal_venue(constraints=None) -> Generator[CloudVenue, None, None]:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="metal-test", provider="equinix-metal",
        account="proj-test", region="sv", credential="equinix-test",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_equinix_metal_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="testrun01", verify_timeout=5.0,
                                 verify_interval=0.01)
    yield rtnval


@testbase.register.resource_factory()
def create_equinix_metal_confirm_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Aspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="testrun01", confirm=True,
                                 verify_timeout=5.0, verify_interval=0.01)
    yield rtnval


@testbase.register.resource_factory()
def create_equinix_metal_mock_client(constraints=None) -> Generator[MockMetalClient, None, None]:
    """
        Return a fresh deterministic MockMetalClient.
    """
    rtnval = MockMetalClient(project_id="proj-test")
    yield rtnval
