"""
    .. module:: notofferedonvenueerror
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Base error for "this venue does not offer that" findings.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai.interfaces.schemavalidationerror import SchemaValidationError


class NotOfferedOnVenueError(SchemaValidationError):
    """
        Base for findings of the form "the requested item is known, but this
        venue does not offer it".

        These are *validation findings* about a spec/venue pairing, not code
        defects: the caller asked a well-formed question and the answer is
        simply "not here".  A venue's ``validate`` may therefore catch one and
        accumulate it alongside the spec's other findings, so an operator sees
        every problem in one pass.

        This derives from :class:`SchemaValidationError` (an ordinary
        :class:`ValueError`) precisely so that it CAN be handled.  Contrast
        with :class:`SchemaSemanticError`, which is still raised when the
        requested item is not a known item at all -- that means the spec
        carries information the run cannot rely on, and it derives from
        ``BaseException`` so it halts the run rather than being folded into a
        report.  Do not merge the two conditions back into one type.
    """


__all__ = ["NotOfferedOnVenueError"]
