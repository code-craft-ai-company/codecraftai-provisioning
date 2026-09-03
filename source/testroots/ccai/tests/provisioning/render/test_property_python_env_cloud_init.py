"""
    .. module:: test_property_python_env_cloud_init
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Property-based tests for the python-env cloud-init renderer.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import shlex

from typing import List

import yaml

from ccai import testbase

from ccai.testbase.properties import given
from ccai.testbase.properties import strategies as st

from ccai.interfaces.pythonenvspec import PythonEnvironmentSpec
from ccai.provisioning.cloudinit.bootstrapsecrets import (
    BootstrapSecrets, IndexCredential,
)
from ccai.provisioning.cloudinit.cloudinitrenderererror import CloudInitRendererError
from ccai.provisioning.cloudinit.pythonenvcloudinitrenderer import (
    bootstrap_script_path, pip_config_path, render_bootstrap_script,
    render_python_env_cloud_init,
)


_FAMILIES = ("ubuntu", "debian", "rhel", "rocky", "almalinux", "fedora",
             "amazon-linux")

# Everything a spec field may legally hold.  The schema rejects only newline,
# carriage-return and NUL, so shell metacharacters, quotes and spaces all
# reach the renderer and must survive both the shell-quoting pass and the
# YAML round trip.
_HOSTILE = "abzAZ09 '\"$`\\;|&<>()[]{}*?#!~%^+=,:@./-"

_token_st = st.text(alphabet=_HOSTILE, min_size=1, max_size=14)
_path_st = _token_st.map(lambda tail: "/opt/venvs/" + tail)
_owner_st = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=8)
_family_st = st.sampled_from(_FAMILIES)
_secret_st = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
                     min_size=8, max_size=20).map(lambda s: "sekret" + s)

_INDEX_URL = "https://pypi.internal/simple"
_CREDENTIAL_REF = "pypi:internal"


def _script_of(fragment: dict, spec: PythonEnvironmentSpec) -> str:
    """
        Pull one spec's bootstrap script out of a rendered fragment.
    """
    wanted = bootstrap_script_path(spec=spec)

    for entry in fragment["write_files"]:
        if entry["path"] == wanted:
            rtnval = entry["content"]
            return rtnval

    raise AssertionError("no bootstrap script for {!r}".format(spec.path))


# pip's own self-upgrade step is an install line too; the package-install
# assertions below are about the line carrying the spec's specifiers.
_PIP_SELF_UPGRADE = '"${PIP[@]}" install --upgrade pip'


def _install_lines(script: str) -> List[str]:
    rtnval = [ln for ln in script.splitlines()
              if ln.startswith('"${PIP[@]}" install') and ln != _PIP_SELF_UPGRADE]
    return rtnval


def _credentialed_fragment(path: str, secret: str, family: str) -> tuple:
    spec = PythonEnvironmentSpec(path=path, packages=["requests"],
                                 index_url=_INDEX_URL,
                                 index_credential=_CREDENTIAL_REF)
    secrets = BootstrapSecrets(index_credentials={
        _CREDENTIAL_REF: IndexCredential(username="__token__", secret=secret),
    })
    fragment = render_python_env_cloud_init(specs=[spec], image_family=family,
                                            secrets=secrets)
    rtnval = (spec, fragment)
    return rtnval


@given(path=_path_st, packages=st.lists(_token_st, min_size=1, max_size=4),
       family=_family_st, constraints={"max_examples": 60})
def test_property_fragment_survives_yaml_round_trip(path: str, packages: List[str],
                                                    family: str) -> None:
    """
        The fragment is dumpable as YAML and reloads to an equal structure.
        cloud-init reads what the renderer emits only after a serialise and
        parse cycle, so anything the dumper cannot express faithfully is a
        defect here rather than on the host.
    """
    spec = PythonEnvironmentSpec(path=path, packages=packages)
    fragment = render_python_env_cloud_init(specs=[spec], image_family=family)

    reloaded = yaml.safe_load(yaml.safe_dump(fragment, default_flow_style=False))

    assert reloaded == fragment
    return


@given(path=_path_st, packages=st.lists(_token_st, min_size=1, max_size=4),
       family=_family_st, constraints={"max_examples": 60})
def test_property_script_body_round_trips_verbatim(path: str, packages: List[str],
                                                   family: str) -> None:
    """
        The bootstrap script reaches the host byte-for-byte.  A dropped
        trailing space or a re-folded long line would change what bash
        executes.
    """
    spec = PythonEnvironmentSpec(path=path, packages=packages)
    fragment = render_python_env_cloud_init(specs=[spec], image_family=family)

    reloaded = yaml.safe_load(yaml.safe_dump(fragment, default_flow_style=False))

    assert _script_of(reloaded, spec) == render_bootstrap_script(spec=spec)
    return


@given(path=_path_st, packages=st.lists(_token_st, min_size=1, max_size=4),
       family=_family_st, constraints={"max_examples": 60})
def test_property_each_package_is_exactly_one_shell_word(path: str,
                                                         packages: List[str],
                                                         family: str) -> None:
    """
        Every package specifier survives shell parsing as a single word equal
        to what the spec asked for.  A specifier carrying a quote, a space or
        a ``$`` must not split into two arguments nor expand.
    """
    spec = PythonEnvironmentSpec(path=path, packages=packages)
    fragment = render_python_env_cloud_init(specs=[spec], image_family=family)
    script = _script_of(fragment, spec)

    lines = _install_lines(script)
    assert len(lines) == 1

    words = shlex.split(lines[0])
    for package in packages:
        assert package in words
    return


@given(path=_path_st, owner=_owner_st, family=_family_st,
       constraints={"max_examples": 60})
def test_property_path_and_owner_survive_shell_quoting(path: str, owner: str,
                                                       family: str) -> None:
    """
        The environment path and the ownership hand-over argument parse back
        to their exact values, however hostile the path.
    """
    spec = PythonEnvironmentSpec(path=path, packages=["requests"], owner=owner)
    fragment = render_python_env_cloud_init(specs=[spec], image_family=family)
    script = _script_of(fragment, spec)

    venv_line = [ln for ln in script.splitlines() if ln.startswith("VENV=")][0]
    assert shlex.split(venv_line[len("VENV="):])[0] == path

    chown_line = [ln for ln in script.splitlines() if ln.startswith("chown -R ")][0]
    assert shlex.split(chown_line)[2] == owner
    return


@given(paths=st.lists(_path_st, min_size=1, max_size=4), family=_family_st,
       constraints={"max_examples": 40})
def test_property_one_runcmd_and_unique_paths_per_spec(paths: List[str],
                                                       family: str) -> None:
    """
        Each distinct environment contributes exactly one ``runcmd`` entry,
        and no two write_files entries collide on a path -- a collision would
        silently drop one environment's script.
    """
    unique = sorted(set(paths))
    # Distinct paths do not guarantee distinct slugs -- runs of unsafe
    # characters collapse to a single dash -- so name each environment
    # explicitly.  The collision case is pinned separately below.
    specs = [PythonEnvironmentSpec(path=p, packages=["requests"],
                                   name="env{}".format(index))
             for index, p in enumerate(unique)]
    fragment = render_python_env_cloud_init(specs=specs, image_family=family)

    assert len(fragment["runcmd"]) == len(unique)

    written = [entry["path"] for entry in fragment["write_files"]]
    assert len(written) == len(set(written))

    for spec in specs:
        assert [bootstrap_script_path(spec=spec)] in fragment["runcmd"]
    return


@given(path=_path_st, secret=_secret_st, family=_family_st,
       constraints={"max_examples": 60})
def test_property_index_secret_never_reaches_the_shell(path: str, secret: str,
                                                       family: str) -> None:
    """
        A resolved index credential belongs in the root-only pip config and
        nowhere else.  It must never appear in the bootstrap script or in
        ``runcmd``, where it would land in cloud-init's world-readable logs
        and in the process table.
    """
    spec, fragment = _credentialed_fragment(path, secret, family)

    assert secret not in _script_of(fragment, spec)
    assert secret not in repr(fragment["runcmd"])

    conf_entries = [e for e in fragment["write_files"]
                    if e["path"] == pip_config_path(spec=spec)]
    assert len(conf_entries) == 1
    assert conf_entries[0]["permissions"] == "0400"
    assert conf_entries[0]["owner"] == "root:root"
    return


@given(path=_path_st, secret=_secret_st, family=_family_st,
       constraints={"max_examples": 40})
def test_property_credentialed_fragment_still_round_trips(path: str, secret: str,
                                                          family: str) -> None:
    """
        Adding a credentialed pip config must not make the fragment
        unserialisable -- the config body carries ``%`` escapes and newlines
        that a careless dumper would refold.
    """
    _spec, fragment = _credentialed_fragment(path, secret, family)

    reloaded = yaml.safe_load(yaml.safe_dump(fragment, default_flow_style=False))

    assert reloaded == fragment
    return


@given(base=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
                    min_size=1, max_size=8),
       pair=st.sampled_from([("!", "?"), ("*", "$"), ("#", "~"), ("(", ")")]),
       family=_family_st, constraints={"max_examples": 40})
def test_property_slug_collision_is_refused(base: str, pair: tuple,
                                            family: str) -> None:
    """
        Two different paths whose slugs collapse to the same slug must be
        refused, not silently merged.  Both environments would otherwise
        write to one script path and one of them would vanish.
    """
    first = PythonEnvironmentSpec(path="/opt/venvs/{}{}".format(base, pair[0]),
                                  packages=["requests"])
    second = PythonEnvironmentSpec(path="/opt/venvs/{}{}".format(base, pair[1]),
                                   packages=["requests"])

    assert first.path != second.path
    assert first.slug == second.slug

    with testbase.raises(CloudInitRendererError):
        render_python_env_cloud_init(specs=[first, second], image_family=family)
    return
