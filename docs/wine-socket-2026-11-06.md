# Wine socket startup diagnosis

The 2025 runtime failure happened before CAD, in the first font registry query.
Its `wine: socket : Function not implemented` was independent of CLI test
assertions. Default container isolation is retained.

## Original diagnostic evidence

| Run | Source | Original ZIP SHA-256 | Result |
| --- | --- | --- | --- |
| [42194557462](https://github.com/YJBeetle/DockerSW/actions/runs/42194557462) | 5c2600c | 82a7a5844e07c562d6a7b7d1b3d65e29a9516ad33621150e87f460cf680f72c9 | x64 sockets succeed; Wine switches to i386 and exits 1; a surviving traced server caused wrapper timeout 124 |
| [42197827348](https://github.com/YJBeetle/DockerSW/actions/runs/42197827348) | eb35617 | ea8ea1ff892151148d06af8f203d376f8c816e8986ea1bcda56fb3fe861e281c | i386 libc/legacy syscall 102 return ENOSYS; direct syscall 359 succeeds; the configured wine64 executable was absent |
| [42198797648](https://github.com/YJBeetle/DockerSW/actions/runs/42198797648) | e8deaa2 | 27b28b71eb333ef09b8c800c0544c12af32bcb775569af3d07a7564a002c99eb | unified wine still enters i386 even with an explicit system32 PE path |
| [42199514292](https://github.com/YJBeetle/DockerSW/actions/runs/42199514292) | 766f61a | f04eb9cf43f7f2d8583321462aad584296688bf08421afc6e4fae7b8cee88919 | WINEARCH=wow64 keeps x64 loader, socket syscall 41 succeeds, same registry query exits 0 with empty stderr |

The runner used Docker 29.4.2, runc 1.5.2 and Linux 7.0.0-1019-azure.
The exact loaded seccomp profile was not independently recovered. The observed
syscall behavior is retained without claiming that profile's hash or ancestry.
These were isolated, public-runtime diagnostics: no SW/CAD, private installation
materials, image publication or release aliases were involved.

## Candidate correction and acceptance boundary

Keep prefix creation as win64, then use `WINEARCH=wow64` for normal runtime
execution. The entrypoint preserves an explicitly provided mode. Wine's
[11.16 manual](https://github.com/wine-mirror/wine/blob/wine-11.16/tools/wine/wine.man.in#L205-L221)
supports switching an existing 64-bit prefix between win64 and wow64. No internal
loader override, libc/Wine patch or security-profile relaxation is used.

The registry probe proves this startup path only. The candidate still requires
all existing runtime/managed-COM, installation, real SOLIDWORKS, property
save/reopen, export, visible/localized and lifecycle gates. Existing 32-bit
helpers must run through the supported new WoW64 path. No formal image alias
may be advanced merely because this diagnostic passed.
