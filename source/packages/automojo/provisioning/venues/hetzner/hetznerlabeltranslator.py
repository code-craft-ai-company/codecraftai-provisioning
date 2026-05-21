"""
    .. module:: hetznerlabeltranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Label round-trip helpers between neutral tag dicts and the
               Hetzner labels dict shape.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os
import re

from typing import Dict, Optional

from automojo.provisioning.venues.hetzner.hetznererrors import (
    HetznerValidationError
)


OWNER_LABEL_KEY = "automojo.owned-by"
OWNER_LABEL_VALUE = "automojo-provisioning"
RUN_ID_LABEL_KEY = "automojo.run-id"
RESOURCE_NAME_LABEL_KEY = "automojo.resource-name"
RESOURCE_KIND_LABEL_KEY = "automojo.resource-kind"

HETZNER_LABEL_PART_MAX = 63
HETZNER_LABEL_PREFIX_MAX = 253

# Name segment of a key or a value: alphanumeric on both ends, with
# dashes / underscores / dots permitted in the interior.
_NAME_PART = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$")
# Optional DNS-subdomain prefix on a key.
_PREFIX_PART = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$")


def _validate_label_key(*, key: str) -> None:
    """
        Validate a label key against Hetzner's character rules.

        A key may carry an optional ``prefix/`` DNS-subdomain segment
        before the name segment.

        :param key: The label key string.

        :raises: HetznerValidationError
    """
    if not isinstance(key, str):
        err_msg_lines = ["Hetzner label key must be a string."]
        err_msg_lines.append("KEY: {!r}".format(key))
        err_msg = os.linesep.join(err_msg_lines)
        raise HetznerValidationError(err_msg)

    if len(key) == 0:
        raise HetznerValidationError("Hetzner label key must not be empty.")

    prefix: Optional[str] = None
    name = key
    if "/" in key:
        slash_index = key.index("/")
        prefix = key[:slash_index]
        name = key[slash_index + 1:]

    if prefix is not None:
        if len(prefix) == 0 or len(prefix) > HETZNER_LABEL_PREFIX_MAX:
            err_msg_lines = ["Hetzner label key prefix length is invalid."]
            err_msg_lines.append("KEY: {!r}".format(key))
            err_msg = os.linesep.join(err_msg_lines)
            raise HetznerValidationError(err_msg)
        if _PREFIX_PART.match(prefix) is None:
            err_msg_lines = ["Hetzner label key prefix has invalid chars."]
            err_msg_lines.append("KEY: {!r}".format(key))
            err_msg = os.linesep.join(err_msg_lines)
            raise HetznerValidationError(err_msg)

    if len(name) == 0 or len(name) > HETZNER_LABEL_PART_MAX:
        err_msg_lines = ["Hetzner label key name length is invalid."]
        err_msg_lines.append("KEY: {!r}".format(key))
        err_msg = os.linesep.join(err_msg_lines)
        raise HetznerValidationError(err_msg)

    if _NAME_PART.match(name) is None:
        err_msg_lines = ["Hetzner label key name has invalid characters."]
        err_msg_lines.append("KEY: {!r}".format(key))
        err_msg = os.linesep.join(err_msg_lines)
        raise HetznerValidationError(err_msg)

    return


def _validate_label_value(*, key: str, value: str) -> None:
    """
        Validate a label value against Hetzner's character rules.

        :param key: The owning label key (for error context).
        :param value: The label value string.

        :raises: HetznerValidationError
    """
    if not isinstance(value, str):
        err_msg_lines = ["Hetzner label value must be a string."]
        err_msg_lines.append("KEY: {!r}".format(key))
        err_msg_lines.append("VALUE: {!r}".format(value))
        err_msg = os.linesep.join(err_msg_lines)
        raise HetznerValidationError(err_msg)

    if len(value) == 0:
        # Hetzner permits an empty value.
        return

    if len(value) > HETZNER_LABEL_PART_MAX:
        err_msg_lines = ["Hetzner label value exceeds 63-char limit."]
        err_msg_lines.append("KEY: {}".format(key))
        err_msg_lines.append("LENGTH: {}".format(len(value)))
        err_msg = os.linesep.join(err_msg_lines)
        raise HetznerValidationError(err_msg)

    if _NAME_PART.match(value) is None:
        err_msg_lines = ["Hetzner label value has invalid characters."]
        err_msg_lines.append("KEY: {}".format(key))
        err_msg_lines.append("VALUE: {!r}".format(value))
        err_msg = os.linesep.join(err_msg_lines)
        raise HetznerValidationError(err_msg)

    return


class HetznerLabelTranslator:
    """
        Translator between a neutral flat tag dict and the Hetzner
        labels dict (a flat ``{key: value}`` mapping).

        Conformant inputs round-trip as identity:
        ``from_hetzner(to_hetzner(x)) == x`` after key-sorting.
    """

    @classmethod
    def to_hetzner(cls, *,
                   neutral_tags: Optional[Dict[str, str]]
                   ) -> Dict[str, str]:
        """
            Convert a neutral flat tag dict to a Hetzner labels dict.

            :param neutral_tags: Flat ``{key: value}`` dict of tag pairs.

            :returns: A flat ``{key: value}`` dict.
            :raises: HetznerValidationError
        """
        out: Dict[str, str] = {}
        if neutral_tags is None:
            rtnval = out
            return rtnval

        for key, value in neutral_tags.items():
            _validate_label_key(key=key)
            _validate_label_value(key=key, value=value)
            out[key] = value

        rtnval = out
        return rtnval

    @classmethod
    def from_hetzner(cls, *, labels: Optional[Dict[str, str]]
                     ) -> Dict[str, str]:
        """
            Convert a Hetzner labels dict back to a neutral flat tag dict.

            :param labels: Flat ``{key: value}`` dict from a Hetzner object.

            :returns: A neutral flat ``{key: value}`` dict.
        """
        out: Dict[str, str] = {}
        if labels is None:
            rtnval = out
            return rtnval

        sorted_keys = sorted(labels.keys())
        for key in sorted_keys:
            out[key] = labels[key]

        rtnval = out
        return rtnval

    @classmethod
    def base_labels(cls, *, run_id: str, resource_name: str,
                    resource_kind: str,
                    extra: Optional[Dict[str, str]] = None,
                    defaults: Optional[Dict[str, str]] = None
                    ) -> Dict[str, str]:
        """
            Build the full Hetzner labels dict for a created resource.

            :param run_id: The provisioning run identifier.
            :param resource_name: Neutral resource name.
            :param resource_kind: Neutral resource kind string.
            :param extra: Optional user-declared tags.
            :param defaults: Optional venue default labels.

            :returns: A flat ``{key: value}`` labels dict.
            :raises: HetznerValidationError
        """
        combined: Dict[str, str] = {}
        combined[OWNER_LABEL_KEY] = OWNER_LABEL_VALUE
        combined[RUN_ID_LABEL_KEY] = run_id
        combined[RESOURCE_NAME_LABEL_KEY] = resource_name
        combined[RESOURCE_KIND_LABEL_KEY] = resource_kind

        if defaults is not None:
            for key, value in defaults.items():
                combined[key] = value

        if extra is not None:
            for key, value in extra.items():
                combined[key] = value

        rtnval = cls.to_hetzner(neutral_tags=combined)
        return rtnval

    @classmethod
    def is_owned(cls, *, labels: Optional[Dict[str, str]]) -> bool:
        """
            Check whether a labels dict carries the owner-label pair.

            :param labels: Flat labels dict or None.

            :returns: True when owned by automojo-provisioning.
        """
        if labels is None:
            rtnval = False
            return rtnval
        rtnval = labels.get(OWNER_LABEL_KEY, None) == OWNER_LABEL_VALUE
        return rtnval

    @classmethod
    def belongs_to_run(cls, *, labels: Optional[Dict[str, str]],
                       run_id: str) -> bool:
        """
            Check whether a labels dict carries the (owner, run-id) pair.

            :param labels: Flat labels dict or None.
            :param run_id: Expected run-id value.

            :returns: True when owned by automojo and matching the run id.
        """
        if labels is None:
            rtnval = False
            return rtnval
        if labels.get(OWNER_LABEL_KEY, None) != OWNER_LABEL_VALUE:
            rtnval = False
            return rtnval
        rtnval = labels.get(RUN_ID_LABEL_KEY, None) == run_id
        return rtnval

    @classmethod
    def label_selector(cls, *, run_id: str) -> str:
        """
            Build a Hetzner ``label_selector`` query for owned resources.

            :param run_id: The provisioning run identifier.

            :returns: A label-selector string for list-by-label calls.
        """
        rtnval = "{}={},{}={}".format(
            OWNER_LABEL_KEY, OWNER_LABEL_VALUE,
            RUN_ID_LABEL_KEY, run_id,
        )
        return rtnval
