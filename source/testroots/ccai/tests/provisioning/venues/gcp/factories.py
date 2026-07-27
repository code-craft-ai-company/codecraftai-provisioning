"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for GCP venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from collections.abc import Generator
from typing import Any

from ccai import testbase

from ccai.credentials.gcpserviceaccountkeycredential import (
    GcpServiceAccountKeyCredential
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.google.gcpregionconfig import GcpRegionConfig
from ccai.provisioning.venues.google.gcpsessionfactory import (
    SERVICE_COMPUTE, SERVICE_TPU, SERVICE_STORAGE, SERVICE_DNS
)
from ccai.provisioning.venues.google.googlecloudprovisioner import (
    GoogleCloudProvisioner
)

from ._mockgcp import (
    build_fake_compute, FakeTpuClient, FakeStorageClient, FakeDnsClient
)

@testbase.register.resource_factory()
def create_gcp_credential(constraints=None) -> Generator[GcpServiceAccountKeyCredential, None, None]:
    """
        Return a deterministic GcpServiceAccountKeyCredential.
    """
    rtnval = GcpServiceAccountKeyCredential(
        identifier="gcp-test", categories=["cloud-venue"],
        project_id="codecraftai-test", client_email="svc@codecraftai-test.iam"
                                                 ".gserviceaccount.com",
        private_key_id="abcdef0123456789",
        private_key="-----BEGIN PRIVATE KEY-----\nFAKE\n"
                    "-----END PRIVATE KEY-----\n",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_gcp_region_config(constraints=None) -> Generator[GcpRegionConfig, None, None]:
    """
        Return a deterministic GcpRegionConfig.
    """
    rtnval = GcpRegionConfig(
        project="codecraftai-test", region="us-central1",
        zone="us-central1-a",
        default_tags={"ccai:component": "test"},
    )
    yield rtnval


@testbase.register.resource_factory()
def create_gcp_venue(constraints=None) -> Generator[CloudVenue, None, None]:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="gcp-test", provider="gcp",
        account="codecraftai-test",
        region="us-central1", credential="gcp-test",
    )
    yield rtnval


@testbase.register.resource_factory()
def create_gcp_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Return a ProvisioningAspects bundle for tests.
    """
    rtnval = ProvisioningAspects(runid="testrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    yield rtnval


@testbase.register.resource_factory()
def create_gcp_confirm_aspects(constraints=None) -> Generator[ProvisioningAspects, None, None]:
    """
        Aspects with confirm=True for destroy.
    """
    rtnval = ProvisioningAspects(runid="testrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    yield rtnval


@testbase.register.resource_factory()
def create_gcp_make_provisioner(venue, credential, region_config, constraints=None) -> Generator[Any, None, None]:
    """
        Return a factory that builds a wired GoogleCloudProvisioner.
    """
    def _factory(*, spec=None, vpn_control_plane=None):
        provisioner = GoogleCloudProvisioner(
            venue=venue, credential=credential,
            region_config=region_config, spec=spec,
            vpn_control_plane=vpn_control_plane,
        )
        fakes = install_fakes(provisioner=provisioner)
        return provisioner, fakes
    yield _factory
