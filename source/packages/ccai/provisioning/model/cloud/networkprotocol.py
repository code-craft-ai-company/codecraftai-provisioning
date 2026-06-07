"""
    .. module:: networkprotocol
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Enum describing the venue-neutral network protocol of a
               security-group rule.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from enum import Enum


class NetworkProtocol(str, Enum):
    """
        Venue-neutral network protocol for a security-group ingress / egress
        rule.

        - TCP: the Transmission Control Protocol.
        - UDP: the User Datagram Protocol.
        - ICMP: the Internet Control Message Protocol (IPv4).
        - ICMPV6: the Internet Control Message Protocol for IPv6.
        - ALL: every protocol; venues map this to their own wildcard token.
    """
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    ICMPV6 = "icmpv6"
    ALL = "all"
