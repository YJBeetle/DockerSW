# Wine attach refusal verification — 2026-11-06

This is a targeted lifecycle check, not a complete CAD acceptance or a new
image release. The existing local executable image
`377e9edd59f86333740cc1e3b049d546997b826907b5ce9851b571ebc205ecab`
was run in its own disposable container with SWCLI source
`4c3bfb2143e4f549a5da84d64e3ef40adb4195de` and current native wrappers mounted
read-only as test inputs. No user SW, VM or other container was stopped.

The real command `swcli daemon start --attach-existing --json` was called once
at a dedicated loopback endpoint. It returned exit code 1 and the original
`ExistingHostNotFound` JSON after 56.866 seconds. The endpoint refused connections
before and after. Process observations found no live SW before, during sampling,
or afterward, and no live Windows Python daemon remained. Raw final `ps` state
also records exited Python/Wine zombies; these are not hidden or described as
live daemons. The harness never issues stop, restart or a second start.

The first attempt stopped in a read-only preflight while the container was still
initializing; its receipt records zero startup calls. It is preserved separately.
After initialization reached the resident `sleep` command, a new evidence directory
was used for the single actual startup attempt. No startup API failure was retried.

Original evidence is in
`/private/tmp/swcli-wine-attach-refusal-4c3bfb2-20261106/`:

- `evidence/`: original preflight failure, unmodified.
- `evidence-ready/`: separate stdout/stderr, exit codes, hashes, process snapshots
  and the successful negative-test receipt.
- `independent-audit.json`, `SHA256SUMS.json`: independent checks and file hashes.
- `final-process-stat.txt`: independent live/exited process classification.
- `container-exit.txt`, `cleanup.txt`: container exited 137 and was removed.

The initial container stop reached its 10-second container-only stop deadline,
used SIGKILL, and reported a missing Podman network namespace. The stopped
container was independently observed and its exact record removed successfully;
`cleanup.txt` records `remove_exit=0 exists_exit=1`. This container cleanup issue
is separate from the successful SWCLI refusal and is not reported as graceful
runtime teardown.

Receipt SHA-256:
`f74aa648049727001f993c5485b299990d8deb339de641e67610fc2d10e09832`.
Harness SHA-256:
`5855edce9c3146ad29ef1683929598aed958e6c0fabb701cfae4f9f16d2cd2f0`.

The CI integration runs this gate after the existing visible gate has verified
its owned daemon stopped. It reuses that container, saves evidence under
`attach-refusal/`, and blocks promotion on any failed assertion. It adds no CAD
matrix, host-start retry, user-host shutdown or relaxed native-call budget.
