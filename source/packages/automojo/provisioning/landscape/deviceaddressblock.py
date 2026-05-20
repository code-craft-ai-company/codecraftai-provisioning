"""
    .. module:: deviceaddressblock
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DeviceAddressBlock used in emitted landscape device entries.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, Optional

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field


class DeviceAddressBlock(SchemaObject):
    """
        Subset of address fields emitted for one device in landscape.yaml.

        ``public`` is OMITTED (not None) when the host has no public IP.
        ``overlay`` is only present when the host joined a VPN overlay.
    """

    public = Field(str, required=False, default=None)
    private = Field(str, required=False, default=None)
    overlay = Field(dict, required=False, default=None)

    def __init__(self, *, public: Optional[str] = None,
                 private: Optional[str] = None,
                 overlay: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a DeviceAddressBlock.

            :param public: Optional public IP address string.
            :param private: Optional private IP address string.
            :param overlay: Optional {provider, address, magic_dns} dict.
        """
        super().__init__(public=public, private=private, overlay=overlay)
        return

    def to_emitted_dict(self) -> Dict[str, Any]:
        """
            Produce the landscape-shaped dict, omitting absent keys.

            :returns: Dict with only the populated address keys.
        """
        rtnval: Dict[str, Any] = {}
        if self.public is not None:
            rtnval["public"] = self.public
        if self.private is not None:
            rtnval["private"] = self.private
        if self.overlay is not None:
            rtnval["overlay"] = self.overlay
        return rtnval
