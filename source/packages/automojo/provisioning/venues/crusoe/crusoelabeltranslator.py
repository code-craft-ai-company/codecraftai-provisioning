"""
    .. module:: crusoelabeltranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CrusoeLabelTranslator — neutral tag list <-> Crusoe label dict.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Dict, List


class CrusoeLabelTranslator:
    """
        Translate between the neutral tag form (a list of single-entry dicts)
        and Crusoe's label form (a flat string-to-string dict).

        For conformant inputs — every tag a single-entry dict with non-empty
        string key/value, and no duplicate keys — the round trip
        ``from_crusoe(to_crusoe(tags))`` is the identity.
    """

    def to_crusoe(self, *, neutral_tags: List[Dict[str, str]]) -> Dict[str, str]:
        """
            Translate a neutral tag list into a Crusoe label dict.

            :param neutral_tags: A list of single-entry tag dicts.

            :returns: A flat label dictionary.
        """
        rtnval: Dict[str, str] = {}
        if neutral_tags is None:
            return rtnval

        for entry in neutral_tags:
            for key, value in entry.items():
                rtnval[key] = value
        return rtnval

    def from_crusoe(self, *, labels: Dict[str, str]) -> List[Dict[str, str]]:
        """
            Translate a Crusoe label dict into the neutral tag list form.

            Keys are emitted in sorted order so the result is deterministic.

            :param labels: A flat label dictionary.

            :returns: A list of single-entry tag dicts.
        """
        rtnval: List[Dict[str, str]] = []
        if labels is None:
            return rtnval

        for key in sorted(labels.keys()):
            rtnval.append({key: labels[key]})
        return rtnval
