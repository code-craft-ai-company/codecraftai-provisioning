"""
    .. module:: cloudinitmerge
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Merge helper for venue-neutral cloud-init fragments.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import copy
import os

from typing import Any, Dict, Optional

from ccai.provisioning.cloudinit.cloudinitrenderererror import (
    CloudInitRendererError
)


def merge_cloud_init_fragments(*fragments: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
        Merge cloud-init fragments produced by the shared renderers.

        List-valued keys (``write_files``, ``runcmd``, ``packages``, ...)
        are concatenated in argument order, so bootstrap ordering follows
        the order the fragments are passed.  Scalar keys must agree
        across fragments; a conflict raises rather than silently picking
        a winner.  ``None`` fragments are skipped.

        :param fragments: Fragment dicts (or ``None``).

        :returns: A new merged dict; inputs are not mutated.

        :raises: CloudInitRendererError
    """
    rtnval: Dict[str, Any] = {}

    for fragment in fragments:
        if fragment is None:
            continue
        for key, value in fragment.items():
            if key not in rtnval:
                rtnval[key] = copy.deepcopy(value)
                continue

            existing = rtnval[key]
            if isinstance(existing, list) and isinstance(value, list):
                existing.extend(copy.deepcopy(value))
                continue

            if existing == value:
                continue

            err_msg_lines = ["Conflicting scalar value while merging cloud-init fragments."]
            err_msg_lines.append("KEY: {!r}".format(key))
            err_msg_lines.append("EXISTING: {!r}".format(existing))
            err_msg_lines.append("INCOMING: {!r}".format(value))
            err_msg = os.linesep.join(err_msg_lines)
            raise CloudInitRendererError(err_msg)

    return rtnval


__all__ = ["merge_cloud_init_fragments"]
