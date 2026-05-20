"""
    .. module:: vstagtranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tag round-trip helpers between neutral single-entry tag dicts
        and the vSphere Category + Tag model.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Dict, List, Optional

from automojo.provisioning.venues.vsphere.vserrors import VsValidationError


OWNER_TAG_KEY = "automojo:owned-by"
OWNER_TAG_VALUE = "automojo-provisioning"
RUN_ID_TAG_KEY = "automojo-run-id"
RESOURCE_NAME_TAG_KEY = "automojo:resource-name"
RESOURCE_KIND_TAG_KEY = "automojo:resource-kind"


class VsCategoryTag:
    """
        A single resolved vSphere ``(category, tag)`` pair.

        vSphere models a tag as a value scoped under a named Category.  The
        venue creates one Category per neutral tag key and one Tag per
        ``key=value`` pair, so the neutral key becomes ``category`` and the
        neutral value becomes ``tag``.
    """

    def __init__(self, *, category: str, tag: str) -> None:
        """
            Construct a VsCategoryTag.

            :param category: The vSphere category name (neutral tag key).
            :param tag: The vSphere tag value (neutral tag value).
        """
        self.category: str = category
        self.tag: str = tag
        return

    def __eq__(self, other: object) -> bool:
        """
            Value equality on (category, tag).

            :param other: The object to compare against.

            :returns: True when both fields match.
        """
        if not isinstance(other, VsCategoryTag):
            rtnval = False
            return rtnval
        rtnval = self.category == other.category and self.tag == other.tag
        return rtnval

    def __repr__(self) -> str:
        """
            Return a debug representation.

            :returns: A string representation.
        """
        rtnval = "VsCategoryTag(category={!r}, tag={!r})".format(
            self.category, self.tag
        )
        return rtnval


def to_vs(*, neutral_tags: Optional[List[Dict[str, str]]]
          ) -> List[VsCategoryTag]:
    """
        Convert neutral single-entry tag dicts to vSphere category+tag pairs.

        :param neutral_tags: List of single-entry ``{key: value}`` dicts.

        :returns: A key-sorted list of :class:`VsCategoryTag`.
        :raises: VsValidationError
    """
    if neutral_tags is None:
        rtnval: List[VsCategoryTag] = []
        return rtnval

    pairs: List[VsCategoryTag] = []
    seen_keys: Dict[str, str] = {}
    for entry in neutral_tags:
        if not isinstance(entry, dict):
            err_msg_lines = ["Neutral tag entry is not a dict."]
            err_msg_lines.append("ENTRY: {!r}".format(entry))
            err_msg = os.linesep.join(err_msg_lines)
            raise VsValidationError(err_msg)
        if len(entry) != 1:
            err_msg_lines = ["Neutral tag entry must be a single-key dict."]
            err_msg_lines.append("ENTRY: {!r}".format(entry))
            err_msg = os.linesep.join(err_msg_lines)
            raise VsValidationError(err_msg)

        for key, value in entry.items():
            if not isinstance(key, str) or not isinstance(value, str):
                err_msg_lines = ["Tag key and value must be strings."]
                err_msg_lines.append("KEY: {!r}".format(key))
                err_msg_lines.append("VALUE: {!r}".format(value))
                err_msg = os.linesep.join(err_msg_lines)
                raise VsValidationError(err_msg)

            if key in seen_keys:
                err_msg_lines = ["Duplicate tag key in neutral tag set."]
                err_msg_lines.append("KEY: {}".format(key))
                err_msg = os.linesep.join(err_msg_lines)
                raise VsValidationError(err_msg)

            seen_keys[key] = value
            pairs.append(VsCategoryTag(category=key, tag=value))

    pairs.sort(key=lambda p: p.category)
    rtnval = pairs
    return rtnval


def from_vs(*, refs: Optional[List[VsCategoryTag]]
            ) -> List[Dict[str, str]]:
    """
        Convert vSphere category+tag pairs back to neutral single-entry dicts.

        This is the exact inverse of :func:`to_vs`; round-tripping
        ``neutral -> to_vs -> from_vs`` is the identity for any input.

        :param refs: List of :class:`VsCategoryTag`.

        :returns: A category-sorted list of single-entry neutral dicts.
    """
    if refs is None:
        rtnval: List[Dict[str, str]] = []
        return rtnval

    sorted_refs = sorted(refs, key=lambda p: p.category)
    out: List[Dict[str, str]] = []
    for ref in sorted_refs:
        out.append({ref.category: ref.tag})

    rtnval = out
    return rtnval


def base_resource_tags(*, run_id: str, resource_name: str,
                       resource_kind: str,
                       extra: Optional[List[Dict[str, str]]] = None,
                       defaults: Optional[List[Dict[str, str]]] = None
                       ) -> List[Dict[str, str]]:
    """
        Build the full neutral tag list for a created vSphere resource.

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


def belongs_to_run(*, neutral_tags: Optional[List[Dict[str, str]]],
                   run_id: str) -> bool:
    """
        Check whether a neutral tag list carries the (owner, run-id) pair.

        :param neutral_tags: Neutral tag list.
        :param run_id: Expected run-id value.

        :returns: True when owned by automojo and matching the run id.
    """
    if neutral_tags is None:
        rtnval = False
        return rtnval

    flat: Dict[str, str] = {}
    for entry in neutral_tags:
        for key, value in entry.items():
            flat[key] = value

    if flat.get(OWNER_TAG_KEY, None) != OWNER_TAG_VALUE:
        rtnval = False
        return rtnval

    rtnval = flat.get(RUN_ID_TAG_KEY, None) == run_id
    return rtnval
