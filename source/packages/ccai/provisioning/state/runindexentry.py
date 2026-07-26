"""
    .. module:: runindexentry
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RunIndexEntry — one line in the runs index.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import List, Optional, Union

from ccai.interfaces.schemaobject import SchemaObject
from ccai.interfaces.schemafield import Field

from ccai.provisioning.state.runstatus import RunStatus


class RunIndexEntry(SchemaObject):
    """
        One entry in ``.output/provisioning/index.yaml``.

        Carries the runid, the started/finished timestamps as ISO-8601
        strings, the current status, the source spec path, and the venue
        list the run targeted.
    """

    runid = Field(str, required=True)
    started = Field(str, required=True)
    finished = Field(str, required=False, default=None)
    status = Field(str, required=True)
    spec_path = Field(str, required=False, default=None)
    venues = Field(list, required=False, default=None)

    def __init__(self, *, runid: str, started: str,
                 status: Union[RunStatus, str],
                 finished: Optional[str] = None,
                 spec_path: Optional[str] = None,
                 venues: Optional[List[str]] = None) -> None:
        """
            Construct a RunIndexEntry.

            :param runid: Run identifier.
            :param started: ISO-8601 start timestamp.
            :param status: A RunStatus value (or its string form).
            :param finished: Optional ISO-8601 finish timestamp.
            :param spec_path: Source spec path.
            :param venues: Venue names targeted.
        """
        if isinstance(status, RunStatus):
            status_value = status.value
        else:
            status_value = RunStatus(status).value

        effective_venues = venues if venues is not None else []

        super().__init__(runid=runid, started=started, finished=finished,
                         status=status_value, spec_path=spec_path,
                         venues=effective_venues)
        return
