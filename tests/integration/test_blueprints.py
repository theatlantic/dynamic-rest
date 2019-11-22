from unittest import TestCase, skipIf
from dj.test import TemporaryApplication
from django.conf import settings
import requests
import time
import json
import os


class DJBlueprintsTestCase(TestCase):

    @skipIf(
        not settings.ENABLE_INTEGRATION_TESTS,
        'Integration tests disabled'
    )
    def test_blueprints(self):
        # Generate a test application
        application = TemporaryApplication()

        # Add a model
        application.execute('generate model foo --not-interactive')

        # Create and apply migrations
        application.execute('migrate')

        # Add this project as a dependency
        # This file is ROOT/tests/integration/test_blueprints.py
        root = os.path.abspath(os.path.join(__file__, '../../..'))
        application.execute('add %s --dev --not-interactive' % root)

        # Generate an API endpoint for the generated model
        application.execute('generate api v0 foo --not-interactive')

        # Start the server
        server = application.execute('serve 9123', run_async=True)

        time.sleep(2)

        # Verify a simple POST flow for the "foo" resource
        response = requests.post('http://localhost:9123/v0/foos/')
        self.assertTrue(response.status_code, 201)
        content = json.loads(response.content)
        self.assertEquals(content, {'foo': {'id': 1}})

        # Stop the server
        server.terminate()
