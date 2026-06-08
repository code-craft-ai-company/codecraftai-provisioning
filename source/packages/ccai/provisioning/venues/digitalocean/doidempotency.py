"""
    .. module:: doidempotency
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Read-by-tag helpers for idempotent DigitalOcean resource lookup.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import List, Optional

from ccai.provisioning.venues.digitalocean.dotagtranslator import (
    OWNER_TAG_KEY, OWNER_TAG_VALUE, RESOURCE_NAME_TAG_KEY, RUN_ID_TAG_KEY,
    to_flat
)


def run_tag_string(*, run_id: str) -> str:
    """
        Return the encoded run-id tag string used for ``tag_name`` queries.

        DigitalOcean list endpoints accept a single ``tag_name`` filter; the
        venue tags every resource with the encoded run-id pair and filters on
        it for read-before-create.

        :param run_id: The provisioning run identifier.

        :returns: The encoded ``ccai:owner=<run-id>`` tag string.
    """
    from ccai.provisioning.venues.digitalocean.dotagtranslator import (
        _escape
    )
    rtnval = "{}={}".format(_escape(value=RUN_ID_TAG_KEY),
                            _escape(value=run_id))
    return rtnval


def is_owned(*, do_tags: Optional[List[str]]) -> bool:
    """
        Check whether a DigitalOcean tag list carries the owner-tag pair.

        :param do_tags: DigitalOcean tag string-list.

        :returns: True when owned by codecraftai-provisioning.
    """
    flat = to_flat(do_tags=do_tags)
    rtnval = flat.get(OWNER_TAG_KEY, None) == OWNER_TAG_VALUE
    return rtnval


def belongs_to_run(*, do_tags: Optional[List[str]], run_id: str) -> bool:
    """
        Check whether a DigitalOcean tag list carries the (owner, run-id)
        pair.

        :param do_tags: DigitalOcean tag string-list.
        :param run_id: Expected run-id value.

        :returns: True when owned by ccai and matching the run id.
    """
    flat = to_flat(do_tags=do_tags)
    if flat.get(OWNER_TAG_KEY, None) != OWNER_TAG_VALUE:
        rtnval = False
        return rtnval
    rtnval = flat.get(RUN_ID_TAG_KEY, None) == run_id
    return rtnval


def matches_name(*, do_tags: Optional[List[str]], run_id: str,
                 resource_name: str) -> bool:
    """
        Check whether a tag list carries the (owner, run-id, name) triple.

        :param do_tags: DigitalOcean tag string-list.
        :param run_id: Expected run-id value.
        :param resource_name: Expected neutral resource name.

        :returns: True when all three tags match.
    """
    if not belongs_to_run(do_tags=do_tags, run_id=run_id):
        rtnval = False
        return rtnval
    flat = to_flat(do_tags=do_tags)
    rtnval = flat.get(RESOURCE_NAME_TAG_KEY, None) == resource_name
    return rtnval
