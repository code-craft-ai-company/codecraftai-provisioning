"""
    .. module:: imagefamilynotofferederror
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Error raised when a venue cannot serve a canonical image family.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai.provisioning.model.cloud.notofferedonvenueerror import (
    NotOfferedOnVenueError
)


class ImageFamilyNotOfferedOnVenueError(NotOfferedOnVenueError):
    """
        Raised when an image family normalises to a canonical
        :class:`ImageFamily` member that the requested venue cannot serve.

        The family is real; this venue simply publishes no image for it.  That
        is a validation finding about a spec/venue pairing, so a venue's
        ``validate`` may aggregate it into its report.

        A family string that does not normalise to any canonical member is a
        different condition: :func:`normalize_family` raises
        :class:`SchemaSemanticError` for it, which derives from
        ``BaseException`` and halts, because the spec then names something
        that does not exist.
    """


__all__ = ["ImageFamilyNotOfferedOnVenueError"]
