"""
    .. module:: cloudegressrule
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral egress rule descriptor.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import List, Optional, Union

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.exceptions import SchemaValidationError
from automojo.provisioning.model.cloud.networkprotocol import NetworkProtocol
from automojo.provisioning.model.cloud.cloudingressrule import (
    coerce_network_protocol
)
from automojo.provisioning.model.cloud.validators import (
    validate_cidr, validate_port_range
)


class CloudEgressRule(SchemaObject):
    """
        Venue-neutral security-group egress rule.

        Mirror of CloudIngressRule with destination fields in place of source
        fields.  A rule must specify at least one destination.
    """

    protocol = Field(str, required=True)
    from_port = Field(int, required=True)
    to_port = Field(int, required=True)
    dest_cidrs = Field(list, required=False, default=None)
    dest_sg = Field(str, required=False, default=None)
    description = Field(str, required=False, default="")

    def __init__(self, *, protocol: Union[NetworkProtocol, str],
                 from_port: int, to_port: int,
                 dest_cidrs: Optional[List[str]] = None,
                 dest_sg: Optional[str] = None,
                 description: str = "") -> None:
        """
            Construct a CloudEgressRule.

            :param protocol: Neutral network protocol; either a
                             NetworkProtocol member or its lowercase token
                             (tcp, udp, icmp, icmpv6, all).
            :param from_port: Lower port bound (inclusive).
            :param to_port: Upper port bound (inclusive).
            :param dest_cidrs: Optional list of destination CIDR strings.
            :param dest_sg: Optional destination security group name.
            :param description: Free-form rule description.

            :raises: SchemaValidationError, SchemaSemanticError
        """
        effective_protocol = coerce_network_protocol(value=protocol)
        validate_port_range(from_port=from_port, to_port=to_port)

        effective_dest_cidrs = dest_cidrs if dest_cidrs is not None else []

        cidrs_provided = len(effective_dest_cidrs) > 0
        sg_provided = dest_sg is not None and len(dest_sg) > 0

        if not cidrs_provided and not sg_provided:
            err_msg_lines = ["Egress rule must specify a destination."]
            err_msg_lines.append("dest_cidrs must be non-empty or dest_sg must be set.")
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaValidationError(err_msg)

        for cidr in effective_dest_cidrs:
            validate_cidr(value=cidr)

        super().__init__(protocol=effective_protocol.value,
                         from_port=from_port, to_port=to_port,
                         dest_cidrs=effective_dest_cidrs, dest_sg=dest_sg,
                         description=description)
        return
