"""
    .. module:: hetznerlocationconfig
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: HetznerLocationConfig — location + default labels bundle.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Dict, Optional


HETZNER_LOCATIONS = frozenset({"nbg1", "fsn1", "hel1", "ash", "hil", "sin"})


class HetznerLocationConfig:
    """
        Bundle describing where a :class:`HetznerCloudProvisioner` operates.

        Holds the default Hetzner location slug and a list of default labels
        applied to every resource the venue creates.
    """

    def __init__(self, *, location: str,
                 default_labels: Optional[Dict[str, str]] = None
                 ) -> None:
        """
            Construct a HetznerLocationConfig.

            :param location: Hetzner location slug (e.g. ``nbg1``).
            :param default_labels: Optional flat dict of label key/value pairs
                                   applied to every created resource.

            :raises: ValueError
        """
        if location is None or len(location) == 0:
            raise ValueError("HetznerLocationConfig.location must not be empty.")

        if location not in HETZNER_LOCATIONS:
            raise ValueError(
                "HetznerLocationConfig.location {!r} is not a known Hetzner "
                "location slug.".format(location)
            )

        effective_labels = default_labels if default_labels is not None else {}

        self._location: str = location
        self._default_labels: Dict[str, str] = effective_labels
        return

    @property
    def location(self) -> str:
        """
            Return the default Hetzner location slug.

            :returns: The location string.
        """
        rtnval = self._location
        return rtnval

    @property
    def default_labels(self) -> Dict[str, str]:
        """
            Return the flat dict of default labels.

            :returns: A defensive copy of the default label dict.
        """
        rtnval = dict(self._default_labels)
        return rtnval
