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
    def to_vultr(cls, *, neutral_tags: Optional[List[Dict[str, str]]]
                 ) -> List[str]:
        """
            Convert neutral single-entry tag dicts to Vultr string tags.

            :param neutral_tags: List of single-entry ``{key: value}`` dicts.

            :returns: A key-sorted list of ``"key=value"`` strings.
            :raises: VultrValidationError
        """
        if neutral_tags is None:
            rtnval: List[str] = []
            return rtnval

        seen_keys: Dict[str, str] = {}
        for entry in neutral_tags:
            if not isinstance(entry, dict):
                err_msg_lines = ["Neutral tag entry is not a dict."]
                err_msg_lines.append("ENTRY: {!r}".format(entry))
                err_msg = os.linesep.join(err_msg_lines)
                raise VultrValidationError(err_msg)
            if len(entry) != 1:
                err_msg_lines = [
                    "Neutral tag entry must be a single-key dict."
                ]
                err_msg_lines.append("ENTRY: {!r}".format(entry))
                err_msg = os.linesep.join(err_msg_lines)
                raise VultrValidationError(err_msg)

            for key, value in entry.items():
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
                if key in seen_keys:
                    err_msg_lines = ["Duplicate tag key in neutral tag set."]
                    err_msg_lines.append("KEY: {}".format(key))
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
                   ) -> List[Dict[str, str]]:
        """
            Convert a Vultr string tag list back to neutral single-entry dicts.

            :param strings: List of ``"key=value"`` strings.

            :returns: A key-sorted list of single-entry neutral dicts.
        """
        if strings is None:
            rtnval: List[Dict[str, str]] = []
            return rtnval

        pairs: Dict[str, str] = {}
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

        sorted_keys = sorted(pairs.keys())
        out: List[Dict[str, str]] = []
        for key in sorted_keys:
            out.append({key: pairs[key]})

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
                           extra: Optional[List[Dict[str, str]]] = None,
                           defaults: Optional[List[Dict[str, str]]] = None
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

        rtnval = cls.to_vultr(neutral_tags=combined)
        return rtnval
