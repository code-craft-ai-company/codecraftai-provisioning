"""
    .. module:: metalprojectconfig
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MetalProjectConfig — project id + metro + default tags bundle.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Dict, List, Optional


class MetalProjectConfig:
    """
        Bundle describing where an :class:`EquinixMetalCloudProvisioner`
        operates.

        Holds the Equinix Metal project id, the default metro slug, and a
        list of default tags applied to every resource the venue creates.
        The Project is the apex container; the provisioner does not create
        it, it operates within an existing project.
    """

    def __init__(self, *, project_id: str, metro: str,
                 default_tags: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a MetalProjectConfig.

            :param project_id: Equinix Metal project identifier.
            :param metro: Default Equinix metro slug (e.g. ``sv``).
            :param default_tags: Optional flat dict of tag key/value pairs to
                                 apply to every created resource.
        """
        if project_id is None or len(project_id) == 0:
            raise ValueError("MetalProjectConfig.project_id must not be empty.")

        if metro is None or len(metro) == 0:
            raise ValueError("MetalProjectConfig.metro must not be empty.")

        effective_tags = default_tags if default_tags is not None else {}

        self._project_id: str = project_id
        self._metro: str = metro
        self._default_tags: Dict[str, str] = effective_tags
        return

    @property
    def project_id(self) -> str:
        """
            Return the Equinix Metal project id.

            :returns: The project id string.
        """
        rtnval = self._project_id
        return rtnval

    @property
    def metro(self) -> str:
        """
            Return the default metro slug.

            :returns: The metro slug string.
        """
        rtnval = self._metro
        return rtnval

    @property
    def default_tags(self) -> Dict[str, str]:
        """
            Return the list of default tag dicts.

            :returns: A defensive copy of the default tag list.
        """
        rtnval = dict(self._default_tags)
        return rtnval
