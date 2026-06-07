"""
    .. module:: deviceaddressset
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Address-set descriptor attached to provisioned cloud devices.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Optional

from ccai.restclient.base.schemaobject import SchemaObject
from ccai.restclient.base.schemafield import Field


class DeviceAddressSet(SchemaObject):
    """
        Multi-plane address set for a provisioned cloud device.

        Address planes follow the AddressPlane vocabulary from
        ``codecraftai-interfaces``; the model layer carries the data only.
    """

    public_ipv4 = Field(str, required=False, default=None)
    public_ipv6 = Field(str, required=False, default=None)
    private_ipv4 = Field(str, required=False, default=None)
    private_ipv6 = Field(str, required=False, default=None)
    vpn_ipv4 = Field(str, required=False, default=None)
    vpn_ipv6 = Field(str, required=False, default=None)
    hostname = Field(str, required=False, default=None)

    def __init__(self, *,
                 public_ipv4: Optional[str] = None,
                 public_ipv6: Optional[str] = None,
                 private_ipv4: Optional[str] = None,
                 private_ipv6: Optional[str] = None,
                 vpn_ipv4: Optional[str] = None,
                 vpn_ipv6: Optional[str] = None,
                 hostname: Optional[str] = None) -> None:
        """
            Construct a DeviceAddressSet.

            :param public_ipv4: Public IPv4 address, if any.
            :param public_ipv6: Public IPv6 address, if any.
            :param private_ipv4: Private IPv4 address, if any.
            :param private_ipv6: Private IPv6 address, if any.
            :param vpn_ipv4: VPN-plane IPv4 address, if any.
            :param vpn_ipv6: VPN-plane IPv6 address, if any.
            :param hostname: Canonical hostname, if any.
        """
        super().__init__(public_ipv4=public_ipv4, public_ipv6=public_ipv6,
                         private_ipv4=private_ipv4, private_ipv6=private_ipv6,
                         vpn_ipv4=vpn_ipv4, vpn_ipv6=vpn_ipv6,
                         hostname=hostname)
        return
