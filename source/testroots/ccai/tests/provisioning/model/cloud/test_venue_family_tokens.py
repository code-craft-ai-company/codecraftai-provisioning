"""
    .. module:: test_venue_family_tokens
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Cross-venue invariants pinning image-family vocabulary to
               the canonical ``ImageFamily`` tokens.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>

    ``CloudImage.family`` always stores a canonical ``ImageFamily`` value,
    so venue code that keys a table or compares against any other spelling
    (``"amazonlinux"``, ``"rockylinux"``, ``"redhat"`` ...) can never match.
    Two such sites shipped before these tests existed (the VPN cloud-init
    renderer and the AWS SSM parameter selection).  These tests guard the
    tables directly and lint the venue sources for the literal pattern.
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os
import re
import unittest

from typing import Dict, Iterable, List, Tuple

import ccai.provisioning.venues as venues_package

from ccai.provisioning.cloudinit import vpncloudinitrenderer
from ccai.provisioning.cloudinit import pythonenvcloudinitrenderer
from ccai.provisioning.model.cloud.imagefamily import (
    ImageFamily, normalize_family, _FAMILY_ALIASES,
)
from ccai.provisioning.venues.aws.resources import imageresolver as aws_images
from ccai.provisioning.venues.azure.resources import imageresolver as azure_images
from ccai.provisioning.venues.crusoe import crusoeresolver
from ccai.provisioning.venues.digitalocean import doresolver
from ccai.provisioning.venues.google.resources import instancemanager as google_instances
from ccai.provisioning.venues.hetzner import hetznerresolver
from ccai.provisioning.venues.linode import linoderesolver
from ccai.provisioning.venues.oracle.resources import imageresolver as oracle_images
from ccai.provisioning.venues.vultr import vultrresolver


_CANONICAL = frozenset(member.value for member in ImageFamily)

# Every spelling the alias table accepts that is NOT itself canonical.  A
# venue literal equal to one of these is a latent bug: the comparison can
# never be true against a normalised family.
_NON_CANONICAL_ALIASES = frozenset(
    alias for alias in _FAMILY_ALIASES if alias not in _CANONICAL
)

# Family-keyed tables in venue code: (label, iterable of keys).
_FAMILY_TABLES: List[Tuple[str, Iterable[str]]] = [
    ("aws._SSM_PREFIXES", aws_images._SSM_PREFIXES.keys()),
    ("aws._AMI_OWNERS", aws_images._AMI_OWNERS.keys()),
    ("aws._NAME_PATTERNS", aws_images._NAME_PATTERNS.keys()),
    ("azure._FAMILY_PUBLISHER_OFFER", azure_images._FAMILY_PUBLISHER_OFFER.keys()),
    ("azure._SKU_TEMPLATES", azure_images._SKU_TEMPLATES.keys()),
    ("crusoe._IMAGE_FAMILY_ALIASES", crusoeresolver._IMAGE_FAMILY_ALIASES.keys()),
    ("digitalocean._IMAGE_SLUGS", [fam for (fam, _ver) in doresolver._IMAGE_SLUGS]),
    ("google._IMAGE_FAMILY_TABLE", google_instances._IMAGE_FAMILY_TABLE.keys()),
    ("hetzner._IMAGE_FAMILY_PREFIX", hetznerresolver._IMAGE_FAMILY_PREFIX.keys()),
    ("linode._IMAGE_FAMILY_MAP", linoderesolver._IMAGE_FAMILY_MAP.keys()),
    ("oracle._OS_NAMES", oracle_images._OS_NAMES.keys()),
    ("vultr._OS_FAMILY_HINTS", vultrresolver._OS_FAMILY_HINTS.keys()),
    ("cloudinit.SUPPORTED_LINUX_FAMILIES", vpncloudinitrenderer.SUPPORTED_LINUX_FAMILIES),
    ("cloudinit.SUPPORTED_WINDOWS_FAMILIES", vpncloudinitrenderer.SUPPORTED_WINDOWS_FAMILIES),
    ("cloudinit.PREREQUISITE_PACKAGES_BY_FAMILY",
     [m.value for m in pythonenvcloudinitrenderer.PREREQUISITE_PACKAGES_BY_FAMILY]),
]

# Lines that compare, test membership, or declare a dict key; every quoted
# lower-case token on such a line is checked against the alias set.
_CANDIDATE_LINE = re.compile(r"==|!=|\bin\s*[\(\{\[]|\"\s*:")
_QUOTED_TOKEN = re.compile(r"\"(?P<token>[a-z][a-z0-9_-]*)\"")


def _suspect_tokens(line: str) -> List[str]:
    """
        Return the quoted tokens on a comparison / membership / dict-key
        line that spell a non-canonical family alias.
    """
    if _CANDIDATE_LINE.search(line) is None:
        rtnval: List[str] = []
        return rtnval
    rtnval = [m.group("token") for m in _QUOTED_TOKEN.finditer(line)
              if m.group("token") in _NON_CANONICAL_ALIASES]
    return rtnval


def _venue_source_files() -> List[str]:
    root = os.path.dirname(os.path.abspath(venues_package.__file__))
    rtnval: List[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            if filename.endswith(".py"):
                rtnval.append(os.path.join(dirpath, filename))
    rtnval.sort()
    return rtnval


class FamilyTableTests(unittest.TestCase):

    def test_every_family_keyed_table_uses_canonical_tokens(self) -> None:
        for label, keys in _FAMILY_TABLES:
            with self.subTest(table=label):
                stray = sorted(k for k in keys if k not in _CANONICAL)
                self.assertEqual(stray, [], "{} has non-canonical keys".format(label))
        return

    def test_alias_table_covers_every_canonical_family(self) -> None:
        covered = set(_FAMILY_ALIASES.values())
        self.assertEqual(covered, set(ImageFamily))
        for member in ImageFamily:
            with self.subTest(family=member.value):
                self.assertEqual(normalize_family(value=member.value), member)
        return

    def test_no_canonical_token_is_shadowed_by_an_alias(self) -> None:
        for token in _CANONICAL:
            with self.subTest(token=token):
                self.assertEqual(_FAMILY_ALIASES[token].value, token)
        return


class VenueSourceLintTests(unittest.TestCase):

    def test_no_venue_compares_or_keys_on_a_non_canonical_alias(self) -> None:
        offenders: Dict[str, List[str]] = {}
        for path in _venue_source_files():
            with open(path, "r", encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, start=1):
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if len(_suspect_tokens(line)) > 0:
                        offenders.setdefault(path, []).append(
                            "{}: {}".format(lineno, stripped)
                        )
        self.assertEqual(offenders, {})
        return

    def test_lint_pattern_catches_the_original_bug_shapes(self) -> None:
        # Regression guard for the lint itself.
        samples = [
            'if family == "amazonlinux":',
            '_TABLE = {"rockylinux": "x"}',
            'if fam in ("redhat", "rhel"):',
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(len(_suspect_tokens(sample)) > 0, sample)
        self.assertEqual(_suspect_tokens('if family == "ubuntu":'), [])
        self.assertEqual(_suspect_tokens('msg = "use amazonlinux here"'), [])
        return


if __name__ == "__main__":
    unittest.main()
