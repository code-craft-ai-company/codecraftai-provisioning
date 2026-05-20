"""
    .. module:: cloudingressrule
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral ingress rule descriptor.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import List, Optional

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.exceptions import SchemaValidationError
from automojo.provisioning.model.cloud.validators import (
    validate_cidr, validate_port_range, validate_protocol
)


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

    def __init__(self, *, protocol: str, from_port: int, to_port: int,
                 source_cidrs: Optional[List[str]] = None,
                 source_sg: Optional[str] = None,
                 description: str = "") -> None:
        """
            Construct a CloudIngressRule.

            :param protocol: One of tcp, udp, icmp, all.
            :param from_port: Lower port bound (inclusive).
            :param to_port: Upper port bound (inclusive).
            :param source_cidrs: Optional list of source CIDR strings.
            :param source_sg: Optional source security group name.
            :param description: Free-form rule description.

            :raises: SchemaValidationError
        """
        validate_protocol(protocol=protocol)
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

        super().__init__(protocol=protocol, from_port=from_port, to_port=to_port,
                         source_cidrs=effective_source_cidrs, source_sg=source_sg,
                         description=description)
        return
