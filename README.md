# ODrive two-motor workbench

A local Python website for two commissioned ODrive Pro boards: one test motor in speed control and one sensored load motor in opposing torque control. The application uses real board data only; there is no simulation mode. When disconnected, values are unavailable and motor commands are blocked. Starting the application, opening a page, saving a plan or viewing a script does not connect or start a motor.

The hardware code is implemented but has not been validated on the physical rig. Keep the application disconnected while waiting for the USB isolators. You can prepare the connection profile, plan tests and inspect the Python source now.

## First-time setup on a lab computer

Use these instructions once on each Windows or Linux computer that may operate the rig. Copy the complete `motor-dashboard` folder to the computer's local drive first. Do not run it from OneDrive, a network share or a USB drive, and do not copy a `.venv` folder from another computer.

Before connecting either board:

1. Install 64-bit Python 3.10 or later.
2. Confirm that the motors are mechanically safe, the independent emergency stop is available and the correct USB isolator is fitted to each ODrive.
3. Close the ODrive GUI, `odrivetool` and any other program that could be using either board. Only one program can own an ODrive USB connection at a time.
4. Complete the operating-system setup below.

### Windows 10 or 11

1. Open PowerShell in the copied `motor-dashboard` folder.
2. Run:

   ```powershell
   .\start.ps1
   ```

   The launcher creates a new `.venv` for this computer, installs the required packages and starts the dashboard. If Python is installed but is not available from PowerShell, provide its full path:

   ```powershell
   .\start.ps1 -PythonPath 'C:\path\to\python.exe'
   ```

3. If Windows blocks local PowerShell scripts, use the manual commands under **Manual setup or troubleshooting** below.
4. When the launcher reports that it is ready, open [http://127.0.0.1:8765](http://127.0.0.1:8765) in a browser.

### Linux

The ODrive Python package requires a supported 64-bit Linux distribution, `libusb` and ODrive USB permission rules. These commands are written for Ubuntu or Debian-based lab computers.

1. Open a terminal in the copied `motor-dashboard` folder and install the required system packages:

   ```bash
   sudo apt update
   sudo apt install python3 python3-venv python3-pip libusb-1.0-0 curl
   ```

2. Install the official ODrive USB permission rules once on that computer:

   ```bash
   sudo bash -c "curl https://cdn.odriverobotics.com/files/odrive-udev-rules.rules > /etc/udev/rules.d/91-odrive.rules && udevadm control --reload-rules && udevadm trigger"
   ```

3. Unplug and reconnect both ODrives after installing the rules.
4. Create this computer's Python environment and install the application dependencies:

   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install --upgrade pip
   .venv/bin/python -m pip install -r requirements.txt
   ```

5. Start the dashboard without `sudo`:

   ```bash
   .venv/bin/python app.py
   ```

6. Open [http://127.0.0.1:8765](http://127.0.0.1:8765) in a browser.

### First connection on either operating system

Starting the application does not connect to or start a motor. In the dashboard:

1. Open **Connections**.
2. Enter the two ODrive serial numbers and assign the physical test and load roles.
3. Enter the verified local speed, current and direction limits.
4. Complete the commissioning confirmations only after checking the physical rig.
5. Save the profile, click **Connect**, and resolve every readiness blocker before attempting motion.

Repeat these checks when moving the rig to a different computer. Never treat the dashboard's software Stop button as an emergency stop.

## Start the application after first-time setup

The ODrive Python dependency is pinned to `odrive==0.6.11.post1`; this is a Python package version, not a firmware recommendation.

On Windows, open PowerShell in the folder and run:

```powershell
.\start.ps1
```

On Linux, open a terminal in the folder and run:

```bash
.venv/bin/python app.py
```

Then open [http://127.0.0.1:8765](http://127.0.0.1:8765). The server binds only to that computer. Stop the application with Ctrl+C after ending the test. A second process cannot use the same port.

The default recording target is 20 Hz. On Windows, `start.ps1 -Rate 50` requests a different rate. On either operating system, `app.py --rate 50` requests a rate between 1 and 100 Hz. The board polling rate is a separate connection-profile setting. Neither setting guarantees that rate; inspect actual timestamps and achieved rate. Increasing the recorder rate cannot create new board samples.

## Manual setup or troubleshooting

If the Windows launcher cannot create the environment automatically, run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

If the `py` launcher is unavailable, replace `py -3` with the full path to `python.exe`. Delete only the local `.venv` directory and recreate it if it was copied from another computer or refers to a Python installation that no longer exists. Do not delete the `recordings` directory when doing this.

## Pages

The horizontal menu bar spans the top of every page and stays visible while scrolling. **Stop Both Motors**, on the right, requests IDLE on both boards: torque is removed and the motors coast. It is a software command. It does not brake and is **not an emergency stop**.

| Page | Purpose |
| --- | --- |
| Home | Operating sequence and safety notes. |
| Dashboard | Both motors side by side: state, modes, speed and Iq reference vs measured with tracking errors, Id, estimated torque (firmware estimate and Kt × Iq), DC voltage, current and power, temperatures, decoded faults, recording state and elapsed time, with live plots. Motor commands: start/apply a test speed and an opposing load in N·m or A, set the load to zero, stop both. |
| Motor Monitoring | Test motor on the left, load motor on the right. For each: DC voltage, DC current, speed, position in mechanical revolutions from a display zero, estimated torque and phase currents A/B/C, as values and time series. Also connection, axis state, feedback mode, faults, units and data age. Time window, graph visibility, pause/resume display, and Zero Displayed Position (display only). |
| Test Matrix | CSV upload → preview and validation → save; example CSV and column reference. Readiness with links to the setting behind each blocker. Visual speed × load matrix with sensored and sensorless tiles styled differently. Run Selected Test, Run All Selected Tests, Pause After Current Test, Resume, Stop Both Motors and Cancel, Retry and Skip. Per-point status (pending, settling, recording, completed, blocked, failed, skipped) and overall progress. |
| Results | Process steady-state captures. For each load, current ripple vs speed with separate sensored and sensorless lines, and a selector for raw peak-to-peak or fitted-fundamental residual peak-to-peak. Export CSV and full run ZIPs. |
| Configuration | Discover boards and assign roles. Identity, firmware and decoded faults. Allowlisted settings editor (preview → apply with read-back → optional save → reconnect and verify). Supervised calibration. Configuration backup and restore. |
| Connections | Serial numbers, validated rig limits, directions, chain coupling, sensorless confirmation; explicit connect and disconnect; readiness. |
| Troubleshooting | Quick fixes for local limits, watchdogs and controller modes. |
| Python scripts | Read the source files that implement the application. Viewing never runs them. |
| Compare repeats | Statistics across independent repeats. |

Earlier analysis history is kept. Historical records keep their original acquisition-source tags.

## Test matrix CSV

Download the example from the Test Matrix page (`/example-test-matrix.csv`). Columns:

| Column | Unit | Meaning |
| --- | --- | --- |
| `test_id` | text | Unique name (letters, digits, `-`, `_`). |
| `feedback_mode` | — | `sensored` or `sensorless` (test motor). The load motor is always sensored. |
| `speed_rpm` | rpm | Test-motor speed setpoint, mechanical. |
| `load` | N·m or A | Opposing load magnitude, in `load_unit`. |
| `load_unit` | `Nm` or `A` | `Nm` = load-motor torque command. `A` = load-motor q-axis current (torque = Kt × current). |
| `settle_time_s` | s | Time the point must stay inside tolerance before recording. |
| `speed_tolerance_rpm` | rpm | Allowed speed deviation. |
| `load_tolerance` | as `load_unit` | Allowed load deviation. |
| `record_duration_s` | s | Steady-state recording length. |
| `capture_rate_hz` | Hz | Requested high-rate capture rate; blank = native. Onboard capture only runs at the board's control-loop rate. A higher request is rejected, and the actual rate is always recorded. |
| `repeat` | count | Repeat number of the same point. |
| `notes` | text | Optional. |

Validation reports errors row by row. Rig-limit problems appear as warnings and are enforced again, against the connected boards, before every test. The validated maximum load on Connections is in A, so torque loads are converted with the load board's configured Kt, and the Kt used is recorded with each run.

## Recording and results

- The live display is separate from acquisition. The browser refresh rate never sets the recording rate.
- Host telemetry (`telemetry.csv`) is **sequential USB polling**, not high-rate or synchronized acquisition. Actual host timestamps, per-board read intervals and dropped samples are recorded.
- High-rate steady-state data uses the documented ODrive onboard oscilloscope through `odrive.utils.high_rate_capture`. It runs at the board's native control-loop rate with no decimation, into a finite buffer per board.
  - Each dataset's JSON records the requested and native rate, actual rate, dropped samples, the declared channel bandwidth and filtering, within-board timing quantisation, and `boards_share_clock: false`.
  - The two boards are not synchronized.
- Raw data is CSV and metadata is JSON. The metadata includes board serials, firmware, configuration, feedback mode, the matrix point with its load unit and the Kt used, units, calibration references and capture settings.
- Runs are never overwritten, and interrupted or failed runs are kept and labelled.
- **Ripple metrics.** *Raw peak-to-peak* is the largest (max − min) of the original phase A/B/C samples in the analysis window. It includes the fundamental, so it grows with load current. *Residual peak-to-peak* is the largest phase peak-to-peak after a least-squares fit of DC plus the fundamental (speed × pole pairs) is removed.
- **Limitations.**
  - A constant steady-state fundamental is assumed.
  - Control-loop-rate capture cannot resolve PWM-frequency ripple.
  - Channel bandwidth is as declared by the operator.
  - Unavailable metrics are reported as unavailable, never filled in.

## Dependencies and compatibility

- Python 3.10 or newer. Tested with Python 3.13.14 on Windows 11.
- `requirements.txt`: `numpy>=1.24,<3`, `odrive==0.6.11.post1`. `requirements-lock.txt` lists the exact versions the tests passed with (numpy 2.5.3, odrive 0.6.11.post1 and its dependencies).
- Firmware: released ODrive Pro firmware 0.6.x, 0.6.10 or newer, the same on both boards. Written against the 0.6.12 documentation. See `docs/REFERENCE_REVIEW.md` for what was checked, what the app supports, and what it deliberately leaves out (firmware flashing, Inspector-style unrestricted writes, CAN/UART/GPIO features).
- Before relying on the app with real boards, run the read-only property survey (next section) on each board and resolve any missing properties.

## Stage 0: read-only property survey

Before relying on any property name with real boards, survey each board once:

```powershell
.\.venv\Scripts\python.exe survey_odrive.py --serial <SERIAL>
```

Close the ODrive GUI, `odrivetool` and this workbench first. The survey:

- connects to that one serial number;
- reads every property value, type and writability;
- records function signatures **without calling them**;
- lists which properties used by the workbench are missing on that firmware;
- saves `surveys/<serial>_<time>.json` and releases USB.

It writes nothing and cannot calibrate, arm, save or reboot.

## Event log

Every command sent to `/api/command` (request, then accepted/rejected/failed) and every controller state change is appended to `recordings/logs/events-YYYYMMDD.jsonl`. Bulky fields such as imported CSV text are summarised, not copied.

## Commissioning before the first connection

Commission each motor on the Configuration page (or in the official ODrive GUI; close it before connecting here). Configure the power limits, motor, encoder and control modes; run motor calibration and then encoder offset calibration; do the hand-turn direction check; save to the boards. The application does not flash firmware.

The current adapter checks these requirements before allowing motion:

- Distinct hexadecimal serial numbers assigned to the physical test and load roles.
- Verified motor-shaft-turn units and direction conventions, including the opposing load direction.
- Positive, experimentally validated local maximum speed and load-current limits. The profile starts with zero limits so an unconfigured rig cannot start.
- Completed motor calibration and valid sensored commutation calibration where required.
- Firmware motor-current and velocity limits that are readable, positive and compatible with the selected point.
- Test drive already configured for `VELOCITY_CONTROL`, `VEL_RAMP` and a positive velocity ramp rate.
- Load drive already configured for `TORQUE_CONTROL`, `TORQUE_RAMP`, a positive torque ramp rate and a readable positive torque constant.
- Sensored feedback on the load drive. The test drive must already be configured for the selected feedback mode (the queue never switches it). Sensorless additionally needs the commissioning confirmation, a validated minimum speed, and a verified chain coupling.
- An enabled onboard watchdog on each board with a timeout of at least max(0.5 seconds, six polling periods) and no more than 2 seconds. The application feeds it while it owns active motion.
- A verified stop procedure. This implementation supports only requesting `IDLE` to disable torque on both drives, allowing the rig to coast.
- Both boards initially idle, with readable zero active errors and disarm reasons.
- The same released 0.6.x firmware on both boards (0.6.10 or newer with inspected APIs).
- Initial velocity and torque setpoints (`axis0.config.init_vel` / `init_torque`) both zero; firmware restores these values during arming.

The application may reject additional unsupported configurations rather than guess signal mappings or motion behavior. Read the readiness details and hardware source for the exact checks. Role verification means inspecting the physical rig; checking a box does not validate wiring, units or operating limits.

Match the actual motor voltage/current limits, regeneration handling, mechanical coupling, guards and independent emergency-stop provision to your commissioned rig. The website's Stop control requests a software coast-to-IDLE stop. It is not an emergency stop and does not ensure that the shaft has stopped rotating.

## Connect and run one matrix point

1. On Connections, enter the two serial numbers, verified local limits, directions and required commissioning confirmations. Save the profile while disconnected.
2. Click Connect. Connection discovers only those serial numbers and reads their state/configuration; it does not enable motion. Confirm that the physical role assignment and displayed firmware/state are correct.
3. Resolve the readiness blockers. Fault clearing is a separate explicit action, and no automatic restart occurs.
4. On Test matrix, create or choose the desired speed/load/method/repeat point. Set recording duration and settling tolerances. Generating a matrix proposes points; it does not approve them as feasible for the rig.
5. Click Run selected test. This explicit action starts the configured sensored motor control, holds load torque at zero until the test motor reaches the load-application speed, waits for the point to settle, records for the specified duration, then requests the supported stop. If it does not settle within 60 seconds or a board/control/acquisition fault occurs, the workflow fails and requests a stop.
6. Inspect both Motors columns during the run. The browser display updates independently of the recorder.
7. Open Review and export, inspect timing and channel availability, record the outcome and download the complete run ZIP.

Manual condition application and recording are separate controls where provided. Ending a manual recording does not itself promise a mechanical stop: use Stop and inspect the rig. Closing the browser does not stop the Python application, active workflow or recording. Ending the Python application requests the supported stop; if communications fail, the application cannot guarantee delivery and reports the fault.

Sensorless start follows the documented firmware workflow: with both encoders set to the sensorless estimator, requesting closed loop runs the open-loop `sensorless_ramp`, then the firmware switches to closed loop. The firmware exposes no documented flag for that handover, and 0.6.x documents sensorless mode as experimental. So the app never overwrites the ramp's velocity input, and only applies the test speed target (and later the load) after the sensorless speed estimate has agreed with the load encoder, through the verified coupling ratio, for the configured hold time. If that doesn't happen before the start-up timeout, both motors are stopped. This must be validated on the rig before sensorless data is trusted.

## What the plots mean

Unavailable or unsupported channels remain blank/null and are not replaced with zeros. A disconnected board does not produce invented readings. Sign conventions are configured per motor; compare directions only after verifying the physical mapping.

- **DC voltage:** reported board bus voltage.
- **DC current:** the controller's reported/estimated DC-bus current, distinct from motor phase current and torque-producing Iq. Negative values can represent regeneration under the verified sign convention.
- **Speed and position:** speed in rpm; displayed position in revolutions relative to the first reading after connection, Run selected or Zero positions. Raw axis position is preserved in recordings. In sensorless operation these are not automatically independent encoder measurements.
- **Torque:** the configured torque constant multiplied by reported Iq, explicitly labelled as an estimate. It is not a torque-transducer measurement.

The profile can describe a separately verified encoder path and scale for comparison measurements. Record its provenance and calibration. Do not label a generic sensorless velocity estimate as an independent encoder reference.

## CSV, timing and high-rate acquisition

The live recorder saves new hardware samples to `recordings`, with actual host timestamps, per-board read timing, commands, channel provenance and run metadata. Missing values remain missing. A run bundle includes raw CSV files, events, metadata, source-file snapshots and retained review history. Earlier files are preserved when a test is repeated.

The two boards and their fields are read sequentially. Their host timestamps do not make the measurements simultaneous. Windows scheduling, USB latency and the number of available fields all affect the achieved acquisition rate. The dashboard refresh rate and chart history length do not set the CSV sampling bandwidth.

New steady-state plans require high-rate capture by default. Before motion, each board must expose the compatible oscilloscope API, a readable control-loop rate and all requested channels. Missing capability blocks the point before starting. Existing older plans retain their saved capture choice. The Connections page reports capability, rate and finite buffer size; enter the documented measurement bandwidth and filtering there before processing ripple. A motor current-control bandwidth is not automatically a measurement bandwidth.

At settling, `capture_runtime.py` uses the official synchronous ODrive capture helper on the existing connections. Two download threads keep the controller thread available for watchdog feeding and Stop. Each drive saves phase A/B/C current, DC voltage/current, speed and axis position. A sensorless test additionally saves the verified independent encoder angle and estimated electrical angle (up to nine channels). Raw angles remain available; relative mechanical revolutions are derived using the saved pole-pair count. Signals unavailable on the installed firmware block capture rather than becoming generated values.

Each board produces a **finite native-rate buffer**, not an unlimited high-rate stream. CSV files preserve the helper's trigger-relative control-cycle indices, device-reported sample rate, original axis positions and relative positions. Separate boards are **not synchronized**. The configured recording duration must cover capture and download. If duration expires while capture/download is pending, Stop/disconnect occurs, steady-state tolerances are lost, or the buffer is incomplete, the run is retained and marked invalid for ripple processing. Downloads time out after 25 seconds; an unfinished worker retains buffer ownership until it returns. Increase recording duration for a slow USB connection. Neither the reported control-loop rate nor a smooth graph establishes PWM switching-ripple bandwidth.

The feature must still be checked on the actual installed firmware and USB setup. Firmware lacking the required endpoints cannot capture these channels from this application. The app never installs prerelease firmware or weakens motion prerequisites to obtain capture support. External DAQ/oscilloscope imports remain available with explicit units, bandwidth, calibration and timing declarations. `capture_helpers.py` remains an optional standalone development helper; do not open another connection to a drive already in use.

## Running the matrix

Open **Configure tests** to generate paired speed/load points or edit the included subset. Select a tile, then **Run selected**, or press **Run all selected tests** once to queue all included pending points. The Python process runs the queue independently of the browser. Each point settles, records, coasts to IDLE, and waits until both reported speeds are below 5 rpm before the next start. A fault, incomplete acquisition, unsupported feedback mode or missing capability pauses the queue with a reason. Stop cancels pending work. An application restart never resumes motion automatically.

Feedback routing is never switched by the queue: a point whose feedback mode differs from the test board's current configuration is blocked, with a link to Configuration. Pause After Current Test lets the running point finish, then pauses the queue. A failed point pauses the queue, and it resumes only after each failed point is retried (as a new attempt, keeping the failed run) or skipped with a reason. A completed tile means acquisition finished, not that an operator has accepted the result.

## Processing current ripple

**Review & export > Process all recorded results** reads original high-rate CSV samples. It uses a common duration (the shortest eligible buffer) so sensored and sensorless channel counts do not give unequal maximum-search windows. It fits a DC term plus sine/cosine at the electrical fundamental separately for each phase. The fundamental comes from captured speed and configured pole pairs, or a previously saved analysis of that same dataset with an explicit frequency for imported data. For imports without speed, first load the dataset, enter its frequency and Analyze selected window; then Process all recorded results. A frequency entered for one run is never applied to other speeds.

The metric selector offers:

- **Raw peak-to-peak:** `max over A/B/C of (max sample - min sample)` of the original phase currents in amperes (includes the fundamental).
- **Residual peak-to-peak:** `max over A/B/C of (max residual - min residual)` in amperes after the DC + fundamental fit.
- The absolute-peak residual is still calculated and exported in the CSV.

Each load graph has separate sensored and sensorless lines against rpm. A point is the maximum across valid independent repeats; the results table and CSV retain both metrics for each repeat. Retried attempts count once (latest valid attempt). Different acquisition sources, rates, bandwidths, filtering, device identities, calibration or analysis windows remain separate groups. Missing data remains gaps. Operator acceptance is displayed separately from numerical quality checks; process again after changes to runs/reviews.

Unknown bandwidth/filtering, missing phase currents, timing gaps, clipping, partial/interrupted captures, speed outside tolerance or insufficient electrical cycles prevent ripple results. These are in-band residual metrics and include harmonics/noise; they are not isolated PWM ripple. Raw data, metadata and derived results are retained in each run ZIP; **Export processed results CSV** saves the comparison table with both metrics and run IDs.

## Files and checks

- `app.py`: local HTTP server, test workflow and host CSV recording.
- `hardware.py`: real board connections, telemetry, readiness checks and explicit motor commands.
- `experiment.py`: plans, run storage, review history and ZIP export.
- `signals.py` and `analysis.py`: channel definitions, quality checks and numerical analysis.
- `import_data.py`: external CSV import and provenance.
- `capture_runtime.py`: onboard capture, original samples and per-board metadata.
- `batch_runner.py`: persistent test queue and restart recovery.
- `processing.py`: quality-gated ripple comparisons and processed CSV export.
- `capture_helpers.py`: optional standalone development helper.
- `fixture_boards.py`: fake boards used only by the automated tests; never imported by the application.
- `survey_odrive.py`: Stage 0 read-only property survey (command line).
- `event_log.py`: JSONL command and state-change log.
- `recordings/connection-profile.json`: explicitly saved local profile.

Run `.venv\\Scripts\\python.exe -m unittest` for the automated checks (matrix validation, sequencing, recording, fault handling, configuration updates, calibration guards, sensorless handover). The tests use `fixture_boards.py` only. Test fixtures exercise disconnected behavior, command validation and data handling without connecting physical boards. Passing them does not validate actual motor control, sensorless handover, USB timing, emergency stopping or measurement accuracy.

Official references for commissioning and API details:

- [ODrive Python package](https://docs.odriverobotics.com/v/latest/guides/python-package.html)
- [ODrive hardware configuration](https://docs.odriverobotics.com/v/latest/manual/hardware-config.html)
- [ODrive sensorless operation](https://docs.odriverobotics.com/v/latest/manual/hardware-config.html#sensorless)

- [ODrive high-rate capture](https://docs.odriverobotics.com/v/latest/interfaces/odrivetool.html#high-rate-capture)

## Fixing blocked setup checks

Open **Troubleshooting** from the menu bar or the readiness panel. The five cards show the current local limits and each board's watchdog and control-mode checks.

1. Enter validated local maximum speed and load current, then **Save local rig limits**. These only limit commands from this computer. Connected boards must be idle; values above their existing velocity/current limits are rejected.
2. Connect the boards and verify their physical roles and axis units on Connections. Use **Read current board settings** to refresh the forms.
3. Enter compatible watchdog timeouts and validated ramp rates. Test speed ramp is entered in rpm/s and converted to turns/s²; load torque ramp is entered in N·m/s.
4. Click **Preview board changes**. Inspect both serial numbers and every current/proposed value. The tool sets test velocity control + velocity ramp, load torque control + torque ramp, enables both watchdogs, and zeros current and initial inputs. It does not run calibration, switch encoders or increase firmware current/voltage limits.
5. Click **Apply reviewed board changes**. Each setting is read back. Both boards must stay IDLE, disarmed and below 1 rpm; no tests, captures or batches may be active. A changed/expired preview is rejected. Partial failures remain visible and are logged under `recordings/settings-history.jsonl`.
6. To retain settings across power loss, tick the separate save option before Apply. This saves the entire current board configuration and may reboot the boards. Automatic startup must be disabled; connections are released and you must reconnect to verify persistence. A lost save response is reported as unconfirmed, never treated as success.

These actions do not start either motor. Other readiness checks still apply. The watchdog timeout must be at least max(0.5 seconds, six polling periods) and at most 2 seconds. Lower polling rates may need adjustment in Connections. Clear errors is a separate action after resolving their cause.
