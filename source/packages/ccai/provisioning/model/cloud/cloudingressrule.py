"""
    .. module:: cloudingressrule
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral ingress rule descriptor.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import List, Optional, Union

from ccai.interfaces.schemaobject import SchemaObject
from ccai.interfaces.schemafield import Field

from ccai.interfaces.schemavalidationerror import SchemaValidationError
from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.provisioning.model.cloud.networkprotocol import NetworkProtocol
from ccai.interfaces.schemavalidators import (
    validate_cidr, validate_port_range
)


def coerce_network_protocol(*, value: Union[NetworkProtocol, str]
                            ) -> NetworkProtocol:
    """
        Coerce an enum-or-string value into a NetworkProtocol member.

        :param value: A NetworkProtocol member or its string token.

        :returns: The resolved NetworkProtocol member.
        :raises: SchemaSemanticError
    """
    if isinstance(value, NetworkProtocol):
        rtnval = value
        return rtnval

    if isinstance(value, str):
        normalized = value.strip().lower()
        for member in NetworkProtocol:
            if member.value == normalized:
                rtnval = member
                return rtnval

    supported = [member.value for member in NetworkProtocol]
    err_msg_lines = ["Unknown network protocol."]
    err_msg_lines.append("VALUE: {!r}".format(value))
    err_msg_lines.append("SUPPORTED: {}".format(", ".join(supported)))
    err_msg = os.linesep.join(err_msg_lines)
    raise SchemaSemanticError(err_msg)


class CloudIngressRule(SchemaObject):
    """
        Venue-neutral security-group ingress rule.

        A rule must specify at least one source (CIDR list or source security
        group).  Port range must be monotonic and bounded to 0..65535.
    """

    protocol = Field(str, required=True)
    from_port = Field(int, required=True)
    to_port = Field(int, required=True)
    source_cidrs = Field(list, required=False, default=None)
    source_sg = Field(str, required=False, default=None)
    description = Field(str, required=False, default="")

    def __init__(self, *, protocol: Union[NetworkProtocol, str],
                 from_port: int, to_port: int,
                 source_cidrs: Optional[List[str]] = None,
                 source_sg: Optional[str] = None,
                 description: str = "") -> None:
        """
            Construct a CloudIngressRule.

            :param protocol: Neutral network protocol; either a
                             NetworkProtocol member or its lowercase token
                             (tcp, udp, icmp, icmpv6, all).
            :param from_port: Lower port bound (inclusive).
            :param to_port: Upper port bound (inclusive).
            :param source_cidrs: Optional list of source CIDR strings.
            :param source_sg: Optional source security group name.
            :param description: Free-form rule description.

            :raises: SchemaValidationError, SchemaSemanticError
        """
        effective_protocol = coerce_network_protocol(value=protocol)
        validate_port_range(from_port=from_port, to_port=to_port)

        effective_source_cidrs = source_cidrs if source_cidrs is not None else []

        cidrs_provided = len(effective_source_cidrs) > 0
        sg_provided = source_sg is not None and len(source_sg) > 0

        if not cidrs_provided and not sg_provided:
            err_msg_lines = ["Ingress rule must specify a source."]
            err_msg_lines.append("source_cidrs must be non-empty or source_sg must be set.")
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaValidationError(err_msg)

        for cidr in effective_source_cidrs:
            validate_cidr(value=cidr)

        super().__init__(protocol=effective_protocol.value,
                         from_port=from_port, to_port=to_port,
                         source_cidrs=effective_source_cidrs, source_sg=source_sg,
                         description=description)
        return
