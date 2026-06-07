"""
    .. module:: cloudloadbalancerlistener
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral typed load balancer listener descriptor.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Optional

from ccai.restclient.base.schemaobject import SchemaObject
from ccai.restclient.base.schemafield import Field

from ccai.provisioning.model.exceptions import SchemaValidationError


_SUPPORTED_PROTOCOLS = ("HTTP", "HTTPS", "TCP", "UDP")

_MIN_PORT = 1
_MAX_PORT = 65535


def _validate_port(*, value: int, field_name: str) -> None:
    """
        Validate that a port value is an integer within the legal range.

        :param value: The port value to validate.
        :param field_name: Name of the field for error reporting.

        :raises: SchemaValidationError
    """
    if value is None or not isinstance(value, int) or isinstance(value, bool):
        raise SchemaValidationError(
            "{} must be an integer.".format(field_name)
        )

    if value < _MIN_PORT or value > _MAX_PORT:
        err_msg_lines = ["Listener port out of range."]
        err_msg_lines.append("FIELD: {}".format(field_name))
        err_msg_lines.append("VALUE: {}".format(value))
        err_msg_lines.append(
            "RANGE: {}..{}".format(_MIN_PORT, _MAX_PORT)
        )
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaValidationError(err_msg)

    return


class CloudLoadBalancerListener(SchemaObject):
    """
        Venue-neutral typed load balancer listener descriptor.

        Pairs an LB-facing port with a backend target port and a protocol.
        HTTPS listeners may carry an optional TLS certificate reference.
    """

    protocol = Field(str, required=True)
    port = Field(int, required=True)
    target_port = Field(int, required=True)
    tls_certificate_ref = Field(str, required=False, default=None)

    def __init__(self, *, protocol: str, port: int, target_port: int,
                 tls_certificate_ref: Optional[str] = None) -> None:
        """
            Construct a CloudLoadBalancerListener.

            :param protocol: One of HTTP, HTTPS, TCP, UDP.
            :param port: The LB-facing listener port.
            :param target_port: The backend instance port.
            :param tls_certificate_ref: Optional TLS certificate reference.

            :raises: SchemaValidationError
        """
        if protocol is None or protocol not in _SUPPORTED_PROTOCOLS:
            err_msg_lines = ["Unsupported listener protocol."]
            err_msg_lines.append("VALUE: {!r}".format(protocol))
            err_msg_lines.append(
                "SUPPORTED: {}".format(", ".join(_SUPPORTED_PROTOCOLS))
            )
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaValidationError(err_msg)

        _validate_port(value=port, field_name="port")
        _validate_port(value=target_port, field_name="target_port")

        super().__init__(protocol=protocol, port=port,
                         target_port=target_port,
                         tls_certificate_ref=tls_certificate_ref)
        return
