"""Stage 1 tests: no simulation mode, discovery, derived dashboard signals, event log, survey walker."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from hardware import HardwareController, DEFAULT_PROFILE, IDLE, CLOSED_LOOP
from fixture_boards import MockConnector, MOCK_PROFILE, MOCK_SERIALS
from event_log import EventLog
import survey_odrive


def mock_profile(**extra):
    return dict(DEFAULT_PROFILE, **MOCK_PROFILE, roles_verified=True, axis_units_verified=True,
        stop_policy_verified=True, **extra)


def wait_for(predicate, timeout=3.):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(.02)
    return False


class MockModeTests(unittest.TestCase):
    def setUp(self):
        self.hw = HardwareController(mock_profile(), connector=MockConnector())

    def tearDown(self):
        self.hw.close()

    def test_application_has_no_simulation_mode(self):
        root = Path(__file__).resolve().parent
        for name in ('app.py', 'hardware.py', 'experiment.py', 'batch_runner.py', 'capture_runtime.py', 'workbench.js'):
            text = (root/name).read_text(encoding='utf-8')
            self.assertNotIn('fixture_boards', text, name)
            self.assertNotIn('--mock', text, name)

    def test_discovery_lists_serials_without_connecting(self):
        snap = self.hw.discover(.5)
        serials = [b['serial'] for b in snap['discovered']['boards']]
        self.assertEqual(serials, sorted(MOCK_SERIALS.values()))
        self.assertEqual({b['assigned_role'] for b in snap['discovered']['boards']}, {'test', 'load'})
        self.assertEqual(snap['state'], 'DISCONNECTED')
        self.assertFalse(any(b['connected'] for b in snap['boards'].values()))

    def test_discovery_refused_while_connected(self):
        self.hw.connect()
        with self.assertRaises(ValueError):
            self.hw.discover(.5)

    def test_connect_reads_config_and_derives_dashboard_signals(self):
        snap = self.hw.connect()
        for role in ('test', 'load'):
            board = snap['boards'][role]
            self.assertTrue(board['connected'])
            self.assertEqual(board['configuration']['axis0.config.motor.calibration_current'], 5.)
            self.assertIsNone(board['configuration']['inc_encoder0.config.cpr'])  # not on mock: unavailable
            s = board['signals']
            self.assertAlmostEqual(s['electrical_power_w'], s['dc_voltage_v']*s['dc_current_a'])
            self.assertAlmostEqual(s['iq_error_a'], s['iq_command_a']-s['iq_a'])
            if role == 'test':  # velocity control: speed error defined
                self.assertIsNotNone(s['speed_error_rpm'])
            else:  # torque control: a speed error would be meaningless
                self.assertIsNone(s['speed_error_rpm'])
        blocked = [c['name'] for c in snap['readiness'] if c['state'] != 'pass']
        self.assertEqual(blocked, [])

    def test_mock_start_applies_load_after_speed_then_stop_coasts(self):
        self.hw.connect()
        self.hw.start(300, 1., 'sensored')
        self.assertTrue(wait_for(lambda: self.hw.snapshot()['state'] == 'RUNNING'))
        self.assertTrue(wait_for(lambda: abs((self.hw.snapshot()['boards']['test']['signals']['speed_rpm'] or 0)-300) < 15))
        load = self.hw.snapshot()['boards']['load']['signals']
        self.assertLess(load['torque_command_nm'], 0)  # opposing load in load-board coordinates
        snap = self.hw.stop()
        self.assertTrue(all(b['state_code'] == IDLE for b in snap['boards'].values()))

    def test_sensorless_start_still_blocked_in_mock(self):
        self.hw.connect()
        with self.assertRaises(ValueError):
            self.hw.start(300, 0., 'sensorless')


class RigStatusTests(unittest.TestCase):
    def test_rig_status_is_hardware_labelled_with_recording_clock(self):
        from app import Rig
        with tempfile.TemporaryDirectory() as directory:
            controller = HardwareController(mock_profile(), connector=MockConnector())
            rig = Rig(Path(directory), rate=20, controller=controller)
            try:
                status = rig.status()
                self.assertEqual(status['source'], 'HARDWARE')
                self.assertIsNone(status['recording_elapsed_s'])
            finally:
                rig.close()


class EventLogTests(unittest.TestCase):
    def test_commands_and_outcomes_are_jsonl_and_bulk_is_summarised(self):
        with tempfile.TemporaryDirectory() as directory:
            log = EventLog(Path(directory))
            log.command({'action': 'import', 'csv': 'x'*5000, 'run_id': 'r1'})
            log.outcome({'action': 'import'}, 'rejected', 'bad mapping')
            lines = [json.loads(l) for f in Path(directory).glob('events-*.jsonl') for l in f.read_text().splitlines()]
            self.assertEqual([l['kind'] for l in lines], ['command', 'outcome'])
            self.assertEqual(lines[0]['request']['csv'], '<5000 characters>')
            self.assertEqual(lines[1]['result'], 'rejected')


class SurveyWalkTests(unittest.TestCase):
    def test_walk_reads_properties_and_never_calls_functions(self):
        class Prop:
            def __init__(self, codec, writable):
                self.codec, self.writable = codec, writable

        class Func:
            def __call__(self, *args):
                raise AssertionError('The survey must never call a firmware function.')

        class Obj:
            pass

        axis_type = type('Axis', (Obj,), {'current_state': 1})
        axis_type._props = {'current_state': Prop('uint8', False)}
        axis = axis_type()
        axis.watchdog_feed = Func()
        root_type = type('Root', (Obj,), {'vbus_voltage': 26.5, 'serial_number': 123})
        root_type._props = {'vbus_voltage': Prop('float', False), 'serial_number': Prop('uint64', False)}
        root = root_type()
        root.axis0 = axis
        root.reboot = Func()

        def is_property(owner, name):
            prop = getattr(owner, '_props', {}).get(name)
            return (prop.codec, prop.writable) if prop else None

        props, funcs = survey_odrive.walk(root, is_property,
            lambda v, n: f'{n}()' if isinstance(v, Func) else None, lambda v: isinstance(v, Obj))
        self.assertEqual({p['path']: p['value'] for p in props},
            {'axis0.current_state': 1, 'serial_number': 123, 'vbus_voltage': 26.5})
        self.assertEqual(sorted(f['path'] for f in funcs), ['axis0.watchdog_feed', 'reboot'])
        comparison = survey_odrive.compare(props, funcs)
        self.assertIn('axis0.vel_estimate', comparison['missing_properties'])
        self.assertIn('clear_errors', comparison['missing_functions'])


if __name__ == '__main__':
    unittest.main()
