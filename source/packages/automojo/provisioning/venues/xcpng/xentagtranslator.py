"""
    .. module:: xentagtranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: XenTagTranslator — neutral tag list <-> XAPI ``other_config``
        plus ``tags`` list, with run-id ownership encoding.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List


# The ``other_config`` key carrying the provisioning run id; plan and
# inventory match VMs by this key.
RUN_ID_KEY = "automojo-run-id"

# The ``other_config`` ownership marker pair, mirroring
# CloudProvisioner.OWNER_TAG_KEY / OWNER_TAG_VALUE.
OWNER_KEY = "automojo-owned-by"
OWNER_VALUE = "automojo-provisioning"


class XenTagTranslator:
    """
        Translate between the neutral tag form and the XAPI tag form.

        The neutral form is a list of single-entry dicts.  XCP-ng has no
        first-class queryable tag index, so the venue stores each neutral
        tag two ways:

        * Under ``VM.other_config`` as a flat ``key -> value`` mapping
          (queryable, and where the run-id / ownership markers also live).
        * In the legacy ``VM.tags`` list, with each pair encoded as a single
          ``key=value`` string entry.

        For conformant inputs — every tag a single-entry dict with non-empty
        string key/value, no duplicate keys, and no key containing ``=`` —
        ``from_xen(to_xen(tags, run_id))`` is the identity on the neutral
        list (modulo key ordering, which :meth:`from_xen` sorts).
    """

    def to_xen(self, *, neutral_tags: List[Dict[str, str]],
               run_id: str) -> Dict[str, Any]:
        """
            Translate a neutral tag list into the XAPI tag form.

            :param neutral_tags: A list of single-entry tag dicts.
            :param run_id: The provisioning run id to stamp into
                           ``other_config``.

            :returns: A dict with ``other_config`` (flat str->str mapping)
                      and ``tags`` (``key=value`` string list) keys.
        """
        other_config: Dict[str, str] = {}
        tags: List[str] = []

        if neutral_tags is not None:
            for entry in neutral_tags:
                for key, value in entry.items():
                    other_config[key] = value
                    tags.append("{}={}".format(key, value))

        other_config[RUN_ID_KEY] = run_id
        other_config[OWNER_KEY] = OWNER_VALUE

        rtnval: Dict[str, Any] = {
            "other_config": other_config,
            "tags": tags,
        }
        return rtnval

    def from_xen(self, *, vm_record: Any) -> List[Dict[str, str]]:
        """
            Recover the neutral tag list from a XAPI VM record.

            The neutral list is reconstructed from ``other_config``, with the
            run-id and ownership marker keys stripped.  Keys are emitted in
            sorted order so the result is deterministic.

            :param vm_record: A XenVm typed record (or an object exposing an
                              ``other_config`` mapping).

            :returns: A list of single-entry neutral tag dicts.
        """
        other_config = getattr(vm_record, "other_config", None)
        if other_config is None:
            rtnval: List[Dict[str, str]] = []
            return rtnval

        reserved = {RUN_ID_KEY, OWNER_KEY}
        out: List[Dict[str, str]] = []
        for key in sorted(other_config.keys()):
            if key in reserved:
                continue
            out.append({key: other_config[key]})
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
