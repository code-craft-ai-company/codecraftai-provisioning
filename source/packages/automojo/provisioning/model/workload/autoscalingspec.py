"""
    .. module:: autoscalingspec
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Autoscaling parameters for a WorkloadCluster.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.exceptions import SchemaValidationError


class AutoscalingSpec(SchemaObject):
    """
        Cluster autoscaling parameters.

        ``target_utilisation`` is a fraction in (0, 1].
    """

    min_nodes = Field(int, required=True)
    max_nodes = Field(int, required=True)
    target_utilisation = Field(float, required=True)

    def __init__(self, *, min_nodes: int, max_nodes: int,
                 target_utilisation: float) -> None:
        """
            Construct an AutoscalingSpec.

            :param min_nodes: Minimum node count; must be ≥ 0.
            :param max_nodes: Maximum node count; must be ≥ ``min_nodes``.
            :param target_utilisation: Target utilisation in (0, 1].

            :raises: SchemaValidationError
        """
        if min_nodes is None or not isinstance(min_nodes, int):
            raise SchemaValidationError("min_nodes must be an int.")

        if max_nodes is None or not isinstance(max_nodes, int):
            raise SchemaValidationError("max_nodes must be an int.")

        if min_nodes < 0:
            raise SchemaValidationError("min_nodes must be ≥ 0.")

        if max_nodes < min_nodes:
            raise SchemaValidationError(
                "max_nodes must be ≥ min_nodes (got {} < {}).".format(
                    max_nodes, min_nodes
                )
            )

        if target_utilisation is None or not isinstance(target_utilisation, float):
            raise SchemaValidationError(
                "target_utilisation must be a float."
            )

        if target_utilisation <= 0.0 or target_utilisation > 1.0:
            raise SchemaValidationError(
                "target_utilisation must be in (0, 1], got {}".format(
                    target_utilisation
                )
            )

        super().__init__(min_nodes=min_nodes, max_nodes=max_nodes,
                         target_utilisation=target_utilisation)
        return
