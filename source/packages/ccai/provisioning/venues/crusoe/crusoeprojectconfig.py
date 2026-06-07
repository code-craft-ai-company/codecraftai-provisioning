"""
    .. module:: crusoeprojectconfig
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CrusoeProjectConfig — project id + default location + default
        labels bundle for the Crusoe venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Dict, List, Optional


class CrusoeProjectConfig:
    """
        Bundle describing where a :class:`CrusoeCloudProvisioner` operates.

        Crusoe Cloud groups resources under a project; this config holds the
        project identifier, the default location, and a list of default
        labels applied to every resource the venue creates.
    """

    def __init__(self, *, project_id: str, location: str,
                 default_labels: Optional[List[Dict[str, str]]] = None) -> None:
        """
            Construct a CrusoeProjectConfig.

            :param project_id: The Crusoe project identifier.
            :param location: Default Crusoe location (e.g. ``us-east1-a``).
            :param default_labels: Optional list of single-entry label dicts
                applied to every created resource.

            :raises: ValueError
        """
        if project_id is None or len(project_id) == 0:
            raise ValueError("CrusoeProjectConfig.project_id must not be empty.")
        if location is None or len(location) == 0:
            raise ValueError("CrusoeProjectConfig.location must not be empty.")

        effective_labels = default_labels if default_labels is not None else []

        self._project_id: str = project_id
        self._location: str = location
        self._default_labels: List[Dict[str, str]] = effective_labels
        return

    @property
    def project_id(self) -> str:
        """
            Return the Crusoe project identifier.

            :returns: The project id string.
        """
        rtnval = self._project_id
        return rtnval

    @property
    def location(self) -> str:
        """
            Return the default Crusoe location.

            :returns: The location string.
        """
        rtnval = self._location
        return rtnval

    @property
    def default_labels(self) -> List[Dict[str, str]]:
        """
            Return the list of default label dicts.

            :returns: A defensive copy of the default label list.
        """
        rtnval = list(self._default_labels)
        return rtnval
