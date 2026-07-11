"""
    .. module:: dopagination
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Page-following helper for DigitalOcean (pydo) list endpoints.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Callable, Dict, List


# DigitalOcean list endpoints default to per_page=20.  A single .list() call
# therefore returns only the first page, so find/destroy/list_owned that iterate
# one response silently miss owned resources on page 2+ (duplicate create,
# orphaned teardown).  This helper follows links.pages.next until the listing is
# exhausted and returns the full aggregated item list.
_DEFAULT_PER_PAGE = 200


def collect_all_pages(*, list_fn: Callable[..., Dict[str, Any]],
                      data_key: str,
                      per_page: int = _DEFAULT_PER_PAGE,
                      **list_kwargs: Any) -> List[Dict[str, Any]]:
    """
        Follow DigitalOcean pagination and return every item across all pages.

        :param list_fn: A pydo ``.list``-style method returning a response dict.
        :param data_key: The response key holding the item list (e.g.
                         ``"droplets"``).
        :param per_page: Page size requested from the API.
        :param list_kwargs: Extra keyword arguments forwarded to ``list_fn``
                            (e.g. ``tag_name`` or ``domain_name``).

        :returns: The aggregated list of item dicts across all pages.
    """
    items: List[Dict[str, Any]] = []
    page = 1
    while True:
        response = list_fn(per_page=per_page, page=page, **list_kwargs)
        batch = list(response.get(data_key, []))
        items.extend(batch)
        if len(batch) == 0:
            break

        links = response.get("links", None)
        has_next = False
        if isinstance(links, dict):
            pages = links.get("pages", None)
            if isinstance(pages, dict) and pages.get("next", None) is not None:
                has_next = True

        if has_next is not True:
            break
        page = page + 1

    rtnval = items
    return rtnval
