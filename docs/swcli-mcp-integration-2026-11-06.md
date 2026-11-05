# Native MCP and daemon utilities integration — 2026-11-06

SWCLI is pinned at 1354a6c5126243c50369451ef5477e0beab41b2c. The public
`/usr/local/bin/sw-cli` script only configures native Python/path/endpoint and
`SWCLI_DAEMON_UTILS`, then forwards every argument unchanged. The selected
shell utilities execute Windows daemon actions through the configured Wine
Python. The action comes from Python's parser, so leading global options do
not change host routing. No second lifecycle service/state is introduced.

MCP SDK 1.30.0 is added only to Linux client dependencies. Target Python 3.10 /
Linux wheel resolution passed. The Wine Windows daemon keeps its existing
base dependencies. Status and stop are native protocol calls, without Wine
startup solely for observation/management. CAD calls remain connection-only.
Explicit start still honors the existing COM-instance guard and attach choice.
No force-new option or multi-instance behavior change is included.

33 adapter tests passed, including unchanged public arguments, utility overrides,
Windows runtime selection, delegation, Unicode paths, and entrypoint failure
propagation. SWCLI's portable suite passed 1598 tests (21 platform skips),
official MCP SDK transport tests passed on native Python 3.11 and 3.14, and
its original Windows evidence covers hidden start, document shutdown refusal,
disconnect retention and explicit stop. Local wrapper tests use fake runtimes;
image/native Wine acceptance remains the separate build workflow's result.

## CI contract follow-up

[Push run 42114936792](https://github.com/YJBeetle/DockerSW/actions/runs/42114936792)
failed in the runtime image-layer unit test before any image build or native CAD
acceptance. Its fixed-source check still looked for Windows PYTHONPATH wiring
in the now-native-only frontend wrapper. The assertion now checks the separate
daemon utilities and confirms the payload includes that executable. The native
client source check and the no-installed-wheel checks are retained.

The SWCLI pointer advances to 1204621910fecc42a9694f9df94ad77c90ee8da5, whose
only changes fix the Windows-specific test assertion and record that evidence.
No runtime, wrapper, workflow, native timeout or acceptance guard changed here.
The complete local logic chain passed: 114 runtime tests, 33 adapter tests and
1598 SWCLI tests (21 platform skips on macOS). No VM was used. CI and native
Wine acceptance remain separate results, not inferred from these unit tests.
Original failed-job log SHA-256: `bbc308e5db907dc105ba5c1111da5c83e32dcbb82b3b21dae4b3825cf10faa12`.

## Wine descendant pipe EOF startup fix

[Push run 42116004763](https://github.com/YJBeetle/DockerSW/actions/runs/42116004763)
passed runtime unit checks but failed the shared native step. The owned hidden
SW was healthy and already processing CAD work when, at 300+30 seconds, the
entrypoint received HostLauncherTimeout. Its exit interrupted docker exec (137).
The exit code does not prove OOM or a Wine native API failure.

SWCLI 3eba5c4 changes daemon utils capture to private temporary files, waiting
only for the utility process rather than EOF from resident Wine descendants.
The timeout, host ownership, unknown-outcome guard and no-retry policy remain.
1600 source unit tests passed (21 platform skips). A separate workspaceroot
Wine 11.16 / Windows Python 3.11.9 probe reproduced the difference: PIPE returned
at 4.060 s although the leader exited at 0.816 s; file stdio returned at 0.616 s
with the background child still alive. No SW was used in that probe.

Original failed build log SHA-256:
`323ecc83184662e139a1c5ecec4a37a36d668654d036a50e4a6b1b43536763b8`.
Original artifact 13458160476 SHA-256:
`644e5fbd235cfe57125946c2edcba7556d69df6810a2b1e33afe1021ddc59053`.
SSH Wine probe result SHA-256:
`eccc915099d1f980764fde8ec8a97ad305d58ec100b9f0b53a9800f2bdb8e21d`.

The new push retains complete build/Wine validation and promotion policy.
Its native outcome and independent MCP runtime acceptance are separate evidence;
the probe and portable tests do not stand in for a completed CAD matrix.

## Independent Linux/Wine MCP acceptance

The exact fixed SWCLI source `3eba5c42776c6714d1a36a6458fab47aa7c3ff6d`
with the unchanged `882cc964` native wrapper/daemon utilities and MCP SDK 1.30.0
passed a real Linux/Wine lifecycle test on workspaceroot. A separately named
Podman container used cached SW2025/Wine11.16; it published no ports and changed
no existing service or container. This was not the complete CAD matrix.

- MCP initialization, five-tool discovery and offline status left SW and the
  Windows daemon absent, confirmed by independent process snapshots.
- One explicit start succeeded after 79.013 seconds with hidden owned SW PID612.
- The first stdio connection closed; SW and daemon remained. The second
  connection observed the same ready owned PID612 and an empty document list.
- One explicit stop succeeded; the MCP connection still answered ping. Final
  SW/WindowsPython processes were empty. The isolated container exited0 and was
  removed normally, with its full container ID recorded.

The original `mcp-lifecycle.json` SHA-256 is
`ffd8e1a6640bd7fb0310b344e08834290705a1ca1f003c36658765f594c7d782`.
The source archive's daemon_manager.py was independently compared byte for byte
with the fixed commit. Raw lifecycle, startup/daemon logs, process snapshots,
container identity and cleanup receipt are retained under the local evidence
directory `/private/tmp/swcli-mcp-3eba5c4-20261106`.

The complete image/Wine matrix is independently tracked by
[2025 push run42123274873](https://github.com/YJBeetle/DockerSW/actions/runs/42123274873)
at image-source commit `89a742d9da657ea6e1cc97592a7e7a8bdc8b68c8`.
Its outcome has not been inspected after dispatch; this document commit is not
an accepted image SHA or a claim that the complete matrix passed.
