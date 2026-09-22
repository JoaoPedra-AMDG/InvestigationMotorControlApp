"""Documented ODrive 0.6.x values used by the workbench, and the write allowlist.

Every name and numeric value below comes from the ODrive 0.6.12 API reference
(https://docs.odriverobotics.com/v/latest/fibre_types/com_odriverobotics_ODrive.html)
and matches odrive/enums.py in the installed odrive 0.6.11.post1 package.
Explanations are short summaries written for this workbench; follow the linked
reference for the full text. A property that the connected firmware does not
expose is shown as Unavailable and is never written.
"""
import math

DOC = 'https://docs.odriverobotics.com/v/latest/fibre_types/com_odriverobotics_ODrive.html'

AXIS_STATES = {0: 'UNDEFINED', 1: 'IDLE', 2: 'STARTUP_SEQUENCE', 3: 'FULL_CALIBRATION_SEQUENCE',
    4: 'MOTOR_CALIBRATION', 6: 'ENCODER_INDEX_SEARCH', 7: 'ENCODER_OFFSET_CALIBRATION',
    8: 'CLOSED_LOOP_CONTROL', 9: 'LOCKIN_SPIN', 10: 'ENCODER_DIR_FIND', 11: 'HOMING',
    12: 'ENCODER_HALL_POLARITY_CALIBRATION', 13: 'ENCODER_HALL_PHASE_CALIBRATION',
    14: 'ANTICOGGING_CALIBRATION', 15: 'HARMONIC_CALIBRATION', 16: 'HARMONIC_CALIBRATION_COMMUTATION'}
CONTROL_MODES = {0: 'VOLTAGE_CONTROL', 1: 'TORQUE_CONTROL', 2: 'VELOCITY_CONTROL', 3: 'POSITION_CONTROL'}
INPUT_MODES = {0: 'INACTIVE', 1: 'PASSTHROUGH', 2: 'VEL_RAMP', 3: 'POS_FILTER', 4: 'MIX_CHANNELS',
    5: 'TRAP_TRAJ', 6: 'TORQUE_RAMP', 7: 'MIRROR', 8: 'TUNING'}
MOTOR_TYPES = {0: 'PMSM_CURRENT_CONTROL', 2: 'PMSM_VOLTAGE_CONTROL', 3: 'ACIM'}
ENCODER_IDS = {0: 'NONE', 1: 'INC_ENCODER0', 2: 'INC_ENCODER1', 3: 'INC_ENCODER2',
    4: 'SENSORLESS_ESTIMATOR', 5: 'SPI_ENCODER0', 6: 'SPI_ENCODER1', 7: 'SPI_ENCODER2',
    8: 'HALL_ENCODER0', 9: 'HALL_ENCODER1', 10: 'RS485_ENCODER0', 11: 'RS485_ENCODER1',
    12: 'RS485_ENCODER2', 13: 'ONBOARD_ENCODER0', 14: 'ONBOARD_ENCODER1'}

# ODrive.Error bit flags (used by axis0.active_errors and axis0.disarm_reason).
ERRORS = {
    0x1: ('INITIALIZING', 'Board is starting up or reconfiguring; non-IDLE states are refused until it clears. Persisting for more than a few seconds with good DC voltage may indicate damage.'),
    0x2: ('SYSTEM_LEVEL', 'Unexpected firmware-level fault (e.g. memory or thread failure); indicates a firmware bug.'),
    0x4: ('TIMING_ERROR', 'An internal timing deadline was missed, usually from computational overload.'),
    0x8: ('MISSING_ESTIMATE', 'A position, velocity or phase estimate was needed but invalid: encoder not calibrated, not homed, or an encoder is disconnected/misbehaving.'),
    0x10: ('BAD_CONFIG', 'Configuration is invalid or incomplete (e.g. direction not ±1, torque soft limits inverted, motor R/L not valid).'),
    0x20: ('DRV_FAULT', 'The gate driver reported a fault; repeated occurrence within ratings can indicate hardware damage.'),
    0x40: ('MISSING_INPUT', 'No setpoint was provided for the active control input.'),
    0x100: ('DC_BUS_OVER_VOLTAGE', 'DC voltage exceeded config.dc_bus_overvoltage_trip_level; check regeneration handling and the trip level.'),
    0x200: ('DC_BUS_UNDER_VOLTAGE', 'DC voltage fell below config.dc_bus_undervoltage_trip_level; check supply/battery and leads.'),
    0x400: ('DC_BUS_OVER_CURRENT', 'DC current exceeded the axis I_bus_hard_max or board config.dc_max_positive_current.'),
    0x800: ('DC_BUS_OVER_REGEN_CURRENT', 'Regenerated DC current was more negative than I_bus_hard_min or config.dc_max_negative_current.'),
    0x1000: ('CURRENT_LIMIT_VIOLATION', 'Motor current exceeded current_hard_max; widen the soft/hard margin or check current-loop stability.'),
    0x2000: ('MOTOR_OVER_TEMP', 'Motor thermistor exceeded its upper temperature limit.'),
    0x4000: ('INVERTER_OVER_TEMP', 'Inverter (FET) thermistor exceeded its upper temperature limit.'),
    0x8000: ('VELOCITY_LIMIT_VIOLATION', 'Estimated velocity exceeded vel_limit_tolerance × vel_limit.'),
    0x10000: ('POSITION_LIMIT_VIOLATION', 'Position limit violated (no further description in the reference).'),
    0x20000: ('REQUESTED_CURRENT_TOO_HIGH', 'Requested calibration/lock-in current exceeded the effective current limit.'),
    0x1000000: ('WATCHDOG_TIMER_EXPIRED', 'The axis watchdog was not fed within config.watchdog_timeout (communication loss or host stall).'),
    0x2000000: ('ESTOP_REQUESTED', 'An external estop was requested (CAN estop or endstop).'),
    0x4000000: ('SPINOUT_DETECTED', 'Electrical and mechanical power disagreed, indicating a spinout.'),
    0x8000000: ('BRAKE_RESISTOR_DISARMED', 'Another component (often the brake resistor) disarmed; fix the root cause, then clear errors.'),
    0x10000000: ('THERMISTOR_DISCONNECTED', 'Motor thermistor enabled but reads as disconnected.'),
    0x40000000: ('CALIBRATION_ERROR', 'A calibration procedure failed; see procedure_result.'),
}
PROCEDURE_RESULTS = {
    0: ('SUCCESS', 'Procedure finished without faults.'),
    1: ('BUSY', 'Procedure still running.'),
    2: ('CANCELLED', 'Procedure was cancelled by the user.'),
    3: ('DISARMED', 'A fault disarmed the axis; see disarm_reason.'),
    4: ('NO_RESPONSE', 'A component did not respond; most often encoder wiring or configuration.'),
    5: ('POLE_PAIR_CPR_MISMATCH', 'Pole pairs and/or encoder CPR do not match the measured rotation; see observed_encoder_scale_factor.'),
    6: ('PHASE_RESISTANCE_OUT_OF_RANGE', 'Measured phase resistance implausible; check motor leads and resistance_calib_max_voltage.'),
    7: ('PHASE_INDUCTANCE_OUT_OF_RANGE', 'Measured phase inductance implausible; check motor leads and calibration parameters.'),
    8: ('UNBALANCED_PHASES', 'Phase resistances are unbalanced; check connections.'),
    9: ('INVALID_MOTOR_TYPE', 'config.motor.motor_type is not a valid MotorType.'),
    10: ('ILLEGAL_HALL_STATE', 'Too many invalid hall states during calibration.'),
    11: ('TIMEOUT', 'Procedure timed out.'),
    12: ('HOMING_WITHOUT_ENDSTOP', 'Homing requested without an enabled endstop.'),
    13: ('INVALID_STATE', 'Requested state is not a valid AxisState.'),
    14: ('NOT_CALIBRATED', 'State needs calibration first (typically motor then encoder offset calibration).'),
    15: ('NOT_CONVERGING', 'Calibration measurements did not converge (e.g. rotor moved too little).'),
    16: ('REQUESTED_CURRENT_TOO_HIGH', 'Calibration or lock-in current exceeds the configured current limit.'),
}


def decode_errors(value):
    """List of {bit, name, explanation, doc} for an ODrive.Error bitfield; [] for 0/None."""
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return []
    decoded, remaining = [], value
    for bit, (name, text) in ERRORS.items():
        if value & bit:
            decoded.append(dict(bit=bit, name=name, explanation=text, doc=f'{DOC}#ODrive.Error.{name}'))
            remaining &= ~bit
    if remaining:
        decoded.append(dict(bit=remaining, name='UNDOCUMENTED', explanation='Bits not listed in the 0.6.12 reference; check the firmware version.', doc=DOC))
    return decoded


def decode_procedure(value):
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    name, text = PROCEDURE_RESULTS.get(value, ('UNKNOWN', 'Not listed in the 0.6.12 reference.'))
    return dict(code=value, name=name, explanation=text, doc=f'{DOC}#ODrive.ProcedureResult.{name}')


def _entry(path, label, group, kind, unit='', low=None, high=None, choices=None, note=''):
    return dict(path=path, label=label, group=group, kind=kind, unit=unit, min=low, max=high,
        choices=choices, note=note)


# Write allowlist. Ranges are sanity bounds for typing errors, NOT safe operating
# limits; the rig limits are the operator's responsibility and are checked again
# by readiness. Measured quantities (phase R/L, offsets) are calibration outputs
# and are deliberately read-only here.
REGISTRY = [
    _entry('config.dc_bus_overvoltage_trip_level', 'DC-bus overvoltage trip', 'Power', 'float', 'V', 12, 58, note='ODrive Pro maximum rating is 58 V.'),
    _entry('config.dc_bus_undervoltage_trip_level', 'DC-bus undervoltage trip', 'Power', 'float', 'V', 8, 56),
    _entry('config.dc_max_positive_current', 'Max positive DC current', 'Power', 'float', 'A', .1, 120),
    _entry('config.dc_max_negative_current', 'Max negative (regenerative) DC current', 'Power', 'float', 'A', -120, 0, note='Negative value; the battery must accept this charge current.'),
    _entry('config.max_regen_current', 'Max regenerative current', 'Power', 'float', 'A', 0, 120),
    _entry('axis0.config.motor.motor_type', 'Motor type', 'Motor', 'enum', choices=MOTOR_TYPES),
    _entry('axis0.config.motor.pole_pairs', 'Pole pairs', 'Motor', 'int', '', 1, 50),
    _entry('axis0.config.motor.torque_constant', 'Torque constant', 'Motor', 'float', 'N·m/A', .001, 10, note='ODrive convention Kt = 8.27 / Kv.'),
    _entry('axis0.config.motor.current_soft_max', 'Current soft max', 'Motor', 'float', 'A', .1, 120),
    _entry('axis0.config.motor.current_hard_max', 'Current hard max (trip)', 'Motor', 'float', 'A', .1, 150),
    _entry('axis0.config.motor.calibration_current', 'Calibration current', 'Motor', 'float', 'A', .1, 60),
    _entry('axis0.config.motor.resistance_calib_max_voltage', 'Resistance-calibration max voltage', 'Motor', 'float', 'V', .1, 30),
    _entry('axis0.config.motor.current_control_bandwidth', 'Current-control bandwidth', 'Motor', 'float', 'rad/s', 10, 10000),
    _entry('axis0.config.motor.direction', 'Motor direction', 'Motor', 'enum', choices={-1: '-1', 1: '+1'}, note='Normally set by encoder offset calibration.'),
    _entry('axis0.motor.motor_thermistor.config.enabled', 'Motor thermistor enabled', 'Thermal', 'bool', note='Only enable with a thermistor connected.'),
    _entry('axis0.motor.motor_thermistor.config.temp_limit_lower', 'Motor derating start', 'Thermal', 'float', '°C', 0, 200),
    _entry('axis0.motor.motor_thermistor.config.temp_limit_upper', 'Motor over-temperature trip', 'Thermal', 'float', '°C', 0, 200),
    _entry('axis0.config.load_encoder', 'Load (position/velocity) encoder', 'Encoder', 'enum', choices=ENCODER_IDS),
    _entry('axis0.config.commutation_encoder', 'Commutation encoder', 'Encoder', 'enum', choices=ENCODER_IDS),
    _entry('inc_encoder0.config.enabled', 'Incremental encoder 0 enabled', 'Encoder', 'bool'),
    _entry('inc_encoder0.config.cpr', 'Incremental encoder 0 CPR', 'Encoder', 'int', 'counts/rev', 4, 1000000),
    _entry('axis0.config.calibration_lockin.current', 'Encoder-calibration lock-in current', 'Encoder', 'float', 'A', .1, 60),
    _entry('axis0.config.sensorless_ramp.vel', 'Sensorless ramp final speed', 'Sensorless', 'float', 'rad/s electrical', 1, 5000),
    _entry('axis0.config.sensorless_ramp.accel', 'Sensorless ramp acceleration', 'Sensorless', 'float', 'rad/s² electrical', .1, 5000),
    _entry('axis0.config.sensorless_ramp.current', 'Sensorless ramp current', 'Sensorless', 'float', 'A', .1, 60),
    _entry('axis0.config.sensorless_ramp.ramp_time', 'Sensorless ramp time', 'Sensorless', 'float', 's', 0, 30),
    _entry('axis0.controller.config.control_mode', 'Control mode', 'Control', 'enum', choices=CONTROL_MODES),
    _entry('axis0.controller.config.input_mode', 'Input mode', 'Control', 'enum', choices=INPUT_MODES),
    _entry('axis0.controller.config.vel_limit', 'Velocity limit', 'Control', 'float', 'turn/s', .01, 200),
    _entry('axis0.controller.config.vel_limit_tolerance', 'Velocity-limit fault tolerance', 'Control', 'float', '×', 1, 10),
    _entry('axis0.controller.config.enable_vel_limit', 'Velocity limit enabled', 'Control', 'bool'),
    _entry('axis0.controller.config.enable_torque_mode_vel_limit', 'Velocity limit in torque mode', 'Control', 'bool'),
    _entry('axis0.controller.config.enable_overspeed_error', 'Overspeed fault enabled', 'Control', 'bool'),
    _entry('axis0.controller.config.vel_ramp_rate', 'Velocity ramp rate', 'Control', 'float', 'turn/s²', .001, 1000),
    _entry('axis0.controller.config.torque_ramp_rate', 'Torque ramp rate', 'Control', 'float', 'N·m/s', .001, 100),
    _entry('axis0.controller.config.vel_gain', 'Velocity gain', 'Control', 'float', 'N·m/(turn/s)', 0, 10),
    _entry('axis0.controller.config.vel_integrator_gain', 'Velocity integrator gain', 'Control', 'float', 'N·m/turn', 0, 100),
    _entry('axis0.config.torque_soft_min', 'Torque soft min', 'Control', 'float', 'N·m', -50, 0),
    _entry('axis0.config.torque_soft_max', 'Torque soft max', 'Control', 'float', 'N·m', 0, 50),
    _entry('axis0.config.enable_watchdog', 'Watchdog enabled', 'Watchdog', 'bool'),
    _entry('axis0.config.watchdog_timeout', 'Watchdog timeout', 'Watchdog', 'float', 's', .05, 10),
    _entry('axis0.config.init_vel', 'Velocity input at arming', 'Start-up', 'float', 'turn/s', 0, 0, note='Must be 0: firmware loads it into input_vel when arming.'),
    _entry('axis0.config.init_torque', 'Torque input at arming', 'Start-up', 'float', 'N·m', 0, 0, note='Must be 0: firmware loads it into input_torque when arming.'),
    _entry('axis0.config.startup_closed_loop_control', 'Closed loop at power-up', 'Start-up', 'bool', note='Must stay off: motors must never start on power-up.'),
    _entry('axis0.config.startup_motor_calibration', 'Motor calibration at power-up', 'Start-up', 'bool', note='Must stay off.'),
    _entry('axis0.config.startup_encoder_index_search', 'Index search at power-up', 'Start-up', 'bool', note='Must stay off.'),
    _entry('axis0.config.startup_encoder_offset_calibration', 'Encoder calibration at power-up', 'Start-up', 'bool', note='Must stay off.'),
    _entry('axis0.config.startup_homing', 'Homing at power-up', 'Start-up', 'bool', note='Must stay off.'),
]
REGISTRY_BY_PATH = {e['path']: e for e in REGISTRY}
FORCED_FALSE = {'axis0.config.startup_closed_loop_control', 'axis0.config.startup_motor_calibration',
    'axis0.config.startup_encoder_index_search', 'axis0.config.startup_encoder_offset_calibration',
    'axis0.config.startup_homing'}
# Role policy: the test motor runs speed control, the load motor torque control.
ROLE_MODES = {'test': (2, 2), 'load': (1, 6)}
PRO_MAX_VOLTAGE = 58.


def coerce(path, value):
    """Validate one proposed value against the allowlist; returns the typed value."""
    entry = REGISTRY_BY_PATH.get(path)
    if entry is None:
        raise ValueError(f'{path} is not in the workbench write allowlist.')
    kind, label = entry['kind'], entry['label']
    if kind == 'bool':
        if not isinstance(value, bool):
            raise ValueError(f'{label} must be true or false.')
        if path in FORCED_FALSE and value:
            raise ValueError(f'{label} must stay off; automatic start-up behaviour is not permitted.')
        return value
    if isinstance(value, bool):
        raise ValueError(f'{label} must be a number.')
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{label} must be a number.') from None
    if not math.isfinite(number):
        raise ValueError(f'{label} must be finite.')
    if kind == 'enum':
        if number != int(number) or int(number) not in entry['choices']:
            raise ValueError(f'{label} must be one of: ' + ', '.join(f'{k} ({v})' for k, v in entry['choices'].items()))
        return int(number)
    if kind == 'int':
        if number != int(number):
            raise ValueError(f'{label} must be a whole number.')
        number = int(number)
    if not entry['min'] <= number <= entry['max']:
        raise ValueError(f"{label} must be between {entry['min']:g} and {entry['max']:g} {entry['unit']}.".strip())
    return number


def cross_check(role, values):
    """Consistency rules on the complete post-change configuration of one board."""
    problems = []
    get = values.get
    soft, hard = get('axis0.config.motor.current_soft_max'), get('axis0.config.motor.current_hard_max')
    if isinstance(soft, (int, float)) and isinstance(hard, (int, float)) and hard <= soft:
        problems.append('Current hard max must be greater than current soft max.')
    tmin, tmax = get('axis0.config.torque_soft_min'), get('axis0.config.torque_soft_max')
    if isinstance(tmin, (int, float)) and isinstance(tmax, (int, float)) and tmin > tmax:
        problems.append('Torque soft min must not exceed torque soft max.')
    under, over = get('config.dc_bus_undervoltage_trip_level'), get('config.dc_bus_overvoltage_trip_level')
    if isinstance(under, (int, float)) and isinstance(over, (int, float)) and under >= over:
        problems.append('DC undervoltage trip must be below the overvoltage trip.')
    low, high = get('axis0.motor.motor_thermistor.config.temp_limit_lower'), get('axis0.motor.motor_thermistor.config.temp_limit_upper')
    if isinstance(low, (int, float)) and isinstance(high, (int, float)) and low >= high:
        problems.append('Motor derating start must be below the over-temperature trip.')
    control, input_mode = ROLE_MODES[role]
    if get('axis0.controller.config.control_mode') not in (None, control):
        problems.append(f"The {'test' if role == 'test' else 'load'} motor must use {CONTROL_MODES[control]}.")
    if get('axis0.controller.config.input_mode') not in (None, input_mode):
        problems.append(f"The {'test' if role == 'test' else 'load'} motor must use {INPUT_MODES[input_mode]}.")
    if role == 'load' and 4 in (get('axis0.config.load_encoder'), get('axis0.config.commutation_encoder')):
        problems.append('The load motor must stay sensored; it is the independent speed reference.')
    for path in FORCED_FALSE:
        if get(path) is True:
            problems.append(REGISTRY_BY_PATH[path]['label'] + ' is on; it must be turned off.')
    for path in ('axis0.config.init_vel', 'axis0.config.init_torque'):
        if isinstance(get(path), (int, float)) and get(path) != 0:
            problems.append(REGISTRY_BY_PATH[path]['label'] + ' must be 0.')
    return problems
