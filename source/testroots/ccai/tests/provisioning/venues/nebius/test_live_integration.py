"""
    .. module:: test_live_integration
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Gated end-to-end Nebius venue test against a sandbox project.

    This module is skipped unless ``RUN_LIVE_NEBIUS=1`` is set.  When
    enabled it requires ``NEBIUS_SA_TOKEN`` and ``NEBIUS_PARENT_ID`` and
    drives a real apply / inventory / destroy cycle against a Nebius
    sandbox project.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai.errors.exceptions import SkipError


import os


from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.venues.nebius.nebiuscloudprovisioner import (
    NebiusCloudProvisioner
)

from ._specfactory import basic_spec


_RUN_LIVE = os.environ.get("RUN_LIVE_NEBIUS", "0") == "1"


def test_live_apply_inventory_destroy() -> None:
    """
        Apply, inventory, and destroy a minimal spec against a real Nebius
        sandbox project.
    """
    if not _RUN_LIVE:
        raise SkipError("RUN_LIVE_NEBIUS != 1; live test skipped.")

    token = os.environ.get("NEBIUS_SA_TOKEN", None)
    parent_id = os.environ.get("NEBIUS_PARENT_ID", None)
    if token is None or parent_id is None:
        raise SkipError("NEBIUS_SA_TOKEN / NEBIUS_PARENT_ID are not set.")

    from ccai.credentials.nebiusserviceaccountcredential import (
        NebiusServiceAccountCredential
    )
    from ccai.restclient.nebius.nebiusclient import NebiusClient

    credential = NebiusServiceAccountCredential(
        identifier="nebius-live", categories=["hpc-venue"], token=token,
    )
    client = NebiusClient(credential=credential)

    spec = basic_spec()
    spec.parent_id = parent_id

    venue = CloudVenue(
        name="nebius-live", provider="nebius",
        account=parent_id, region="eu-north1",
        credential="nebius-live",
    )
    aspects = ProvisioningAspects(runid="liverun01")
    confirm = ProvisioningAspects(runid="liverun01", confirm=True)

    provisioner = NebiusCloudProvisioner(venue=venue, client=client,
                                         spec=spec)
    try:
        provisioner.validate(aspects=aspects)
        provisioner.apply(aspects=aspects)
        inventory = provisioner.inventory(aspects=aspects)
        assert len(inventory) > 0
    finally:
        provisioner.destroy(aspects=confirm)
    return
