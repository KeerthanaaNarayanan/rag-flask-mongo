# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.error_response import ErrorResponse  # noqa: E501
from swagger_server.models.query_request import QueryRequest  # noqa: E501
from swagger_server.models.query_response import QueryResponse  # noqa: E501
from swagger_server.test import BaseTestCase


class TestQueryController(BaseTestCase):
    """QueryController integration test stubs"""

    def test_query_documents(self):
        """Test case for query_documents

        Query ingested documents
        """
        body = QueryRequest()
        response = self.client.open(
            '/query',
            method='POST',
            data=json.dumps(body),
            content_type='application/json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
