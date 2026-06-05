# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.error_response import ErrorResponse  # noqa: E501
from swagger_server.models.ingest_body1 import IngestBody1  # noqa: E501
from swagger_server.models.ingest_response import IngestResponse  # noqa: E501
from swagger_server.test import BaseTestCase


class TestIngestionController(BaseTestCase):
    """IngestionController integration test stubs"""

    def test_ingest_document(self):
        """Test case for ingest_document

        Ingest a document
        """
        body = IngestBody1()
        data = dict(file='file_example',
                    collection_name='collection_name_example')
        response = self.client.open(
            '/ingest',
            method='POST',
            data=json.dumps(body),
            data=data,
            content_type='multipart/form-data')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
