"""CSV test-matrix import: parse, validate row by row, preview, then save as plans.

The CSV is the operator's statement of intent. Validation checks types, units,
ranges and uniqueness; it cannot prove a point is safe or feasible on the rig.
Rig-limit and feasibility checks run again, against the connected boards, before
each test starts.
"""
import csv
import io
import math

COLUMNS = [
    ('test_id', 'text', 'Unique name for the test point, e.g. S0400-L050-R1. Letters, digits, - and _ only.'),
    ('feedback_mode', 'text', 'Test-motor feedback: sensored or sensorless. The load motor is always sensored.'),
    ('speed_rpm', 'rpm', 'Test-motor speed setpoint in mechanical revolutions per minute (> 0).'),
    ('load', 'N·m or A', 'Opposing load magnitude (≥ 0). Its unit is given by load_unit.'),
    ('load_unit', 'Nm | A', 'Nm = load-motor torque command in newton-metres. A = load-motor q-axis current in amperes (torque = Kt × current). Never mix them up.'),
    ('settle_time_s', 's', 'How long speed and load must stay inside tolerance before recording starts.'),
    ('speed_tolerance_rpm', 'rpm', 'Allowed speed deviation from speed_rpm while settling and recording.'),
    ('load_tolerance', 'same as load_unit', 'Allowed load deviation, in the same unit as load.'),
    ('record_duration_s', 's', 'Steady-state recording length.'),
    ('capture_rate_hz', 'Hz', 'Requested high-rate capture rate. Onboard capture runs at the board control-loop rate; a request above it is rejected before the run, and the actual rate is recorded. Leave blank for the native rate.'),
    ('repeat', 'count', 'Repeat number (1, 2, 3 …) of the same operating point.'),
    ('notes', 'text', 'Optional free text.'),
]
REQUIRED = [c for c, _, _ in COLUMNS if c not in ('capture_rate_hz', 'notes')]
EXAMPLE = [
    ['S0400-L000-SEN-R1', 'sensored', 400, 0, 'Nm', 2, 10, .02, 5, '', 1, 'No-load reference'],
    ['S0400-L050-SEN-R1', 'sensored', 400, .5, 'Nm', 2, 10, .02, 5, '', 1, ''],
    ['S0400-L050-SLS-R1', 'sensorless', 400, .5, 'Nm', 2, 10, .02, 5, '', 1, 'Requires commissioned sensorless start'],
    ['S0800-L050-SEN-R1', 'sensored', 800, .5, 'Nm', 2, 10, .02, 5, '', 1, ''],
    ['S0800-I003-SEN-R1', 'sensored', 800, 3, 'A', 2, 10, .2, 5, '', 1, 'Load given as current'],
]


def example_csv():
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow([c for c, _, _ in COLUMNS])
    writer.writerows(EXAMPLE)
    return stream.getvalue().encode('utf-8')


def _number(text, name, low, high, errors, row, integer=False, blank=None):
    text = (text or '').strip()
    if text == '':
        if blank is not None:
            return blank if blank != 'none' else None
        errors.append(f'Row {row}: {name} is required.')
        return None
    try:
        value = float(text)
    except ValueError:
        errors.append(f'Row {row}: {name} "{text}" is not a number.')
        return None
    if not math.isfinite(value) or not low <= value <= high:
        errors.append(f'Row {row}: {name} must be between {low:g} and {high:g}.')
        return None
    if integer and value != int(value):
        errors.append(f'Row {row}: {name} must be a whole number.')
        return None
    return int(value) if integer else value


def parse(text, existing_ids=(), limits=None):
    """Return {'rows': [...plans...], 'errors': [...], 'warnings': [...]} without saving."""
    if not isinstance(text, str) or not text.strip():
        return dict(rows=[], errors=['The file is empty.'], warnings=[])
    if len(text) > 2_000_000:
        return dict(rows=[], errors=['The file is larger than 2 MB.'], warnings=[])
    reader = csv.DictReader(io.StringIO(text.lstrip('﻿')))
    header = [h.strip() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED if c not in header]
    unknown = [h for h in header if h not in [c for c, _, _ in COLUMNS]]
    if missing:
        return dict(rows=[], errors=['Missing columns: '+', '.join(missing)+'. Download the example CSV for the exact header.'], warnings=[])
    errors, warnings, rows, seen = [], [], [], set()
    if unknown:
        warnings.append('Ignored unknown columns: '+', '.join(unknown))
    limits = limits or {}
    for number, raw in enumerate(reader, start=2):
        raw = {(k or '').strip(): (v or '').strip() for k, v in raw.items()}
        if not any(raw.values()):
            continue
        before = len(errors)
        test_id = raw.get('test_id', '')
        if not test_id or len(test_id) > 64 or any(not (c.isalnum() or c in '-_') for c in test_id):
            errors.append(f'Row {number}: test_id must be 1–64 letters, digits, - or _.')
        elif test_id in seen:
            errors.append(f'Row {number}: test_id {test_id} appears more than once in this file.')
        elif test_id in existing_ids:
            errors.append(f'Row {number}: test_id {test_id} already exists in the saved matrix.')
        seen.add(test_id)
        mode = raw.get('feedback_mode', '').lower()
        if mode not in ('sensored', 'sensorless'):
            errors.append(f'Row {number}: feedback_mode must be sensored or sensorless.')
        unit = raw.get('load_unit', '').replace('·', '').replace(' ', '')
        unit = {'Nm': 'Nm', 'nm': 'Nm', 'NM': 'Nm', 'A': 'A', 'a': 'A'}.get(unit)
        if unit is None:
            errors.append(f'Row {number}: load_unit must be Nm (torque) or A (current).')
        speed = _number(raw.get('speed_rpm'), 'speed_rpm', .001, 100000, errors, number)
        load = _number(raw.get('load'), 'load', 0, 1000, errors, number)
        settle = _number(raw.get('settle_time_s'), 'settle_time_s', 0, 60, errors, number)
        speed_tol = _number(raw.get('speed_tolerance_rpm'), 'speed_tolerance_rpm', .01, 10000, errors, number)
        load_tol = _number(raw.get('load_tolerance'), 'load_tolerance', .0001, 1000, errors, number)
        duration = _number(raw.get('record_duration_s'), 'record_duration_s', .1, 3600, errors, number)
        rate = _number(raw.get('capture_rate_hz'), 'capture_rate_hz', 1, 1e6, errors, number, blank='none')
        repeat = _number(raw.get('repeat'), 'repeat', 1, 100, errors, number, integer=True)
        if len(errors) > before:
            continue
        max_rpm, max_a, min_sensorless = limits.get('max_speed_rpm'), limits.get('max_load_a'), limits.get('sensorless_min_rpm')
        if max_rpm and speed > max_rpm:
            warnings.append(f'Row {number} ({test_id}): {speed:g} rpm is above the validated maximum {max_rpm:g} rpm; it will be blocked at run time.')
        if max_a and unit == 'A' and load > max_a:
            warnings.append(f'Row {number} ({test_id}): {load:g} A is above the validated maximum {max_a:g} A; it will be blocked at run time.')
        if mode == 'sensorless' and min_sensorless and speed < min_sensorless:
            warnings.append(f'Row {number} ({test_id}): sensorless at {speed:g} rpm is below the validated minimum {min_sensorless:g} rpm; it will be blocked.')
        rows.append(dict(test_id=test_id, method=mode, test_type='steady state', rpm=speed, load=load, load_unit=unit,
            settle_s=settle, settle_rpm=speed_tol, settle_load=load_tol, duration_s=duration,
            capture_rate_hz=rate, repeat=repeat, notes=raw.get('notes', '')[:4000], capture_high_rate=True, selected=True))
    if not rows and not errors:
        errors.append('The file has a header but no test rows.')
    return dict(rows=rows, errors=errors, warnings=warnings)
