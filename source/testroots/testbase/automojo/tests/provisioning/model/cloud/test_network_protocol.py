"""
    .. module:: test_network_protocol
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: NetworkProtocol enum + ingress / egress rule coercion tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import unittest

from ccai.provisioning.model.exceptions import SchemaSemanticError
from ccai.provisioning.model.cloud.networkprotocol import NetworkProtocol
from ccai.provisioning.model.cloud.cloudingressrule import (
    CloudIngressRule, coerce_network_protocol
)
from ccai.provisioning.model.cloud.cloudegressrule import CloudEgressRule


class NetworkProtocolTests(unittest.TestCase):

    def test_members_carry_lowercase_tokens(self) -> None:
        self.assertEqual(NetworkProtocol.TCP.value, "tcp")
        self.assertEqual(NetworkProtocol.UDP.value, "udp")
        self.assertEqual(NetworkProtocol.ICMP.value, "icmp")
        self.assertEqual(NetworkProtocol.ICMPV6.value, "icmpv6")
        self.assertEqual(NetworkProtocol.ALL.value, "all")
        return

    def test_coerce_accepts_enum(self) -> None:
        resolved = coerce_network_protocol(value=NetworkProtocol.UDP)
        self.assertEqual(resolved, NetworkProtocol.UDP)
        return

    def test_coerce_accepts_string_case_insensitive(self) -> None:
        resolved = coerce_network_protocol(value="TCP")
        self.assertEqual(resolved, NetworkProtocol.TCP)
        resolved_mixed = coerce_network_protocol(value="  IcmpV6 ")
        self.assertEqual(resolved_mixed, NetworkProtocol.ICMPV6)
        return

    def test_coerce_rejects_unknown(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            coerce_network_protocol(value="sctp")
        return


class IngressRuleProtocolTests(unittest.TestCase):

    def test_accepts_string_protocol(self) -> None:
        rule = CloudIngressRule(protocol="tcp", from_port=22, to_port=22,
                                source_cidrs=["10.0.0.0/8"])
        self.assertEqual(rule.protocol, NetworkProtocol.TCP.value)
        return

    def test_accepts_enum_protocol(self) -> None:
        rule = CloudIngressRule(protocol=NetworkProtocol.ALL,
                                from_port=0, to_port=65535,
                                source_cidrs=["0.0.0.0/0"])
        self.assertEqual(rule.protocol, NetworkProtocol.ALL.value)
        return

    def test_rejects_unknown_protocol(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            CloudIngressRule(protocol="bogus", from_port=22, to_port=22,
                             source_cidrs=["10.0.0.0/8"])
        return


class EgressRuleProtocolTests(unittest.TestCase):

    def test_accepts_string_protocol(self) -> None:
        rule = CloudEgressRule(protocol="udp", from_port=53, to_port=53,
                               dest_cidrs=["0.0.0.0/0"])
        self.assertEqual(rule.protocol, NetworkProtocol.UDP.value)
        return

    def test_accepts_enum_protocol(self) -> None:
        rule = CloudEgressRule(protocol=NetworkProtocol.ICMPV6,
                               from_port=0, to_port=0,
                               dest_cidrs=["::/0"])
        self.assertEqual(rule.protocol, NetworkProtocol.ICMPV6.value)
        return

    def test_rejects_unknown_protocol(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            CloudEgressRule(protocol="xyz", from_port=22, to_port=22,
                            dest_cidrs=["10.0.0.0/8"])
        return


if __name__ == "__main__":
    unittest.main()
