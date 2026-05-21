"""
    .. module:: vultrtagtranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tag round-trip helpers between neutral dicts and Vultr string
               tag lists.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Dict, List, Optional

from automojo.provisioning.venues.vultr.vultrerrors import VultrValidationError


OWNER_TAG_KEY = "automojo:owned-by"
OWNER_TAG_VALUE = "automojo-provisioning"
RUN_ID_TAG_KEY = "automojo:owner"
RESOURCE_NAME_TAG_KEY = "automojo:resource-name"
RESOURCE_KIND_TAG_KEY = "automojo:resource-kind"


class VultrTagTranslator:
    """
        Translator between the neutral single-entry tag dict list and the
        Vultr string-list tag representation (``["key=value", ...]``).

        Round-tripping ``from_vultr(to_vultr(tags))`` is the identity over
        the set of ``key=value`` pairs (key-sorted).
    """

    @classmethod
    def to_vultr(cls, *, neutral_tags: Optional[Dict[str, str]]
                 ) -> List[str]:
        """
            Convert a neutral flat tag dict to Vultr string tags.

            :param neutral_tags: Flat ``{key: value}`` dict of tag pairs.

            :returns: A key-sorted list of ``"key=value"`` strings.
            :raises: VultrValidationError
        """
        if neutral_tags is None:
            rtnval: List[str] = []
            return rtnval

        seen_keys: Dict[str, str] = {}
        for key, value in neutral_tags.items():
            if not isinstance(key, str) or not isinstance(value, str):
                err_msg_lines = ["Tag key and value must be strings."]
                err_msg_lines.append("KEY: {!r}".format(key))
                err_msg_lines.append("VALUE: {!r}".format(value))
                err_msg = os.linesep.join(err_msg_lines)
                raise VultrValidationError(err_msg)
            if "=" in key:
                err_msg_lines = [
                    "Tag key may not contain an '=' separator."
                ]
                err_msg_lines.append("KEY: {!r}".format(key))
                err_msg = os.linesep.join(err_msg_lines)
                raise VultrValidationError(err_msg)
            seen_keys[key] = value

        sorted_keys = sorted(seen_keys.keys())
        out: List[str] = []
        for key in sorted_keys:
            out.append("{}={}".format(key, seen_keys[key]))

        rtnval = out
        return rtnval

    @classmethod
    def from_vultr(cls, *, strings: Optional[List[str]]
                   ) -> Dict[str, str]:
        """
            Convert a Vultr string tag list back to a neutral flat tag dict.

            :param strings: List of ``"key=value"`` strings.

            :returns: A neutral flat ``{key: value}`` dict.
        """
        pairs: Dict[str, str] = {}
        if strings is None:
            rtnval = pairs
            return rtnval

        for entry in strings:
            if not isinstance(entry, str):
                continue
            if "=" not in entry:
                pairs[entry] = ""
                continue
            split_index = entry.index("=")
            key = entry[:split_index]
            value = entry[split_index + 1:]
            pairs[key] = value

        out: Dict[str, str] = {}
        for key in sorted(pairs.keys()):
            out[key] = pairs[key]

        rtnval = out
        return rtnval

    @classmethod
    def owner_tag_strings(cls, *, run_id: str) -> List[str]:
        """
            Return the owner + run-id tag strings used to filter listings.

            :param run_id: The provisioning run identifier.

            :returns: A list of ``"key=value"`` strings.
        """
        rtnval = [
            "{}={}".format(OWNER_TAG_KEY, OWNER_TAG_VALUE),
            "{}={}".format(RUN_ID_TAG_KEY, run_id),
        ]
        return rtnval

    @classmethod
    def base_resource_tags(cls, *, run_id: str, resource_name: str,
                           resource_kind: str,
                           extra: Optional[Dict[str, str]] = None,
                           defaults: Optional[Dict[str, str]] = None
                           ) -> List[str]:
        """
            Build the full Vultr string tag list for a created resource.

            :param run_id: The provisioning run identifier.
            :param resource_name: Neutral resource name.
            :param resource_kind: Neutral resource kind string.
            :param extra: Optional user-declared neutral tags.
            :param defaults: Optional venue default neutral tags.

            :returns: A key-sorted list of ``"key=value"`` strings.
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

        rtnval = cls.to_vultr(neutral_tags=combined)
        return rtnval
