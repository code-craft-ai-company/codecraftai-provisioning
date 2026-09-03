"""
    .. module:: pythonenvcloudinitrenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Renderer producing cloud-init payloads that deploy Python
               virtual environments on first boot.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>

    The renderer is the first-boot counterpart of the
    ``python-environment-management`` sysman feature.  It turns a list of
    :class:`PythonEnvironmentSpec` objects into a venue-neutral cloud-init
    fragment: a ``packages`` list that installs the interpreter
    prerequisites for the image family, one root-only bootstrap script per
    environment under ``/etc/ccai/python-env/``, and a ``runcmd`` entry per
    script.  Each script performs the same steps, in the same order and
    with the same argv shape, as
    ``PythonEnvironmentManagementBase.deploy`` — remove (when ``recreate``),
    create when the interpreter is missing, upgrade pip, install
    requirements files, install packages, hand ownership to ``owner`` —
    so a later sysman run against the same host converges as ``SKIPPED``.

    Quoting is the load-bearing safety property.  Every spec-supplied
    value that reaches a shell line is wrapped by
    :func:`quote_for_shell`; index URLs are written to a root-only
    ``pip.conf`` and referenced through ``PIP_CONFIG_FILE`` rather than
    placed on a command line, so the world-readable cloud-init log never
    carries them.  A private index declared through
    ``PythonEnvironmentSpec.index_credential`` is resolved by the engine
    into a :class:`BootstrapSecrets` container and embedded as URL
    userinfo inside that same ``0400`` file — never in the script, never
    in ``runcmd``.

    Windows image families are rejected: cloud-init on Windows (cloudbase-
    init) does not share the ``write_files`` / ``runcmd`` model this
    renderer relies on.  Use the sysman ``WindowsPythonEnvironmentManager``
    after boot instead.
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import quote, urlsplit, urlunsplit

from ccai.interfaces.pythonenvspec import PythonEnvironmentSpec

from ccai.provisioning.cloudinit.bootstrapsecrets import (
    BootstrapSecrets, IndexCredential, current_bootstrap_secrets
)
from ccai.provisioning.cloudinit.cloudinitrenderererror import (
    CloudInitRendererError
)
from ccai.provisioning.cloudinit.secretquoting import quote_for_shell
from ccai.provisioning.model.cloud.imagefamily import (
    ImageFamily, normalize_family
)


BOOTSTRAP_DIRECTORY = "/etc/ccai/python-env"

# Interpreter prerequisites per image family, installed through cloud-init's
# ``packages`` module (which runs before ``runcmd``).  Debian-family images
# split ``ensurepip`` into ``python3-venv``; a stock image cannot run
# ``python3 -m venv`` without it.  These mirror the per-OS
# ``ensure_prerequisites`` defaults in the sysman packages.
PREREQUISITE_PACKAGES_BY_FAMILY: Dict[ImageFamily, List[str]] = {
    ImageFamily.UBUNTU: ["python3", "python3-venv", "python3-pip"],
    ImageFamily.DEBIAN: ["python3", "python3-venv", "python3-pip"],
    ImageFamily.RHEL: ["python3", "python3-pip"],
    ImageFamily.ROCKY: ["python3", "python3-pip"],
    ImageFamily.ALMALINUX: ["python3", "python3-pip"],
    ImageFamily.FEDORA: ["python3", "python3-pip"],
    ImageFamily.AMAZON_LINUX: ["python3", "python3-pip"],
}

_PIP_GENERAL_OPTIONS = "--disable-pip-version-check --no-input"


def _resolve_family(*, image_family: str) -> ImageFamily:
    """
        Coerce the image family onto a supported Linux member.

        :param image_family: Canonical token or alias.

        :returns: The ImageFamily member.

        :raises: SchemaSemanticError (unknown family, propagated),
                 CloudInitRendererError (known family without a first-boot
                 bootstrap, e.g. windows-server)
    """
    # An unknown family is a SchemaSemanticError from normalize_family: the
    # caller is misusing the model.  It propagates unchanged (semantic
    # errors derive from BaseException on purpose so misuse stops the run).
    # Only a *known* family this renderer cannot bootstrap is a renderer
    # error.
    family = normalize_family(value=image_family)

    if family not in PREREQUISITE_PACKAGES_BY_FAMILY:
        supported = sorted(member.value for member in PREREQUISITE_PACKAGES_BY_FAMILY)
        err_msg_lines = ["Image family has no first-boot python-env bootstrap."]
        err_msg_lines.append("SUPPORTED: {}".format(", ".join(supported)))
        err_msg_lines.append("ACTUAL: {!r}".format(image_family))
        if family == ImageFamily.WINDOWS_SERVER:
            err_msg_lines.append(
                "HINT: converge Windows hosts after boot with the sysman "
                "WindowsPythonEnvironmentManager."
            )
        err_msg = os.linesep.join(err_msg_lines)
        raise CloudInitRendererError(err_msg)

    rtnval = family
    return rtnval


def _validate_specs(*, specs: Sequence[PythonEnvironmentSpec]) -> None:
    """
        Reject empty input, wrong types, and duplicate paths or slugs.

        :param specs: The environment specs.

        :raises: CloudInitRendererError
    """
    if specs is None or len(specs) == 0:
        raise CloudInitRendererError(
            "At least one PythonEnvironmentSpec is required."
        )

    seen_paths: Dict[str, int] = {}
    seen_slugs: Dict[str, int] = {}
    for index, spec in enumerate(specs):
        if not isinstance(spec, PythonEnvironmentSpec):
            raise CloudInitRendererError(
                "specs[{}] is not a PythonEnvironmentSpec: {!r}".format(index, type(spec))
            )
        if spec.path in seen_paths:
            raise CloudInitRendererError(
                "Duplicate environment path {!r} at specs[{}] and specs[{}].".format(
                    spec.path, seen_paths[spec.path], index
                )
            )
        seen_paths[spec.path] = index

        slug = spec.slug
        if slug in seen_slugs:
            raise CloudInitRendererError(
                "Duplicate environment slug {!r} at specs[{}] and specs[{}]; "
                "set a distinct 'name' on one of them.".format(
                    slug, seen_slugs[slug], index
                )
            )
        seen_slugs[slug] = index
    return


def bootstrap_script_path(*, spec: PythonEnvironmentSpec) -> str:
    """
        Host path of the bootstrap script for a spec.

        :param spec: The environment spec.

        :returns: ``/etc/ccai/python-env/<slug>.sh``.
    """
    rtnval = "{}/{}.sh".format(BOOTSTRAP_DIRECTORY, spec.slug)
    return rtnval


def pip_config_path(*, spec: PythonEnvironmentSpec) -> str:
    """
        Host path of the pip configuration file for a spec.

        :param spec: The environment spec.

        :returns: ``/etc/ccai/python-env/<slug>.pip.conf``.
    """
    rtnval = "{}/{}.pip.conf".format(BOOTSTRAP_DIRECTORY, spec.slug)
    return rtnval


def embed_index_credential(*, url: str, credential: IndexCredential) -> str:
    """
        Return ``url`` with the credential embedded as percent-encoded
        HTTP basic-auth userinfo (``https://user:secret@host/path``).

        :param url: A credential-free index URL.
        :param credential: The credential to embed.

        :returns: The credentialed URL.
    """
    parts = urlsplit(url)
    userinfo = "{}:{}".format(quote(credential.username, safe=""),
                              quote(credential.secret, safe=""))
    host_port = parts.hostname or ""
    if parts.port is not None:
        host_port = "{}:{}".format(host_port, parts.port)
    netloc = "{}@{}".format(userinfo, host_port)
    rtnval = urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    return rtnval


def _resolve_index_credential(*, spec: PythonEnvironmentSpec,
                              secrets: Optional[BootstrapSecrets]
                              ) -> Optional[IndexCredential]:
    """
        Find the credential a spec names in the explicit or ambient
        :class:`BootstrapSecrets`.

        :param spec: The environment spec.
        :param secrets: Explicit container, or ``None`` to use the one
                        bound by the engine for the current apply.

        :returns: The credential, or ``None`` when the spec names none.

        :raises: CloudInitRendererError when the spec names a credential
                 that no container resolves — the renderer never silently
                 emits an unauthenticated URL for a private index.
    """
    if spec.index_credential is None:
        rtnval: Optional[IndexCredential] = None
        return rtnval

    effective = secrets if secrets is not None else current_bootstrap_secrets()
    credential = effective.credential_for(spec=spec) if effective is not None else None
    if credential is None:
        err_msg_lines = ["Python environment names an index_credential that was not "
                         "resolved for this run."]
        err_msg_lines.append("PATH: {}".format(spec.path))
        err_msg_lines.append("INDEX_CREDENTIAL: {}".format(spec.index_credential))
        err_msg_lines.append("HINT: construct the ProvisioningEngine with "
                             "credential_lookup=... so LOAD_VALIDATE resolves it.")
        err_msg = os.linesep.join(err_msg_lines)
        raise CloudInitRendererError(err_msg)

    rtnval = credential
    return rtnval


def render_pip_config(*, spec: PythonEnvironmentSpec,
                      credential: Optional[IndexCredential] = None) -> str:
    """
        Render the ``pip.conf`` body for a spec's index configuration.

        Multi-value keys use pip's newline-plus-indent continuation form.
        When ``credential`` is given it is embedded into ``index_url`` and
        into every ``extra_index_urls`` entry on the same host; other hosts
        are left credential-free.

        :param spec: The environment spec.
        :param credential: Optional resolved index credential.

        :returns: The INI text (empty when the spec has no index
                  configuration).
    """
    if not spec.has_index_configuration:
        rtnval = ""
        return rtnval

    index_host: Optional[str] = None
    if spec.index_url is not None:
        index_host = urlsplit(spec.index_url).hostname

    def _maybe_credentialed(url: str) -> str:
        if credential is None:
            return url
        if urlsplit(url).hostname != index_host:
            return url
        return embed_index_credential(url=url, credential=credential)

    lines: List[str] = ["[global]"]
    if spec.index_url is not None:
        lines.append("index-url = {}".format(_maybe_credentialed(spec.index_url)))
    if spec.extra_index_urls is not None and len(spec.extra_index_urls) > 0:
        lines.append("extra-index-url =")
        for url in spec.extra_index_urls:
            lines.append("    {}".format(_maybe_credentialed(url)))
    if spec.trusted_hosts is not None and len(spec.trusted_hosts) > 0:
        lines.append("trusted-host =")
        for host in spec.trusted_hosts:
            lines.append("    {}".format(host))
    rtnval = "\n".join(lines) + "\n"
    return rtnval


def render_bootstrap_script(*, spec: PythonEnvironmentSpec) -> str:
    """
        Render the bash bootstrap script for one environment.

        The step order and the pip argv shape match
        ``PythonEnvironmentManagementBase.deploy`` so a post-boot sysman
        run finds nothing left to do.

        :param spec: The environment spec.

        :returns: The script text.
    """
    venv_q = quote_for_shell(value=spec.path)
    interp_q = quote_for_shell(value=spec.interpreter)

    lines: List[str] = []
    lines.append("#!/bin/bash")
    lines.append("set -euo pipefail")
    lines.append("VENV={}".format(venv_q))
    lines.append("PY={}".format(interp_q))

    if spec.recreate:
        lines.append('rm -rf "${VENV}"')

    create_args = ["-m", "venv"]
    if spec.system_site_packages:
        create_args.append("--system-site-packages")
    lines.append('if [ ! -x "${VENV}/bin/python" ]; then')
    lines.append('  "${{PY}}" {} "${{VENV}}"'.format(" ".join(create_args)))
    lines.append("fi")

    lines.append('PIP=("${{VENV}}/bin/python" -m pip {})'.format(_PIP_GENERAL_OPTIONS))

    if spec.has_index_configuration:
        conf_q = quote_for_shell(value=pip_config_path(spec=spec))
        lines.append("export PIP_CONFIG_FILE={}".format(conf_q))

    if spec.upgrade_pip:
        lines.append('"${PIP[@]}" install --upgrade pip')

    upgrade_flag = " --upgrade" if spec.upgrade_packages else ""
    option_tokens = ""
    if spec.pip_options is not None and len(spec.pip_options) > 0:
        option_tokens = " " + " ".join(
            quote_for_shell(value=token) for token in spec.pip_options
        )

    if spec.requirements_files is not None and len(spec.requirements_files) > 0:
        file_tokens: List[str] = []
        for requirements_file in spec.requirements_files:
            file_tokens.append("-r {}".format(quote_for_shell(value=requirements_file)))
        if spec.constraints_files is not None:
            for constraints_file in spec.constraints_files:
                file_tokens.append("-c {}".format(quote_for_shell(value=constraints_file)))
        lines.append('"${{PIP[@]}}" install{}{} {}'.format(
            upgrade_flag, option_tokens, " ".join(file_tokens)
        ))

    if spec.packages is not None and len(spec.packages) > 0:
        package_tokens = " ".join(quote_for_shell(value=pkg) for pkg in spec.packages)
        lines.append('"${{PIP[@]}}" install{}{} {}'.format(
            upgrade_flag, option_tokens, package_tokens
        ))

    if spec.owner is not None:
        owner_q = quote_for_shell(value=spec.owner)
        lines.append('chown -R {} "${{VENV}}"'.format(owner_q))

    rtnval = "\n".join(lines) + "\n"
    return rtnval


def render_python_env_cloud_init(*, specs: Sequence[PythonEnvironmentSpec],
                                 image_family: str,
                                 secrets: Optional[BootstrapSecrets] = None
                                 ) -> Dict[str, Any]:
    """
        Render the cloud-init fragment deploying every spec on first boot.

        :param specs: The environment specs (at least one).
        :param image_family: Image family token or alias.
        :param secrets: Optional resolved :class:`BootstrapSecrets`; when
                        ``None`` the container bound by the engine for the
                        current apply is used.

        :returns: A dict with ``package_update``, ``packages``,
                  ``write_files`` and ``runcmd`` keys, suitable for
                  ``yaml.safe_dump`` after merging with other fragments.

        :raises: CloudInitRendererError
    """
    family = _resolve_family(image_family=image_family)
    _validate_specs(specs=specs)

    write_files: List[Dict[str, Any]] = []
    runcmd: List[Any] = []

    for spec in specs:
        if spec.has_index_configuration:
            credential = _resolve_index_credential(spec=spec, secrets=secrets)
            write_files.append({
                "path": pip_config_path(spec=spec),
                "owner": "root:root",
                "permissions": "0400",
                "content": render_pip_config(spec=spec, credential=credential),
            })
        script_path = bootstrap_script_path(spec=spec)
        write_files.append({
            "path": script_path,
            "owner": "root:root",
            "permissions": "0700",
            "content": render_bootstrap_script(spec=spec),
        })
        runcmd.append([script_path])

    rtnval: Dict[str, Any] = {
        "package_update": True,
        "packages": list(PREREQUISITE_PACKAGES_BY_FAMILY[family]),
        "write_files": write_files,
        "runcmd": runcmd,
    }
    return rtnval


__all__ = [
    "BOOTSTRAP_DIRECTORY",
    "PREREQUISITE_PACKAGES_BY_FAMILY",
    "bootstrap_script_path",
    "embed_index_credential",
    "pip_config_path",
    "render_bootstrap_script",
    "render_pip_config",
    "render_python_env_cloud_init",
]
