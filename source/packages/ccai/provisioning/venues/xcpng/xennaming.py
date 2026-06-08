"""
    .. module:: xennaming
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared run-id / VM-name helpers for the XCP-ng venue
        provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


def run_id_short(*, run_id: str) -> str:
    """
        Return the short form of a run id used in VM-name suffixes.

        :param run_id: The full provisioning run id.

        :returns: The first eight characters of the run id.
    """
    if run_id is None:
        rtnval = "run"
        return rtnval
    if len(run_id) <= 8:
        rtnval = run_id
        return rtnval
    rtnval = run_id[:8]
    return rtnval


def vm_name_for(*, spec_name: str, run_id: str) -> str:
    """
        Compose the venue-side VM name_label from a spec name and run id.

        The run id is encoded into the VM ``name_label`` as
        ``<spec-name>-<run-id-short>`` so plan / inventory ownership matching
        is possible without first reading ``other_config``.

        :param spec_name: The neutral instance name.
        :param run_id: The provisioning run id.

        :returns: The composed venue-side VM name_label.
    """
    rtnval = "{}-{}".format(spec_name, run_id_short(run_id=run_id))
    return rtnval


def volume_name_for(*, spec_name: str, run_id: str) -> str:
    """
        Compose the venue-side VDI name_label from a spec name and run id.

        :param spec_name: The neutral volume name.
        :param run_id: The provisioning run id.

        :returns: The composed venue-side VDI name_label.
    """
    rtnval = "{}-{}".format(spec_name, run_id_short(run_id=run_id))
    return rtnval
