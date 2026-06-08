"""
    .. module:: test_instance_size_resolver_wiring
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Per-venue resolver tests proving neutral-token translation and
               native-string passthrough.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import unittest

from ccai.provisioning.model.cloud.cloudinstancesizecatalog import (
    reset_default_instance_size_catalog
)
from ccai.provisioning.venues.hetzner.hetznerresolver import HetznerResolver
from ccai.provisioning.venues.linode.linoderesolver import LinodeResolver
from ccai.provisioning.venues.digitalocean.doresolver import DoResolver


class ResolverWiringTests(unittest.TestCase):

    def setUp(self) -> None:
        reset_default_instance_size_catalog()
        return

    def test_hetzner_translates_neutral_token(self) -> None:
        native = HetznerResolver.size_to_type(size_hint="general.large")
        self.assertEqual(native, "cx42")
        return

    def test_hetzner_passes_native_string_through(self) -> None:
        native = HetznerResolver.size_to_type(size_hint="cx22")
        self.assertEqual(native, "cx22")
        return

    def test_linode_translates_neutral_token(self) -> None:
        resolver = LinodeResolver()
        native = resolver.size_to_type(size_hint="general.large")
        self.assertEqual(native, "g6-standard-6")
        return

    def test_digitalocean_translates_neutral_token(self) -> None:
        resolver = DoResolver()
        native = resolver.size_to_slug(size_hint="general.large")
        self.assertEqual(native, "s-4vcpu-8gb")
        return

    def test_digitalocean_passes_native_string_through(self) -> None:
        resolver = DoResolver()
        native = resolver.size_to_slug(size_hint="s-2vcpu-4gb")
        self.assertEqual(native, "s-2vcpu-4gb")
        return


if __name__ == "__main__":
    unittest.main()
