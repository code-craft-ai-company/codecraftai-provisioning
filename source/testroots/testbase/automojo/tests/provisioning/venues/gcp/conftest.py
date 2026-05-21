"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for GCP venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import pytest

from automojo.credentials.gcpserviceaccountkeycredential import (
    GcpServiceAccountKeyCredential
)
from automojo.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
from automojo.provisioning.venues.google.gcpregionconfig import GcpRegionConfig
from automojo.provisioning.venues.google.gcpsessionfactory import (
    SERVICE_COMPUTE, SERVICE_TPU, SERVICE_STORAGE, SERVICE_DNS
)
from automojo.provisioning.venues.google.googlecloudprovisioner import (
    GoogleCloudProvisioner
)

from ._mockgcp import (
    build_fake_compute, FakeTpuClient, FakeStorageClient, FakeDnsClient
)


@pytest.fixture
def credential() -> GcpServiceAccountKeyCredential:
    """
        Return a deterministic GcpServiceAccountKeyCredential.
    """
    rtnval = GcpServiceAccountKeyCredential(
        identifier="gcp-test", categories=["cloud-venue"],
        project_id="automojo-test", client_email="svc@automojo-test.iam"
                                                 ".gserviceaccount.com",
        private_key_id="abcdef0123456789",
        private_key="-----BEGIN PRIVATE KEY-----\nFAKE\n"
                    "-----END PRIVATE KEY-----\n",
    )
    return rtnval


@pytest.fixture
def region_config() -> GcpRegionConfig:
    """
        Return a deterministic GcpRegionConfig.
    """
    rtnval = GcpRegionConfig(
        project="automojo-test", region="us-central1",
        zone="us-central1-a",
        default_tags=[{"automojo:component": "test"}],
    )
    return rtnval


@pytest.fixture
def venue() -> CloudVenue:
    """
        Return a CloudVenue for tests.
    """
    rtnval = CloudVenue(
        name="gcp-test", provider="gcp",
        account="automojo-test",
        region="us-central1", credential="gcp-test",
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


def install_fakes(*, provisioner: GoogleCloudProvisioner) -> dict:
    """
        Install in-memory fake clients into a provisioner's session factory.

        :param provisioner: The GoogleCloudProvisioner to wire fakes into.

        :returns: A dict of the installed fake client objects.
    """
    compute = build_fake_compute()
    tpu = FakeTpuClient()
    storage = FakeStorageClient()
    dns = FakeDnsClient()

    factory = provisioner.session_factory
    factory.set_client(service_name=SERVICE_COMPUTE, client=compute)
    factory.set_client(service_name=SERVICE_TPU, client=tpu)
    factory.set_client(service_name=SERVICE_STORAGE, client=storage)
    factory.set_client(service_name=SERVICE_DNS, client=dns)

    rtnval = {"compute": compute, "tpu": tpu, "storage": storage,
              "dns": dns}
    return rtnval


@pytest.fixture
def make_provisioner(venue, credential, region_config):
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
    return _factory
