"""
    .. module:: cloudsubnet
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral cloud subnet descriptor.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Dict, Optional

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.cloud.validators import validate_cidr, validate_name


class CloudSubnet(SchemaObject):
    """
        Venue-neutral subnet descriptor.

        References a CloudNetwork by name.  Subnet-in-network containment and
        sibling non-overlap are enforced at lifecycle validate time, not here.
    """

    name = Field(str, required=True)
    network = Field(str, required=True)
    cidr = Field(str, required=True)
    zone = Field(str, required=True)
    public = Field(bool, required=False, default=False)
    tags = Field(dict, required=False, default=None)

    def __init__(self, *, name: str, network: str, cidr: str, zone: str,
                 public: bool = False,
                 tags: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a CloudSubnet.

            :param name: Subnet name.
            :param network: Name of the enclosing CloudNetwork.
            :param cidr: Subnet CIDR (IPv4 or IPv6).
            :param zone: Availability zone identifier.
            :param public: When True the venue must attach an internet path.
            :param tags: Optional flat dict of tag key/value pairs.

            :raises: SchemaValidationError
        """
        validate_name(value=name)
        validate_name(value=network)
        validate_cidr(value=cidr)
        validate_name(value=zone)

        effective_tags = tags if tags is not None else {}

        super().__init__(name=name, network=network, cidr=cidr, zone=zone,
                         public=public, tags=effective_tags)
        return
