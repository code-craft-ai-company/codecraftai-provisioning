"""
    .. module:: test_imageresolver_ssm_param
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Pins the SSM parameter shape the AWS image resolver requests
               per canonical image family.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import unittest

from typing import Any, Dict, List

from ccai.provisioning.venues.aws.resources.imageresolver import ImageResolver


class _FakeSsmClient:

    def __init__(self) -> None:
        self.requested: List[str] = []
        return

    def get_parameter(self, *, Name: str) -> Dict[str, Any]:
        self.requested.append(Name)
        rtnval = {"Parameter": {"Value": "ami-0123456789abcdef0"}}
        return rtnval


class _FakeSessionFactory:

    def __init__(self) -> None:
        self.ssm = _FakeSsmClient()
        return

    def client(self, *, service_name: str) -> Any:
        assert service_name == "ssm", service_name
        return self.ssm


class ImageResolverSsmParameterTests(unittest.TestCase):

    def _resolver(self) -> ImageResolver:
        self.factory = _FakeSessionFactory()
        rtnval = ImageResolver(session_factory=self.factory)
        return rtnval

    def test_amazon_linux_uses_amzn2_parameter(self) -> None:
        # ``CloudImage.family`` stores the canonical ``amazon-linux`` token;
        # the resolver compared against ``amazonlinux`` and fell through to
        # the generic ``<prefix>/<version>/latest/ami-id`` shape.
        resolver = self._resolver()
        ami_id = resolver._try_ssm(family="amazon-linux", version="2",
                                   arch="x86_64")
        self.assertEqual(ami_id, "ami-0123456789abcdef0")
        self.assertEqual(
            self.factory.ssm.requested,
            ["/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2"],
        )
        return

    def test_ubuntu_uses_canonical_stable_current_parameter(self) -> None:
        resolver = self._resolver()
        resolver._try_ssm(family="ubuntu", version="24.04", arch="arm64")
        self.assertEqual(
            self.factory.ssm.requested,
            ["/aws/service/canonical/ubuntu/server/24.04/stable/current/arm64/hvm/ebs-gp2/ami-id"],
        )
        return

    def test_unknown_family_skips_ssm(self) -> None:
        resolver = self._resolver()
        self.assertIsNone(resolver._try_ssm(family="rocky", version="9", arch="x86_64"))
        self.assertEqual(self.factory.ssm.requested, [])
        return


if __name__ == "__main__":
    unittest.main()
