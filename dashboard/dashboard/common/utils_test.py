# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import unittest

import mock

from google.appengine.ext import ndb

from dashboard.common import testing_common
from dashboard.common import utils
from dashboard.models import graph_data


class UtilsTest(testing_common.TestCase):

  def setUp(self):
    super(UtilsTest, self).setUp()
    testing_common.SetIsInternalUser('internal@chromium.org', True)
    testing_common.SetIsInternalUser('foo@chromium.org', False)

  def _AssertMatches(self, test_path, pattern):
    """Asserts that a test path matches a pattern with MatchesPattern."""
    test_key = utils.TestKey(test_path)
    self.assertTrue(utils.TestMatchesPattern(test_key, pattern))

  def _AssertDoesntMatch(self, test_path, pattern):
    """Asserts that a test path doesn't match a pattern with MatchesPattern."""
    test_key = utils.TestKey(test_path)
    self.assertFalse(utils.TestMatchesPattern(test_key, pattern))

  def testMatchesPattern_AllWildcards(self):
    self._AssertMatches(
        'ChromiumPerf/cros-one/dromaeo.top25/Total', '*/*/*/*')
    self._AssertDoesntMatch(
        'ChromiumPerf/cros-one/dromaeo.top25/Total', '*/*/*')

  def testMatchesPattern_SomeWildcards(self):
    self._AssertMatches(
        'ChromiumPerf/cros-one/dromaeo.top25/Total',
        'ChromiumPerf/*/dromaeo.top25/*')
    self._AssertDoesntMatch(
        'ChromiumPerf/cros-one/dromaeo.top25/Total',
        'ChromiumPerf/*/dromaeo.another_page_set/*')

  def testMatchesPattern_SomePartialWildcards(self):
    self._AssertMatches(
        'ChromiumPerf/cros-one/dromaeo.top25/Total',
        'ChromiumPerf/cros-*/dromaeo.*/Total')
    self._AssertDoesntMatch(
        'ChromiumPerf/cros-one/dromaeoXtop25/Total',
        'ChromiumPerf/cros-*/dromaeo.*/Total')
    self._AssertDoesntMatch(
        'ChromiumPerf/cros-one/dromaeo.top25/Total',
        'OtherMaster/cros-*/dromaeo.*/Total')

  def testMatchesPattern_MorePartialWildcards(self):
    # Note that the wildcard matches zero or more characters.
    self._AssertMatches(
        'ChromiumPerf/cros-one/dromaeo.top25/Total',
        'Chromium*/cros-one*/*.*/To*al')
    self._AssertDoesntMatch(
        'ChromiumPerf/cros-one/dromaeo.top25/Total',
        'Chromium*/linux-*/*.*/To*al')

  def testMatchesPattern_RequiresFullMatchAtEnd(self):
    # If there is no wildcard at the beginning or end of the
    # test path part, then a part will only match if it matches
    # right up to the beginning or end.
    self._AssertDoesntMatch(
        'ChromiumPerf/cros-one/dromaeo.top25/Total',
        'ChromiumPerf/cros-one/dromaeo.top25/*Tot')
    self._AssertDoesntMatch(
        'ChromiumPerf/cros-one/dromaeo.top25/Total',
        'ChromiumPerf/cros-one/dromaeo.top25/otal*')

  def _PutEntitiesAllExternal(self):
    """Puts entities (none internal-only) and returns the keys."""
    master = graph_data.Master(id='M').put()
    graph_data.Bot(parent=master, id='b').put()
    keys = [
        graph_data.TestMetadata(id='M/b/a', internal_only=False).put(),
        graph_data.TestMetadata(id='M/b/b', internal_only=False).put(),
        graph_data.TestMetadata(id='M/b/c', internal_only=False).put(),
        graph_data.TestMetadata(id='M/b/d', internal_only=False).put(),
    ]
    return keys

  def _PutEntitiesHalfInternal(self):
    """Puts entities (half internal-only) and returns the keys."""
    master = graph_data.Master(id='M').put()
    graph_data.Bot(parent=master, id='b').put()
    keys = [
        graph_data.TestMetadata(id='M/b/ax', internal_only=True).put(),
        graph_data.TestMetadata(id='M/b/a', internal_only=False).put(),
        graph_data.TestMetadata(id='M/b/b', internal_only=False).put(),
        graph_data.TestMetadata(id='M/b/bx', internal_only=True).put(),
        graph_data.TestMetadata(id='M/b/c', internal_only=False).put(),
        graph_data.TestMetadata(id='M/b/cx', internal_only=True).put(),
        graph_data.TestMetadata(id='M/b/d', internal_only=False).put(),
        graph_data.TestMetadata(id='M/b/dx', internal_only=True).put(),
    ]
    return keys

  def testGetMulti_ExternalUser_ReturnsSomeEntities(self):
    keys = self._PutEntitiesHalfInternal()
    self.SetCurrentUser('foo@chromium.org')
    self.assertEqual(len(keys) / 2, len(utils.GetMulti(keys)))

  def testGetMulti_InternalUser_ReturnsAllEntities(self):
    keys = self._PutEntitiesHalfInternal()
    self.SetCurrentUser('internal@chromium.org')
    self.assertEqual(len(keys), len(utils.GetMulti(keys)))

  def testGetMulti_AllExternalEntities_ReturnsAllEntities(self):
    keys = self._PutEntitiesAllExternal()
    self.SetCurrentUser('internal@chromium.org')
    self.assertEqual(len(keys), len(utils.GetMulti(keys)))

  def testTestPath_Test(self):
    key = ndb.Key('Master', 'm', 'Bot', 'b', 'Test', 'suite', 'Test', 'metric')
    self.assertEqual('m/b/suite/metric', utils.TestPath(key))

  def testTestPath_TestMetadata(self):
    key = ndb.Key('TestMetadata', 'm/b/suite/metric')
    self.assertEqual('m/b/suite/metric', utils.TestPath(key))

  def testTestPath_Container(self):
    key = ndb.Key('TestContainer', 'm/b/suite/metric')
    self.assertEqual('m/b/suite/metric', utils.TestPath(key))

  def testTestMetadataKey_None(self):
    key = utils.TestMetadataKey(None)
    self.assertIsNone(key)

  def testTestMetadataKey_Test(self):
    key = utils.TestMetadataKey(
        ndb.Key('Master', 'm', 'Bot', 'b', 'Test', 'suite', 'Test', 'metric'))
    self.assertEqual('TestMetadata', key.kind())
    self.assertEqual('m/b/suite/metric', key.id())
    self.assertEqual(('TestMetadata', 'm/b/suite/metric'), key.flat())

  def testTestMetadataKey_TestMetadata(self):
    original_key = ndb.Key('TestMetadata', 'm/b/suite/metric')
    key = utils.TestMetadataKey(original_key)
    self.assertEqual(original_key, key)

  def testTestMetadataKey_String(self):
    key = utils.TestMetadataKey('m/b/suite/metric/page')
    self.assertEqual('TestMetadata', key.kind())
    self.assertEqual('m/b/suite/metric/page', key.id())
    self.assertEqual(('TestMetadata', 'm/b/suite/metric/page'), key.flat())

  def testOldStyleTestKey_None(self):
    key = utils.OldStyleTestKey(None)
    self.assertIsNone(key)

  def testOldStyleTestKey_Test(self):
    original_key = ndb.Key(
        'Master', 'm', 'Bot', 'b', 'Test', 'suite', 'Test', 'metric')
    key = utils.OldStyleTestKey(original_key)
    self.assertEqual(original_key, key)

  def testOldStyleTestKey_TestMetadata(self):
    key = utils.OldStyleTestKey(ndb.Key('TestMetadata', 'm/b/suite/metric'))
    self.assertEqual('Test', key.kind())
    self.assertEqual('metric', key.id())
    self.assertEqual(
        ('Master', 'm', 'Bot', 'b', 'Test', 'suite', 'Test', 'metric'),
        key.flat())

  def testOldStyleTestKey_String(self):
    key = utils.OldStyleTestKey('m/b/suite/metric')
    self.assertEqual('Test', key.kind())
    self.assertEqual('metric', key.id())
    self.assertEqual(
        ('Master', 'm', 'Bot', 'b', 'Test', 'suite', 'Test', 'metric'),
        key.flat())

  def testTestSuiteName_Basic(self):
    key = utils.TestKey('Master/bot/suite-foo/sub/x/y/z')
    self.assertEqual('suite-foo', utils.TestSuiteName(key))

  def testMinimumRange_Empty_ReturnsNone(self):
    self.assertIsNone(utils.MinimumRange([]))

  def testMinimumRange_NotOverlapping_ReturnsNone(self):
    self.assertIsNone(utils.MinimumRange([(5, 10), (15, 20)]))

  def testMinimumRange_OneRange_ReturnsSameRange(self):
    self.assertEqual((5, 10), utils.MinimumRange([(5, 10)]))

  def testMinimumRange_OverlapsForOneNumber_ReturnsRangeWithOneNumber(self):
    self.assertEqual((5, 5), utils.MinimumRange([(2, 5), (5, 10)]))

  def testMinimumRange_MoreThanTwoRanges_ReturnsIntersection(self):
    self.assertEqual((6, 14), utils.MinimumRange(
        [(3, 20), (5, 15), (6, 25), (3, 14)]))

  def testValidate_StringNotInOptionList_Fails(self):
    with self.assertRaises(ValueError):
      utils.Validate(
          ['completed', 'pending', 'failed'], 'running')

  def testValidate_InvalidType_Fails(self):
    with self.assertRaises(ValueError):
      utils.Validate(int, 'a string')

  def testValidate_MissingProperty_Fails(self):
    with self.assertRaises(ValueError):
      utils.Validate(
          {'status': str, 'try_job_id': int, 'required_property': int},
          {'status': 'completed', 'try_job_id': 1234})

  def testValidate_InvalidTypeInDict_Fails(self):
    with self.assertRaises(ValueError):
      utils.Validate(
          {'status': int, 'try_job_id': int},
          {'status': 'completed', 'try_job_id': 1234})

  def testValidate_StringNotInNestedOptionList_Fails(self):
    with self.assertRaises(ValueError):
      utils.Validate(
          {'values': {'nested_values': ['orange', 'banana']}},
          {'values': {'nested_values': 'apple'}})

  def testValidate_MissingPropertyInNestedDict_Fails(self):
    with self.assertRaises(ValueError):
      utils.Validate(
          {'values': {'nested_values': ['orange', 'banana']}},
          {'values': {}})

  def testValidate_ExpectedValueIsNone_Passes(self):
    utils.Validate(None, 'running')

  def testValidate_StringInOptionList_Passes(self):
    utils.Validate(str, 'a string')

  def testValidate_HasExpectedProperties_Passes(self):
    utils.Validate(
        {'status': str, 'try_job_id': int},
        {'status': 'completed', 'try_job_id': 1234})

  def testValidate_StringInNestedOptionList_Passes(self):
    utils.Validate(
        {'values': {'nested_values': ['orange', 'banana']}},
        {'values': {'nested_values': 'orange'}})

  def testValidate_TypeConversion_Passes(self):
    utils.Validate([1], '1')

  @mock.patch.object(utils, 'ServiceAccountHttp', mock.MagicMock())
  @mock.patch('common.utils.discovery.build')
  def testIsGroupMember_PositiveCase(self, mock_discovery_build):
    mock_request = mock.MagicMock()
    mock_request.execute = mock.MagicMock(return_value={'is_member': True})
    mock_service = mock.MagicMock()
    mock_service.membership = mock.MagicMock(
        return_value=mock_request)
    mock_discovery_build.return_value = mock_service
    self.assertTrue(utils.IsGroupMember('foo@bar.com', 'group'))
    mock_service.membership.assert_called_once_with(
        identity='foo@bar.com', group='group')

  @mock.patch.object(utils, 'ServiceAccountHttp', mock.MagicMock())
  @mock.patch('logging.error')
  @mock.patch('common.utils.discovery.build')
  def testIsGroupMember_RequestFails_LogsErrorAndReturnsFalse(
      self, mock_discovery_build, mock_logging_error):
    mock_service = mock.MagicMock()
    mock_service.membership = mock.MagicMock(
        return_value={'error': 'Some error'})
    mock_discovery_build.return_value = mock_service
    self.assertFalse(utils.IsGroupMember('foo@bar.com', 'group'))
    self.assertEqual(1, mock_logging_error.call_count)


def _MakeMockFetch(base64_encoded=True, status=200):
  """Returns a mock fetch object that returns a canned response."""
  def _MockFetch(_):
    response_text = json.dumps({'key': 'this is well-formed JSON.'})
    if base64_encoded:
      response_text = base64.b64encode(response_text)
    return testing_common.FakeResponseObject(status, response_text)
  return _MockFetch


class DownloadChromiumFileTest(testing_common.TestCase):

  @mock.patch('google.appengine.api.urlfetch.fetch',
              _MakeMockFetch())
  def testDownloadChromiumFile_BasicCase(self):
    self.assertEqual(
        json.dumps({'key': 'this is well-formed JSON.'}),
        utils.DownloadChromiumFile('some/file'))

  @mock.patch('google.appengine.api.urlfetch.fetch',
              _MakeMockFetch(base64_encoded=False))
  @mock.patch('logging.error')
  def testDownloadChromiumFile_BadEncoding(self, mock_logging_error):
    self.assertIsNone(utils.DownloadChromiumFile('some/file'))
    self.assertEqual(1, mock_logging_error.call_count)

  @mock.patch('google.appengine.api.urlfetch.fetch',
              _MakeMockFetch(status=400))
  @mock.patch('logging.error')
  def testDownloadChromiumFile_Non200Status(self, mock_logging_error):
    self.assertIsNone(utils.DownloadChromiumFile('some/file'))
    self.assertEqual(1, mock_logging_error.call_count)


if __name__ == '__main__':
  unittest.main()
