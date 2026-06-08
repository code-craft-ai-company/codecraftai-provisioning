"""
    .. module:: cloudresourcekind
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Typed discriminator enum for CloudResourceProfile.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from enum import Enum


class CloudResourceKind(str, Enum):
    """
        Discriminator for the kind of resource a CloudResourceProfile describes.
    """
    NETWORK = "network"
    SUBNET = "subnet"
    SECURITY_GROUP = "sg"
    KEYPAIR = "keypair"
    IMAGE = "image"
    INSTANCE = "instance"
    VOLUME = "volume"
    BUCKET = "bucket"
    LOAD_BALANCER = "lb"
    DNS_RECORD = "dns"
