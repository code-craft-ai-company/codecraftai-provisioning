"""
    .. module:: awsboto3sessionfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AwsBoto3SessionFactory — lazy boto3.Session builder.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Optional

from ccai.credentials.awsaccesskeycredential import AwsAccessKeyCredential
from ccai.provisioning.venues.aws.awsregionconfig import AwsRegionConfig


class AwsBoto3SessionFactory:
    """
        Lazy factory that builds a ``boto3.Session`` from an
        :class:`AwsAccessKeyCredential` and an :class:`AwsRegionConfig`.

        The session is constructed on first access and cached.  No global
        boto3 state is created at construction time, so this class is safe
        to instantiate in tests that swap ``boto3`` for a moto-decorated
        process.
    """

    def __init__(self, *, credential: AwsAccessKeyCredential,
                 region_config: AwsRegionConfig) -> None:
        """
            Construct an AwsBoto3SessionFactory.

            :param credential: An AwsAccessKeyCredential.
            :param region_config: The AwsRegionConfig.
        """
        self._credential: AwsAccessKeyCredential = credential
        self._region_config: AwsRegionConfig = region_config
        self._session: Optional[Any] = None
        return

    @property
    def region_config(self) -> AwsRegionConfig:
        """
            Return the bound :class:`AwsRegionConfig`.

            :returns: The AwsRegionConfig.
        """
        rtnval = self._region_config
        return rtnval

    def session(self) -> Any:
        """
            Return the cached ``boto3.Session``, building it on first call.

            :returns: A ``boto3.Session`` instance.
        """
        if self._session is not None:
            rtnval = self._session
            return rtnval

        import boto3
        built = boto3.Session(
            aws_access_key_id=self._credential.keyid,
            aws_secret_access_key=self._credential.secret,
            region_name=self._region_config.region,
        )
        self._session = built

        rtnval = self._session
        return rtnval

    def client(self, *, service_name: str) -> Any:
        """
            Return a boto3 service client.

            :param service_name: AWS service identifier (``ec2``, ``s3``, ...).

            :returns: A boto3 client.
        """
        sess = self.session()
        rtnval = sess.client(service_name)
        return rtnval

    def resource(self, *, service_name: str) -> Any:
        """
            Return a boto3 service resource handle.

            :param service_name: AWS service identifier.

            :returns: A boto3 resource handle.
        """
        sess = self.session()
        rtnval = sess.resource(service_name)
        return rtnval
