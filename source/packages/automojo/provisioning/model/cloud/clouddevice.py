

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional


class CloudDevice:
    """
    A class representing a cloud device.

        :param identifier: The unique identifier of the cloud device.
        :param category: The category of the cloud device.
        :param group: The group of the cloud device.
        :param profile: The profile of the cloud device.
        :param role: The role of the cloud device.
        :param tags: A list of tags to attach to the cloud device.
    """

    def __init__(self, *, identifier: str, category: str, group: str, profile: str, role: str, tags: Optional[List[Dict[str, str]]] = None):
        self._identifier = identifier
        self._category = category
        self._group = group
        self._profile = profile
        self._role = role
        self._tags = tags if tags is not None else []
        return
    
    @property
    def category(self) -> str:
        """
        Get the category of the cloud device.

        :return: The category of the cloud device.
        """
        return self._category
    
    @property
    def group(self) -> str:
        """
        Get the group of the cloud device.

        :return: The group of the cloud device.
        """
        return self._group
    
    @property
    def identifier(self) -> str:
        """
        Get the identifier of the cloud device.

        :return: The identifier of the cloud device.
        """
        return self._identifier
    
    @property
    def profile(self) -> str:
        """
        Get the profile of the cloud device.

        :return: The profile of the cloud device.
        """
        return self._profile
    
    @property
    def role(self) -> str:
        """
        Get the role of the cloud device.

        :return: The role of the cloud device.
        """
        return self._role

    @property
    def tags(self) -> List[Dict[str, str]]:
        """
        Get the tags of the cloud device.

        :return: The tags of the cloud device.
        """
        return self._tags
    
