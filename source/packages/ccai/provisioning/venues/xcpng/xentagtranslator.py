"""
    .. module:: xentagtranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: XenTagTranslator — neutral tag list <-> XAPI ``other_config``
        plus ``tags`` list, with run-id ownership encoding.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List


# The ``other_config`` key carrying the provisioning run id; plan and
# inventory match VMs by this key.
RUN_ID_KEY = "codecraftai-run-id"

# The ``other_config`` ownership marker pair, mirroring
# CloudProvisioner.OWNER_TAG_KEY / OWNER_TAG_VALUE.
OWNER_KEY = "codecraftai-owned-by"
OWNER_VALUE = "codecraftai-provisioning"


class XenTagTranslator:
    """
        Translate between the neutral tag form and the XAPI tag form.

        The neutral form is a flat ``{key: value}`` dict.  XCP-ng has no
        first-class queryable tag index, so the venue stores each neutral
        tag two ways:

        * Under ``VM.other_config`` as a flat ``key -> value`` mapping
          (queryable, and where the run-id / ownership markers also live).
        * In the legacy ``VM.tags`` list, with each pair encoded as a single
          ``key=value`` string entry.

        For conformant inputs — non-empty string keys/values and no key
        containing ``=`` — ``from_xen(to_xen(tags, run_id))`` is the
        identity on the neutral dict (modulo key ordering, which
        :meth:`from_xen` sorts).
    """

    def to_xen(self, *, neutral_tags: Dict[str, str],
               run_id: str) -> Dict[str, Any]:
        """
            Translate a neutral tag dict into the XAPI tag form.

            :param neutral_tags: A flat ``{key: value}`` dict of tag pairs.
            :param run_id: The provisioning run id to stamp into
                           ``other_config``.

            :returns: A dict with ``other_config`` (flat str->str mapping)
                      and ``tags`` (``key=value`` string list) keys.
        """
        other_config: Dict[str, str] = {}
        tags: List[str] = []

        if neutral_tags is not None:
            for key, value in neutral_tags.items():
                other_config[key] = value
                tags.append("{}={}".format(key, value))

        other_config[RUN_ID_KEY] = run_id
        other_config[OWNER_KEY] = OWNER_VALUE

        rtnval: Dict[str, Any] = {
            "other_config": other_config,
            "tags": tags,
        }
        return rtnval

    def from_xen(self, *, vm_record: Any) -> Dict[str, str]:
        """
            Recover the neutral tag dict from a XAPI VM record.

            The neutral dict is reconstructed from ``other_config``, with the
            run-id and ownership marker keys stripped.  Keys are emitted in
            sorted order so the result is deterministic.

            :param vm_record: A XenVm typed record (or an object exposing an
                              ``other_config`` mapping).

            :returns: A flat ``{key: value}`` dict of neutral tag pairs.
        """
        other_config = getattr(vm_record, "other_config", None)
        if other_config is None:
            rtnval: Dict[str, str] = {}
            return rtnval

        reserved = {RUN_ID_KEY, OWNER_KEY}
        out: Dict[str, str] = {}
        for key in sorted(other_config.keys()):
            if key in reserved:
                continue
            out[key] = other_config[key]
        rtnval = out
        return rtnval

    def run_id_of(self, *, vm_record: Any) -> str:
        """
            Return the provisioning run id stamped on a XAPI VM record.

            :param vm_record: A XenVm typed record.

            :returns: The run id string, or an empty string when absent.
        """
        other_config = getattr(vm_record, "other_config", None)
        if other_config is None:
            rtnval = ""
            return rtnval
        rtnval = other_config.get(RUN_ID_KEY, "")
        return rtnval
