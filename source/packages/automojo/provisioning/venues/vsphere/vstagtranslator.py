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


def to_vs(*, neutral_tags: Optional[Dict[str, str]]
          ) -> List[VsCategoryTag]:
    """
        Convert a neutral flat tag dict to vSphere category+tag pairs.

        :param neutral_tags: Flat ``{key: value}`` dict of tag pairs.

        :returns: A key-sorted list of :class:`VsCategoryTag`.
        :raises: VsValidationError
    """
    if neutral_tags is None:
        rtnval: List[VsCategoryTag] = []
        return rtnval

    pairs: List[VsCategoryTag] = []
    for key, value in neutral_tags.items():
        if not isinstance(key, str) or not isinstance(value, str):
            err_msg_lines = ["Tag key and value must be strings."]
            err_msg_lines.append("KEY: {!r}".format(key))
            err_msg_lines.append("VALUE: {!r}".format(value))
            err_msg = os.linesep.join(err_msg_lines)
            raise VsValidationError(err_msg)

        pairs.append(VsCategoryTag(category=key, tag=value))

    pairs.sort(key=lambda p: p.category)
    rtnval = pairs
    return rtnval


def from_vs(*, refs: Optional[List[VsCategoryTag]]
            ) -> Dict[str, str]:
    """
        Convert vSphere category+tag pairs back to a neutral flat tag dict.

        This is the exact inverse of :func:`to_vs`; round-tripping
        ``neutral -> to_vs -> from_vs`` is the identity for any input.

        :param refs: List of :class:`VsCategoryTag`.

        :returns: A neutral flat ``{key: value}`` dict, category-sorted.
    """
    out: Dict[str, str] = {}
    if refs is None:
        rtnval = out
        return rtnval

    sorted_refs = sorted(refs, key=lambda p: p.category)
    for ref in sorted_refs:
        out[ref.category] = ref.tag

    rtnval = out
    return rtnval


def base_resource_tags(*, run_id: str, resource_name: str,
                       resource_kind: str,
                       extra: Optional[Dict[str, str]] = None,
                       defaults: Optional[Dict[str, str]] = None
                       ) -> Dict[str, str]:
    """
        Build the full neutral tag dict for a created vSphere resource.

        :param run_id: The provisioning run identifier.
        :param resource_name: Neutral resource name.
        :param resource_kind: Neutral resource kind string.
        :param extra: Optional user-declared tags.
        :param defaults: Optional venue default tags.

        :returns: Combined neutral flat tag dict.
    """
    combined: Dict[str, str] = {}
    combined[OWNER_TAG_KEY] = OWNER_TAG_VALUE
    combined[RUN_ID_TAG_KEY] = run_id
    combined[RESOURCE_NAME_TAG_KEY] = resource_name
    combined[RESOURCE_KIND_TAG_KEY] = resource_kind

    if defaults is not None:
        for key, value in defaults.items():
            combined[key] = value

    if extra is not None:
        for key, value in extra.items():
            combined[key] = value

    rtnval = combined
    return rtnval


def belongs_to_run(*, neutral_tags: Optional[Dict[str, str]],
                   run_id: str) -> bool:
    """
        Check whether a neutral tag dict carries the (owner, run-id) pair.

        :param neutral_tags: Neutral flat tag dict.
        :param run_id: Expected run-id value.

        :returns: True when owned by automojo and matching the run id.
    """
    if neutral_tags is None:
        rtnval = False
        return rtnval

    flat: Dict[str, str] = dict(neutral_tags)

    if flat.get(OWNER_TAG_KEY, None) != OWNER_TAG_VALUE:
        rtnval = False
        return rtnval

    rtnval = flat.get(RUN_ID_TAG_KEY, None) == run_id
    return rtnval
