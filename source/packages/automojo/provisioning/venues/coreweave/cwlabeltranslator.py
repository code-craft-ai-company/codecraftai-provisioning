"""
    .. module:: cwlabeltranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CwLabelTranslator — neutral tag list <-> Kubernetes label dict
        with key/value sanitisation and round-trip identity for conformant
        inputs.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import logging
import re

from typing import Dict


# A Kubernetes label value/key segment is at most 63 chars, must start and
# end with an alphanumeric, and may contain '-', '_', '.' internally.
_K8S_LABEL_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9\-_.]{0,61}[A-Za-z0-9])?$")

_MAX_LABEL_LENGTH = 63


class CwLabelTranslator:
    """
        Translate between the neutral tag form (a flat ``{key: value}`` dict)
        and the Kubernetes label form (a flat string-to-string dict).

        For conformant inputs — keys and values that already satisfy the
        Kubernetes label rules — the round trip ``from_k8s(to_k8s(tags))``
        is the identity.  Non-conformant key/value characters are replaced
        and a warning is emitted per change.
    """

    def __init__(self, *, logger_name: str = "automojo.provisioning.coreweave") -> None:
        """
            Initialise the translator.

            :param logger_name: The logger name used to emit sanitisation
                warnings.

            :returns: ``None``.
        """
        self._logger_name = logger_name
        return

    def is_conformant(self, *, value: str) -> bool:
        """
            Report whether a key/value segment already satisfies the
            Kubernetes label rules.

            :param value: The candidate label key or value.

            :returns: ``True`` when the value needs no sanitisation.
        """
        if value is None:
            rtnval = False
            return rtnval

        if len(value) == 0:
            rtnval = False
            return rtnval

        match = _K8S_LABEL_RE.match(value)
        rtnval = match is not None
        return rtnval

    def sanitise(self, *, value: str) -> str:
        """
            Sanitise a single key/value segment to the Kubernetes label
            rules, emitting a warning when the value is changed.

            :param value: The candidate label key or value.

            :returns: A Kubernetes-conformant label segment.
        """
        original = value

        if value is None or len(value) == 0:
            replaced = "x"
        else:
            replaced = re.sub(r"[^A-Za-z0-9\-_.]", "-", value)

        if len(replaced) > _MAX_LABEL_LENGTH:
            replaced = replaced[0:_MAX_LABEL_LENGTH]

        replaced = replaced.strip("-_.")
        if len(replaced) == 0:
            replaced = "x"

        if replaced != original:
            logger = logging.getLogger(self._logger_name)
            logger.warning("Sanitised label segment %r to %r for Kubernetes "
                            "conformance.", original, replaced)

        rtnval = replaced
        return rtnval

    def to_k8s(self, *, neutral_tags: Dict[str, str]) -> Dict[str, str]:
        """
            Translate a neutral tag dict into a Kubernetes label dict.

            :param neutral_tags: A flat ``{key: value}`` dict of tag pairs.

            :returns: A flat Kubernetes label dictionary.
        """
        rtnval: Dict[str, str] = {}
        if neutral_tags is None:
            return rtnval

        for key, value in neutral_tags.items():
            if self.is_conformant(value=key):
                safe_key = key
            else:
                safe_key = self.sanitise(value=key)

            if self.is_conformant(value=value):
                safe_value = value
            else:
                safe_value = self.sanitise(value=value)

            rtnval[safe_key] = safe_value

        return rtnval

    def from_k8s(self, *, labels: Dict[str, str]) -> Dict[str, str]:
        """
            Translate a Kubernetes label dict into the neutral tag dict form.

            Keys are emitted in sorted order so the result is deterministic.

            :param labels: A flat Kubernetes label dictionary.

            :returns: A flat ``{key: value}`` dict of tag pairs.
        """
        rtnval: Dict[str, str] = {}
        if labels is None:
            return rtnval

        for key in sorted(labels.keys()):
            rtnval[key] = labels[key]

        return rtnval


__all__ = ["CwLabelTranslator"]
