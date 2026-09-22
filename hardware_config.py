"""Configuration writes, backup/restore and supervised calibration for HardwareController.

These methods run only on the controller's single owner thread (they are invoked
through HardwareController._call). Every write follows one path:
preview (board identity + exact before/after) -> explicit apply with a one-time
token -> per-value read-back -> optional save to non-volatile memory, after
which the board reboots and the operator explicitly reconnects to verify.
"""
import copy
import time
import uuid

from odrive_reference import REGISTRY, REGISTRY_BY_PATH, coerce, cross_check, decode_procedure
from settings_support import same

IDLE, CLOSED_LOOP = 1, 8
CALIBRATIONS = {
    'motor': (4, 'MOTOR_CALIBRATION', 'Measures phase resistance and inductance. The motor is energised and beeps; the rotor should not turn much.'),
    'encoder_offset': (7, 'ENCODER_OFFSET_CALIBRATION', 'Turns the rotor slowly in both directions to find encoder direction and offset. The chain turns the other motor too.'),
    'full': (3, 'FULL_CALIBRATION_SEQUENCE', 'Motor calibration followed by encoder offset calibration.'),
}
CALIBRATION_CHECKLIST = [
    'The physical emergency stop is within reach and has been tested.',
    'Guards are fitted; nobody is touching the motors, chain or sprockets.',
    'The rotor can turn freely: no gravity, spring or brake load (inertia and light friction only).',
    'The other motor is IDLE and may be turned by the chain.',
    'The calibration current is within the motor rating and the supply can deliver it.',
]
CALIBRATION_TIMEOUT_S = 90.


class ConfigMixin:
    # ---- public API (queued onto the owner thread) ----
    def preview_config(self, changes, origin='manual'):
        return self._call('preview_config', copy.deepcopy(changes), origin)

    def backup_config(self):
        return self._call('backup_config')

    def preview_restore(self, backup, allow_other_serial=False):
        return self._call('preview_restore', copy.deepcopy(backup), allow_other_serial)

    def verify_persisted(self):
        return self._call('verify_persisted')

    def calibrate(self, role, kind, confirmations):
        return self._call('calibrate', role, kind, list(confirmations or []))

    # ---- implementation ----
    def _registry_values(self, device):
        values = {}
        for entry in REGISTRY:
            value = self._reader(device, entry['path'])
            values[entry['path']] = value if isinstance(value, (bool, int, float)) else None
        return values

    def _do_preview_config(self, changes, origin):
        self._settings_idle()
        if not self._profile['roles_verified'] or not self._profile['axis_units_verified']:
            raise ValueError('Verify the physical board roles and motor-shaft units in Connections first.')
        if not isinstance(changes, dict) or not changes or set(changes) - {'test', 'load'}:
            raise ValueError('Changes must be grouped by board role: test and/or load.')
        self._do_refresh_settings()
        planned, problems = [], []
        for role, values in changes.items():
            if not isinstance(values, dict) or not values:
                raise ValueError(f'No changes given for the {role} board.')
            device = self._devices[role]
            current = self._registry_values(device)
            after = dict(current)
            for path, raw in values.items():
                value = coerce(path, raw)
                before = current.get(path)
                if before is None:
                    raise ValueError(f'{role}: {path} is unavailable on this firmware; it cannot be written.')
                if isinstance(before, bool) != isinstance(value, bool):
                    raise ValueError(f'{role}: {path} type does not match the board value.')
                after[path] = value
                if not same(before, value):
                    entry = REGISTRY_BY_PATH[path]
                    planned.append(dict(role=role, serial=self._profile[role+'_serial'],
                        firmware=self._boards[role].get('firmware'), path=path, label=entry['label'],
                        unit=entry['unit'], before=before, after=value))
            problems += [f'{role.title()} board: {p}' for p in cross_check(role, after)]
        if problems:
            raise ValueError('Change rejected. ' + ' '.join(problems))
        if not planned:
            raise ValueError('Nothing to change: every proposed value already matches the board.')
        self._settings_preview = dict(token=uuid.uuid4().hex, expires_at=time.monotonic()+120,
            epoch=self._motion_epoch, changes=planned, origin=origin)
        self._settings_result = None

    def _do_backup_config(self):
        if not self._devices:
            raise ValueError('Connect the boards before taking a configuration backup.')
        boards = {}
        for role, device in self._devices.items():
            boards[role] = dict(serial=self._profile[role+'_serial'], firmware=self._boards[role].get('firmware'),
                values=self._registry_values(device))
        self._backup = dict(kind='odrive-workbench-config-backup', version=1,
            created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), boards=boards,
            note='Allowlisted settings only. Calibration results (phase R/L, encoder offset) are not restored.')

    def _do_preview_restore(self, backup, allow_other_serial):
        if not isinstance(backup, dict) or backup.get('kind') != 'odrive-workbench-config-backup':
            raise ValueError('This file is not a workbench configuration backup.')
        changes = {}
        for role, board in (backup.get('boards') or {}).items():
            if role not in ('test', 'load') or role not in self._devices:
                continue
            if board.get('serial') != self._profile[role+'_serial'] and allow_other_serial is not True:
                raise ValueError(f"The {role} backup was taken from board {board.get('serial')}, not {self._profile[role+'_serial']}. "
                    'Confirm restoring onto a different board explicitly.')
            values = {p: v for p, v in (board.get('values') or {}).items() if p in REGISTRY_BY_PATH and v is not None}
            if values:
                changes[role] = values
        if not changes:
            raise ValueError('The backup contains no restorable values for the connected boards.')
        current = {r: self._registry_values(self._devices[r]) for r in changes}
        changes = {r: {p: v for p, v in vals.items() if not same(current[r].get(p), v)} for r, vals in changes.items()}
        changes = {r: v for r, v in changes.items() if v}
        if not changes:
            raise ValueError('The boards already match the backup.')
        self._do_preview_config(changes, 'restore')

    def _do_verify_persisted(self):
        expected = getattr(self, '_persist_expect', None)
        if not expected:
            raise ValueError('No saved configuration is waiting for verification.')
        if not self._devices:
            self._do_connect()
        mismatches = []
        for role, values in expected.items():
            device = self._devices.get(role)
            for path, value in values.items():
                actual = self._reader(device, path) if device else None
                if not same(actual, value):
                    mismatches.append(dict(role=role, path=path, expected=value, actual=actual))
        self._settings_result = dict(state='persistence verified after reboot' if not mismatches else 'persistence check FAILED',
            changes=[], verified=[], saved=list(expected), error='', mismatches=mismatches)
        if not mismatches:
            self._persist_expect = None

    def _do_calibrate(self, role, kind, confirmations):
        if role not in ('test', 'load'):
            raise ValueError('Choose the test or load board.')
        if kind not in CALIBRATIONS:
            raise ValueError('Unknown calibration type.')
        if sorted(confirmations) != list(range(len(CALIBRATION_CHECKLIST))):
            raise ValueError('Confirm every safety condition before calibrating.')
        if getattr(self, '_calibration', None) and self._calibration.get('state') == 'running':
            raise ValueError('A calibration is already running.')
        self._settings_idle()
        device = self._devices[role]
        errors = [self._reader(d, 'axis0.active_errors') for d in self._devices.values()]
        if any(e != 0 for e in errors):
            raise ValueError('Clear board errors (and fix their cause) before calibrating.')
        state_code, name, _ = CALIBRATIONS[kind]
        self._calibration = dict(role=role, kind=kind, state_name=name, state='running',
            started=time.monotonic(), started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            result=None, detail='Requested '+name+'.')
        try:
            device.axis0.watchdog_feed()
            device.axis0.requested_state = state_code
        except Exception as exc:
            self._calibration.update(state='failed', detail='Request failed: '+str(exc))
            self._request_idle()
            raise

    def _calibration_tick(self):
        """Called from the owner loop while a calibration runs: feed, watch, finish."""
        cal = getattr(self, '_calibration', None)
        if not cal or cal['state'] != 'running':
            return
        device = self._devices.get(cal['role'])
        if device is None:
            cal.update(state='failed', detail='Board disconnected during calibration.')
            return
        try:
            device.axis0.watchdog_feed()
            state = self._reader(device, 'axis0.current_state')
            elapsed = time.monotonic()-cal['started']
            if state == IDLE and elapsed > .5:
                result = decode_procedure(self._reader(device, 'axis0.procedure_result'))
                errors = self._reader(device, 'axis0.active_errors')
                ok = result is not None and result['code'] == 0 and errors == 0
                cal.update(state='succeeded' if ok else 'failed', result=result,
                    detail=('Calibration finished. Read the new values below, then save to keep them across power cycles.'
                            if ok else 'Calibration did not succeed: ' + (result['name'] if result else 'no procedure result') + '.'))
                self._boards[cal['role']]['configuration'] = self._configuration(device)
            elif elapsed > CALIBRATION_TIMEOUT_S:
                device.axis0.requested_state = IDLE
                cal.update(state='failed', detail=f'Timed out after {CALIBRATION_TIMEOUT_S:.0f} s; IDLE requested.')
        except Exception as exc:
            cal.update(state='failed', detail='Communication failure during calibration: '+str(exc))
            self._request_idle()

    def calibration_info(self):
        return dict(checklist=CALIBRATION_CHECKLIST,
            kinds={k: dict(state=v[1], description=v[2]) for k, v in CALIBRATIONS.items()})
