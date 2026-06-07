"""
    .. module:: ntxcategorytranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: NtxCategoryTranslator — translates neutral tags to / from
               Prism Central Categories + Values with round-trip identity.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict

from ccai.provisioning.venues.nutanix.ntxnaming import RUN_ID_CATEGORY


class NtxCategoryTranslator:
    """
        Translates the neutral tag model to Prism Central Categories.

        Prism models a tag as a *Value* scoped under a named *Category*
        key.  This translator ensures one Category per neutral tag key
        plus the ``codecraftai-run-id`` Category, ensures a Value per
        ``key=value`` pair, and produces a ``categories`` map
        (``key -> value``) suitable for a :class:`VmSpec`.  Reading the
        map back from a VM recovers the neutral tag list so round-tripping
        is the identity (modulo the injected ``codecraftai-run-id`` entry).
    """

    def __init__(self, *, client: Any) -> None:
        """
            Construct an NtxCategoryTranslator.

            :param client: The Nutanix interop client.
        """
        self._client = client
        return

    def ensure(self, *, neutral_tags: Dict[str, str], run_id: str,
               aspects: Any) -> Dict[str, str]:
        """
            Ensure every neutral tag and the run-id Category exist.

            :param neutral_tags: The neutral flat tag dict.
            :param run_id: The provisioning run id.
            :param aspects: Behaviour control for the interop client.

            :returns: A Prism category map (``key -> value``) carrying the
                neutral tags plus the ``codecraftai-run-id`` entry.
        """
        mapping: Dict[str, str] = {}

        effective_tags = neutral_tags if neutral_tags is not None else {}
        for key, value in effective_tags.items():
            self._client.categories.ensure_category(name=key,
                                                    value=value,
                                                    aspects=aspects)
            mapping[key] = value

        self._client.categories.ensure_category(name=RUN_ID_CATEGORY,
                                                value=run_id,
                                                aspects=aspects)
        mapping[RUN_ID_CATEGORY] = run_id

        rtnval = mapping
        return rtnval

    def read(self, *, vm: Any) -> Dict[str, str]:
        """
            Recover the neutral tag dict from a Prism VM entity.

            The ``codecraftai-run-id`` Category is dropped from the recovered
            dict so the round-trip is the identity on the caller-supplied
            neutral tags.

            :param vm: A :class:`NutanixVm` record.

            :returns: The recovered neutral flat tag dict.
        """
        rtnval: Dict[str, str] = {}

        raw = getattr(vm, "raw", None)
        if raw is None:
            return rtnval

        metadata = raw.get("metadata", {})
        categories_mapping = metadata.get("categories_mapping", None)
        if categories_mapping is None:
            categories_mapping = metadata.get("categories", None)
        if categories_mapping is None:
            return rtnval

        for key in sorted(categories_mapping.keys()):
            if key == RUN_ID_CATEGORY:
                continue
            values = categories_mapping[key]
            if isinstance(values, list):
                if len(values) > 0:
                    rtnval[key] = values[0]
            else:
                rtnval[key] = values

        return rtnval

    def run_id_of(self, *, vm: Any) -> str:
        """
            Extract the ``codecraftai-run-id`` Category value from a VM.

            :param vm: A :class:`NutanixVm` record.

            :returns: The run id string, or an empty string when absent.
        """
        rtnval = ""

        raw = getattr(vm, "raw", None)
        if raw is None:
            return rtnval

        metadata = raw.get("metadata", {})
        categories_mapping = metadata.get("categories_mapping", None)
        if categories_mapping is None:
            categories_mapping = metadata.get("categories", None)
        if categories_mapping is None:
            return rtnval

        values = categories_mapping.get(RUN_ID_CATEGORY, None)
        if values is None:
            return rtnval
        if isinstance(values, list):
            if len(values) > 0:
                rtnval = values[0]
        else:
            rtnval = values

        return rtnval
