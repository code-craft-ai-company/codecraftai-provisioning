"""
    .. module:: cloudkeypair
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral SSH key pair descriptor.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai.interfaces.schemaobject import SchemaObject
from ccai.interfaces.schemafield import Field

from ccai.interfaces.schemavalidationerror import SchemaValidationError
from ccai.interfaces.schemavalidators import validate_name


class CloudKeyPair(SchemaObject):
    """
        Venue-neutral SSH key pair descriptor.

        Holds public key material; private key handling is out of scope for the
        model layer.
    """

    name = Field(str, required=True)
    public_key_material = Field(str, required=True)

    def __init__(self, *, name: str, public_key_material: str) -> None:
        """
            Construct a CloudKeyPair.

            :param name: Key pair name.
            :param public_key_material: OpenSSH-format public key string.

            :raises: SchemaValidationError
        """
        validate_name(value=name)

        if public_key_material is None or len(public_key_material) == 0:
            raise SchemaValidationError("public_key_material must not be empty.")

        super().__init__(name=name, public_key_material=public_key_material)
        return
