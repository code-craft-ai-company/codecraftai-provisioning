"""
    .. module:: test_accelerator_catalog
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Catalog loader unit + property tests (totality / injectivity / round-trip).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os
import tempfile
import unittest

from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.errors.exceptions import ConfigurationError

from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.provisioning.model.cloud.cloudacceleratorcatalog import (
    CloudAcceleratorCatalog, default_accelerator_catalog,
    reset_default_accelerator_catalog
)
from ccai.provisioning.model.cloud.cloudacceleratorcatalogentry import (
    CloudAcceleratorCatalogEntry
)


def _build_pairs(catalog: CloudAcceleratorCatalog):
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
        reset_default_accelerator_catalog()
        self._catalog = default_accelerator_catalog()
        return

    def test_default_catalog_has_known_entries(self) -> None:
        names = {e.neutral_name for e in self._catalog.entries()}
        self.assertIn("H100_SXM", names)
        self.assertIn("A100_80G_SXM", names)
        self.assertIn("TPU_V5P", names)
        return

    def test_resolve_known_pair(self) -> None:
        sku = self._catalog.resolve(neutral_name="H100_SXM", venue="aws")
        self.assertEqual(sku, "p5.48xlarge")
        return

    def test_resolve_unknown_name_raises(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            self._catalog.resolve(neutral_name="DOES_NOT_EXIST", venue="aws")
        return

    def test_resolve_unsupported_venue_raises(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            self._catalog.resolve(neutral_name="TPU_V5P", venue="aws")
        return

    def test_supported_venues_returns_all_listed_venues(self) -> None:
        for entry in self._catalog.entries():
            expected = sorted(entry.venue_skus.keys())
            actual = self._catalog.supported_venues(
                neutral_name=entry.neutral_name
            )
            self.assertEqual(actual, expected)
        with self.assertRaises(SchemaSemanticError):
            self._catalog.supported_venues(neutral_name="DOES_NOT_EXIST")
        return

    def test_load_error_includes_line_number(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            yaml_path = os.path.join(td, "bad-entry.yaml")
            content = (
                "version: 1\n"
                "entries:\n"
                "  - neutral_name: GOOD\n"
                "    kind: GPU\n"
                "    memory_gb: 80\n"
                "    interconnect: NONE\n"
                "    venue_skus: {aws: good-sku}\n"
                "  - kind: GPU\n"
                "    memory_gb: 40\n"
                "    interconnect: NONE\n"
                "    venue_skus: {aws: bad-sku}\n"
            )
            with open(yaml_path, "w") as fh:
                fh.write(content)
            with self.assertRaises(ConfigurationError) as ctx:
                CloudAcceleratorCatalog.from_path(path=yaml_path)
            self.assertIn("LINE:", str(ctx.exception))
        return

    def test_load_rejects_sku_collision(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            yaml_path = os.path.join(td, "bad.yaml")
            content = (
                "version: 1\n"
                "entries:\n"
                "  - neutral_name: A\n"
                "    kind: GPU\n"
                "    memory_gb: 80\n"
                "    interconnect: NONE\n"
                "    venue_skus: {aws: same-sku}\n"
                "  - neutral_name: B\n"
                "    kind: GPU\n"
                "    memory_gb: 80\n"
                "    interconnect: NONE\n"
                "    venue_skus: {aws: same-sku}\n"
            )
            with open(yaml_path, "w") as fh:
                fh.write(content)
            with self.assertRaises(ConfigurationError):
                CloudAcceleratorCatalog.from_path(path=yaml_path)
        return

    def test_load_rejects_malformed_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            yaml_path = os.path.join(td, "bad.yaml")
            with open(yaml_path, "w") as fh:
                fh.write("entries: [: : : :]\n")
            with self.assertRaises(ConfigurationError):
                CloudAcceleratorCatalog.from_path(path=yaml_path)
        return

    def test_env_override_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            yaml_path = os.path.join(td, "override.yaml")
            content = (
                "version: 1\n"
                "entries:\n"
                "  - neutral_name: ONLY\n"
                "    kind: GPU\n"
                "    memory_gb: 40\n"
                "    interconnect: NONE\n"
                "    venue_skus: {aws: only-sku}\n"
            )
            with open(yaml_path, "w") as fh:
                fh.write(content)
            os.environ["CCAI_ACCELERATOR_CATALOG"] = yaml_path
            try:
                reset_default_accelerator_catalog()
                cat = default_accelerator_catalog()
                names = [e.neutral_name for e in cat.entries()]
                self.assertEqual(names, ["ONLY"])
            finally:
                del os.environ["CCAI_ACCELERATOR_CATALOG"]
                reset_default_accelerator_catalog()
        return


class CatalogPropertyTests(unittest.TestCase):

    def setUp(self) -> None:
        reset_default_accelerator_catalog()
        self._catalog = default_accelerator_catalog()
        self._pairs = _build_pairs(self._catalog)
        return

    def test_property_totality(self) -> None:
        for entry, venue in self._pairs:
            expected = entry.venue_skus[venue]
            actual = self._catalog.resolve(neutral_name=entry.neutral_name,
                                           venue=venue)
            self.assertEqual(actual, expected)
        return

    def test_property_round_trip(self) -> None:
        for entry, venue in self._pairs:
            sku = self._catalog.resolve(neutral_name=entry.neutral_name,
                                        venue=venue)
            name_back = self._catalog.inverse_lookup(venue_sku=sku,
                                                    venue=venue)
            self.assertEqual(name_back, entry.neutral_name)
        return

    def test_property_injectivity_per_venue(self) -> None:
        # No two neutral names map to the same SKU within one venue.
        per_venue: dict = {}
        for entry in self._catalog.entries():
            for venue, sku in entry.venue_skus.items():
                key = (venue, sku)
                if key in per_venue:
                    self.fail(
                        "SKU collision: ({}, {}) used by {!r} and {!r}".format(
                            venue, sku, per_venue[key], entry.neutral_name
                        )
                    )
                per_venue[key] = entry.neutral_name
        return

    @given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_",
                   min_size=1, max_size=12),
           st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
                   min_size=1, max_size=12), constraints={"max_examples": 30})
    def test_property_unknown_rejection(self, neutral_name, venue) -> None:
        known_names = {e.neutral_name for e in self._catalog.entries()}
        if neutral_name in known_names:
            return  # generated value happens to match a known catalog entry
        with self.assertRaises(SchemaSemanticError):
            self._catalog.resolve(neutral_name=neutral_name, venue=venue)
        return


if __name__ == "__main__":
    unittest.main()
