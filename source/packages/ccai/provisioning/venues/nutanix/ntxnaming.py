"""
    .. module:: ntxnaming
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared run-id / resource-name helpers for the Nutanix venue
               provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


# Prism Category Name carrying the provisioning run id on owned entities.
RUN_ID_CATEGORY = "codecraftai-run-id"


def run_id_short(*, run_id: str) -> str:
    """
        Return the short form of a run id used in resource-name suffixes.

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


def resource_name_for(*, spec_name: str, run_id: str) -> str:
    """
        Compose the venue-side Prism resource name from a spec name and
        run id.

        Every VM / Subnet / VPC / Volume Group created by a run carries a
        stable name of the form ``<spec-name>-<run-id-short>`` so
        pre-create lookups by name can distinguish CREATE from SKIP.

        :param spec_name: The neutral resource name.
        :param run_id: The provisioning run id.

        :returns: The composed venue-side resource name.
    """
    rtnval = "{}-{}".format(spec_name, run_id_short(run_id=run_id))
    return rtnval
