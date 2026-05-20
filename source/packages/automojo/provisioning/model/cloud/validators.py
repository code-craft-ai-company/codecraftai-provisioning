"""
    .. module:: validators
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shape-only validation helpers shared by cloud model classes.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import ipaddress
import os

from typing import Optional

from automojo.provisioning.model.exceptions import SchemaValidationError


_DEFAULT_NAME_MAX_LEN = 63

_SUPPORTED_PROTOCOLS = ("tcp", "udp", "icmp", "all")

_SUPPORTED_DNS_RECORD_TYPES = ("A", "AAAA", "CNAME", "TXT", "MX", "SRV")


def validate_cidr(*, value: str) -> None:
    """
        Validate that the supplied value is a parseable IPv4 or IPv6 CIDR.

        :param value: The CIDR string to validate.

        :raises: SchemaValidationError
    """
    if value is None:
        raise SchemaValidationError("CIDR value must not be None.")

    if not isinstance(value, str):
        raise SchemaValidationError("CIDR value must be a string.")

    if len(value) == 0:
        raise SchemaValidationError("CIDR value must not be empty.")

    try:
        ipaddress.ip_network(value, strict=False)
    except ValueError as xcpt:
        err_msg_lines = ["Malformed CIDR value."]
        err_msg_lines.append("VALUE: {!r}".format(value))
        err_msg_lines.append("CAUSE: {}".format(xcpt))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaValidationError(err_msg) from None

    return


def validate_name(*, value: str, max_len: int = _DEFAULT_NAME_MAX_LEN) -> None:
    """
        Validate that a resource name is non-empty and below the venue-neutral length.

        :param value: The name to validate.
        :param max_len: Maximum permitted length (default 63).

        :raises: SchemaValidationError
    """
    if value is None:
        raise SchemaValidationError("Name value must not be None.")

    if not isinstance(value, str):
        raise SchemaValidationError("Name value must be a string.")

    if len(value) == 0:
        raise SchemaValidationError("Name value must not be empty.")

    if len(value) > max_len:
        err_msg_lines = ["Name value exceeds venue-neutral length limit."]
        err_msg_lines.append("LIMIT: {}".format(max_len))
        err_msg_lines.append("ACTUAL: {}".format(len(value)))
        err_msg_lines.append("VALUE: {!r}".format(value))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaValidationError(err_msg)

    return


def validate_port_range(*, from_port: int, to_port: int) -> None:
    """
        Validate that the supplied port range is monotonic and within 0..65535.

        :param from_port: Lower port bound (inclusive).
        :param to_port: Upper port bound (inclusive).

        :raises: SchemaValidationError
    """
    if from_port is None:
        raise SchemaValidationError("from_port must not be None.")

    if to_port is None:
        raise SchemaValidationError("to_port must not be None.")

    if not isinstance(from_port, int):
        raise SchemaValidationError("from_port must be an int.")

    if not isinstance(to_port, int):
        raise SchemaValidationError("to_port must be an int.")

    if from_port < 0 or from_port > 65535:
        raise SchemaValidationError(
            "from_port must be in 0..65535, got {}".format(from_port)
        )

    if to_port < 0 or to_port > 65535:
        raise SchemaValidationError(
            "to_port must be in 0..65535, got {}".format(to_port)
        )

    if from_port > to_port:
        err_msg_lines = ["Port range is inverted."]
        err_msg_lines.append("FROM: {}".format(from_port))
        err_msg_lines.append("TO: {}".format(to_port))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaValidationError(err_msg)

    return


def validate_protocol(*, protocol: str) -> None:
    """
        Validate that a security-rule protocol is one of the supported neutral values.

        :param protocol: The protocol name.

        :raises: SchemaValidationError
    """
    if protocol is None:
        raise SchemaValidationError("protocol must not be None.")

    if not isinstance(protocol, str):
        raise SchemaValidationError("protocol must be a string.")

    if protocol not in _SUPPORTED_PROTOCOLS:
        err_msg_lines = ["Unsupported security-rule protocol."]
        err_msg_lines.append("SUPPORTED: {}".format(", ".join(_SUPPORTED_PROTOCOLS)))
        err_msg_lines.append("ACTUAL: {!r}".format(protocol))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaValidationError(err_msg)

    return


def validate_dns_record_type(*, record_type: str) -> None:
    """
        Validate that a DNS record type is in the supported set.

        :param record_type: The DNS record type name.

        :raises: SchemaValidationError
    """
    if record_type is None:
        raise SchemaValidationError("record_type must not be None.")

    if record_type not in _SUPPORTED_DNS_RECORD_TYPES:
        err_msg_lines = ["Unsupported DNS record type."]
        err_msg_lines.append(
            "SUPPORTED: {}".format(", ".join(_SUPPORTED_DNS_RECORD_TYPES))
        )
        err_msg_lines.append("ACTUAL: {!r}".format(record_type))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaValidationError(err_msg)

    return


def validate_positive_int(*, value: int, field_name: str) -> None:
    """
        Validate that an integer field is strictly positive.

        :param value: The integer to check.
        :param field_name: The field name (used in error messages).

        :raises: SchemaValidationError
    """
    if value is None:
        raise SchemaValidationError("{} must not be None.".format(field_name))

    if not isinstance(value, int):
        raise SchemaValidationError(
            "{} must be an int, got {!r}".format(field_name, type(value).__name__)
        )

    if value <= 0:
        raise SchemaValidationError(
            "{} must be > 0, got {}".format(field_name, value)
        )

    return


def subnet_contained_in_network(*, subnet_cidr: str, network_cidr: str) -> bool:
    """
        Return True if the subnet CIDR is contained within the network CIDR.

        :param subnet_cidr: The candidate subnet CIDR string.
        :param network_cidr: The enclosing network CIDR string.

        :returns: True if contained.
    """
    sub = ipaddress.ip_network(subnet_cidr, strict=False)
    net = ipaddress.ip_network(network_cidr, strict=False)
    rtnval = sub.subnet_of(net)
    return rtnval


def cidrs_overlap(*, cidr_a: str, cidr_b: str) -> bool:
    """
        Return True if two CIDRs overlap.

        :param cidr_a: First CIDR.
        :param cidr_b: Second CIDR.

        :returns: True if the networks overlap.
    """
    a = ipaddress.ip_network(cidr_a, strict=False)
    b = ipaddress.ip_network(cidr_b, strict=False)
    rtnval = a.overlaps(b)
    return rtnval
