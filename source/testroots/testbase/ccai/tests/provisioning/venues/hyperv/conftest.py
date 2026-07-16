"""
    .. module:: conftest
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared fixtures for the Hyper-V venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List

import pytest

from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.hyperv.hvhostconfig import HvHostConfig

from ._mockclient import (
    MockHypervClient
)


class FakeVpnControlPlane:
    """
        Minimal in-memory ``IVPNControlPlane`` stand-in for venue tests.

        Mints a deterministic auth key and records every device deleted so
        the destroy / VPN-cleanup assertion can verify the de-registration.
    """

    def __init__(self) -> None:
        """
            Construct a FakeVpnControlPlane.
        """
        self.minted_authkey: str = "tskey-test-0000"
        self.deleted_devices: List[str] = []
        self.devices: List[Any] = []
        self._mint_count: int = 0
        return

    def mint_authkey(self, *, reusable: bool, ephemeral: bool,
                     tags: List[str], ttl_seconds: int,
                     aspects: Any = None) -> str:
        """
            Mint a deterministic auth key (real IVPNControlPlane signature).

            :param reusable: Whether the key is reusable.
            :param ephemeral: Whether the registration is ephemeral.
            :param tags: The tags bound to the key.
            :param ttl_seconds: The key TTL.
            :param aspects: ProvisioningAspects.

            :returns: A deterministic auth key string.
        """
        self._mint_count = self._mint_count + 1
        rtnval = "tskey-{}".format(self._mint_count)
        return rtnval

    def register_device(self, *, device_id: str, hostname: str) -> None:
        """
            Simulate a client joining the tailnet under a hostname.

            :param device_id: The provider-assigned device id.
            :param hostname: The hostname the client registered with.

            :returns: ``None``.
        """
        from ccai.interfaces.ivpncontrolplane import VPNDeviceRecord
        self.devices.append(VPNDeviceRecord(
            device_id=device_id, hostname=hostname, overlay_address=None))
        return

    def list_devices(self, *, aspects: Any = None) -> List[Any]:
        """
            Enumerate the currently-registered devices.

            :param aspects: ProvisioningAspects.

            :returns: The list of device records.
        """
        rtnval = list(self.devices)
        return rtnval

    def delete_device(self, *, device_id: str, aspects: Any = None) -> None:
        """
            Record a VPN device de-registration.

            :param device_id: The provider device id.
            :param aspects: ProvisioningAspects.

            :returns: ``None``.
        """
        self.deleted_devices.append(device_id)
        return


@pytest.fixture
def venue() -> CloudVenue:
    """
        Return a CloudVenue for the Hyper-V venue tests.

        :returns: A CloudVenue instance.
    """
    rtnval = CloudVenue(name="hyperv-test", provider="hyperv",
                        endpoint="winrm://hv-host:5985",
                        region="lab", credential="hv-cred")
    return rtnval


@pytest.fixture
def host_config() -> HvHostConfig:
    """
        Return an HvHostConfig for the Hyper-V venue tests.

        :returns: An HvHostConfig instance.
    """
    rtnval = HvHostConfig(host="hv-host")
    return rtnval


@pytest.fixture
def client() -> MockHypervClient:
    """
        Return a fresh in-memory MockHypervClient.

        :returns: A MockHypervClient instance.
    """
    rtnval = MockHypervClient()
    return rtnval


@pytest.fixture
def vpn_control_plane() -> FakeVpnControlPlane:
    """
        Return a FakeVpnControlPlane for VPN-join tests.

        :returns: A FakeVpnControlPlane instance.
    """
    rtnval = FakeVpnControlPlane()
    return rtnval


@pytest.fixture
def aspects() -> ProvisioningAspects:
    """
        Return a ProvisioningAspects bundle for tests.

        :returns: A ProvisioningAspects instance.
    """
    rtnval = ProvisioningAspects(runid="hvrun01", verify_timeout=30.0,
                                 verify_interval=0.05)
    return rtnval


@pytest.fixture
def confirm_aspects() -> ProvisioningAspects:
    """
        Return ProvisioningAspects with confirm=True for destroy.

        :returns: A ProvisioningAspects instance.
    """
    rtnval = ProvisioningAspects(runid="hvrun01", confirm=True,
                                 verify_timeout=30.0, verify_interval=0.05)
    return rtnval
