"""
    .. module:: gcpidempotency
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Read-by-label helpers for idempotent GCP resource lookup.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Dict, Optional

from ccai.provisioning.venues.google.gcptagging import (
    OWNER_LABEL_KEY, OWNER_LABEL_VALUE, RESOURCE_NAME_LABEL_KEY,
    RUN_ID_LABEL_KEY
)


def owner_label_filter(*, run_id: str,
                       resource_name: Optional[str] = None) -> str:
    """
        Build a GCP ``list`` filter expression selecting owner+run+name.

        :param run_id: The provisioning run identifier.
        :param resource_name: Optional neutral resource name.

        :returns: A GCP API list-filter expression string.
    """
    clauses = [
        "labels.{}={}".format(OWNER_LABEL_KEY, OWNER_LABEL_VALUE),
        "labels.{}={}".format(RUN_ID_LABEL_KEY, run_id),
    ]
    if resource_name is not None:
        clauses.append("labels.{}={}".format(RESOURCE_NAME_LABEL_KEY,
                                             resource_name))
    rtnval = " AND ".join(clauses)
    return rtnval


def is_owned(*, labels: Optional[Dict[str, str]]) -> bool:
    """
        Check whether a labels mapping carries the owner-label pair.

        :param labels: GCP labels mapping or None.

        :returns: True when owned by codecraftai-provisioning.
    """
    if labels is None:
        rtnval = False
        return rtnval
    rtnval = labels.get(OWNER_LABEL_KEY, None) == OWNER_LABEL_VALUE
    return rtnval


def belongs_to_run(*, labels: Optional[Dict[str, str]],
                   run_id: str) -> bool:
    """
        Check whether a labels mapping carries the (owner, run-id) pair.

        :param labels: GCP labels mapping or None.
        :param run_id: Expected run-id value.

        :returns: True when owned by ccai and matching the run id.
    """
    if labels is None:
        rtnval = False
        return rtnval
    if labels.get(OWNER_LABEL_KEY, None) != OWNER_LABEL_VALUE:
        rtnval = False
        return rtnval
    rtnval = labels.get(RUN_ID_LABEL_KEY, None) == run_id
    return rtnval
