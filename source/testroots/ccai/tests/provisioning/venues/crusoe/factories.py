"""
    .. module:: factories
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Test resource factories for the Crusoe venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from collections.abc import Generator

from ccai import testbase

from ccai.provisioning.model.cloud.cloudvenue import CloudVenue

from ccai.provisioning.venues.crusoe.crusoecloudprovisioner import (
    CrusoeCloudProvisioner
)
from ccai.provisioning.venues.crusoe.crusoeprojectconfig import (
    CrusoeProjectConfig
)


from ccai.tests.provisioning.venues.crusoe._mockclient import MockCrusoeClient


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

@testbase.register.resource_factory()
def create_crusoe_crusoe_aspects(constraints=None) -> Generator[_Aspects, None, None]:
    """
        Return a default aspects object for tests.

        :returns: An aspects stand-in.
    """
    rtnval = _Aspects(runid="run-1")
    yield rtnval


@testbase.register.resource_factory()
def create_crusoe_crusoe_confirm_aspects(constraints=None) -> Generator[_Aspects, None, None]:
    """
        Return a confirm=True aspects object for destroy tests.

        :returns: An aspects stand-in with confirm set.
    """
    rtnval = _Aspects(runid="run-1", confirm=True)
    yield rtnval


@testbase.register.resource_factory()
def create_crusoe_crusoe_venue(constraints=None) -> Generator[CloudVenue, None, None]:
    """
        Return a CloudVenue describing the Crusoe test venue.

        :returns: A CloudVenue.
    """
    rtnval = CloudVenue(name="crusoe-test", provider="crusoe",
                        region="us-east1", credential="crusoe-cred")
    yield rtnval


@testbase.register.resource_factory()
def create_crusoe_mock_client(constraints=None) -> Generator[MockCrusoeClient, None, None]:
    """
        Return a fresh in-memory MockCrusoeClient.

        :returns: A MockCrusoeClient.
    """
    rtnval = MockCrusoeClient()
    yield rtnval


@testbase.register.resource_factory()
def create_crusoe_project_config(constraints=None) -> Generator[CrusoeProjectConfig, None, None]:
    """
        Return a CrusoeProjectConfig for tests.

        :returns: A CrusoeProjectConfig.
    """
    rtnval = CrusoeProjectConfig(project_id="proj-1", location="us-east1-a")
    yield rtnval


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


def make_provisioner(*, venue: CloudVenue, client: MockCrusoeClient,
                     project_config: CrusoeProjectConfig, spec=None,
                     vpn_control_plane=None) -> CrusoeCloudProvisioner:
    """
        Build a CrusoeCloudProvisioner bound to the mock client.

        Not a resource factory: the tests call it directly with a spec they
        build per case, so there is nothing for the injector to resolve.

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
