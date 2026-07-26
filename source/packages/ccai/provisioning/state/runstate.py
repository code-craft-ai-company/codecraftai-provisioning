"""
    .. module:: runstate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RunState — full persisted state of a single provisioning run.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.interfaces.schemaobject import SchemaObject
from ccai.interfaces.schemafield import Field

from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.model.cloud.provisioningresult import (
    ProvisioningResult
)


class RunState(SchemaObject):
    """
        Full persisted state of a provisioning run.

        ``spec`` is the normalised input spec dict.  ``plan`` is the
        per-venue plan dict.  ``results`` maps venue_name -> ProvisioningResult.
        ``inventory`` maps venue_name -> List[ProvisionedResource].
    """

    runid = Field(str, required=True)
    spec = Field(dict, required=False, default=None)
    plan = Field(dict, required=False, default=None)
    results = Field(dict, required=False, default=None)
    inventory = Field(dict, required=False, default=None)

    def __init__(self, *, runid: str,
                 spec: Optional[Dict[str, Any]] = None,
                 plan: Optional[Dict[str, Any]] = None,
                 results: Optional[Dict[str, ProvisioningResult]] = None,
                 inventory: Optional[
                     Dict[str, List[ProvisionedResource]]
                 ] = None) -> None:
        """
            Construct a RunState.

            :param runid: Run identifier.
            :param spec: Normalised spec dict.
            :param plan: PipelinePlan-shaped dict.
            :param results: Per-venue ProvisioningResult map.
            :param inventory: Per-venue resource list map.
        """
        effective_spec = spec if spec is not None else {}
        effective_plan = plan if plan is not None else {}
        effective_results = results if results is not None else {}
        effective_inv = inventory if inventory is not None else {}

        super().__init__(runid=runid, spec=effective_spec,
                         plan=effective_plan,
                         results=effective_results,
                         inventory=effective_inv)
        return
