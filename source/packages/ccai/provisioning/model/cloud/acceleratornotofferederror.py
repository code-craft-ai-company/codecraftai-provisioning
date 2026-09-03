"""
    .. module:: acceleratornotofferederror
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Error raised when a catalogued accelerator has no SKU on a venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai.provisioning.model.cloud.notofferedonvenueerror import (
    NotOfferedOnVenueError
)


class AcceleratorNotOfferedOnVenueError(NotOfferedOnVenueError):
    """
        Raised when the accelerator catalog holds the requested neutral name
        but the requested venue publishes no SKU for it.

        This is a *validation finding* about a spec/venue pairing, not a code
        defect: the caller asked a well-formed question ("does this venue
        offer an H100?") and the answer is simply "no".  A venue's
        ``validate`` may therefore catch it and accumulate it alongside the
        other findings for the spec, so an operator sees every problem in one
        pass.

        It derives from :class:`NotOfferedOnVenueError` (ultimately an
        ordinary :class:`ValueError`) precisely so that it CAN be handled.
        Contrast
        with :class:`SchemaSemanticError`, which the catalog still raises when
        the neutral name is not in the catalog at all -- that means the caller
        was given, or wrote, information the code cannot rely on, and it
        derives from ``BaseException`` so that it halts the run rather than
        being aggregated into a report.  Do not merge these two conditions
        back into one exception type.
    """


__all__ = ["AcceleratorNotOfferedOnVenueError"]
