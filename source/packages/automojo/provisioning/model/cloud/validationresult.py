"""
    .. module:: validationresult
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: ValidationResult record summarising lifecycle validation outcome.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field


class ValidationResult(SchemaObject):
    """
        Outcome of CloudProvisioner.validate.

        Subclasses raise SchemaSemanticError on failure; this dataclass
        exists so callers that want a structured success record (instead of
        the implicit None) can request it via aspects.
    """

    ok = Field(bool, required=True)
    errors = Field(list, required=False, default=None)
    warnings = Field(list, required=False, default=None)

    def __init__(self, *, ok: bool,
                 errors: Optional[List[Dict[str, Any]]] = None,
                 warnings: Optional[List[Dict[str, Any]]] = None) -> None:
        """
            Construct a ValidationResult.

            :param ok: True when validation succeeded.
            :param errors: Optional list of structured error records.
            :param warnings: Optional list of structured warning records.
        """
        effective_errors = errors if errors is not None else []
        effective_warnings = warnings if warnings is not None else []
        super().__init__(ok=ok, errors=effective_errors,
                         warnings=effective_warnings)
        return
