"""
    .. module:: llnaming
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared run-id / instance-name helpers for the Lambda Labs
               venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


def run_id_short(*, run_id: str) -> str:
    """
        Return the short form of a run id used in instance-name suffixes.

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


def instance_name_for(*, spec_name: str, run_id: str) -> str:
    """
        Compose the venue-side instance name from a spec name and run id.

        Lambda Labs has no native tag field, so the run id is encoded into
        the instance ``name`` field as ``<spec-name>-<run-id-short>`` to
        make plan/inventory ownership matching possible.

        :param spec_name: The neutral instance name.
        :param run_id: The provisioning run id.

        :returns: The composed venue-side instance name.
    """
    rtnval = "{}-{}".format(spec_name, run_id_short(run_id=run_id))
    return rtnval
