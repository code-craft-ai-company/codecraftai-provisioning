"""
    .. module:: cloudacceleratorcatalog
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Loader + lookup for the neutral-name → venue-SKU accelerator catalog.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os
import threading

from typing import Any, Dict, List, Optional

import yaml

from automojo.errors.exceptions import ConfigurationError

from automojo.provisioning.model.exceptions import (
    SchemaSemanticError, SchemaValidationError
)
from automojo.provisioning.model.cloud.cloudacceleratorcatalogentry import (
    CloudAcceleratorCatalogEntry
)


_DEFAULT_CATALOG_FILENAME = "accelerators.yaml"

_ENV_OVERRIDE = "AUTOMOJO_ACCELERATOR_CATALOG"

_LINE_KEY = "__line__"


class _LineMarkingSafeLoader(yaml.SafeLoader):
    """
        A SafeLoader variant that records the 1-based source line of every
        mapping node under the ``__line__`` key so that load-time catalog
        errors can point at the offending YAML line.
    """


def _construct_mapping_with_line(loader: "_LineMarkingSafeLoader",
                                 node: yaml.MappingNode) -> Dict[str, Any]:
    """
        Construct a mapping and inject the source line number.

        :param loader: The active YAML loader.
        :param node: The mapping node being constructed.

        :returns: The constructed mapping with a ``__line__`` entry.
    """
    mapping = loader.construct_mapping(node, deep=True)
    mapping[_LINE_KEY] = node.start_mark.line + 1
    rtnval = mapping
    return rtnval


_LineMarkingSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_with_line
)


def _strip_line_marks(value: Any) -> Any:
    """
        Recursively remove injected ``__line__`` keys from a loaded document.

        :param value: A loaded YAML value (dict, list, or scalar).

        :returns: The same value with all ``__line__`` keys removed.
    """
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for key, item in value.items():
            if key == _LINE_KEY:
                continue
            cleaned[key] = _strip_line_marks(item)
        rtnval: Any = cleaned
    elif isinstance(value, list):
        rtnval = [_strip_line_marks(item) for item in value]
    else:
        rtnval = value
    return rtnval


class CloudAcceleratorCatalog:
    """
        Immutable in-memory catalog of accelerator entries.

        Built once from a YAML file and indexed both forward (neutral_name →
        venue → SKU) and reverse (venue → SKU → neutral_name).  Injectivity per
        venue is enforced at load time.
    """

    def __init__(self, *, entries: List[CloudAcceleratorCatalogEntry]) -> None:
        """
            Construct from an already-validated list of entries.

            :param entries: Catalog entry list.

            :raises: ConfigurationError on duplicate neutral_name or per-venue
                     (sku → neutral_name) collision.
        """
        self._entries: List[CloudAcceleratorCatalogEntry] = list(entries)
        self._by_name: Dict[str, CloudAcceleratorCatalogEntry] = {}
        self._reverse: Dict[str, Dict[str, str]] = {}

        self._build_indexes()
        return

    def _build_indexes(self) -> None:
        """
            Build forward + reverse indexes and enforce uniqueness invariants.

            :raises: ConfigurationError
        """
        for entry in self._entries:
            if entry.neutral_name in self._by_name:
                err_msg_lines = ["Duplicate neutral_name in accelerator catalog."]
                err_msg_lines.append("NAME: {}".format(entry.neutral_name))
                err_msg = os.linesep.join(err_msg_lines)
                raise ConfigurationError(err_msg)
            self._by_name[entry.neutral_name] = entry

            for venue, sku in entry.venue_skus.items():
                venue_map = self._reverse.setdefault(venue, {})
                if sku in venue_map:
                    existing = venue_map[sku]
                    err_msg_lines = [
                        "Accelerator catalog collision: two neutral_names "
                        "map to the same (venue, sku)."
                    ]
                    err_msg_lines.append("VENUE: {}".format(venue))
                    err_msg_lines.append("SKU: {}".format(sku))
                    err_msg_lines.append(
                        "NAMES: {!r} and {!r}".format(existing, entry.neutral_name)
                    )
                    err_msg = os.linesep.join(err_msg_lines)
                    raise ConfigurationError(err_msg)
                venue_map[sku] = entry.neutral_name
        return

    @classmethod
    def from_path(cls, *, path: str) -> "CloudAcceleratorCatalog":
        """
            Load a catalog from a YAML file path.

            :param path: Filesystem path to the YAML file.

            :returns: A constructed CloudAcceleratorCatalog.
            :raises: ConfigurationError
        """
        if path is None or len(path) == 0:
            raise ConfigurationError("catalog path must not be empty.")

        if not os.path.exists(path):
            raise ConfigurationError(
                "Accelerator catalog file not found: {!r}".format(path)
            )

        with open(path, "r", encoding="utf-8") as fh:
            try:
                raw_document = yaml.load(fh, Loader=_LineMarkingSafeLoader)
            except yaml.YAMLError as xcpt:
                err_msg_lines = ["Malformed YAML in accelerator catalog file."]
                err_msg_lines.append("PATH: {}".format(path))
                problem_mark = getattr(xcpt, "problem_mark", None)
                if problem_mark is not None:
                    err_msg_lines.append(
                        "LINE: {}".format(problem_mark.line + 1)
                    )
                    err_msg_lines.append(
                        "COLUMN: {}".format(problem_mark.column + 1)
                    )
                err_msg_lines.append("CAUSE: {}".format(xcpt))
                err_msg = os.linesep.join(err_msg_lines)
                raise ConfigurationError(err_msg) from None

        if not isinstance(raw_document, dict):
            raise ConfigurationError(
                "Accelerator catalog YAML root must be a mapping."
            )

        entries_payload = raw_document.get("entries", None)
        if entries_payload is None or not isinstance(entries_payload, list):
            raise ConfigurationError(
                "Accelerator catalog YAML must define an 'entries' list."
            )

        built_entries: List[CloudAcceleratorCatalogEntry] = []
        for index, entry_payload in enumerate(entries_payload):
            if not isinstance(entry_payload, dict):
                raise ConfigurationError(
                    "Accelerator catalog entry #{} is not a mapping.".format(index)
                )

            entry_line = entry_payload.get(_LINE_KEY, None)
            clean_payload = _strip_line_marks(entry_payload)

            try:
                entry = CloudAcceleratorCatalogEntry.from_dict(clean_payload)
            except (SchemaValidationError, TypeError,
                    KeyError, ValueError) as xcpt:
                err_msg_lines = ["Invalid accelerator catalog entry."]
                err_msg_lines.append("PATH: {}".format(path))
                err_msg_lines.append("INDEX: {}".format(index))
                if entry_line is not None:
                    err_msg_lines.append("LINE: {}".format(entry_line))
                err_msg_lines.append("PAYLOAD: {!r}".format(clean_payload))
                err_msg_lines.append("CAUSE: {}".format(xcpt))
                err_msg = os.linesep.join(err_msg_lines)
                raise ConfigurationError(err_msg) from None
            built_entries.append(entry)

        rtnval = cls(entries=built_entries)
        return rtnval

    def entries(self) -> List[CloudAcceleratorCatalogEntry]:
        """
            Return the full list of catalog entries (defensive copy).

            :returns: A new list of entries.
        """
        rtnval = list(self._entries)
        return rtnval

    def resolve(self, *, neutral_name: str, venue: str) -> str:
        """
            Resolve a neutral name + venue to a venue-side SKU.

            :param neutral_name: Catalog-unique neutral name.
            :param venue: Provisioning venue name.

            :returns: The venue-side SKU string.
            :raises: SchemaSemanticError
        """
        entry = self._by_name.get(neutral_name, None)
        if entry is None:
            err_msg_lines = ["Unknown accelerator neutral_name."]
            err_msg_lines.append("REQUESTED: {!r}".format(neutral_name))
            err_msg_lines.append(
                "KNOWN: {}".format(", ".join(sorted(self._by_name.keys())))
            )
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        sku = entry.venue_skus.get(venue, None)
        if sku is None:
            err_msg_lines = [
                "Accelerator is not supported on the requested venue."
            ]
            err_msg_lines.append("NEUTRAL_NAME: {}".format(neutral_name))
            err_msg_lines.append("VENUE: {!r}".format(venue))
            err_msg_lines.append(
                "SUPPORTED_VENUES: {}".format(
                    ", ".join(sorted(entry.venue_skus.keys()))
                )
            )
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        return sku

    def neutral_name(self, *, venue: str, sku: str) -> str:
        """
            Inverse lookup: given a venue + venue-side SKU, return the neutral name.

            :param venue: Provisioning venue name.
            :param sku: Venue-side SKU string.

            :returns: The neutral name.
            :raises: SchemaSemanticError
        """
        venue_map = self._reverse.get(venue, None)
        if venue_map is None:
            err_msg_lines = ["No catalog entries for the requested venue."]
            err_msg_lines.append("VENUE: {!r}".format(venue))
            err_msg_lines.append(
                "KNOWN VENUES: {}".format(", ".join(sorted(self._reverse.keys())))
            )
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        name = venue_map.get(sku, None)
        if name is None:
            err_msg_lines = ["No accelerator catalog entry matches (venue, sku)."]
            err_msg_lines.append("VENUE: {}".format(venue))
            err_msg_lines.append("SKU: {!r}".format(sku))
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        return name

    def inverse_lookup(self, *, venue_sku: str, venue: str) -> str:
        """
            Alias of :meth:`neutral_name` matching the design spec wording.

            :param venue_sku: Venue-side SKU string.
            :param venue: Provisioning venue name.

            :returns: The neutral name.
        """
        rtnval = self.neutral_name(venue=venue, sku=venue_sku)
        return rtnval

    def supported_venues(self, *, neutral_name: str) -> List[str]:
        """
            Return the list of venues that publish a SKU for a neutral name.

            :param neutral_name: Catalog-unique neutral name.

            :returns: Sorted list of venue names.
            :raises: SchemaSemanticError
        """
        entry = self._by_name.get(neutral_name, None)
        if entry is None:
            err_msg_lines = ["Unknown accelerator neutral_name."]
            err_msg_lines.append("REQUESTED: {!r}".format(neutral_name))
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        rtnval = sorted(entry.venue_skus.keys())
        return rtnval


_singleton_lock = threading.Lock()
_singleton_catalog: Optional[CloudAcceleratorCatalog] = None


def _packaged_catalog_path() -> str:
    """
        Resolve the absolute path to the packaged accelerators.yaml file.

        :returns: Absolute file path.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    rtnval = os.path.join(here, _DEFAULT_CATALOG_FILENAME)
    return rtnval


def default_accelerator_catalog() -> CloudAcceleratorCatalog:
    """
        Return the process-wide default catalog singleton.

        Respects the ``AUTOMOJO_ACCELERATOR_CATALOG`` env var override; falls
        back to the catalog packaged alongside this module.

        :returns: A CloudAcceleratorCatalog instance.
    """
    global _singleton_catalog

    if _singleton_catalog is not None:
        rtnval = _singleton_catalog
        return rtnval

    with _singleton_lock:
        if _singleton_catalog is None:
            override = os.environ.get(_ENV_OVERRIDE, None)
            if override is not None and len(override) > 0:
                catalog_path = override
            else:
                catalog_path = _packaged_catalog_path()
            _singleton_catalog = CloudAcceleratorCatalog.from_path(
                path=catalog_path
            )

    rtnval = _singleton_catalog
    return rtnval


def reset_default_accelerator_catalog() -> None:
    """
        Reset the singleton; intended for test isolation only.
    """
    global _singleton_catalog
    with _singleton_lock:
        _singleton_catalog = None
    return
