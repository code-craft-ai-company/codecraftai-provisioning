"""
    .. module:: pvenaming
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared run-id / tag / VM-name helpers for the Proxmox VE
               venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


RUN_ID_TAG_PREFIX: str = "codecraftai-run-id="

OWNER_TAG: str = "codecraftai-owned-by=codecraftai-provisioning"


def run_id_tag(*, run_id: str) -> str:
    """
        Compose the per-run discriminator Proxmox tag.

        :param run_id: The provisioning run id.

        :returns: A tag string of the form ``codecraftai-run-id=<id>``.
    """
    rtnval = "{}{}".format(RUN_ID_TAG_PREFIX, run_id)
    return rtnval


def has_run_id_tag(*, tags: list, run_id: str) -> bool:
    """
        Return whether a Proxmox tag list carries the run-id tag.

        :param tags: The Proxmox tag-string list.
        :param run_id: The provisioning run id.

        :returns: ``True`` when the run-id tag is present.
    """
    wanted = run_id_tag(run_id=run_id)
    rtnval = False
    if tags is not None:
        if wanted in tags:
            rtnval = True
    return rtnval


def vm_name_for(*, spec_name: str, run_id: str) -> str:
    """
        Compose the venue-side VM name from a spec name and run id.

        Proxmox VM names must be DNS labels; the run-id short form is
        appended so plan / inventory ownership matching has a stable
        signal even before tags are read.

        :param spec_name: The neutral instance name.
        :param run_id: The provisioning run id.

        :returns: The composed venue-side VM name.
    """
    rtnval = "{}-{}".format(spec_name, run_id_short(run_id=run_id))
    return rtnval


def run_id_short(*, run_id: str) -> str:
    """
        Return the short form of a run id used in VM-name suffixes.

        :param run_id: The provisioning run id.

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
