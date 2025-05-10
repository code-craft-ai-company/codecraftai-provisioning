
__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional


class CloudGroup:
    """
    A class representing a group of cloud resources.
    """

    def __init__(self, *, name: str, description: str, tags: Optional[List[Dict[str, str]]] = None):
        """
        Initialize a CloudGroup instance.

        :param name: The name of the cloud group.
        :param description: An optional description of the cloud group.
        :param tags: An optional list of tags to attach to the cloud group.

        """
        self._name = name
        self._description = description
        self._tags = tags if tags is not None else []
        return

    @property
    def description(self) -> str:
        """
        Get the description of the cloud group.

        :return: The description of the cloud group.
        """
        return self._description
    
    @property
    def name(self) -> str:
        """
        Get the name of the cloud group.

        :return: The name of the cloud group.
        """
        return self._name
    
    @property
    def tags(self) -> List[Dict[str, str]]:
        """
        Get the tags of the cloud group.

        :return: The tags of the cloud group.
        """
        return self._tags
    
