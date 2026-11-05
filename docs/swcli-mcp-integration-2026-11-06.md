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
