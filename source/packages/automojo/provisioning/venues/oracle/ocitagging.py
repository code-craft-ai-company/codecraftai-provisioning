"""
    .. module:: ocitagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tag round-trip helpers between neutral dicts and the OCI
               freeform-tags shape (a flat ``Dict[str, str]``).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Dict, List, Optional

from automojo.provisioning.venues.oracle.ocierrors import OciValidationError


OWNER_TAG_KEY = "automojo_owned-by"
OWNER_TAG_VALUE = "automojo-provisioning"
RUN_ID_TAG_KEY = "automojo_run-id"
RESOURCE_NAME_TAG_KEY = "automojo_resource-name"
RESOURCE_KIND_TAG_KEY = "automojo_resource-kind"

# OCI freeform-tag limits.
OCI_TAG_KEY_MAX = 100
OCI_TAG_VALUE_MAX = 256


def to_freeform(*, neutral_tags: Optional[List[Dict[str, str]]]
                ) -> Dict[str, str]:
    """
        Convert neutral single-entry tag dicts to the OCI freeform-tags shape.

        OCI freeform tags are a flat ``Dict[str, str]``.

        :param neutral_tags: List of single-entry ``{key: value}`` dicts.

        :returns: A flat ``{key: value}`` dict.
        :raises: OciValidationError
    """
    if neutral_tags is None:
        rtnval: Dict[str, str] = {}
        return rtnval

    out: Dict[str, str] = {}
    for entry in neutral_tags:
        if not isinstance(entry, dict):
            err_msg_lines = ["Neutral tag entry is not a dict."]
            err_msg_lines.append("ENTRY: {!r}".format(entry))
            err_msg = os.linesep.join(err_msg_lines)
            raise OciValidationError(err_msg)
        if len(entry) != 1:
            err_msg_lines = ["Neutral tag entry must be a single-key dict."]
            err_msg_lines.append("ENTRY: {!r}".format(entry))
            err_msg = os.linesep.join(err_msg_lines)
            raise OciValidationError(err_msg)

        for key, value in entry.items():
            if not isinstance(key, str) or not isinstance(value, str):
                err_msg_lines = ["Tag key and value must be strings."]
                err_msg_lines.append("KEY: {!r}".format(key))
                err_msg_lines.append("VALUE: {!r}".format(value))
                err_msg = os.linesep.join(err_msg_lines)
                raise OciValidationError(err_msg)

            if len(key) > OCI_TAG_KEY_MAX:
                err_msg_lines = ["Tag key exceeds OCI 100-char limit."]
                err_msg_lines.append("KEY: {!r}".format(key))
                err_msg = os.linesep.join(err_msg_lines)
                raise OciValidationError(err_msg)

            if len(value) > OCI_TAG_VALUE_MAX:
                err_msg_lines = ["Tag value exceeds OCI 256-char limit."]
                err_msg_lines.append("KEY: {}".format(key))
                err_msg_lines.append("LENGTH: {}".format(len(value)))
                err_msg = os.linesep.join(err_msg_lines)
                raise OciValidationError(err_msg)

            if key in out:
                err_msg_lines = ["Duplicate tag key in neutral tag set."]
                err_msg_lines.append("KEY: {}".format(key))
                err_msg = os.linesep.join(err_msg_lines)
                raise OciValidationError(err_msg)

            out[key] = value

    rtnval = out
    return rtnval


def from_freeform(*, freeform_tags: Optional[Dict[str, str]]
                  ) -> List[Dict[str, str]]:
    """
        Convert an OCI freeform-tags dict back to neutral single-entry dicts.

        :param freeform_tags: A flat ``{key: value}`` dict.

        :returns: A key-sorted list of single-entry neutral dicts.
    """
    if freeform_tags is None:
        rtnval: List[Dict[str, str]] = []
        return rtnval

    out: List[Dict[str, str]] = []
    for key in sorted(freeform_tags.keys()):
        out.append({key: freeform_tags[key]})

    rtnval = out
    return rtnval


def base_resource_tags(*, run_id: str, resource_name: str,
                       resource_kind: str,
                       extra: Optional[List[Dict[str, str]]] = None,
                       defaults: Optional[List[Dict[str, str]]] = None
                       ) -> List[Dict[str, str]]:
    """
        Build the full neutral tag list for a created OCI resource.

        :param run_id: The provisioning run identifier.
        :param resource_name: Neutral resource name.
        :param resource_kind: Neutral resource kind string.
        :param extra: Optional user-declared tags.
        :param defaults: Optional venue default tags.

        :returns: Combined neutral tag list.
    """
    combined: List[Dict[str, str]] = []
    combined.append({OWNER_TAG_KEY: OWNER_TAG_VALUE})
    combined.append({RUN_ID_TAG_KEY: run_id})
    combined.append({RESOURCE_NAME_TAG_KEY: resource_name})
    combined.append({RESOURCE_KIND_TAG_KEY: resource_kind})

    if defaults is not None:
        for entry in defaults:
            combined.append(dict(entry))

    if extra is not None:
        for entry in extra:
            combined.append(dict(entry))

    rtnval = combined
    return rtnval


def freeform_for_resource(*, run_id: str, resource_name: str,
                          resource_kind: str,
                          extra: Optional[List[Dict[str, str]]] = None,
                          defaults: Optional[List[Dict[str, str]]] = None
                          ) -> Dict[str, str]:
    """
        Build the OCI freeform-tags dict for a created resource directly.

        :param run_id: The provisioning run identifier.
        :param resource_name: Neutral resource name.
        :param resource_kind: Neutral resource kind string.
        :param extra: Optional user-declared tags.
        :param defaults: Optional venue default tags.

        :returns: An OCI freeform-tags dict.
    """
    neutral = base_resource_tags(run_id=run_id, resource_name=resource_name,
                                 resource_kind=resource_kind, extra=extra,
                                 defaults=defaults)
    rtnval = to_freeform(neutral_tags=neutral)
    return rtnval
