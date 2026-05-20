"""
    .. module:: nebiuslabeltranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Round-trip translation between neutral tags and Nebius labels.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Dict, List, Optional

from automojo.provisioning.venues.nebius.nebiuserrors import (
    NebiusValidationError
)


OWNER_LABEL_KEY = "automojo-owned-by"
OWNER_LABEL_VALUE = "automojo-provisioning"
RUN_ID_LABEL_KEY = "automojo-run-id"
RESOURCE_NAME_LABEL_KEY = "automojo-resource-name"
RESOURCE_KIND_LABEL_KEY = "automojo-resource-kind"


class NebiusLabelTranslator:
    """
        Translator between the neutral ``List[Dict[str, str]]`` tag shape and
        the Nebius labels dict.

        Round-tripping conformant inputs through :meth:`to_nebius` then
        :meth:`from_nebius` is the identity transformation.
    """

    def to_nebius(self, *, neutral_tags: Optional[List[Dict[str, str]]]
                  ) -> Dict[str, str]:
        """
            Translate neutral single-entry tag dicts into a Nebius labels
            dict, preserving every key/value verbatim.

            :param neutral_tags: A list of single-entry ``{key: value}``
                dicts, or ``None``.

            :returns: A flat labels dict.

            :raises: NebiusValidationError when an entry is not a
                single-key dict or a duplicate key is detected.
        """
        labels: Dict[str, str] = {}
        if neutral_tags is None:
            rtnval = labels
            return rtnval

        for entry in neutral_tags:
            if not isinstance(entry, dict):
                err_msg_lines = ["Neutral tag entry is not a dict."]
                err_msg_lines.append("ENTRY: {!r}".format(entry))
                err_msg = os.linesep.join(err_msg_lines)
                raise NebiusValidationError(err_msg)
            if len(entry) != 1:
                err_msg_lines = [
                    "Neutral tag entry must be a single-key dict."
                ]
                err_msg_lines.append("ENTRY: {!r}".format(entry))
                err_msg = os.linesep.join(err_msg_lines)
                raise NebiusValidationError(err_msg)

            for key, value in entry.items():
                if key in labels:
                    err_msg_lines = [
                        "Duplicate tag key in neutral tag set."
                    ]
                    err_msg_lines.append("KEY: {}".format(key))
                    err_msg = os.linesep.join(err_msg_lines)
                    raise NebiusValidationError(err_msg)
                labels[key] = value

        rtnval = labels
        return rtnval

    def from_nebius(self, *, labels: Optional[Dict[str, str]]
                    ) -> List[Dict[str, str]]:
        """
            Translate a Nebius labels dict back into the neutral
            single-entry tag-dict list, key-sorted for determinism.

            :param labels: A Nebius labels dict, or ``None``.

            :returns: A key-sorted list of single-entry neutral dicts.
        """
        out: List[Dict[str, str]] = []
        if labels is None:
            rtnval = out
            return rtnval

        for key in sorted(labels.keys()):
            out.append({key: labels[key]})

        rtnval = out
        return rtnval

    def base_labels(self, *, run_id: str, resource_name: str,
                    resource_kind: str,
                    extra: Optional[List[Dict[str, str]]] = None
                    ) -> Dict[str, str]:
        """
            Build the full Nebius labels dict for a created resource.

            :param run_id: The provisioning run identifier.
            :param resource_name: Neutral resource name.
            :param resource_kind: Neutral resource kind string.
            :param extra: Optional user-declared neutral tags.

            :returns: A Nebius labels dict carrying the ownership triple
                plus any user labels.
        """
        labels: Dict[str, str] = {}
        labels[OWNER_LABEL_KEY] = OWNER_LABEL_VALUE
        labels[RUN_ID_LABEL_KEY] = run_id
        labels[RESOURCE_NAME_LABEL_KEY] = resource_name
        labels[RESOURCE_KIND_LABEL_KEY] = resource_kind

        if extra is not None:
            user_labels = self.to_nebius(neutral_tags=extra)
            for key, value in user_labels.items():
                labels[key] = value

        rtnval = labels
        return rtnval
