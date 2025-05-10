
__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Automation Mojo LLC"
__credits__ = []


import yaml

from automojo.provisioning.model.cloud.cloudvenue import CloudVenue

class ProvisioningEngine:
    """
    The ProvisioningEngine class is responsible for managing the provisioning of resources.
    It handles the creation, deletion, and management of resources in a cloud environment.
    """

    def __init__(self, *, specinfo: dict):
        """
        Initializes the ProvisioningEngine instance.
        """
        self._specinfo = specinfo
        
        self._apodinfo = specinfo["apod"]
        self._envinfo = specinfo["environment"]
        
        self._cloud_venues = []
        if "venues" in self._envinfo:
            venues_list = self._envinfo["venues"]
            for venue in venues_list:
                self._cloud_venues.append(CloudVenue(**venue))

        self._cloud_groups = []
        if "groups" in self._envinfo:
            groups_list = self._envinfo["groups"]
            for group in groups_list:
                self._cloud_groups.append(group)

        self._cloud_resource_profiles = []
        if "profiles" in self._specinfo:
            profiles_list = self._specinfo["profiles"]
            for profile in profiles_list:
                self._cloud_resource_profiles.append(profile)

        self._cloud_devices = []
        if "devices" in self._apodinfo:
            devices_list = self._apodinfo["devices"]
            for device in devices_list:
                self._cloud_devices.append(device)

        self._cloud_provisioners = []

        return

    @classmethod
    def create_provisioning_engine(cls, specification: str) -> "ProvisioningEngine":
        """
        Create a new ProvisioningEngine instance.

        :param specification: The path to a specification file to use when creating the provisioning engine.

        :return: A new ProvisioningEngine instance.
        """
        pengine = None
        specinfo = None

        if specification is not None:
            with open(specification, "r") as specfile:
                specinfo = yaml.safe_load(specfile)
            
            pengine = cls(specinfo=specinfo)

        else:
            raise ValueError("Specification file path is required.")

        return pengine