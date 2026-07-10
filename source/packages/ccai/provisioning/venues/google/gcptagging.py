"""
    .. module:: gcptagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Label round-trip helpers between neutral tag dicts and GCP labels.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import json
import os

from typing import Any, Dict, List, Optional

from ccai.provisioning.venues.google.gcperrors import GcpValidationError


# GCP VPC networks, subnetworks, firewall rules and resource policies have no
# ``labels`` field.  Their ownership + neutral-name + tag round-trip is carried
# in the ``description`` field instead, behind this marker prefix so it can be
# recognised and parsed back without colliding with a user description.
OWNER_DESCRIPTION_PREFIX = "ccai-provisioning:"


# GCP labels do not allow ':' in keys, so the ccai namespace separator is
# rendered with '_' inside labels and reconstructed on read-back.
OWNER_LABEL_KEY = "ccai_owned-by"
OWNER_LABEL_VALUE = "codecraftai-provisioning"
RUN_ID_LABEL_KEY = "ccai_owner"
RESOURCE_NAME_LABEL_KEY = "ccai_resource-name"
RESOURCE_KIND_LABEL_KEY = "ccai_resource-kind"

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


def to_labels(*, neutral_tags: Optional[Dict[str, str]],
              warnings: Optional[List[Dict[str, Any]]] = None
              ) -> Dict[str, str]:
    """
        Convert a neutral flat tag dict to a GCP labels mapping.

        Keys and values are lowercased and illegal characters are replaced;
        every change appends a warning record to ``warnings`` when supplied.

        :param neutral_tags: Flat ``{key: value}`` dict of tag pairs.
        :param warnings: Optional list to append change warnings to.

        :returns: A flat ``{key: value}`` GCP labels dict.
        :raises: GcpValidationError
    """
    if neutral_tags is None:
        rtnval: Dict[str, str] = {}
        return rtnval

    labels: Dict[str, str] = {}
    for key, value in neutral_tags.items():
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
                ) -> Dict[str, str]:
    """
        Convert a GCP labels mapping back to a neutral flat tag dict.

        Already-conformant inputs round-trip as identity (key-sorted).

        :param labels: Flat ``{key: value}`` GCP labels dict.

        :returns: A neutral flat ``{key: value}`` dict.
    """
    out: Dict[str, str] = {}
    if labels is None:
        rtnval = out
        return rtnval

    for key in sorted(labels.keys()):
        out[key] = labels[key]

    rtnval = out
    return rtnval


def base_resource_labels(*, run_id: str, resource_name: str,
                         resource_kind: str,
                         extra: Optional[Dict[str, str]] = None,
                         defaults: Optional[Dict[str, str]] = None
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


def owner_description(*, run_id: str, resource_name: str,
                      resource_kind: str,
                      extra: Optional[Dict[str, str]] = None,
                      defaults: Optional[Dict[str, str]] = None) -> str:
    """
        Build the ``description`` payload for a label-less GCP resource.

        The payload embeds the same label mapping a label-bearing resource
        would carry, so ownership checks and tag read-back reuse the label
        helpers unchanged.

        :param run_id: The provisioning run identifier.
        :param resource_name: Neutral resource name.
        :param resource_kind: Neutral resource kind string.
        :param extra: Optional user-declared tags.
        :param defaults: Optional venue default tags.

        :returns: A ``description`` string carrying the owner marker.
    """
    labels = base_resource_labels(
        run_id=run_id, resource_name=resource_name,
        resource_kind=resource_kind, extra=extra, defaults=defaults,
    )
    payload: Dict[str, Any] = {"version": 1, "labels": labels}
    encoded = json.dumps(payload, sort_keys=True)
    rtnval = "{}{}".format(OWNER_DESCRIPTION_PREFIX, encoded)
    return rtnval


def parse_owner_labels(*, description: Optional[str]
                       ) -> Optional[Dict[str, str]]:
    """
        Recover the embedded label mapping from a resource ``description``.

        Returns ``None`` for a description that is missing, does not carry the
        owner marker, or cannot be decoded — i.e. a resource not owned by this
        provisioner.  Absence and non-ownership are legitimate values here, so
        a malformed marker is treated as not-owned rather than raised.

        :param description: The resource ``description`` field (may be None).

        :returns: The embedded ``{key: value}`` label dict, or ``None``.
    """
    if description is None:
        rtnval: Optional[Dict[str, str]] = None
        return rtnval

    if not description.startswith(OWNER_DESCRIPTION_PREFIX):
        rtnval = None
        return rtnval

    encoded = description[len(OWNER_DESCRIPTION_PREFIX):]
    try:
        payload = json.loads(encoded)
    except (ValueError, TypeError):
        rtnval = None
        return rtnval

    if not isinstance(payload, dict):
        rtnval = None
        return rtnval

    labels = payload.get("labels", None)
    if not isinstance(labels, dict):
        rtnval = None
        return rtnval

    out: Dict[str, str] = {}
    for key in labels:
        out[str(key)] = str(labels[key])

    rtnval = out
    return rtnval
