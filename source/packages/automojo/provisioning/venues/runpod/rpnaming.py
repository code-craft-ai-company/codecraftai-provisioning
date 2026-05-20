"""
    .. module:: rpnaming
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RunPod resource-naming helpers — every pod and volume is named
        with a ``<spec-name>-<run-id-short>`` prefix so a run's resources can
        be discovered and reclaimed.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


def pod_name(*, workload_name: str, run_id_short: str) -> str:
    """
        Compose the RunPod pod name for a workload.

        :param workload_name: The neutral workload name.
        :param run_id_short: The short run-id prefix.

        :returns: The composed pod name.
    """
    rtnval = "{}-{}".format(workload_name, run_id_short)
    return rtnval


def volume_name(*, volume_name_base: str, run_id_short: str) -> str:
    """
        Compose the RunPod network-volume name for a volume request.

        :param volume_name_base: The neutral volume name.
        :param run_id_short: The short run-id prefix.

        :returns: The composed volume name.
    """
    rtnval = "{}-{}".format(volume_name_base, run_id_short)
    return rtnval


def belongs_to_run(*, resource_name: str, run_id_short: str) -> bool:
    """
        Report whether a RunPod resource name belongs to a run.

        :param resource_name: The RunPod resource name.
        :param run_id_short: The short run-id prefix.

        :returns: ``True`` when the name carries the run-id suffix.
    """
    if resource_name is None:
        rtnval = False
        return rtnval

    suffix = "-{}".format(run_id_short)
    rtnval = resource_name.endswith(suffix)
    return rtnval


__all__ = ["pod_name", "volume_name", "belongs_to_run"]
