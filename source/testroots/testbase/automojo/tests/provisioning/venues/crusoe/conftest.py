"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared pytest fixtures for the Crusoe venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import sys

from pathlib import Path

import pytest

from automojo.provisioning.model.cloud.cloudvenue import CloudVenue

from automojo.provisioning.venues.crusoe.crusoecloudprovisioner import (
    CrusoeCloudProvisioner
)
from automojo.provisioning.venues.crusoe.crusoeprojectconfig import (
    CrusoeProjectConfig
)

sys.path.insert(0, str(Path(__file__).parent))

from _mockclient import MockCrusoeClient  # noqa: E402


class _Aspects:
    """
        Minimal aspects stand-in carrying runid and confirm.
    """

    def __init__(self, *, runid: str = "run-1",
                 confirm: bool = False) -> None:
        """
            :param runid: The provisioning run identifier.
            :param confirm: Whether destroy is confirmed.
        """
        self.runid = runid
        self.confirm = confirm
        return


@pytest.fixture
def crusoe_aspects() -> _Aspects:
    """
        Return a default aspects object for tests.

        :returns: An aspects stand-in.
    """
    rtnval = _Aspects(runid="run-1")
    return rtnval


@pytest.fixture
def crusoe_confirm_aspects() -> _Aspects:
    """
        Return a confirm=True aspects object for destroy tests.

        :returns: An aspects stand-in with confirm set.
    """
    rtnval = _Aspects(runid="run-1", confirm=True)
    return rtnval


@pytest.fixture
def crusoe_venue() -> CloudVenue:
    """
        Return a CloudVenue describing the Crusoe test venue.

        :returns: A CloudVenue.
    """
    rtnval = CloudVenue(name="crusoe-test", provider="crusoe",
                        management_url="https://api.crusoecloud.com",
                        subscription="proj-1", region="us-east1",
                        credential="crusoe-cred")
    return rtnval


@pytest.fixture
def mock_client() -> MockCrusoeClient:
    """
        Return a fresh in-memory MockCrusoeClient.

        :returns: A MockCrusoeClient.
    """
    rtnval = MockCrusoeClient()
    return rtnval


@pytest.fixture
def project_config() -> CrusoeProjectConfig:
    """
        Return a CrusoeProjectConfig for tests.

        :returns: A CrusoeProjectConfig.
    """
    rtnval = CrusoeProjectConfig(project_id="proj-1", location="us-east1-a")
    return rtnval


def make_provisioner(*, venue: CloudVenue, client: MockCrusoeClient,
                     project_config: CrusoeProjectConfig, spec=None,
                     vpn_control_plane=None) -> CrusoeCloudProvisioner:
    """
        Build a CrusoeCloudProvisioner bound to the mock client.

        :param venue: The CloudVenue.
        :param client: The MockCrusoeClient.
        :param project_config: The CrusoeProjectConfig.
        :param spec: Optional CrusoeSpec.
        :param vpn_control_plane: Optional VPN control plane.

        :returns: A CrusoeCloudProvisioner.
    """
    rtnval = CrusoeCloudProvisioner(venue=venue, client=client,
                                    project_config=project_config, spec=spec,
                                    vpn_control_plane=vpn_control_plane)
    return rtnval
