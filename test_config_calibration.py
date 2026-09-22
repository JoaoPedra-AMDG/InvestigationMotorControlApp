"""Configuration writes, backup/restore, calibration, fault decoding, load units and sensorless handover.

Uses fixture_boards only; nothing here touches USB or real hardware.
"""
import time
import unittest

from hardware import HardwareController, DEFAULT_PROFILE, IDLE, CLOSED_LOOP
from fixture_boards import MockConnector, MOCK_PROFILE
from odrive_reference import coerce, cross_check, decode_errors, decode_procedure
from hardware_config import CALIBRATION_CHECKLIST

ALL_CONFIRMED = list(range(len(CALIBRATION_CHECKLIST)))


def profile(**extra):
    return dict(DEFAULT_PROFILE, **MOCK_PROFILE, roles_verified=True, axis_units_verified=True,
        stop_policy_verified=True, **extra)


def wait_for(predicate, timeout=4.):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(.02)
    return False


class ReferenceTests(unittest.TestCase):
    def test_error_bits_decode_with_documented_names(self):
        names = [e['name'] for e in decode_errors(0x1000000 | 0x200)]
        self.assertEqual(names, ['DC_BUS_UNDER_VOLTAGE', 'WATCHDOG_TIMER_EXPIRED'])
        self.assertEqual(decode_errors(0), [])
        self.assertEqual(decode_errors(0x80)[0]['name'], 'UNDOCUMENTED')
        self.assertEqual(decode_procedure(14)['name'], 'NOT_CALIBRATED')

    def test_allowlist_rejects_unknown_paths_out_of_range_and_startup_flags(self):
        with self.assertRaisesRegex(ValueError, 'allowlist'):
            coerce('axis0.config.motor.phase_resistance', .05)  # calibration output: read-only
        with self.assertRaisesRegex(ValueError, 'between'):
            coerce('config.dc_bus_overvoltage_trip_level', 70)  # above the Pro rating
        with self.assertRaisesRegex(ValueError, 'must stay off'):
            coerce('axis0.config.startup_closed_loop_control', True)
        self.assertEqual(coerce('axis0.config.motor.pole_pairs', 7.0), 7)
        with self.assertRaises(ValueError):
            coerce('axis0.config.motor.pole_pairs', 7.5)

    def test_cross_checks_enforce_role_policy_and_limit_ordering(self):
        problems = cross_check('load', {'axis0.config.motor.current_soft_max': 20., 'axis0.config.motor.current_hard_max': 10.,
            'axis0.controller.config.control_mode': 2, 'axis0.config.load_encoder': 4})
        text = ' '.join(problems)
        self.assertIn('hard max', text)
        self.assertIn('TORQUE_CONTROL', text)
        self.assertIn('must stay sensored', text)


class ConfigWriteTests(unittest.TestCase):
    def setUp(self):
        self.connector = MockConnector()
        self.hw = HardwareController(profile(), connector=self.connector)
        self.hw.connect()
        self.test_board = self.connector.boards[MOCK_PROFILE['test_serial']]

    def tearDown(self):
        self.hw.close()

    def test_preview_shows_identity_and_before_after_then_apply_reads_back(self):
        snap = self.hw.preview_config({'test': {'axis0.controller.config.vel_limit': 40., 'axis0.config.motor.current_soft_max': 15.}})
        changes = snap['settings_preview']['changes']
        self.assertEqual({c['path']: (c['before'], c['after']) for c in changes},
            {'axis0.controller.config.vel_limit': (50., 40.), 'axis0.config.motor.current_soft_max': (20., 15.)})
        self.assertTrue(all(c['serial'] == MOCK_PROFILE['test_serial'] and c['firmware'] == '0.6.11' for c in changes))
        self.assertEqual(self.test_board.axis0.controller.config.vel_limit, 50.)  # preview writes nothing
        result = self.hw.apply_settings(snap['settings_preview']['token'], False)['settings_result']
        self.assertEqual(len(result['verified']), 2)
        self.assertEqual(self.test_board.axis0.controller.config.vel_limit, 40.)
        self.assertIn('not saved', result['state'])

    def test_token_is_single_use_and_rejects_changes_made_after_preview(self):
        snap = self.hw.preview_config({'test': {'axis0.controller.config.vel_limit': 40.}})
        self.test_board.axis0.controller.config.vel_limit = 45.  # someone else changed it
        with self.assertRaisesRegex(ValueError, 'changed after preview'):
            self.hw.apply_settings(snap['settings_preview']['token'], False)
        with self.assertRaisesRegex(ValueError, 'expired or was already used'):
            self.hw.apply_settings(snap['settings_preview']['token'], False)

    def test_invalid_or_policy_breaking_changes_are_rejected_before_any_write(self):
        with self.assertRaisesRegex(ValueError, 'VELOCITY_CONTROL'):
            self.hw.preview_config({'test': {'axis0.controller.config.control_mode': 1}})
        with self.assertRaisesRegex(ValueError, 'hard max'):
            self.hw.preview_config({'load': {'axis0.config.motor.current_hard_max': 5.}})
        with self.assertRaisesRegex(ValueError, 'unavailable on this firmware'):
            self.hw.preview_config({'test': {'config.max_regen_current': 5.}})  # fixture lacks it
        self.assertEqual(self.test_board.axis0.config.motor.current_hard_max, 30.)

    def test_partial_failure_reports_what_was_verified(self):
        snap = self.hw.preview_config({'test': {'axis0.controller.config.vel_limit': 40., 'axis0.controller.config.vel_gain': .3}})
        original = type(self.test_board.axis0.controller.config).__setattr__

        def failing(obj, name, value):
            if name == 'vel_gain':
                raise ConnectionError('USB write failed')
            original(obj, name, value)
        type(self.test_board.axis0.controller.config).__setattr__ = failing
        try:
            with self.assertRaisesRegex(ValueError, 'Settings update incomplete'):
                self.hw.apply_settings(snap['settings_preview']['token'], False)
        finally:
            type(self.test_board.axis0.controller.config).__setattr__ = original
        result = self.hw.snapshot()['settings_result']
        self.assertEqual(result['state'], 'partial or failed')
        self.assertEqual([c['path'] for c in result['verified']], ['axis0.controller.config.vel_limit'])

    def test_save_then_reconnect_verifies_persistence(self):
        snap = self.hw.preview_config({'load': {'axis0.controller.config.torque_ramp_rate': .5}})
        result = self.hw.apply_settings(snap['settings_preview']['token'], True)
        self.assertEqual(result['state'], 'DISCONNECTED')  # boards reboot after save
        self.assertEqual(result['persist_pending'], {'load': {'axis0.controller.config.torque_ramp_rate': .5}})
        verified = self.hw.verify_persisted()
        self.assertEqual(verified['settings_result']['state'], 'persistence verified after reboot')
        self.assertIsNone(verified['persist_pending'])

    def test_no_writes_during_motion(self):
        self.hw.start(300, 0., 'sensored')
        with self.assertRaisesRegex(ValueError, 'stop motion'):
            self.hw.preview_config({'test': {'axis0.controller.config.vel_limit': 40.}})
        self.hw.stop()

    def test_backup_and_restore_round_trip_with_identity_check(self):
        backup = self.hw.backup_config()['backup']
        self.assertEqual(backup['boards']['test']['serial'], MOCK_PROFILE['test_serial'])
        self.assertEqual(backup['boards']['test']['values']['axis0.controller.config.vel_limit'], 50.)
        self.test_board.axis0.controller.config.vel_limit = 30.
        preview = self.hw.preview_restore(backup)['settings_preview']
        self.assertEqual([(c['path'], c['before'], c['after']) for c in preview['changes']],
            [('axis0.controller.config.vel_limit', 30., 50.)])
        foreign = dict(backup, boards={'test': dict(backup['boards']['test'], serial='ABCDEF000000')})
        with self.assertRaisesRegex(ValueError, 'different board'):
            self.hw.preview_restore(foreign)


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.connector = MockConnector()
        self.hw = HardwareController(profile(), connector=self.connector)
        self.hw.connect()

    def tearDown(self):
        self.hw.close()

    def test_requires_every_safety_confirmation(self):
        with self.assertRaisesRegex(ValueError, 'Confirm every safety condition'):
            self.hw.calibrate('test', 'motor', ALL_CONFIRMED[:-1])
        self.assertEqual(self.connector.boards[MOCK_PROFILE['test_serial']].axis0._state, IDLE)

    def test_supervised_calibration_reports_procedure_result(self):
        self.hw.calibrate('test', 'motor', ALL_CONFIRMED)
        self.assertTrue(wait_for(lambda: self.hw.snapshot()['calibration']['state'] != 'running'))
        cal = self.hw.snapshot()['calibration']
        self.assertEqual(cal['state'], 'succeeded')
        self.assertEqual(cal['result']['name'], 'SUCCESS')

    def test_stop_cancels_calibration(self):
        self.connector.boards[MOCK_PROFILE['test_serial']]._calibration_s = 5.
        self.hw.calibrate('test', 'encoder_offset', ALL_CONFIRMED)
        self.hw.stop()
        self.assertEqual(self.hw.snapshot()['calibration']['state'], 'cancelled')
        self.assertEqual(self.connector.boards[MOCK_PROFILE['test_serial']].axis0._state, IDLE)


class LoadUnitAndSensorlessTests(unittest.TestCase):
    def test_torque_load_converts_and_is_limited_in_amps(self):
        hw = HardwareController(profile(), connector=MockConnector())
        try:
            hw.connect()
            with self.assertRaisesRegex(ValueError, 'above the validated maximum'):
                hw.start(300, .5, 'sensored', 'Nm')  # 0.5 N m / 0.1061 = 4.7 A > 3 A
            hw.start(300, .2, 'sensored', 'Nm')
            # The load is applied once the test motor is up to speed; opposing sign in load coordinates.
            self.assertTrue(wait_for(lambda: hw.snapshot()['boards']['load']['signals']['torque_command_nm'] == -.2))
        finally:
            hw.close()

    def test_sensorless_target_applied_only_after_load_encoder_confirms_handover(self):
        connector = MockConnector()
        test = connector.boards[MOCK_PROFILE['test_serial']].axis0
        test.config.load_encoder = test.config.commutation_encoder = 4
        hw = HardwareController(profile(sensorless_startup_verified=True, sensorless_min_rpm=100.,
            coupling_ratio=1., coupling_sign=1, coupling_verified=True, handover_hold_s=.3), connector=connector)
        try:
            hw.connect()
            snap = hw.start(300, 0., 'sensorless')
            self.assertEqual(snap['state'], 'STARTING')
            self.assertIn('awaiting handover', snap['control_stage'])
            self.assertEqual(test.controller.input_vel, 0.)  # the ramp is never overwritten
            self.assertTrue(wait_for(lambda: 'handover verified' in hw.snapshot()['control_stage']
                or hw.snapshot()['state'] == 'RUNNING', 6.))
            self.assertAlmostEqual(test.controller.input_vel, 5.)  # 300 rpm target applied after confirmation
            hw.stop()
        finally:
            hw.close()


if __name__ == '__main__':
    unittest.main()
