# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import unittest

import mock
import webapp2
import webtest

from google.appengine.api import users

from dashboard import edit_anomalies
from dashboard import xsrf
from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import anomaly


class EditAnomaliesTest(testing_common.TestCase):

  def setUp(self):
    super(EditAnomaliesTest, self).setUp()
    app = webapp2.WSGIApplication([(
        '/edit_anomalies', edit_anomalies.EditAnomaliesHandler)])
    self.testapp = webtest.TestApp(app)
    testing_common.SetSheriffDomains(['chromium.org'])

  def tearDown(self):
    super(EditAnomaliesTest, self).tearDown()
    self.UnsetCurrentUser()

  def _AddAnomaliesToDataStore(self):
    anomaly.Anomaly(start_revision=123456,
                    end_revision=123459,
                    median_before_anomaly=5,
                    median_after_anomaly=10,
                    bug_id=None).put()
    anomaly.Anomaly(start_revision=123460,
                    end_revision=123464,
                    median_before_anomaly=5,
                    median_after_anomaly=10,
                    bug_id=None).put()
    anomaly.Anomaly(start_revision=123465,
                    end_revision=123468,
                    median_before_anomaly=5,
                    median_after_anomaly=10,
                    bug_id=None).put()
    return anomaly.Anomaly.query().fetch(keys_only=True)

  def testPost_NoXSRFToken_Returns403Error(self):
    anomaly_keys = self._AddAnomaliesToDataStore()
    self.testapp.post('/edit_anomalies', {
        'keys': json.dumps([anomaly_keys[0].urlsafe()]),
        'bug_id': 31337,
    }, status=403)
    self.assertIsNone(anomaly_keys[0].get().bug_id)

  @mock.patch.object(utils, 'IsGroupMember', mock.MagicMock(return_value=False))
  def testPost_LoggedIntoInvalidDomain_DoesNotModifyAnomaly(self):
    anomaly_keys = self._AddAnomaliesToDataStore()
    self.SetCurrentUser('foo@bar.com')
    self.testapp.post('/edit_anomalies', {
        'keys': json.dumps([anomaly_keys[0].urlsafe()]),
        'bug_id': 31337,
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    }, status=403)
    self.assertIsNone(anomaly_keys[0].get().bug_id)

  def testPost_LoggedIntoValidSheriffAccount_ChangesBugID(self):
    anomaly_keys = self._AddAnomaliesToDataStore()
    self.SetCurrentUser('sullivan@chromium.org')
    self.testapp.post('/edit_anomalies', {
        'keys': json.dumps([anomaly_keys[0].urlsafe()]),
        'bug_id': 31337,
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    self.assertEqual(31337, anomaly_keys[0].get().bug_id)

  def testPost_RemoveBug(self):
    anomaly_keys = self._AddAnomaliesToDataStore()
    self.SetCurrentUser('sullivan@chromium.org')
    a = anomaly_keys[0].get()
    a.bug_id = 12345
    a.put()
    self.testapp.post('/edit_anomalies', {
        'keys': json.dumps([anomaly_keys[0].urlsafe()]),
        'bug_id': 'REMOVE',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    self.assertIsNone(anomaly_keys[0].get().bug_id)

  def testPost_ChangeBugIDToInvalidID_ReturnsError(self):
    anomaly_keys = self._AddAnomaliesToDataStore()
    self.SetCurrentUser('sullivan@chromium.org')
    a = anomaly_keys[0].get()
    a.bug_id = 12345
    a.put()
    response = self.testapp.post('/edit_anomalies', {
        'keys': json.dumps([anomaly_keys[0].urlsafe()]),
        'bug_id': 'a',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    self.assertEqual(
        {'error': 'Invalid bug ID a'},
        json.loads(response.body))
    self.assertEqual(12345, anomaly_keys[0].get().bug_id)

  def testPost_NoKeysGiven_Error(self):
    anomaly_keys = self._AddAnomaliesToDataStore()
    self.SetCurrentUser('foo@chromium.org')
    response = self.testapp.post('/edit_anomalies', {
        'bug_id': 31337,
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    self.assertEqual(
        {'error': 'No alerts specified to add bugs to.'},
        json.loads(response.body))
    self.assertIsNone(anomaly_keys[0].get().bug_id)

  def testPost_ChangeRevisions(self):
    anomaly_keys = self._AddAnomaliesToDataStore()
    self.SetCurrentUser('sullivan@chromium.org')
    self.testapp.post('/edit_anomalies', {
        'keys': json.dumps([anomaly_keys[0].urlsafe()]),
        'new_start_revision': '123450',
        'new_end_revision': '123455',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    self.assertEqual(123450, anomaly_keys[0].get().start_revision)
    self.assertEqual(123455, anomaly_keys[0].get().end_revision)

  def testPost_NudgeWithInvalidRevisions_ReturnsError(self):
    anomaly_keys = self._AddAnomaliesToDataStore()
    self.SetCurrentUser('sullivan@chromium.org')
    start = anomaly_keys[0].get().start_revision
    end = anomaly_keys[0].get().end_revision
    response = self.testapp.post('/edit_anomalies', {
        'keys': json.dumps([anomaly_keys[0].urlsafe()]),
        'new_start_revision': 'a',
        'new_end_revision': 'b',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    self.assertEqual(start, anomaly_keys[0].get().start_revision)
    self.assertEqual(end, anomaly_keys[0].get().end_revision)
    self.assertEqual(
        {'error': 'Invalid revisions a, b'},
        json.loads(response.body))

  def testPost_IncompleteParametersGiven_ReturnsError(self):
    anomaly_keys = self._AddAnomaliesToDataStore()
    self.SetCurrentUser('sullivan@chromium.org')
    response = self.testapp.post('/edit_anomalies', {
        'keys': json.dumps([anomaly_keys[0].urlsafe()]),
        'new_start_revision': '123',
        'xsrf_token': xsrf.GenerateToken(users.get_current_user()),
    })
    self.assertEqual(
        {'error': 'No bug ID or new revision specified.'},
        json.loads(response.body))


if __name__ == '__main__':
  unittest.main()
