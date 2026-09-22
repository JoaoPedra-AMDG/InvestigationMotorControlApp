"""CSV matrix validation, batch sequencing (pause, retry, skip), recording metadata and raw ripple.

Fixture boards only; no USB and no real hardware.
"""
import csv
import io
import json
import tempfile
import time
import unittest
from pathlib import Path

import matrix_csv
from app import Rig
from experiment import Store, validate_plan
from fixture_boards import MockConnector, MOCK_PROFILE
from hardware import HardwareController, DEFAULT_PROFILE
from processing import raw_peak_to_peak

HEADER = [c for c, _, _ in matrix_csv.COLUMNS]


def csv_text(rows):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(HEADER)
    writer.writerows(rows)
    return stream.getvalue()


def row(test_id, mode='sensored', rpm=200, load=0, unit='A', rate=''):
    return [test_id, mode, rpm, load, unit, .3, 40, .6, .3, rate, 1, '']


def wait_for(predicate, timeout=15.):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(.05)
    return False


class MatrixCsvTests(unittest.TestCase):
    def test_example_csv_is_valid(self):
        result = matrix_csv.parse(matrix_csv.example_csv().decode())
        self.assertEqual(result['errors'], [])
        self.assertEqual(len(result['rows']), len(matrix_csv.EXAMPLE))
        units = {r['test_id']: r['load_unit'] for r in result['rows']}
        self.assertEqual(units['S0800-I003-SEN-R1'], 'A')
        self.assertEqual(units['S0400-L050-SEN-R1'], 'Nm')

    def test_row_errors_are_reported_with_row_numbers(self):
        text = csv_text([row('A1'), row('A1'), row('B 2'), row('C3', mode='hall'), row('D4', unit='W'), row('E5', rpm='fast')])
        errors = ' | '.join(matrix_csv.parse(text)['errors'])
        for expected in ('Row 3: test_id A1 appears more than once', 'Row 4: test_id', 'Row 5: feedback_mode',
                         'Row 6: load_unit must be Nm', 'Row 7: speed_rpm "fast"'):
            self.assertIn(expected, errors)

    def test_missing_columns_and_existing_ids_are_rejected(self):
        self.assertIn('Missing columns', matrix_csv.parse('test_id,speed_rpm\nA,100\n')['errors'][0])
        result = matrix_csv.parse(csv_text([row('OLD')]), existing_ids={'OLD'})
        self.assertIn('already exists', result['errors'][0])

    def test_rig_limit_warnings_do_not_block_import(self):
        result = matrix_csv.parse(csv_text([row('FAST', rpm=5000), row('SLS', mode='sensorless', rpm=100)]),
            limits={'max_speed_rpm': 1000, 'max_load_a': 3, 'sensorless_min_rpm': 300})
        self.assertEqual(result['errors'], [])
        self.assertEqual(len(result['warnings']), 2)

    def test_legacy_current_plans_migrate_to_explicit_unit(self):
        plan = validate_plan({'rpm': 500, 'load_a': 2.5, 'settle_load_a': .3})
        self.assertEqual((plan['load'], plan['load_unit'], plan['settle_load']), (2.5, 'A', .3))
        torque = validate_plan({'rpm': 500, 'load': .4, 'load_unit': 'Nm'})
        self.assertIsNone(torque['load_a'])

    def test_import_saves_pending_plans_and_pairs_methods(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            rows = matrix_csv.parse(csv_text([row('P1'), row('P2', mode='sensorless')]))['rows']
            created = store.import_rows(rows, 'matrix.csv')
            self.assertEqual({p['status'] for p in created}, {'pending'})
            self.assertEqual(created[0]['pair_id'], created[1]['pair_id'])
            with self.assertRaisesRegex(ValueError, 'already exists'):
                store.import_rows(rows)


class BatchSequencingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.connector = MockConnector()
        self.connector.shaft.friction = .02  # coast down quickly between points
        profile = dict(DEFAULT_PROFILE, **MOCK_PROFILE, roles_verified=True, axis_units_verified=True, stop_policy_verified=True)
        self.rig = Rig(Path(self.directory.name), rate=50, controller=HardwareController(profile, connector=self.connector))
        self.rig.action({'action': 'connect'})

    def tearDown(self):
        self.rig.close()
        self.directory.cleanup()

    def import_rows(self, *rows):
        preview = self.rig.action({'action': 'matrix_csv_preview', 'csv': csv_text(rows), 'filename': 't.csv'})
        self.assertEqual(preview['errors'], [])
        ids = self.rig.action({'action': 'matrix_csv_save', 'token': preview['token']})['ids']
        for plan_id in ids:
            self.rig.store.plan(plan_id)['capture_high_rate'] = False  # fixture boards have no oscilloscope
        self.rig.store.save_plans()
        return ids

    def batch(self):
        return self.rig.batch.snapshot()

    def test_pause_after_current_then_resume_completes(self):
        ids = self.import_rows(row('Q1'), row('Q2', rpm=250))
        self.rig.action({'action': 'batch_start', 'ids': ids})
        self.assertTrue(wait_for(lambda: self.batch()['current'] is not None))
        self.rig.action({'action': 'batch_pause'})
        self.assertTrue(wait_for(lambda: self.batch()['state'] == 'paused'))
        self.assertEqual([i['state'] for i in self.batch()['items']], ['recorded', 'queued'])
        self.assertIn('after the current test', self.batch()['reason'])
        self.rig.action({'action': 'batch_resume'})
        self.assertTrue(wait_for(lambda: self.batch()['state'] == 'complete', 25))
        run = self.rig.store.list_runs()[0]
        meta = json.loads((self.rig.store.run_dir(run['id'])/'metadata.json').read_text())
        self.assertEqual(meta['plan']['load_unit'], 'A')
        self.assertIn('load_kt_used', meta['plan'])

    def test_blocked_point_can_be_skipped_with_reason_and_failed_needs_decision(self):
        ids = self.import_rows(row('TOO-FAST', rpm=5000), row('OK'))
        self.rig.action({'action': 'batch_start', 'ids': ids})
        self.assertTrue(wait_for(lambda: self.batch()['state'] == 'paused'))
        self.assertEqual(self.batch()['items'][0]['state'], 'blocked')
        with self.assertRaisesRegex(ValueError, 'reason'):
            self.rig.action({'action': 'batch_skip', 'id': ids[0], 'reason': ''})
        self.rig.action({'action': 'batch_skip', 'id': ids[0], 'reason': 'above validated speed'})
        self.assertEqual(self.rig.store.plan(ids[0])['status'], 'skipped')
        self.rig.action({'action': 'batch_resume'})
        self.assertTrue(wait_for(lambda: self.batch()['state'] == 'complete', 25))

    def test_failed_point_retry_creates_new_attempt_and_keeps_failed_run(self):
        ids = self.import_rows(row('F1'))
        self.rig.action({'action': 'batch_start', 'ids': ids})
        self.assertTrue(wait_for(lambda: self.rig.recording is not None))
        axis = self.connector.boards[MOCK_PROFILE['test_serial']].axis0
        axis.active_errors = 0x1000  # CURRENT_LIMIT_VIOLATION during recording
        self.assertTrue(wait_for(lambda: self.batch()['state'] == 'paused'))
        self.assertEqual(self.batch()['items'][0]['state'], 'failed')
        with self.assertRaisesRegex(ValueError, 'Retry or skip'):
            self.rig.action({'action': 'batch_resume'})
        axis.active_errors = axis.disarm_reason = 0
        self.rig.action({'action': 'clear_errors'})
        snap = self.rig.action({'action': 'batch_retry', 'id': ids[0]})
        self.assertEqual([i['state'] for i in snap['items']], ['retried', 'queued'])
        new = self.rig.store.plan(snap['items'][1]['id'])
        self.assertEqual((new['test_id'], new['retry_of']), ('F1-A2', ids[0]))
        self.assertEqual(len(self.rig.store.list_runs()), 1)  # failed run preserved


class RawRippleTests(unittest.TestCase):
    def test_raw_peak_to_peak_uses_window_and_largest_phase(self):
        rows = [dict(time_s=t/10, ia_a=t, ib_a=-2*t, ic_a=None) for t in range(10)]
        self.assertEqual(raw_peak_to_peak(rows), 18)
        self.assertEqual(raw_peak_to_peak(rows, .2, .5), 4)
        self.assertIsNone(raw_peak_to_peak([dict(time_s=0, ia_a=None)]))


if __name__ == '__main__':
    unittest.main()
