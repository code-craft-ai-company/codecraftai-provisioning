"""
    .. module:: gcptagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Label round-trip helpers between neutral tag dicts and GCP labels.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from automojo.provisioning.venues.google.gcperrors import GcpValidationError


# GCP labels do not allow ':' in keys, so the automojo namespace separator is
# rendered with '_' inside labels and reconstructed on read-back.
OWNER_LABEL_KEY = "automojo_owned-by"
OWNER_LABEL_VALUE = "automojo-provisioning"
RUN_ID_LABEL_KEY = "automojo_owner"
RESOURCE_NAME_LABEL_KEY = "automojo_resource-name"
RESOURCE_KIND_LABEL_KEY = "automojo_resource-kind"

# GCP label rules: keys/values <= 63 chars, lowercase letters, digits,
# underscores and dashes only.  Keys must start with a lowercase letter.
GCP_LABEL_KEY_MAX = 63
GCP_LABEL_VALUE_MAX = 63

_LEGAL_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz0123456789-_"
)


def sanitise_label_component(*, value: str) -> str:
    """
        Sanitise one label key or value to satisfy GCP label rules.

        :param value: Raw label component.

        :returns: A GCP-conformant lowercased label component.
    """
    lowered = value.lower()
    chars: List[str] = []
    for ch in lowered:
        if ch in _LEGAL_CHARS:
            chars.append(ch)
        else:
            chars.append("_")
    sanitised = "".join(chars)
    if len(sanitised) > GCP_LABEL_VALUE_MAX:
        sanitised = sanitised[:GCP_LABEL_VALUE_MAX]
    rtnval = sanitised
    return rtnval


def is_label_conformant(*, key: str, value: str) -> bool:
    """
        Return True when a (key, value) pair already obeys GCP label rules.

        :param key: Label key.
        :param value: Label value.

        :returns: True when the pair would round-trip as identity.
    """
    if len(key) == 0 or len(key) > GCP_LABEL_KEY_MAX:
        rtnval = False
        return rtnval
    if len(value) > GCP_LABEL_VALUE_MAX:
        rtnval = False
        return rtnval
    if key[0] not in "abcdefghijklmnopqrstuvwxyz":
        rtnval = False
        return rtnval
    for ch in key:
        if ch not in _LEGAL_CHARS:
            rtnval = False
            return rtnval
    for ch in value:
        if ch not in _LEGAL_CHARS:
            rtnval = False
            return rtnval
    rtnval = True
    return rtnval


def to_labels(*, neutral_tags: Optional[List[Dict[str, str]]],
              warnings: Optional[List[Dict[str, Any]]] = None
              ) -> Dict[str, str]:
    """
        Convert neutral single-entry tag dicts to a GCP labels mapping.

        Keys and values are lowercased and illegal characters are replaced;
        every change appends a warning record to ``warnings`` when supplied.

        :param neutral_tags: List of single-entry ``{key: value}`` dicts.
        :param warnings: Optional list to append change warnings to.

        :returns: A flat ``{key: value}`` GCP labels dict.
        :raises: GcpValidationError
    """
    if neutral_tags is None:
        rtnval: Dict[str, str] = {}
        return rtnval

    labels: Dict[str, str] = {}
    for entry in neutral_tags:
        if not isinstance(entry, dict):
            err_msg_lines = ["Neutral tag entry is not a dict."]
            err_msg_lines.append("ENTRY: {!r}".format(entry))
            err_msg = os.linesep.join(err_msg_lines)
            raise GcpValidationError(err_msg)
        if len(entry) != 1:
            err_msg_lines = ["Neutral tag entry must be a single-key dict."]
            err_msg_lines.append("ENTRY: {!r}".format(entry))
            err_msg = os.linesep.join(err_msg_lines)
            raise GcpValidationError(err_msg)

        for key, value in entry.items():
            if not isinstance(key, str) or not isinstance(value, str):
                err_msg_lines = ["Tag key and value must be strings."]
                err_msg_lines.append("KEY: {!r}".format(key))
                err_msg_lines.append("VALUE: {!r}".format(value))
                err_msg = os.linesep.join(err_msg_lines)
                raise GcpValidationError(err_msg)

            if len(key) == 0:
                err_msg_lines = ["Tag key must not be empty."]
                err_msg = os.linesep.join(err_msg_lines)
                raise GcpValidationError(err_msg)

            safe_key = sanitise_label_component(value=key)
            safe_value = sanitise_label_component(value=value)

            if safe_key != key and warnings is not None:
                warnings.append({
                    "resource": "<labels>",
                    "warning": ("Tag key {!r} sanitised to {!r} for "
                                "GCP labels.").format(key, safe_key),
                })
            if safe_value != value and warnings is not None:
                warnings.append({
                    "resource": "<labels>",
                    "warning": ("Tag value {!r} sanitised to {!r} for "
                                "GCP labels.").format(value, safe_value),
                })

            labels[safe_key] = safe_value

    rtnval = labels
    return rtnval


def from_labels(*, labels: Optional[Dict[str, str]]
                ) -> List[Dict[str, str]]:
    """
        Convert a GCP labels mapping back to neutral single-entry dicts.

        Already-conformant inputs round-trip as identity (key-sorted).

        :param labels: Flat ``{key: value}`` GCP labels dict.

        :returns: A key-sorted list of single-entry neutral dicts.
    """
    if labels is None:
        rtnval: List[Dict[str, str]] = []
        return rtnval

    out: List[Dict[str, str]] = []
    for key in sorted(labels.keys()):
        out.append({key: labels[key]})

    rtnval = out
    return rtnval


def base_resource_labels(*, run_id: str, resource_name: str,
                         resource_kind: str,
                         extra: Optional[List[Dict[str, str]]] = None,
                         defaults: Optional[List[Dict[str, str]]] = None
                         ) -> Dict[str, str]:
    """
        Build the full GCP labels mapping for a created resource.

        :param run_id: The provisioning run identifier.
        :param resource_name: Neutral resource name.
        :param resource_kind: Neutral resource kind string.
        :param extra: Optional user-declared tags.
        :param defaults: Optional venue default tags.

        :returns: A flat ``{key: value}`` GCP labels dict.
    """
    labels: Dict[str, str] = {}
    labels[OWNER_LABEL_KEY] = OWNER_LABEL_VALUE
    labels[RUN_ID_LABEL_KEY] = sanitise_label_component(value=run_id)
    labels[RESOURCE_NAME_LABEL_KEY] = sanitise_label_component(
        value=resource_name
    )
    labels[RESOURCE_KIND_LABEL_KEY] = sanitise_label_component(
        value=resource_kind
    )

    if defaults is not None:
        default_labels = to_labels(neutral_tags=defaults)
        for key, value in default_labels.items():
            labels[key] = value

    if extra is not None:
        extra_labels = to_labels(neutral_tags=extra)
        for key, value in extra_labels.items():
            labels[key] = value

    rtnval = labels
    return rtnval
