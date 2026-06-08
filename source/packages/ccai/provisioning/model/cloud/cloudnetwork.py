"""
    .. module:: cloudnetwork
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral cloud network (VPC / VNet / Network) descriptor.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Dict, Optional

from ccai.restclient.base.schemaobject import SchemaObject
from ccai.restclient.base.schemafield import Field

from ccai.provisioning.model.cloud.validators import validate_cidr, validate_name


class CloudNetwork(SchemaObject):
    """
        Venue-neutral network descriptor.

        Maps to AWS VPC, Azure VNet, GCP VPC, Hetzner Network, etc.  Shape-only
        validation runs at construction; cross-resource invariants (subnet
        containment) run in the lifecycle validate stage.
    """

    name = Field(str, required=True)
    cidr = Field(str, required=True)
    region = Field(str, required=True)
    tags = Field(dict, required=False, default=None)

    def __init__(self, *, name: str, cidr: str, region: str,
                 tags: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a CloudNetwork.

            :param name: Network name (≤ 63 chars).
            :param cidr: IPv4 or IPv6 CIDR.
            :param region: Venue-neutral region identifier.
            :param tags: Optional flat dict of tag key/value pairs.

            :raises: SchemaValidationError
        """
        validate_name(value=name)
        validate_cidr(value=cidr)
        validate_name(value=region, max_len=63)

        effective_tags = tags if tags is not None else {}

        super().__init__(name=name, cidr=cidr, region=region, tags=effective_tags)
        return
