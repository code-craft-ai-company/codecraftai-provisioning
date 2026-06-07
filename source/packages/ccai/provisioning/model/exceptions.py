"""
    .. module:: exceptions
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the provisioning model layer.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []

from ccai.errors.exceptions import SemanticError


class SchemaValidationError(ValueError):
    """
        Raised when a model object fails *shape* validation at construction time.

        Shape validation covers type membership, enum membership, parseable CIDRs,
        monotonic port ranges, non-empty required strings, and similar
        local-to-the-object checks.
    """


class SchemaSemanticError(SemanticError):
    """
        Raised when a model object fails *cross-resource* semantic validation.

        Semantic validation includes subnet-in-network containment, sibling-subnet
        non-overlap, accelerator support on the chosen venue, and other invariants
        that require looking across more than one object.

        This derives from :class:`ccai.errors.exceptions.SemanticError` (which
        is rooted at ``BaseException``) so that an ordinary ``except Exception`` or
        ``except RuntimeError`` does NOT silently swallow a semantic-validation
        failure. Per the project coding standards, ``SemanticError`` must never be
        caught -- it always bubbles.
    """
