"""
    .. module:: clouddevice
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Provisioned cloud device record with addresses and optional VPN.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, Optional

from ccai.interfaces.schemaobject import SchemaObject
from ccai.interfaces.schemafield import Field

from ccai.provisioning.model.cloud.deviceaddressset import DeviceAddressSet
from ccai.interfaces.vpnjoinspec import VPNJoinSpec


class CloudDevice(SchemaObject):
    """
        Provisioned cloud device record.

        The model layer carries the descriptive fields plus optional address
        set and VPN join spec; behaviour (SSH, attach, etc.) lives in the
        landscaping / interop layers.
    """

    identifier = Field(str, required=True)
    category = Field(str, required=True)
    group = Field(str, required=True)
    profile = Field(str, required=True)
    role = Field(str, required=True)
    addresses = Field(DeviceAddressSet, required=False, default=None)
    vpn_join = Field(VPNJoinSpec, required=False, default=None)
    tags = Field(dict, required=False, default=None)

    def __init__(self, *, identifier: str, category: str, group: str,
                 profile: str, role: str,
                 addresses: Optional[DeviceAddressSet] = None,
                 vpn_join: Optional[VPNJoinSpec] = None,
                 tags: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a CloudDevice.

            :param identifier: Unique device identifier.
            :param category: Device category.
            :param group: Group name.
            :param profile: CloudResourceProfile name backing this device.
            :param role: Functional role.
            :param addresses: Optional DeviceAddressSet.
            :param vpn_join: Optional VPNJoinSpec.
            :param tags: Optional flat dict of tag key/value pairs.
        """
        effective_tags = tags if tags is not None else {}
        super().__init__(identifier=identifier, category=category, group=group,
                         profile=profile, role=role, addresses=addresses,
                         vpn_join=vpn_join, tags=effective_tags)
        return

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CloudDevice":
        """
            Construct from serialised payload, promoting nested types.

            :param data: Serialised payload.

            :returns: A CloudDevice instance.
        """
        if not isinstance(data, dict):
            return data  # type: ignore

        addr_payload = data.get("addresses", None)
        promoted_addrs: Optional[DeviceAddressSet] = None
        if addr_payload is not None:
            if isinstance(addr_payload, DeviceAddressSet):
                promoted_addrs = addr_payload
            else:
                promoted_addrs = DeviceAddressSet.from_dict(addr_payload)

        vpn_payload = data.get("vpn_join", None)
        promoted_vpn: Optional[VPNJoinSpec] = None
        if vpn_payload is not None:
            if isinstance(vpn_payload, VPNJoinSpec):
                promoted_vpn = vpn_payload
            else:
                promoted_vpn = VPNJoinSpec.from_dict(vpn_payload)

        rtnval = cls(identifier=data["identifier"],
                     category=data["category"],
                     group=data["group"], profile=data["profile"],
                     role=data["role"], addresses=promoted_addrs,
                     vpn_join=promoted_vpn,
                     tags=data.get("tags", None))
        return rtnval
