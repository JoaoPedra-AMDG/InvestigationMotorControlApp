"""MOCK ODrive boards for exercising the interface without hardware.

Started only by `app.py --mock`. Everything produced here is labelled MOCK by
HardwareController and stored under `recordings-mock`. The physics is a crude
two-motor shaft model for testing screens and workflows; it is NOT a model of
the BM1109 rig and its numbers must never be reported as measurements.
"""
import math
import random
import threading
import time

IDLE, CLOSED_LOOP = 1, 8
MOCK_WATCHDOG_ERROR = 1  # Mock-only code; not an ODrive firmware error value.
MOCK_SERIALS = {'test': 'F00000000D01', 'load': 'F00000000D02'}
MOCK_PROFILE = dict(test_serial=MOCK_SERIALS['test'], load_serial=MOCK_SERIALS['load'],
    max_speed_rpm=1000., max_load_a=3.)


class Node:
    """Plain attribute container standing in for an ODrive object."""
    def __init__(self, **values):
        self.__dict__.update(values)


class MockShaft:
    """Both mock motors share one chain-coupled shaft (1:1, same positive sense)."""
    def __init__(self):
        self.lock = threading.RLock()
        self.boards = {}
        self.speed = 0.       # turns/s
        self.position = 0.    # turns
        self.last = time.perf_counter()
        self.inertia = 1e-3   # kg m^2, mock value
        self.friction = 5e-4  # N m s/rad, mock value

    def step(self):
        with self.lock:
            now = time.perf_counter()
            elapsed, self.last = min(now-self.last, .5), now
            steps = max(1, int(elapsed/.001))
            dt = elapsed/steps
            for _ in range(steps):
                torque = sum(board.axis0.torque_step(dt, self.speed) for board in self.boards.values())
                omega = self.speed*2*math.pi
                omega += dt*(torque-self.friction*omega)/self.inertia
                self.speed = omega/(2*math.pi)
                self.position += self.speed*dt
            for board in self.boards.values():
                board.update_readings(self.speed, self.position, elapsed)


class MockAxis:
    def __init__(self, board, role):
        object.__setattr__(self, '_board', board)
        object.__setattr__(self, '_role', role)
        object.__setattr__(self, '_state', IDLE)
        object.__setattr__(self, '_last_feed', time.perf_counter())
        object.__setattr__(self, '_torque', 0.)
        object.__setattr__(self, '_integral', 0.)
        velocity = role == 'test'
        motor_cfg = Node(motor_type=0, pole_pairs=3, torque_constant=.1061, phase_resistance=.05,
            phase_inductance=100e-6, phase_resistance_valid=True, phase_inductance_valid=True,
            current_soft_max=20., current_hard_max=30., calibration_current=5.,
            resistance_calib_max_voltage=2., current_control_bandwidth=1000., direction=1)
        self.config = Node(motor=motor_cfg, load_encoder=1, commutation_encoder=1,
            enable_watchdog=True, watchdog_timeout=1., init_vel=0., init_torque=0.,
            startup_closed_loop_control=False, startup_motor_calibration=False,
            startup_encoder_index_search=False, startup_encoder_offset_calibration=False,
            startup_homing=False, torque_soft_min=-3., torque_soft_max=3.,
            sensorless_ramp=Node(vel=50., accel=10., current=5., ramp_time=.5))
        self.controller = Node(input_vel=0., input_torque=0., vel_setpoint=0., torque_setpoint=0.,
            config=Node(control_mode=2 if velocity else 1, input_mode=2 if velocity else 6,
                vel_limit=50., vel_ramp_rate=10., torque_ramp_rate=1., vel_gain=.2,
                vel_integrator_gain=.4, pos_gain=20., enable_vel_limit=True,
                enable_torque_mode_vel_limit=True, use_commutation_vel=False,
                use_load_encoder_for_commutation_vel=False))
        self.motor = Node(
            foc=Node(Iq_measured=0., Id_measured=0., Iq_setpoint=0., Id_setpoint=0., I_measured_report_filter_k=1.),
            alpha_beta_controller=Node(current_meas_phA=0., current_meas_phB=0., current_meas_phC=0.),
            sensorless_estimator=Node(phase=0., phase_vel=0.),
            motor_thermistor=Node(temperature=25., config=Node(enabled=True)),
            fet_thermistor=Node(temperature=25.))
        self.commutation_mapper = Node(config=Node(offset_valid=True, offset=0., scale=3.))
        self.pos_vel_mapper = Node(config=Node(scale=1.))
        self.requested_state_value = IDLE
        self.active_errors = 0
        self.disarm_reason = 0
        self.procedure_result = 0
        self.pos_estimate = 0.
        self.vel_estimate = 0.

    # Reading the axis state advances the shared mock shaft.
    @property
    def current_state(self):
        self._board._shaft.step()
        return self._state

    @property
    def is_armed(self):
        return self._state == CLOSED_LOOP

    @property
    def requested_state(self):
        return self.requested_state_value

    @requested_state.setter
    def requested_state(self, value):
        self.requested_state_value = value
        if value == IDLE:
            object.__setattr__(self, '_state', IDLE)
        elif value == CLOSED_LOOP and self.active_errors == 0:
            self.controller.input_vel = self.config.init_vel
            self.controller.input_torque = self.config.init_torque
            object.__setattr__(self, '_last_feed', time.perf_counter())
            object.__setattr__(self, '_state', CLOSED_LOOP)
        else:
            self.procedure_result = 13  # INVALID_STATE: mock boards do not calibrate.

    def watchdog_feed(self):
        object.__setattr__(self, '_last_feed', time.perf_counter())

    def torque_step(self, dt, speed):
        c = self.controller
        if self._state != CLOSED_LOOP:
            c.vel_setpoint, c.torque_setpoint = speed, 0.
            object.__setattr__(self, '_torque', 0.)
            object.__setattr__(self, '_integral', 0.)
            return 0.
        if self.config.enable_watchdog and time.perf_counter()-self._last_feed > self.config.watchdog_timeout:
            self.active_errors, self.disarm_reason = MOCK_WATCHDOG_ERROR, MOCK_WATCHDOG_ERROR
            object.__setattr__(self, '_state', IDLE)
            return 0.
        kt = self.config.motor.torque_constant
        limit = self.config.motor.current_soft_max*kt
        if c.config.control_mode == 2:
            step = c.config.vel_ramp_rate*dt
            c.vel_setpoint += max(-step, min(step, c.input_vel-c.vel_setpoint))
            error = c.vel_setpoint-speed  # turns/s; gains are in N m per turn/s like ODrive
            integral = max(-limit, min(limit, self._integral+c.config.vel_integrator_gain*error*dt))
            object.__setattr__(self, '_integral', integral)
            torque = c.config.vel_gain*error+integral
        else:
            step = c.config.torque_ramp_rate*dt
            c.torque_setpoint += max(-step, min(step, c.input_torque-c.torque_setpoint))
            torque = c.torque_setpoint
        torque = max(-limit, min(limit, torque))
        object.__setattr__(self, '_torque', torque)
        return torque


class MockBoard:
    def __init__(self, shaft, role, serial):
        self._shaft, self._role = shaft, role
        self.serial_number = int(serial, 16)
        self.fw_version_major, self.fw_version_minor, self.fw_version_revision = 0, 6, 11
        self.fw_version_unreleased = 0
        self.hw_version_major, self.hw_version_minor, self.hw_version_variant = 0, 0, 0
        self.vbus_voltage = 26.5
        self.ibus = 0.
        self.ibus_report_filter_k = 1.
        self.config = Node(dc_bus_overvoltage_trip_level=30., dc_bus_undervoltage_trip_level=20.,
            dc_max_positive_current=20., dc_max_negative_current=-10.,
            brake_resistor0=Node(enable=False))
        self.axis0 = MockAxis(self, role)

    def update_readings(self, speed, position, elapsed):
        a = self.axis0
        kt, pp = a.config.motor.torque_constant, a.config.motor.pole_pairs
        a.vel_estimate, a.pos_estimate = speed, position
        iq = a._torque/kt
        foc = a.motor.foc
        foc.Iq_setpoint = iq
        foc.Iq_measured = iq+random.gauss(0, .02) if a._state == CLOSED_LOOP else 0.
        foc.Id_measured = random.gauss(0, .01) if a._state == CLOSED_LOOP else 0.
        theta = (position*pp % 1)*2*math.pi
        ab = a.motor.alpha_beta_controller
        ab.current_meas_phA = -foc.Iq_measured*math.sin(theta)
        ab.current_meas_phB = -foc.Iq_measured*math.sin(theta-2*math.pi/3)
        ab.current_meas_phC = -foc.Iq_measured*math.sin(theta+2*math.pi/3)
        a.motor.sensorless_estimator.phase = theta-math.pi
        a.motor.sensorless_estimator.phase_vel = speed*pp*2*math.pi
        power = a._torque*speed*2*math.pi+1.5*a.config.motor.phase_resistance*foc.Iq_measured**2
        self.ibus = power/self.vbus_voltage
        self.vbus_voltage = 26.5-.02*self.ibus
        heat = .02*foc.Iq_measured**2-.01*(a.motor.motor_thermistor.temperature-25)
        a.motor.motor_thermistor.temperature += heat*elapsed
        a.motor.fet_thermistor.temperature += .5*heat*elapsed

    def clear_errors(self):
        self.axis0.active_errors = self.axis0.disarm_reason = 0

    def save_configuration(self):
        return True  # Mock: nothing is stored.


class MockConnector:
    """Connector interface used by HardwareController, backed by mock boards."""
    is_mock = True

    def __init__(self):
        self.shaft = MockShaft()
        self.boards = {serial: MockBoard(self.shaft, role, serial) for role, serial in MOCK_SERIALS.items()}

    def discover(self, window_s):
        time.sleep(min(window_s, .2))
        return {serial: 'MOCK ODrive (not hardware)' for serial in self.boards}

    def connect(self, serial, timeout):
        if serial not in self.boards:
            raise TimeoutError(f'No MOCK board with serial {serial}. Mock serials: {", ".join(self.boards)}')
        board = self.boards[serial]
        self.shaft.boards[serial] = board
        return board

    def release(self, device):
        self.shaft.boards.pop(f'{device.serial_number:012X}', None)
