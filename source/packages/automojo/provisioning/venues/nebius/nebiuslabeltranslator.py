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
        Translator between the neutral flat ``Dict[str, str]`` tag shape and
        the Nebius labels dict.

        Round-tripping conformant inputs through :meth:`to_nebius` then
        :meth:`from_nebius` is the identity transformation.
    """

    def to_nebius(self, *, neutral_tags: Optional[Dict[str, str]]
                  ) -> Dict[str, str]:
        """
            Translate a neutral flat tag dict into a Nebius labels
            dict, preserving every key/value verbatim.

            :param neutral_tags: A flat ``{key: value}`` dict of tag pairs,
                or ``None``.

            :returns: A flat labels dict.
        """
        labels: Dict[str, str] = {}
        if neutral_tags is None:
            rtnval = labels
            return rtnval

        for key, value in neutral_tags.items():
            labels[key] = value

        rtnval = labels
        return rtnval

    def from_nebius(self, *, labels: Optional[Dict[str, str]]
                    ) -> Dict[str, str]:
        """
            Translate a Nebius labels dict back into a neutral flat tag
            dict, key-sorted for determinism.

            :param labels: A Nebius labels dict, or ``None``.

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

    def base_labels(self, *, run_id: str, resource_name: str,
                    resource_kind: str,
                    extra: Optional[Dict[str, str]] = None
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
