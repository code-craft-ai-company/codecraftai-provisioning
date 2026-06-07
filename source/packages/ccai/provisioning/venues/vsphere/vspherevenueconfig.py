"""
    .. module:: vspherevenueconfig
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: VSphereVenueConfig — placement + connection bundle for the
        VSphere venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Dict, List, Optional


class VSphereVenueConfig:
    """
        Bundle describing where a :class:`VSphereCloudProvisioner` operates.

        Holds the vCenter connection details, the default placement targets
        (datacenter / cluster / folder), the content-library scope used for
        image resolution, an NSX-presence flag, and a list of default tags
        applied to every resource the venue creates.
    """

    def __init__(self, *, host: str, datacenter: str, cluster: str,
                 folder: str, port: Optional[int] = None,
                 content_library_ids: Optional[List[str]] = None,
                 template_folder: Optional[str] = None,
                 nsx_available: bool = False,
                 subnet_vlan_ids: Optional[Dict[str, int]] = None,
                 default_tags: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a VSphereVenueConfig.

            :param host: vCenter hostname or IP.
            :param datacenter: Datacenter name VMs are placed into.
            :param cluster: Cluster name VMs are placed into.
            :param folder: VM folder path for created VMs.
            :param port: Optional non-default vCenter port.
            :param content_library_ids: Optional content-library ids used as
                                        the image-resolution search scope.
            :param template_folder: Optional folder scanned for VM templates
                                    when no content-library item matches.
            :param nsx_available: True when NSX-T is present; gates
                                  CloudSecurityGroup / CloudLoadBalancer.
            :param subnet_vlan_ids: Optional mapping ``subnet_name -> vlan_id``
                                    used when realising distributed port
                                    groups.
            :param default_tags: Optional flat dict of tag key/value pairs
                                  applied to every created resource.

            :raises: ValueError
        """
        if host is None or len(host) == 0:
            raise ValueError("VSphereVenueConfig.host must not be empty.")
        if datacenter is None or len(datacenter) == 0:
            raise ValueError("VSphereVenueConfig.datacenter must not be empty.")
        if cluster is None or len(cluster) == 0:
            raise ValueError("VSphereVenueConfig.cluster must not be empty.")
        if folder is None or len(folder) == 0:
            raise ValueError("VSphereVenueConfig.folder must not be empty.")

        effective_library_ids = content_library_ids if content_library_ids is not None else []
        effective_vlan_ids = subnet_vlan_ids if subnet_vlan_ids is not None else {}
        effective_default_tags = default_tags if default_tags is not None else {}

        self._host: str = host
        self._datacenter: str = datacenter
        self._cluster: str = cluster
        self._folder: str = folder
        self._port: Optional[int] = port
        self._content_library_ids: List[str] = effective_library_ids
        self._template_folder: Optional[str] = template_folder
        self._nsx_available: bool = nsx_available
        self._subnet_vlan_ids: Dict[str, int] = effective_vlan_ids
        self._default_tags: Dict[str, str] = effective_default_tags
        return

    @property
    def host(self) -> str:
        """
            Return the vCenter host.

            :returns: The host string.
        """
        rtnval = self._host
        return rtnval

    @property
    def datacenter(self) -> str:
        """
            Return the placement datacenter name.

            :returns: The datacenter name.
        """
        rtnval = self._datacenter
        return rtnval

    @property
    def cluster(self) -> str:
        """
            Return the placement cluster name.

            :returns: The cluster name.
        """
        rtnval = self._cluster
        return rtnval

    @property
    def folder(self) -> str:
        """
            Return the VM folder path.

            :returns: The folder path.
        """
        rtnval = self._folder
        return rtnval

    @property
    def port(self) -> Optional[int]:
        """
            Return the optional vCenter port.

            :returns: The port number or None.
        """
        rtnval = self._port
        return rtnval

    @property
    def content_library_ids(self) -> List[str]:
        """
            Return the content-library search scope.

            :returns: A defensive copy of the library id list.
        """
        rtnval = list(self._content_library_ids)
        return rtnval

    @property
    def template_folder(self) -> Optional[str]:
        """
            Return the VM-template fallback folder.

            :returns: The folder path or None.
        """
        rtnval = self._template_folder
        return rtnval

    @property
    def nsx_available(self) -> bool:
        """
            Return whether NSX-T is present in this venue.

            :returns: True when NSX is available.
        """
        rtnval = self._nsx_available
        return rtnval

    @property
    def subnet_vlan_ids(self) -> Dict[str, int]:
        """
            Return the subnet-name to VLAN-id mapping.

            :returns: A defensive copy of the VLAN id mapping.
        """
        rtnval = dict(self._subnet_vlan_ids)
        return rtnval

    @property
    def default_tags(self) -> Dict[str, str]:
        """
            Return the list of default tag dicts.

            :returns: A defensive copy of the default tag list.
        """
        rtnval = dict(self._default_tags)
        return rtnval
