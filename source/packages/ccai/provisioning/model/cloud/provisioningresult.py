"""
    .. module:: provisioningresult
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: ProvisioningResult — outcome of a single venue apply.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.restclient.base.schemaobject import SchemaObject
from ccai.restclient.base.schemafield import Field

from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)


class ProvisioningResult(SchemaObject):
    """
        Result of a single venue apply.

        Carries newly created resources, updated resources, the names of
        skipped (already-in-shape) resources, and an errors list for the
        partial-apply case.
    """

    created = Field(list, required=False, default=None)
    updated = Field(list, required=False, default=None)
    skipped = Field(list, required=False, default=None)
    errors = Field(list, required=False, default=None)

    def __init__(self, *,
                 created: Optional[List[ProvisionedResource]] = None,
                 updated: Optional[List[ProvisionedResource]] = None,
                 skipped: Optional[List[str]] = None,
                 errors: Optional[List[Dict[str, Any]]] = None) -> None:
        """
            Construct a ProvisioningResult.

            :param created: Newly created resources.
            :param updated: Updated resources.
            :param skipped: Names of resources that needed no change.
            :param errors: Per-resource error records (best-effort).
        """
        effective_created = created if created is not None else []
        effective_updated = updated if updated is not None else []
        effective_skipped = skipped if skipped is not None else []
        effective_errors = errors if errors is not None else []

        super().__init__(created=effective_created,
                         updated=effective_updated,
                         skipped=effective_skipped,
                         errors=effective_errors)
        return

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProvisioningResult":
        """
            Reconstruct a ProvisioningResult from a serialised payload.

            :param data: Serialised payload.

            :returns: A ProvisioningResult instance.
        """
        if not isinstance(data, dict):
            return data  # type: ignore

        def _promote(entries: Optional[List[Any]]) -> List[ProvisionedResource]:
            rtnval: List[ProvisionedResource] = []
            if entries is None:
                return rtnval
            for entry in entries:
                if isinstance(entry, ProvisionedResource):
                    rtnval.append(entry)
                else:
                    rtnval.append(ProvisionedResource.from_dict(entry))
            return rtnval

        promoted_created = _promote(data.get("created", None))
        promoted_updated = _promote(data.get("updated", None))

        rtnval = cls(created=promoted_created, updated=promoted_updated,
                     skipped=data.get("skipped", None),
                     errors=data.get("errors", None))
        return rtnval
