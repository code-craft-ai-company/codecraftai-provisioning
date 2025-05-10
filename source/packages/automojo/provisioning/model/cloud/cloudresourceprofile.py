
__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional


class CloudResourceProfile:
    """
    A class to represent a cloud resource profile.

    :param name: The name of the cloud resource profile.
    :param description: A brief description of the cloud resource profile.
    :param credential: The credential used when creating the cloud resource.
    :param parameters: A dictionary of parameters used for the creation of a cloud resource.
    :param tags: A list of tags to attach to cloud resources created using this profile.
    """

    def __init__(self, *, name: str, description: str, credential: str, parameters: Dict[str, Any], tags: Optional[List[Dict[str, str]]] = None):
        self._name = name
        self._description = description
        self._credential = credential
        self._parameters = parameters
        self._tags = tags if tags is not None else []
        return
    
    @property
    def credential(self) -> str:
        """
        Get the credential used when creating the cloud resource.

        :return: The credential used when creating the cloud resource.
        """
        return self._credential

    @property
    def description(self) -> str:
        """
        Get the description of the cloud resource profile.

        :return: The description of the cloud resource profile.
        """
        return self._description
    
    @property
    def name(self) -> str:
        """
        Get the name of the cloud resource profile.

        :return: The name of the cloud resource profile.
        """
        return self._name

    @property
    def parameters(self) -> Dict[str, Any]:
        """
        Get the parameters of the cloud resource profile.

        :return: The parameters of the cloud resource profile.
        """
        return self._parameters

    @property
    def tags(self) -> List[Dict[str, str]]:
        """
        Get the tags of the cloud resource profile.

        :return: The tags of the cloud resource profile.
        """
        return self._tags
    
