"""
    .. module:: cloudinitrenderererror
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception type for cloud-init renderer failures.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


class CloudInitRendererError(ValueError):
    """
        Raised when an unsupported image family is requested or the renderer
        cannot produce a valid payload.
    """
