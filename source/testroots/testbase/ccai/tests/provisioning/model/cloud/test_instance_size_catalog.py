"""
    .. module:: test_instance_size_catalog
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Instance-size catalog loader unit + property tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os
import tempfile
import unittest

from hypothesis import given, settings, strategies as st

from ccai.errors.exceptions import ConfigurationError

from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.provisioning.model.cloud.cloudinstancesizecatalog import (
    CloudInstanceSizeCatalog, default_instance_size_catalog,
    reset_default_instance_size_catalog
)


def _build_pairs(catalog: CloudInstanceSizeCatalog):
    """
        Build the full set of (entry, venue) pairs from the catalog.
    """
    rtnval = []
    for entry in catalog.entries():
        for venue in entry.venue_skus.keys():
            rtnval.append((entry, venue))
    return rtnval


class CatalogLoaderTests(unittest.TestCase):

    def setUp(self) -> None:
        reset_default_instance_size_catalog()
        self._catalog = default_instance_size_catalog()
        return

    def test_default_catalog_has_known_tokens(self) -> None:
        tokens = {e.token for e in self._catalog.entries()}
        self.assertIn("general.small", tokens)
        self.assertIn("general.large", tokens)
        self.assertIn("compute.xlarge", tokens)
        self.assertIn("memory.large", tokens)
        return

    def test_resolve_known_pair(self) -> None:
        sku = self._catalog.resolve(token="general.large", venue="aws")
        self.assertEqual(sku, "m5.xlarge")
        return

    def test_resolve_unknown_token_returns_none(self) -> None:
        # Power-user passthrough: an unrecognised token resolves to None so the
        # caller treats it as an already-native venue size string.
        native = self._catalog.resolve(token="t3.medium", venue="aws")
        self.assertIsNone(native)
        return

    def test_resolve_unsupported_venue_raises(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            self._catalog.resolve(token="general.large", venue="vsphere")
        return

    def test_supported_venues_returns_all_listed_venues(self) -> None:
        for entry in self._catalog.entries():
            expected = sorted(entry.venue_skus.keys())
            actual = self._catalog.supported_venues(token=entry.token)
            self.assertEqual(actual, expected)
        with self.assertRaises(SchemaSemanticError):
            self._catalog.supported_venues(token="does.not.exist")
        return

    def test_vcpu_and_memory_accessors(self) -> None:
        self.assertEqual(self._catalog.vcpu(token="general.large"), 4)
        self.assertEqual(self._catalog.memory_gb(token="general.large"), 16)
        with self.assertRaises(SchemaSemanticError):
            self._catalog.vcpu(token="does.not.exist")
        with self.assertRaises(SchemaSemanticError):
            self._catalog.memory_gb(token="does.not.exist")
        return

    def test_is_known_token(self) -> None:
        self.assertTrue(self._catalog.is_known_token(token="general.large"))
        self.assertFalse(self._catalog.is_known_token(token="t3.medium"))
        return

    def test_load_error_includes_line_number(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            yaml_path = os.path.join(td, "bad-entry.yaml")
            content = (
                "version: 1\n"
                "entries:\n"
                "  - token: general.small\n"
                "    vcpu: 2\n"
                "    memory_gb: 4\n"
                "    venue_skus: {aws: good-sku}\n"
                "  - vcpu: 4\n"
                "    memory_gb: 8\n"
                "    venue_skus: {aws: bad-sku}\n"
            )
            with open(yaml_path, "w") as fh:
                fh.write(content)
            with self.assertRaises(ConfigurationError) as ctx:
                CloudInstanceSizeCatalog.from_path(path=yaml_path)
            self.assertIn("LINE:", str(ctx.exception))
        return

    def test_load_rejects_sku_collision(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            yaml_path = os.path.join(td, "bad.yaml")
            content = (
                "version: 1\n"
                "entries:\n"
                "  - token: general.small\n"
                "    vcpu: 2\n"
                "    memory_gb: 4\n"
                "    venue_skus: {aws: same-sku}\n"
                "  - token: general.medium\n"
                "    vcpu: 2\n"
                "    memory_gb: 8\n"
                "    venue_skus: {aws: same-sku}\n"
            )
            with open(yaml_path, "w") as fh:
                fh.write(content)
            with self.assertRaises(ConfigurationError):
                CloudInstanceSizeCatalog.from_path(path=yaml_path)
        return

    def test_load_rejects_malformed_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            yaml_path = os.path.join(td, "bad.yaml")
            with open(yaml_path, "w") as fh:
                fh.write("entries: [: : : :]\n")
            with self.assertRaises(ConfigurationError):
                CloudInstanceSizeCatalog.from_path(path=yaml_path)
        return

    def test_env_override_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            yaml_path = os.path.join(td, "override.yaml")
            content = (
                "version: 1\n"
                "entries:\n"
                "  - token: general.small\n"
                "    vcpu: 2\n"
                "    memory_gb: 4\n"
                "    venue_skus: {aws: only-sku}\n"
            )
            with open(yaml_path, "w") as fh:
                fh.write(content)
            os.environ["CCAI_INSTANCE_SIZE_CATALOG"] = yaml_path
            try:
                reset_default_instance_size_catalog()
                cat = default_instance_size_catalog()
                tokens = [e.token for e in cat.entries()]
                self.assertEqual(tokens, ["general.small"])
            finally:
                del os.environ["CCAI_INSTANCE_SIZE_CATALOG"]
                reset_default_instance_size_catalog()
        return


class CatalogPropertyTests(unittest.TestCase):

    def setUp(self) -> None:
        reset_default_instance_size_catalog()
        self._catalog = default_instance_size_catalog()
        self._pairs = _build_pairs(self._catalog)
        return

    def test_property_totality(self) -> None:
        # Every token resolves on every venue it lists.
        for entry, venue in self._pairs:
            expected = entry.venue_skus[venue]
            actual = self._catalog.resolve(token=entry.token, venue=venue)
            self.assertEqual(actual, expected)
        return

    def test_property_round_trip(self) -> None:
        for entry, venue in self._pairs:
            sku = self._catalog.resolve(token=entry.token, venue=venue)
            token_back = self._catalog.inverse_lookup(venue_sku=sku,
                                                      venue=venue)
            self.assertEqual(token_back, entry.token)
        return

    def test_property_injectivity_per_venue(self) -> None:
        # No two tokens map to the same SKU within one venue.
        per_venue: dict = {}
        for entry in self._catalog.entries():
            for venue, sku in entry.venue_skus.items():
                key = (venue, sku)
                if key in per_venue:
                    self.fail(
                        "SKU collision: ({}, {}) used by {!r} and {!r}".format(
                            venue, sku, per_venue[key], entry.token
                        )
                    )
                per_venue[key] = entry.token
        return

    @settings(max_examples=30, deadline=None)
    @given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
                   min_size=1, max_size=12),
           st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
                   min_size=1, max_size=12))
    def test_property_unknown_token_returns_none(self, token, venue) -> None:
        known_tokens = {e.token for e in self._catalog.entries()}
        if token in known_tokens:
            return  # generated value happens to match a known token
        native = self._catalog.resolve(token=token, venue=venue)
        self.assertIsNone(native)
        return


if __name__ == "__main__":
    unittest.main()
