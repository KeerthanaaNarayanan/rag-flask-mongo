# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.collections_response import CollectionsResponse  # noqa: E501
from swagger_server.models.error_response import ErrorResponse  # noqa: E501
from swagger_server.models.health_response import HealthResponse  # noqa: E501
from swagger_server.models.inline_response200 import InlineResponse200  # noqa: E501
from swagger_server.test import BaseTestCase


class TestManagementController(BaseTestCase):
    """ManagementController integration test stubs"""

    def test_delete_source(self):
        """Test case for delete_source

        Delete all chunks for a source
        """
        response = self.client.open(
            '/collections/{source}'.format(source='source_example'),
            method='DELETE')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_health_check(self):
        """Test case for health_check

        Service health check
        """
        response = self.client.open(
            '/health',
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_list_collections(self):
        """Test case for list_collections

        List all ingested sources
        """
        response = self.client.open(
            '/collections',
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
