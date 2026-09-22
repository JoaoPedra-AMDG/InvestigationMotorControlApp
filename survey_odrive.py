"""Stage 0: read-only survey of one ODrive's property tree.

Usage (close the ODrive GUI, odrivetool and the workbench first):

    .venv\\Scripts\\python.exe survey_odrive.py --serial 3A1B2C3D4E5F

What it does:
  * connects to exactly the requested serial number over USB;
  * reads every property value and records its type and whether it is writable;
  * records every function's name and signature WITHOUT calling it;
  * compares the tree with the property paths this application uses;
  * writes surveys/<serial>_<UTC time>.json and releases the USB connection.

It never writes a property, never calls a firmware function (so it cannot
calibrate, arm, save, reboot or erase), and never changes the axis state.
Reading properties does not energise the motor.
"""
import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

from hardware import SIGNAL_PATHS, CONFIG_PATHS, release_sync_device

ROOT = Path(__file__).resolve().parent
# Runtime paths the workbench reads or writes outside SIGNAL_PATHS / CONFIG_PATHS.
RUNTIME_PATHS = ['serial_number', 'fw_version_major', 'fw_version_minor', 'fw_version_revision',
    'fw_version_unreleased', 'axis0.current_state', 'axis0.requested_state', 'axis0.active_errors',
    'axis0.disarm_reason', 'axis0.procedure_result', 'axis0.is_armed',
    'axis0.motor.sensorless_estimator.phase_vel', 'control_loop_hz']
RUNTIME_FUNCTIONS = ['axis0.watchdog_feed', 'clear_errors', 'save_configuration', 'reboot']


def _plain(value):
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    return str(value)


def walk(obj, is_property, function_signature, is_object, prefix='', depth=12):
    """Return (properties, functions) for an ODrive object tree.

    is_property(owner_type, name) -> (codec_name, writable) or None
    function_signature(value, name) -> str or None (never calls the function)
    is_object(value) -> bool
    """
    properties, functions = [], []
    if depth <= 0:
        return properties, functions
    names = {n for n in dir(type(obj)) if not n.startswith('_')} | {n for n in vars(obj) if not n.startswith('_')}
    for name in sorted(names):
        path = prefix+name
        info = is_property(type(obj), name)
        if info is not None:
            codec, writable = info
            try:
                value, error = _plain(getattr(obj, name)), None
            except Exception as exc:  # A failed read is recorded, not fatal.
                value, error = None, f'{type(exc).__name__}: {exc}'
            properties.append(dict(path=path, type=codec, writable=writable, value=value, read_error=error))
            continue
        member = vars(obj).get(name)
        signature = function_signature(member, name) if member is not None else None
        if signature is not None:
            functions.append(dict(path=path, signature=signature))
        elif member is not None and is_object(member):
            sub_props, sub_funcs = walk(member, is_property, function_signature, is_object, path+'.', depth-1)
            properties += sub_props
            functions += sub_funcs
    return properties, functions


def compare(properties, functions):
    known = {p['path']: p for p in properties}
    function_paths = {f['path'] for f in functions}
    wanted = list(dict.fromkeys([path for path, _, _ in SIGNAL_PATHS.values()]+CONFIG_PATHS+RUNTIME_PATHS))
    return dict(
        missing_properties=[p for p in wanted if p not in known],
        present_properties={p: dict(type=known[p]['type'], writable=known[p]['writable']) for p in wanted if p in known},
        missing_functions=[f for f in RUNTIME_FUNCTIONS if f not in function_paths])


def odrive_inspectors():
    from odrive.sync_tree import SyncFunction, SyncObject, SyncPropertyAttribute

    def is_property(owner, name):
        member = getattr(owner, name, None)
        return (member._info.codec_name, member._info.writable) if isinstance(member, SyncPropertyAttribute) else None

    def function_signature(value, name):
        return value._info.dump(name) if isinstance(value, SyncFunction) else None

    return is_property, function_signature, lambda value: isinstance(value, SyncObject)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--serial', required=True, help='Exact ODrive serial number (hexadecimal).')
    parser.add_argument('--timeout', type=float, default=5., help='Seconds to wait for that board.')
    parser.add_argument('--out-dir', default=str(ROOT/'surveys'))
    args = parser.parse_args(argv)
    serial = args.serial.strip().upper().removeprefix('0X')
    print('READ-ONLY SURVEY: no property is written and no firmware function is called.', flush=True)
    import odrive
    device = odrive.find_sync(serial_number=serial, timeout=args.timeout, interfaces=['usb'])
    try:
        properties, functions = walk(device, *odrive_inspectors())
    finally:
        release_sync_device(device)
        print('USB connection released.', flush=True)
    values = {p['path']: p['value'] for p in properties}
    firmware = '.'.join(str(values.get('fw_version_'+k)) for k in ('major', 'minor', 'revision'))
    report = dict(serial=serial, surveyed_utc=datetime.now(timezone.utc).isoformat(),
        firmware=firmware, firmware_unreleased=values.get('fw_version_unreleased'),
        odrive_python_package=getattr(odrive, '__version__', None),
        method='Read-only property walk; functions recorded by signature only, never called.',
        comparison=compare(properties, functions), properties=properties, functions=functions)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out/f"{serial}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    c = report['comparison']
    print(f'Firmware {firmware}: {len(properties)} properties, {len(functions)} functions.')
    print(f"Workbench paths present: {len(c['present_properties'])}; missing: {len(c['missing_properties'])}")
    for missing in c['missing_properties']:
        print('  MISSING', missing)
    for missing in c['missing_functions']:
        print('  MISSING FUNCTION', missing)
    print('Saved', path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
