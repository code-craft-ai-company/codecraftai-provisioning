"""
    .. module:: crusoelabeltranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CrusoeLabelTranslator — neutral tag list <-> Crusoe label dict.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Dict


class CrusoeLabelTranslator:
    """
        Translate between the neutral tag form (a flat ``{key: value}`` dict)
        and Crusoe's label form (a flat string-to-string dict).

        For conformant inputs — non-empty string keys/values — the round trip
        ``from_crusoe(to_crusoe(tags))`` is the identity.
    """

    def to_crusoe(self, *, neutral_tags: Dict[str, str]) -> Dict[str, str]:
        """
            Translate a neutral tag dict into a Crusoe label dict.

            :param neutral_tags: A flat ``{key: value}`` dict of tag pairs.

            :returns: A flat label dictionary.
        """
        rtnval: Dict[str, str] = {}
        if neutral_tags is None:
            return rtnval

        for key, value in neutral_tags.items():
            rtnval[key] = value
        return rtnval

    def from_crusoe(self, *, labels: Dict[str, str]) -> Dict[str, str]:
        """
            Translate a Crusoe label dict into the neutral tag dict form.

            Keys are emitted in sorted order so the result is deterministic.

            :param labels: A flat label dictionary.

            :returns: A flat ``{key: value}`` dict of tag pairs.
        """
        rtnval: Dict[str, str] = {}
        if labels is None:
            return rtnval

        for key in sorted(labels.keys()):
            rtnval[key] = labels[key]
        return rtnval
