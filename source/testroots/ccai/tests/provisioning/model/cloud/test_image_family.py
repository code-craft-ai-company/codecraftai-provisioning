"""
    .. module:: test_image_family
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for the canonical image vocabulary — ImageFamily,
        ImageArchitecture, version validation, and coercion helpers.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import unittest

from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.provisioning.model.cloud.imagefamily import (
    ImageArchitecture,
    ImageFamily,
    normalize_architecture,
    normalize_family,
    validate_version,
)


class ImageFamilyEnumTests(unittest.TestCase):

    def test_family_members_present(self) -> None:
        names = set(member.name for member in ImageFamily)
        expected = {"UBUNTU", "DEBIAN", "RHEL", "ROCKY", "ALMALINUX",
                    "FEDORA", "WINDOWS_SERVER", "AMAZON_LINUX"}
        self.assertEqual(names, expected)
        return

    def test_family_values_are_lowercase_tokens(self) -> None:
        self.assertEqual(ImageFamily.UBUNTU.value, "ubuntu")
        self.assertEqual(ImageFamily.WINDOWS_SERVER.value, "windows-server")
        self.assertEqual(ImageFamily.AMAZON_LINUX.value, "amazon-linux")
        return

    def test_architecture_values(self) -> None:
        self.assertEqual(ImageArchitecture.X86_64.value, "x86_64")
        self.assertEqual(ImageArchitecture.ARM64.value, "arm64")
        return


class NormalizeFamilyTests(unittest.TestCase):

    def test_accepts_canonical_token(self) -> None:
        resolved = normalize_family(value="rocky")
        self.assertEqual(resolved, ImageFamily.ROCKY)
        return

    def test_accepts_enum_member(self) -> None:
        resolved = normalize_family(value=ImageFamily.DEBIAN)
        self.assertEqual(resolved, ImageFamily.DEBIAN)
        return

    def test_amazonlinux_alias(self) -> None:
        resolved = normalize_family(value="amazonlinux")
        self.assertEqual(resolved, ImageFamily.AMAZON_LINUX)
        return

    def test_amazon_linux_dashed_alias(self) -> None:
        resolved = normalize_family(value="amazon-linux")
        self.assertEqual(resolved, ImageFamily.AMAZON_LINUX)
        return

    def test_windows_alias(self) -> None:
        resolved = normalize_family(value="windows")
        self.assertEqual(resolved, ImageFamily.WINDOWS_SERVER)
        return

    def test_windows_server_alias(self) -> None:
        resolved = normalize_family(value="windows-server")
        self.assertEqual(resolved, ImageFamily.WINDOWS_SERVER)
        return

    def test_rockylinux_alias(self) -> None:
        resolved = normalize_family(value="rockylinux")
        self.assertEqual(resolved, ImageFamily.ROCKY)
        return

    def test_case_insensitive(self) -> None:
        resolved = normalize_family(value="  UBUNTU  ")
        self.assertEqual(resolved, ImageFamily.UBUNTU)
        return

    def test_unknown_family_rejected(self) -> None:
        with self.assertRaises(SchemaSemanticError) as ctx:
            normalize_family(value="gentoo")
        message = str(ctx.exception)
        self.assertIn("gentoo", message)
        self.assertIn("ubuntu", message)
        return

    def test_empty_family_rejected(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            normalize_family(value="")
        return


class NormalizeArchitectureTests(unittest.TestCase):

    def test_accepts_canonical_token(self) -> None:
        resolved = normalize_architecture(value="x86_64")
        self.assertEqual(resolved, ImageArchitecture.X86_64)
        return

    def test_amd64_alias(self) -> None:
        resolved = normalize_architecture(value="amd64")
        self.assertEqual(resolved, ImageArchitecture.X86_64)
        return

    def test_aarch64_alias(self) -> None:
        resolved = normalize_architecture(value="aarch64")
        self.assertEqual(resolved, ImageArchitecture.ARM64)
        return

    def test_accepts_enum_member(self) -> None:
        resolved = normalize_architecture(value=ImageArchitecture.ARM64)
        self.assertEqual(resolved, ImageArchitecture.ARM64)
        return

    def test_unknown_architecture_rejected(self) -> None:
        with self.assertRaises(SchemaSemanticError) as ctx:
            normalize_architecture(value="ppc64")
        self.assertIn("ppc64", str(ctx.exception))
        return


class ValidateVersionTests(unittest.TestCase):

    def test_accepts_dotted_numeric(self) -> None:
        validate_version(version="24.04")
        validate_version(version="9.4")
        validate_version(version="12")
        return

    def test_rejects_empty(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            validate_version(version="")
        return

    def test_rejects_codename(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            validate_version(version="rolling")
        return

    def test_rejects_trailing_dot(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            validate_version(version="24.")
        return

    def test_rejects_alpha_suffix(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            validate_version(version="24.04beta")
        return


if __name__ == "__main__":
    unittest.main()
