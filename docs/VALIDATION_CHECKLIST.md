# Implementation and validation checklist

Status as of 2026-09-22, branch `claude/odrive-workbench-full`.

- **Implemented**: code exists and the automated tests (`python -m unittest`, 86 tests using `fixture_boards.py` only) cover it.
- **HW-verified**: exercised on the physical rig. **Nothing is HW-verified yet.** No ODrive has been connected during development.
- **Needs rig validation**: must be checked on the rig, in the order below, before its data or safety behaviour is relied on.

| Area | Feature | Implemented | HW-verified | Needs rig validation |
|---|---|---|---|---|
| Connection | Passive USB discovery by serial number | Yes | No | Yes: the discovery API was read from the package source, never run against a board |
| Connection | Connect, identify, release USB (odrive 0.6.11 release path fixed) | Yes | No | Yes |
| Connection | Property names used by the app exist on the firmware | Survey tool only | No | **Run `survey_odrive.py` on both boards first** |
| Configuration | Allowlisted preview → apply → read-back | Yes | No | Yes |
| Configuration | Save to boards, reboot, reconnect and verify persistence | Yes | No | Yes: reboot timing and reconnection on real USB |
| Configuration | Backup and restore (allowlisted settings) | Yes | No | Yes |
| Configuration | Role policy (test velocity, load torque, load sensored), start-up flags forced off | Yes | No | Yes |
| Calibration | Motor calibration, encoder offset, full sequence, with checklist, watchdog feeding and timeout | Yes | No | Yes: with the chain removed first |
| Calibration | Hand-turn direction and coupling check | Guided (manual) | No | Yes |
| Faults | Error-bit and procedure-result decoding with explanations | Yes | No | Yes: compare with the official GUI's display |
| Control | Paired start: load held at zero until test speed; ramps; load in N·m or A | Yes | No | Yes: uncoupled first, then coupled at low limits |
| Control | Stop Both Motors (IDLE, coast) | Yes | No | **Yes: measure coast-down time; confirm the physical E-stop is independent** |
| Control | Watchdogs fed only while the app owns motion; comm loss or stale data stops both | Yes | No | Yes: pull USB during a low-speed run |
| Control | Chain slip or breakage detection from the coupling ratio | Yes | No | Yes |
| Sensorless | Start with handover confirmed against the load encoder | Yes | No | **Yes: firmware calls sensorless experimental** |
| Test Matrix | CSV import, validation, example, units | Yes | n/a | No |
| Test Matrix | Run selected, run all, pause after current, retry, skip, cancel | Yes | No | Yes |
| Test Matrix | Readiness checks with links | Yes | No | Yes |
| Monitoring | Two columns, graphs, time window, visibility, pause, display zero | Yes | No | Yes: values against a meter and a hand-turned shaft |
| Recording | Host telemetry CSV with actual timestamps and dropped samples | Yes | No | Yes: achieved rate with two boards |
| Recording | Onboard high-rate capture, requested vs native rate, not synchronized | Yes | No | **Yes: requires firmware oscilloscope support** |
| Results | Raw and residual peak-to-peak vs speed per load, sensored vs sensorless | Yes | n/a | Needs real captures |
| Firmware | Identification and compatibility | Yes | No | Yes |
| Firmware | Update / flashing | **Unsupported**; use the official GUI or `odrivetool new-dfu` | n/a | n/a |

## Suggested first-connection order

1. Confirm the supply (26.5 V battery, shared bus, no brake resistor), fitted USB isolators and an independent, tested emergency stop.
2. Close the official GUI and odrivetool. Run `survey_odrive.py --serial <S>` on each board (read-only). Fix any property the app needs that is missing.
3. Discover → assign roles → confirm the roles on Connections → connect (read-only). Compare the displayed values with the official GUI.
4. Take a configuration backup.
5. **Chain removed.** Set DC-bus trips and currents from the battery and BMS ratings. Calibrate each motor. Do the direction check. Save, then reconnect and verify.
6. Chain removed: run each motor alone at low speed through the Dashboard (the load at zero). Test Stop Both Motors and USB-pull behaviour.
7. Chain fitted and tensioned: verify the coupling ratio and sign by hand. Run a low-speed, zero-load point, then small loads.
8. Only then run matrices. Sensorless last, after manual commissioning.

## Known gaps

- One intermittent test error was seen once in 12 full runs, while two app servers were running on the same machine. It could not be reproduced and is probably a timing-sensitive test under CPU load.
- The JavaScript was checked in Chromium through the browser pane with test fixtures, not on the lab computer's browser.
