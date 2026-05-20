"""
    .. module:: hostnametemplate
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Pure-function hostname template renderer.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os
import re

from typing import Any, Dict, List

from automojo.provisioning.model.exceptions import SchemaSemanticError


_TOKEN_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

_DNS_LABEL_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")

_MAX_FQDN_LEN = 253


def _normalise(value: str) -> str:
    """
        Lower-case and convert underscores to dashes per DNS label conventions.

        :param value: Raw rendered string.

        :returns: Normalised string suitable for DNS-label checking.
    """
    rtnval = value.lower().replace("_", "-")
    return rtnval


def render_hostname(*, template: str, context: Dict[str, Any]) -> str:
    """
        Render a hostname template against a single context.

        Template variables are referenced as ``{name}`` tokens.  After
        substitution the renderer lower-cases the result and converts
        underscores to dashes, then verifies each dot-separated label matches
        the RFC 1123 DNS label regex and total length is ≤ 253 characters.

        :param template: The template string.
        :param context: Mapping of variable name to value.

        :returns: The fully-rendered hostname.
        :raises: SchemaSemanticError on unknown variables or invalid output.
    """
    if template is None or len(template) == 0:
        raise SchemaSemanticError("hostname template must not be empty.")

    if context is None:
        raise SchemaSemanticError("hostname context must not be None.")

    referenced = _TOKEN_RE.findall(template)

    missing: List[str] = []
    for token in referenced:
        if token not in context:
            missing.append(token)

    if len(missing) > 0:
        err_msg_lines = ["Unknown variable(s) in hostname template."]
        err_msg_lines.append("TEMPLATE: {!r}".format(template))
        err_msg_lines.append("MISSING: {}".format(", ".join(missing)))
        err_msg_lines.append("AVAILABLE: {}".format(", ".join(sorted(context.keys()))))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaSemanticError(err_msg)

    def _sub(match: "re.Match[str]") -> str:
        key = match.group(1)
        return str(context[key])

    raw = _TOKEN_RE.sub(_sub, template)
    rendered = _normalise(raw)

    if len(rendered) == 0:
        raise SchemaSemanticError("rendered hostname must not be empty.")

    if len(rendered) > _MAX_FQDN_LEN:
        err_msg_lines = ["Rendered hostname exceeds DNS FQDN length limit."]
        err_msg_lines.append("LIMIT: {}".format(_MAX_FQDN_LEN))
        err_msg_lines.append("ACTUAL: {}".format(len(rendered)))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaSemanticError(err_msg)

    labels = rendered.split(".")
    bad_labels: List[str] = []
    for label in labels:
        if _DNS_LABEL_RE.match(label) is None:
            bad_labels.append(label)

    if len(bad_labels) > 0:
        err_msg_lines = ["Rendered hostname contains invalid DNS label(s)."]
        err_msg_lines.append("HOSTNAME: {!r}".format(rendered))
        err_msg_lines.append("BAD LABELS: {}".format(", ".join(repr(b) for b in bad_labels)))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaSemanticError(err_msg)

    return rendered


def render_hostnames(*, template: str, contexts: List[Dict[str, Any]]) -> List[str]:
    """
        Render a hostname template against N contexts.

        :param template: The template string.
        :param contexts: List of context dicts.

        :returns: List of rendered hostnames (same length as ``contexts``).
        :raises: SchemaSemanticError on duplicate rendered names or any per-name
                 rendering failure.
    """
    if contexts is None:
        raise SchemaSemanticError("contexts must not be None.")

    rendered: List[str] = []
    for ctx in contexts:
        host = render_hostname(template=template, context=ctx)
        rendered.append(host)

    seen: Dict[str, int] = {}
    for host in rendered:
        seen[host] = seen.get(host, 0) + 1

    duplicates = [h for h, n in seen.items() if n > 1]
    if len(duplicates) > 0:
        err_msg_lines = ["Hostname template produced duplicate names."]
        err_msg_lines.append("TEMPLATE: {!r}".format(template))
        err_msg_lines.append("DUPLICATES: {}".format(", ".join(duplicates)))
        err_msg = os.linesep.join(err_msg_lines)
        raise SchemaSemanticError(err_msg)

    return rendered
