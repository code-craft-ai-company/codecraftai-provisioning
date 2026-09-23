"""
    .. module:: venuecapability
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue accelerator / interconnect / shared-fs capability descriptor.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import List, Optional


class VenueCapability:
    """
        Immutable descriptor of what a single provisioning venue supports for
        HPC / AI workloads.

        The accelerator-and-interconnect design (see ``Venue Support Matrix``
        section) keeps the support matrix as *data*, not code: each venue plugin
        publishes a :class:`VenueCapability` and the lifecycle ``validate`` stage
        consults it instead of hard-coding venue knowledge.

        This class is the stub the lifecycle ``validate`` consults; a venue
        plugin overrides :func:`venue_capability` (or registers a richer
        capability) once its real matrix is wired in.
    """

    def __init__(self, *, venue: str,
                 interconnect_kinds: Optional[List[str]] = None,
                 accelerator_models: Optional[List[str]] = None,
                 shared_fs_attach_kinds: Optional[List[str]] = None,
                 shared_fs_provision_kinds: Optional[List[str]] = None) -> None:
        """
            Construct a VenueCapability descriptor.

            :param venue: The provisioning venue name.
            :param interconnect_kinds: Interconnect kinds the venue supports.
            :param accelerator_models: Neutral accelerator model names the venue
                                       supports; ``None`` means "consult the
                                       catalog" (no venue-side restriction).
            :param shared_fs_attach_kinds: Shared-fs kinds the venue can attach.
            :param shared_fs_provision_kinds: Shared-fs kinds the venue can
                                              provision from scratch.
        """
        self._venue = venue
        self._interconnect_kinds = list(interconnect_kinds) if interconnect_kinds is not None else []
        self._accelerator_models = list(accelerator_models) if accelerator_models is not None else None
        self._shared_fs_attach_kinds = list(shared_fs_attach_kinds) if shared_fs_attach_kinds is not None else []
        self._shared_fs_provision_kinds = list(shared_fs_provision_kinds) if shared_fs_provision_kinds is not None else []
        return

    @property
    def venue(self) -> str:
        """
            The provisioning venue name.
        """
        return self._venue

    @property
    def interconnect_kinds(self) -> List[str]:
        """
            Interconnect kinds the venue supports.
        """
        return list(self._interconnect_kinds)

    @property
    def accelerator_models(self) -> Optional[List[str]]:
        """
            Neutral accelerator model names the venue supports, or ``None`` when
            the venue places no restriction beyond catalog membership.
        """
        if self._accelerator_models is None:
            return None
        return list(self._accelerator_models)

    @property
    def shared_fs_attach_kinds(self) -> List[str]:
        """
            Shared-fs kinds the venue can attach.
        """
        return list(self._shared_fs_attach_kinds)

    @property
    def shared_fs_provision_kinds(self) -> List[str]:
        """
            Shared-fs kinds the venue can provision from scratch.
        """
        return list(self._shared_fs_provision_kinds)

    def supports_interconnect(self, *, kind: str) -> bool:
        """
            Answer whether the venue supports an interconnect kind.

            :param kind: The interconnect kind to check.

            :returns: True when the kind is supported.
        """
        rtnval = kind in self._interconnect_kinds
        return rtnval

    def supports_accelerator(self, *, model: str) -> bool:
        """
            Answer whether the venue supports a neutral accelerator model.

            :param model: The neutral accelerator model name to check.

            :returns: True when the venue places no restriction or the model is
                      in the supported list.
        """
        if self._accelerator_models is None:
            return True
        rtnval = model in self._accelerator_models
        return rtnval


def venue_capability(*, venue: str) -> VenueCapability:
    """
        Return the capability descriptor consulted by lifecycle ``validate``.

        This is the stub entry point.  Until a venue plugin publishes its real
        matrix via ``venue_capabilities()``, this returns an empty-matrix
        :class:`VenueCapability` so that a venue with no published support
        rejects every accelerator / interconnect request during ``validate``.

        :param venue: The provisioning venue name.

        :returns: A VenueCapability for the venue.
    """
    rtnval = VenueCapability(venue=venue)
    return rtnval
