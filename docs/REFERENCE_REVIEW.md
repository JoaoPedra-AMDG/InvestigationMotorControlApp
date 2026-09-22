# Official ODrive GUI reference review and feature checklist

Reviewed 2026-09-22. This workbench is an independent university research tool. It
is **not** an ODrive Robotics product and is not endorsed by ODrive Robotics.

## Sources inspected

| Source | What it provided |
|---|---|
| Official Web GUI, `gui.odriverobotics.com` (opened without a board) | Top-level tabs: **Configuration**, **Dashboard**, **Inspector**, **Firmware Update**, **Docs**. Supported devices listed: ODrive Pro, S1, Micro, USB-CAN Adapter. The wizard steps only appear with a connected board, so they were taken from the documentation. |
| Docs 0.6.12: *Web GUI* (`interfaces/gui.html`) | Needs a WebUSB browser (Chromium). Only one program may own a board at a time. Covers the Windows WinUSB driver and Linux udev rules, and the GUI's analytics. |
| Docs 0.6.12: *odrivetool Setup* (`guides/odrivetool-setup.html`) | Configuration steps the GUI wizard mirrors: power supply limits, motor type, pole pairs and torque constant, motor calibration, current and velocity limits, thermistor limits, encoder setup, encoder offset calibration, closed loop. |
| Docs 0.6.12: *Firmware Update* (`guides/firmware-update.html`) | The GUI installs firmware from 0.6.7 onward; `odrivetool new-dfu` from 0.6.5 onward. Updating **erases configuration and calibration**. Covers the master and devel channels and recovery via forced DFU. |
| Docs 0.6.12: *Hardware Configuration*, Sensorless section | Sensorless mode is **experimental**. It starts with an open-loop ramp (`config.sensorless_ramp`) and switches to closed loop automatically. No property is documented that confirms the switch has happened. |
| Docs 0.6.12: *ODrive API Reference* (`fibre_types/com_odriverobotics_ODrive.html`) | 832 documented objects, properties, functions and enum values, including `ODrive.Error` bit values, `ProcedureResult`, `AxisState`, `EncoderId`, `Motor.torque_estimate`, `Motor.electrical_power`, `Oscilloscope`, `reboot_required`, `save_configuration`, `erase_configuration`, `enter_dfu_mode`. |
| Installed `odrive==0.6.11.post1` package source | `find_sync`; `DeviceManager.subscribe` (passive discovery) and `release_connection`. `high_rate_capture` records at the **native control-loop rate only**, with no decimation. `odrive.enums` values match the documentation. |

**Firmware supported by this workbench:** released 0.6.x, 0.6.10 or newer, with the
same version on both boards (an existing readiness rule). The 0.6.12 documentation
was the reference. The actual boards' property tree must be confirmed with
`survey_odrive.py` (Stage 0) before relying on any property. Every property used
here is either in the 0.6.12 API reference or read defensively: a missing
property shows as **Unavailable** and is never guessed.

## Feature checklist

Status key: **Implemented**: code and automated tests exist. **HW-verified**:
exercised on the physical rig. **Needs rig validation**: implemented but not yet
exercised on hardware. **Unsupported**: deliberately not provided, reason given.

No feature is HW-verified yet. The USB isolators were outstanding and no board
has been connected during development.

| Official GUI feature | This workbench | Status |
|---|---|---|
| Device discovery | Passive USB discovery lists serial numbers without opening a connection | Implemented · Needs rig validation |
| Connect and identify (hex serial, firmware, hardware version) | Connect by assigned serial, identity re-checked on every write | Implemented · Needs rig validation |
| Two boards at once | Explicit **Test Motor** / **Load Motor** roles | Implemented · Needs rig validation |
| Configuration wizard: power supply | DC-bus overvoltage and undervoltage trips, positive and negative DC current, `max_regen_current` | Implemented (preview, apply, read back) · Needs rig validation |
| Configuration wizard: motor | Motor type, pole pairs, torque constant, current soft and hard max, calibration current, resistance-calibration voltage, current-control bandwidth, direction | Implemented · Needs rig validation |
| Configuration wizard: encoder | Load and commutation encoder IDs, incremental encoder 0 enable and CPR, encoder-calibration lock-in current, sensorless ramp. SPI, RS485 and Hall encoder settings are **not** in the allowlist: their object paths on the Pro could not be confirmed without a board. Configure them in the official GUI if needed. | Implemented (incremental and sensorless only) · Needs rig validation |
| Configuration wizard: control | Control and input mode, velocity limit and tolerance, ramps, gains, torque soft limits, torque-mode velocity limit | Implemented · Needs rig validation |
| Watchdog configuration | Enable and timeout, range-checked against the polling rate | Implemented · Needs rig validation |
| Thermistor limits | Motor thermistor enable and limits (`axis0.motor.motor_thermistor.config`). FET limits are not writable here. The motor and FET temperatures are displayed where readable. | Implemented · Needs rig validation (the thermistor path must be confirmed by the survey) |
| Calibration | Supervised motor calibration, encoder offset calibration and full calibration sequence, one axis at a time, with checklist confirmation, `procedure_result` decoding and timeout-to-IDLE | Implemented · Needs rig validation |
| Encoder direction and alignment | Encoder offset calibration determines direction and offset. Motor-direction check is a supervised observation step | Implemented · Needs rig validation |
| Dashboard: commands and live feedback | Paired closed-loop start (test velocity, load torque held at zero until speed), load set and zero, Stop Both | Implemented · Needs rig validation |
| Dashboard: independent per-motor control of arbitrary modes | Restricted: the test motor is velocity-controlled only, the load motor torque-controlled only, and the load is only applied while the test motor is in closed loop | Deliberately restricted (prevents the chain-coupled motors fighting) |
| Fault inspection and explanation | `active_errors` / `disarm_reason` decoded bit by bit using documented values, with short explanations and doc links; `procedure_result` decoded | Implemented · Needs rig validation |
| Fault recovery | Clear errors (only when both are IDLE); never restarts motion | Implemented · Needs rig validation |
| Save configuration | Explicit option. Rejected unless start-up closed loop and start-up calibrations are off. Board reboots, then **Reconnect and verify** compares persisted values | Implemented · Needs rig validation |
| Configuration backup and restore | JSON backup of all registry values for both boards. Restore goes through the same preview → apply → read-back path, with identity check | Implemented · Needs rig validation |
| Firmware identification | Version, unreleased flag, hardware version, bootloader version; compatibility check | Implemented · Needs rig validation |
| Firmware update | Not in this app. Updating erases configuration and calibration and needs the DFU tooling. The documented, supported paths are the official Web GUI *Firmware Update* tab or `odrivetool new-dfu`. The app links to them and asks for a backup first. | **Unsupported** |
| Checking for newer firmware | The release index needs device-specific qualifiers and network access that could not be verified here. The official GUI does this. | **Unsupported** |
| Inspector (browse and edit any property) | Not provided. Writes are limited to a documented allowlist with range checks and read-back. Unrestricted writes would bypass every safeguard. Reading the full tree: use `survey_odrive.py`. | **Unsupported** (by design) |
| Anticogging and harmonic calibration, autotuning, CAN, UART, step/dir, GPIO, endstops, mechanical brake | Not needed for this rig; each has its own motion risk | **Unsupported** |
| Live plotting | Monitoring page plots from host polling (clearly labelled). High-rate data only from onboard capture | Implemented · Needs rig validation |
| Sensorless start | Allowed only when the test board is already set up for sensorless and the operator has confirmed commissioning. The switch to closed loop is confirmed against the sensored load encoder via the coupling ratio before load is applied. Changing the feedback source stays a manual Configuration step. | Implemented · Needs rig validation (firmware calls sensorless experimental) |
| Simulation mode | Not in the delivered app (a requirement). Test fixtures are only used by the automated tests. | Removed |
| *(added)* Test Matrix page | CSV import and validation, explicit N·m / A loads, visual speed × load matrix, run, pause, retry, skip, cancel, readiness links | Implemented · Needs rig validation |
| *(added)* Motor Monitoring page | Two columns with live values and graphs, window, visibility, pause, display-only zero | Implemented · Needs rig validation |
| *(added)* Recording and results | Separate acquisition; host CSV plus onboard capture metadata; raw and residual ripple plots per load | Implemented · Needs rig validation |

See `docs/VALIDATION_CHECKLIST.md` for the per-feature validation status and the first-connection order.
