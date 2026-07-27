"""
    .. module:: factories
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for DigitalOcean venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from collections.abc import Generator

from ccai import testbase

from ccai.credentials.digitaloceanapitokencredential import (
    DigitalOceanApiTokenCredential
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.digitalocean.doclient import (
    DigitalOceanClient
)
from ccai.provisioning.venues.digitalocean.doregionconfig import (
    DoRegionConfig
)

from ccai.tests.provisioning.venues.digitalocean._mockclient import MockDigitalOceanRawClient

@testbase.register.resource_factory()
def create_digitalocean_credential(constraints=None) -> Generator[DigitalOceanApiTokenCredential, None, None]:
    """
        Return a deterministic DigitalOceanApiTokenCredential.
    """
    rtnval = DigitalOceanApiTokenCredential(
        identifier="do-test", categories=["cloud-venue"],
        token="dop_v1_testtoken",
        # Spaces authenticates with its own key pair, not the API token.  A
        # credential without them cannot do bucket work at all, so any spec
        # carrying a bucket needs them present here.
        spaces_access_key="DO00TESTACCESSKEY",
        spaces_secret_key="test-spaces-secret",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_digitalocean_region_config(constraints=None) -> Generator[DoRegionConfig, None, None]:
    """
        Return a deterministic DoRegionConfig.
    """
    rtnval = DoRegionConfig(
        region="nyc3", spaces_region="nyc3",
        default_tags={"ccai:component": "test"},
    )
    yield rtnval


@testbase.register.resource_factory()
def create_digitalocean_venue(constraints=None) -> Generator[CloudVenue, None, None]:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="do-test", provider="digitalocean",
        region="nyc3", credential="do-test",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_digitalocean_raw_client(constraints=None) -> Generator[MockDigitalOceanRawClient, None, None]:
    """
        Return a fresh in-memory mock pydo client.
    """
    rtnval = MockDigitalOceanRawClient()
    yield rtnval


@testbase.register.resource_factory()
def create_digitalocean_do_client(credential, raw_client, constraints=None) -> Generator[DigitalOceanClient, None, None]:
    """
        Return a DigitalOceanClient wrapping the mock clients.

        The Spaces client must be injected too.  Without it, ``spaces()``
        builds a real S3-compatible client and bucket work reaches the network
        — which is what every bucket-touching test was doing before.
    """
    rtnval = DigitalOceanClient(credential=credential, raw_client=raw_client,
                                spaces_client=raw_client.spaces)
    yield rtnval


@testbase.register.resource_factory()
def create_digitalocean_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="dotestrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    yield rtnval


@testbase.register.resource_factory()
def create_digitalocean_confirm_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Aspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="dotestrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    yield rtnval
