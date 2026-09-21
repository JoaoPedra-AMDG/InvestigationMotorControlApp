# ODrive two-motor workbench

A local Python website for two commissioned ODrive Pro boards: one test motor in speed control and one sensored load motor in opposing torque control. The application uses real board data only. When disconnected, values are unavailable and motor commands are blocked. Starting the application, opening a page, saving a plan or viewing a script does not connect or start a motor.

The hardware code is implemented but has not been validated on the physical rig. Keep the application disconnected while waiting for the USB isolators. You can prepare the connection profile, plan tests and inspect the Python source now.

## Start the local application

The project has a local `.venv` environment. Its ODrive Python dependency is pinned to `odrive==0.6.11.post1`; this is a Python package version, not a firmware recommendation. Use Python 3.10 or later.

From PowerShell in this directory:

```powershell
.\start.ps1
```

The launcher creates `.venv` when needed and installs missing requirements. If Python is not on PATH, provide its actual path:

```powershell
.\start.ps1 -PythonPath 'C:\path\to\python.exe'
```

Or set up and start the application manually:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). The server binds only to this computer. Stop the application with Ctrl+C after ending the test. A second process cannot use the same port. If PowerShell blocks local scripts, use the manual Python commands above.

The default recording target is 20 Hz. `start.ps1 -Rate 50`, or `app.py --rate 50`, requests a different host-recorder rate between 1 and 100 Hz. The board polling rate is a separate connection-profile setting. Neither setting guarantees that rate; inspect actual timestamps and achieved rate. Increasing the recorder rate cannot create new board samples.

## Pages

Use the page dropdown to move between these views:

| Page | Purpose |
| --- | --- |
| Home | Operating sequence and explanation of the controls, signals and recording limits. |
| Motors | Test motor in the left column and load motor in the right column; each shows DC voltage, DC current, rotor speed, rotor position and torque. |
| Test matrix | Select a tile and Run selected, or Run all selected tests; watch progress on the matrix. |
| Python scripts | Read the actual source files that implement the application. Viewing source never executes it. |
| Connections | Assign both serial numbers, save the validated profile, explicitly connect, inspect states/readiness and disconnect. |
| Review and export | Process ripple results, switch metrics, compare feedback modes at each load and export results CSV or raw run ZIPs. |

Repeat comparisons and earlier analysis history remain available. Historical records retain their original acquisition-source tags; they are not relabelled as hardware experiments.

## Commissioning before the first connection

Commission both motors individually using the ODrive GUI, save their configurations, and release the GUI's USB connections before connecting this application. The application does not flash firmware, calibrate motors, change encoder routing or save new board configurations.

The current adapter checks these requirements before allowing motion:

- Distinct hexadecimal serial numbers assigned to the physical test and load roles.
- Verified motor-shaft-turn units and direction conventions, including the opposing load direction.
- Positive, experimentally validated local maximum speed and load-current limits. The profile starts with zero limits so an unconfigured rig cannot start.
- Completed motor calibration and valid sensored commutation calibration where required.
- Firmware motor-current and velocity limits that are readable, positive and compatible with the selected point.
- Test drive already configured for `VELOCITY_CONTROL`, `VEL_RAMP` and a positive velocity ramp rate.
- Load drive already configured for `TORQUE_CONTROL`, `TORQUE_RAMP`, a positive torque ramp rate and a readable positive torque constant.
- Sensored feedback on the load drive. This version starts sensored sessions only; sensorless sessions are read-only monitoring/recording.
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

Sensorless Start is currently blocked because the adapter has no verified firmware marker separating the open-loop ramp from observer handover. Commissioning flags do not override that restriction. A separately started sensorless session may be connected for read-only monitoring and manual recording; the app does not feed the watchdog for motion it does not own. Sensorless tests require separately validated startup, handover, minimum speed and stopping behavior for the exact firmware and rig. Selecting a sensorless matrix point does not reconfigure a commissioned sensored drive. Follow the current readiness restriction; unsupported sensorless startup remains blocked rather than being approximated by a speed ramp.

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

Feedback routing is never switched by the queue. Automatic sensorless startup remains blocked; a mixed queue pauses at such a point. Independently commissioned and already running sensorless sessions can be manually recorded using a selected sensorless plan, or imported from an external acquisition. A recorded tile means acquisition finished, not that an operator has accepted the result.

## Processing current ripple

**Review & export > Process all recorded results** reads original high-rate CSV samples. It uses a common duration (the shortest eligible buffer) so sensored and sensorless channel counts do not give unequal maximum-search windows. It fits a DC term plus sine/cosine at the electrical fundamental separately for each phase. The fundamental comes from captured speed and configured pole pairs, or a previously saved analysis of that same dataset with an explicit frequency for imported data. For imports without speed, first load the dataset, enter its frequency and Analyze selected window; then Process all recorded results. A frequency entered for one run is never applied to other speeds.

The metric selector offers:

- **Peak-to-peak:** `max over A/B/C of (max residual - min residual)` in amperes.
- **Absolute peak:** `max over A/B/C of max(abs(residual))` in amperes.

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
- `recordings/connection-profile.json`: explicitly saved local profile.

Run `python -m unittest discover -p 'test_*.py'` using the local environment for automated checks. Test fixtures exercise disconnected behavior, command validation and data handling without connecting physical boards. Passing them does not validate actual motor control, sensorless handover, USB timing, emergency stopping or measurement accuracy.

Official references for commissioning and API details:

- [ODrive Python package](https://docs.odriverobotics.com/v/latest/guides/python-package.html)
- [ODrive hardware configuration](https://docs.odriverobotics.com/v/latest/manual/hardware-config.html)
- [ODrive sensorless operation](https://docs.odriverobotics.com/v/latest/manual/hardware-config.html#sensorless)

- [ODrive high-rate capture](https://docs.odriverobotics.com/v/latest/interfaces/odrivetool.html#high-rate-capture)
