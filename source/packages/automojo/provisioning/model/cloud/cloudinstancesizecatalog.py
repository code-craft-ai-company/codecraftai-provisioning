"""
    .. module:: cloudinstancesizecatalog
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Loader + lookup for the neutral-token -> venue-SKU instance-size catalog.

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
from automojo.provisioning.model.cloud.cloudinstancesizecatalogentry import (
    CloudInstanceSizeCatalogEntry
)


_DEFAULT_CATALOG_FILENAME = "instancesizes.yaml"

_ENV_OVERRIDE = "AUTOMOJO_INSTANCE_SIZE_CATALOG"

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


class CloudInstanceSizeCatalog:
    """
        Immutable in-memory catalog of neutral instance-size entries.

        Built once from a YAML file and indexed both forward (token ->
        venue -> SKU) and reverse (venue -> SKU -> token).  Injectivity per
        venue is enforced at load time.
    """

    def __init__(self, *, entries: List[CloudInstanceSizeCatalogEntry]) -> None:
        """
            Construct from an already-validated list of entries.

            :param entries: Catalog entry list.

            :raises: ConfigurationError on duplicate token or per-venue
                     (sku -> token) collision.
        """
        self._entries: List[CloudInstanceSizeCatalogEntry] = list(entries)
        self._by_token: Dict[str, CloudInstanceSizeCatalogEntry] = {}
        self._reverse: Dict[str, Dict[str, str]] = {}

        self._build_indexes()
        return

    def _build_indexes(self) -> None:
        """
            Build forward + reverse indexes and enforce uniqueness invariants.

            :raises: ConfigurationError
        """
        for entry in self._entries:
            if entry.token in self._by_token:
                err_msg_lines = ["Duplicate token in instance-size catalog."]
                err_msg_lines.append("TOKEN: {}".format(entry.token))
                err_msg = os.linesep.join(err_msg_lines)
                raise ConfigurationError(err_msg)
            self._by_token[entry.token] = entry

            for venue, sku in entry.venue_skus.items():
                venue_map = self._reverse.setdefault(venue, {})
                if sku in venue_map:
                    existing = venue_map[sku]
                    err_msg_lines = [
                        "Instance-size catalog collision: two tokens "
                        "map to the same (venue, sku)."
                    ]
                    err_msg_lines.append("VENUE: {}".format(venue))
                    err_msg_lines.append("SKU: {}".format(sku))
                    err_msg_lines.append(
                        "TOKENS: {!r} and {!r}".format(existing, entry.token)
                    )
                    err_msg = os.linesep.join(err_msg_lines)
                    raise ConfigurationError(err_msg)
                venue_map[sku] = entry.token
        return

    @classmethod
    def from_path(cls, *, path: str) -> "CloudInstanceSizeCatalog":
        """
            Load a catalog from a YAML file path.

            :param path: Filesystem path to the YAML file.

            :returns: A constructed CloudInstanceSizeCatalog.
            :raises: ConfigurationError
        """
        if path is None or len(path) == 0:
            raise ConfigurationError("catalog path must not be empty.")

        if not os.path.exists(path):
            raise ConfigurationError(
                "Instance-size catalog file not found: {!r}".format(path)
            )

        with open(path, "r", encoding="utf-8") as fh:
            try:
                raw_document = yaml.load(fh, Loader=_LineMarkingSafeLoader)
            except yaml.YAMLError as xcpt:
                err_msg_lines = ["Malformed YAML in instance-size catalog file."]
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
                "Instance-size catalog YAML root must be a mapping."
            )

        entries_payload = raw_document.get("entries", None)
        if entries_payload is None or not isinstance(entries_payload, list):
            raise ConfigurationError(
                "Instance-size catalog YAML must define an 'entries' list."
            )

        built_entries: List[CloudInstanceSizeCatalogEntry] = []
        for index, entry_payload in enumerate(entries_payload):
            if not isinstance(entry_payload, dict):
                raise ConfigurationError(
                    "Instance-size catalog entry #{} is not a mapping.".format(
                        index
                    )
                )

            entry_line = entry_payload.get(_LINE_KEY, None)
            clean_payload = _strip_line_marks(entry_payload)

            try:
                entry = CloudInstanceSizeCatalogEntry.from_dict(clean_payload)
            except (SchemaValidationError, TypeError,
                    KeyError, ValueError) as xcpt:
                err_msg_lines = ["Invalid instance-size catalog entry."]
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

    def entries(self) -> List[CloudInstanceSizeCatalogEntry]:
        """
            Return the full list of catalog entries (defensive copy).

            :returns: A new list of entries.
        """
        rtnval = list(self._entries)
        return rtnval

    def is_known_token(self, *, token: str) -> bool:
        """
            Report whether a string is a recognised neutral size token.

            :param token: Candidate neutral token.

            :returns: ``True`` when the token names a catalog entry.
        """
        rtnval = token in self._by_token
        return rtnval

    def resolve(self, *, token: str, venue: str) -> Optional[str]:
        """
            Resolve a neutral size token + venue to a native SKU.

            When ``token`` is not a recognised neutral token, ``None`` is
            returned so that the caller can treat the string as an
            already-native venue size (the power-user passthrough).

            :param token: Candidate neutral size token.
            :param venue: Provisioning venue name.

            :returns: The native SKU string, or ``None`` when ``token`` is
                      not a recognised neutral token.
            :raises: SchemaSemanticError when the token is recognised but the
                     venue does not publish a SKU for it.
        """
        entry = self._by_token.get(token, None)
        if entry is None:
            rtnval: Optional[str] = None
            return rtnval

        sku = entry.venue_skus.get(venue, None)
        if sku is None:
            err_msg_lines = [
                "Instance size is not supported on the requested venue."
            ]
            err_msg_lines.append("TOKEN: {}".format(token))
            err_msg_lines.append("VENUE: {!r}".format(venue))
            err_msg_lines.append(
                "SUPPORTED_VENUES: {}".format(
                    ", ".join(sorted(entry.venue_skus.keys()))
                )
            )
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        rtnval = sku
        return rtnval

    def inverse_lookup(self, *, venue_sku: str, venue: str) -> str:
        """
            Inverse lookup: given a venue + native SKU, return the token.

            :param venue_sku: Native SKU string.
            :param venue: Provisioning venue name.

            :returns: The neutral size token.
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

        token = venue_map.get(venue_sku, None)
        if token is None:
            err_msg_lines = [
                "No instance-size catalog entry matches (venue, sku)."
            ]
            err_msg_lines.append("VENUE: {}".format(venue))
            err_msg_lines.append("SKU: {!r}".format(venue_sku))
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        rtnval = token
        return rtnval

    def supported_venues(self, *, token: str) -> List[str]:
        """
            Return the list of venues that publish a SKU for a token.

            :param token: Catalog-unique neutral size token.

            :returns: Sorted list of venue names.
            :raises: SchemaSemanticError
        """
        entry = self._by_token.get(token, None)
        if entry is None:
            err_msg_lines = ["Unknown instance-size token."]
            err_msg_lines.append("REQUESTED: {!r}".format(token))
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        rtnval = sorted(entry.venue_skus.keys())
        return rtnval

    def vcpu(self, *, token: str) -> int:
        """
            Return the neutral vCPU count for a token.

            :param token: Catalog-unique neutral size token.

            :returns: The vCPU count.
            :raises: SchemaSemanticError
        """
        entry = self._by_token.get(token, None)
        if entry is None:
            err_msg_lines = ["Unknown instance-size token."]
            err_msg_lines.append("REQUESTED: {!r}".format(token))
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        rtnval = entry.vcpu
        return rtnval

    def memory_gb(self, *, token: str) -> int:
        """
            Return the neutral RAM (in GB) for a token.

            :param token: Catalog-unique neutral size token.

            :returns: The RAM in GB.
            :raises: SchemaSemanticError
        """
        entry = self._by_token.get(token, None)
        if entry is None:
            err_msg_lines = ["Unknown instance-size token."]
            err_msg_lines.append("REQUESTED: {!r}".format(token))
            err_msg = os.linesep.join(err_msg_lines)
            raise SchemaSemanticError(err_msg)

        rtnval = entry.memory_gb
        return rtnval

    @classmethod
    def default(cls) -> "CloudInstanceSizeCatalog":
        """
            Return the process-wide default catalog singleton.

            :returns: A CloudInstanceSizeCatalog instance.
        """
        rtnval = default_instance_size_catalog()
        return rtnval


_singleton_lock = threading.Lock()
_singleton_catalog: Optional[CloudInstanceSizeCatalog] = None


def _packaged_catalog_path() -> str:
    """
        Resolve the absolute path to the packaged instancesizes.yaml file.

        :returns: Absolute file path.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    rtnval = os.path.join(here, _DEFAULT_CATALOG_FILENAME)
    return rtnval


def default_instance_size_catalog() -> CloudInstanceSizeCatalog:
    """
        Return the process-wide default catalog singleton.

        Respects the ``AUTOMOJO_INSTANCE_SIZE_CATALOG`` env var override;
        falls back to the catalog packaged alongside this module.

        :returns: A CloudInstanceSizeCatalog instance.
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
            _singleton_catalog = CloudInstanceSizeCatalog.from_path(
                path=catalog_path
            )

    rtnval = _singleton_catalog
    return rtnval


def reset_default_instance_size_catalog() -> None:
    """
        Reset the singleton; intended for test isolation only.
    """
    global _singleton_catalog
    with _singleton_lock:
        _singleton_catalog = None
    return
