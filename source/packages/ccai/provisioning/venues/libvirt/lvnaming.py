"""
    .. module:: lvnaming
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shared run-id / resource-name helpers for the libvirt venue
               provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


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
        Compose the venue-side libvirt resource name from a spec name and
        run id.

        Every Domain / Network / Volume created by a run carries a stable
        name of the form ``<spec-name>-<run-id-short>`` so pre-create
        lookups by name can distinguish CREATE from SKIP.

        :param spec_name: The neutral resource name.
        :param run_id: The provisioning run id.

        :returns: The composed venue-side resource name.
    """
    rtnval = "{}-{}".format(spec_name, run_id_short(run_id=run_id))
    return rtnval


def seed_volume_name_for(*, instance_spec_name: str, run_id: str) -> str:
    """
        Compose the cloud-init seed-ISO volume name for a domain.

        :param instance_spec_name: The neutral instance name.
        :param run_id: The provisioning run id.

        :returns: The seed-ISO volume name.
    """
    base = resource_name_for(spec_name=instance_spec_name, run_id=run_id)
    rtnval = "{}-seed.iso".format(base)
    return rtnval


def boot_volume_name_for(*, instance_spec_name: str, run_id: str) -> str:
    """
        Compose the boot (root) volume name for a domain.

        :param instance_spec_name: The neutral instance name.
        :param run_id: The provisioning run id.

        :returns: The boot volume name.
    """
    base = resource_name_for(spec_name=instance_spec_name, run_id=run_id)
    rtnval = "{}-boot.qcow2".format(base)
    return rtnval
