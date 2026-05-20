"""
    .. module:: imageresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CloudImage → Azure Marketplace image SKU resolver.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Dict

from automojo.provisioning.model.cloud.cloudimage import CloudImage
from automojo.provisioning.venues.azure.azureerrors import AzureValidationError


# Family → (publisher, offer) for Azure Marketplace images.
_FAMILY_PUBLISHER_OFFER: Dict[str, Dict[str, str]] = {
    "ubuntu": {"publisher": "Canonical",
               "offer": "0001-com-ubuntu-server-jammy"},
    "debian": {"publisher": "Debian", "offer": "debian-12"},
    "rhel": {"publisher": "RedHat", "offer": "RHEL"},
    "windows-server": {"publisher": "MicrosoftWindowsServer",
                       "offer": "WindowsServer"},
}

# Per-family, per-version overrides for the offer field (Ubuntu pins the
# release codename into the offer string).
_UBUNTU_OFFER_BY_VERSION: Dict[str, str] = {
    "20.04": "0001-com-ubuntu-server-focal",
    "22.04": "0001-com-ubuntu-server-jammy",
    "24.04": "0001-com-ubuntu-server-noble",
}

# Per-family SKU templates.  ``{version}`` and ``{gen}`` are substituted.
_SKU_TEMPLATES: Dict[str, str] = {
    "ubuntu": "{version_token}-lts-gen2",
    "debian": "12-gen2",
    "rhel": "{version}-gen2",
    "windows-server": "{version}-datacenter-g2",
}


class ImageResolver:
    """
        Resolver from a venue-neutral :class:`CloudImage` to an Azure
        Marketplace image reference (publisher / offer / sku / version).

        The resolver is a pure table lookup; it performs no Azure calls so
        it is safe to use at ``validate`` time.
    """

    def resolve(self, *, image: CloudImage) -> Dict[str, str]:
        """
            Resolve the Azure image reference for a CloudImage.

            :param image: The neutral CloudImage.

            :returns: A dict with publisher, offer, sku, version keys.
            :raises: AzureValidationError
        """
        family = image.family
        version = image.version

        publisher_offer = _FAMILY_PUBLISHER_OFFER.get(family, None)
        if publisher_offer is None:
            err_msg_lines = ["Azure ImageResolver does not support family."]
            err_msg_lines.append("FAMILY: {}".format(family))
            err_msg_lines.append("SUPPORTED: {}".format(
                ", ".join(sorted(_FAMILY_PUBLISHER_OFFER.keys()))
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise AzureValidationError(err_msg)

        publisher = publisher_offer["publisher"]
        offer = publisher_offer["offer"]

        if family == "ubuntu":
            resolved_offer = _UBUNTU_OFFER_BY_VERSION.get(version, None)
            if resolved_offer is None:
                err_msg_lines = ["Azure ImageResolver: unknown Ubuntu version."]
                err_msg_lines.append("VERSION: {}".format(version))
                err_msg_lines.append("SUPPORTED: {}".format(
                    ", ".join(sorted(_UBUNTU_OFFER_BY_VERSION.keys()))
                ))
                err_msg = os.linesep.join(err_msg_lines)
                raise AzureValidationError(err_msg)
            offer = resolved_offer
            version_token = version.replace(".", "_")
            sku = _SKU_TEMPLATES["ubuntu"].format(version_token=version_token)
        else:
            sku = _SKU_TEMPLATES[family].format(version=version)

        out: Dict[str, str] = {}
        out["publisher"] = publisher
        out["offer"] = offer
        out["sku"] = sku
        out["version"] = "latest"
        rtnval = out
        return rtnval

    def image_reference(self, *, image: CloudImage) -> Dict[str, str]:
        """
            Return the Azure ``image_reference`` block for a VM create.

            :param image: The neutral CloudImage.

            :returns: A dict suitable for ``storage_profile.image_reference``.
            :raises: AzureValidationError
        """
        rtnval = self.resolve(image=image)
        return rtnval
