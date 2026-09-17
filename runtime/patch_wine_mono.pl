#!/usr/bin/env perl
# DockerSW: Wine-Mono 11.x COM Callable Wrapper (CCW) Release Assertion Patch
#
# Root Cause:
# In Wine-Mono's mono/mono/metadata/cominterop.c:cominterop_ccw_release (line ~3392):
#   g_assert (ccw->ref_count > 0);
#   if (InterlockedDecrement (&ccw->ref_count) == 0) mono_ccw_destroy (ccw);
#
# When external COM hosts (such as SOLIDWORKS or its export add-ins) perform an
# accidental double-release during high-concurrency export or post-export teardown,
# ccw->ref_count is 0.
# In Windows native .NET Framework CLR, this is handled gracefully without terminating
# the process. In Wine-Mono, the hard assertion calls abort(), immediately killing
# SLDWORKS.exe with SIGABRT and causing subsequent exports to fail with RPC server unavailable.
#
# Fix:
# In libmono-2.0-x86_64.dll:
# Replace the conditional jump to assertion (je +0xac -> 0f 84 ac 00 00 00)
# with 6 NOPs (90 90 90 90 90 90).
# When ref_count is <= 0:
# 1. The abort() assertion is bypassed.
# 2. InterlockedDecrement decrements ref_count to -1.
# 3. `decl %ebp; je destroy` does not take the branch (result != 0), preventing double-destroy.
# 4. The function cleanly exits and returns to the caller, matching Windows native CLR tolerance.

use strict;
use warnings;

my $wineprefix = $ENV{WINEPREFIX} || "/root/.wine";

my @candidates = (
    "$wineprefix/drive_c/windows/mono/mono-2.0/bin/libmono-2.0-x86_64.dll",
    "/root/.wine/drive_c/windows/mono/mono-2.0/bin/libmono-2.0-x86_64.dll",
    "/opt/sw-runtime/managed-com/libmono-2.0-x86_64.dll",
);

my $target_dll = $ARGV[0];
if (!$target_dll) {
    for my $c (@candidates) {
        if (-f $c) {
            $target_dll = $c;
            last;
        }
    }
}

if (!$target_dll || ! -f $target_dll || ! -w $target_dll) {
    # If no file found or not writable, exit cleanly
    exit 0;
}

open my $fh, "+<:raw", $target_dll or exit 0;

# Pattern in libmono-2.0-x86_64.dll cominterop_ccw_release:
# 4d 8b 6e 08                 movq   0x8(%r14), %r13
# 4d 85 ed                    testq  %r13, %r13
# 0f 84 9f 00 00 00           je     assertion_not_null
# 41 83 7d 00 00              cmpl   $0x0, (%r13)
# 0f 84 ac 00 00 00           je     assertion_ref_count_positive (to patch)
# 48 8b 80 48 04 00 00        movq   0x448(%rax), %rax
my $expected = pack("H*", "4d8b6e084d85ed0f849f00000041837d00000f84ac000000488b8048040000");
my $patched  = pack("H*", "4d8b6e084d85ed0f849f00000041837d0000909090909090488b8048040000");
my $pattern_len = length($expected);

# Fast path: check known Wine-Mono 11.3.0 offset
my $fast_offset = 0x175588;
seek $fh, $fast_offset, 0;
my $buf;
read $fh, $buf, $pattern_len;

if (defined $buf && $buf eq $patched) {
    print "[DockerSW] libmono-2.0-x86_64.dll already patched at 0x" . sprintf("%x", $fast_offset) . "\n";
    close $fh;
    exit 0;
}

my $found_offset = -1;
if (defined $buf && $buf eq $expected) {
    $found_offset = $fast_offset;
} else {
    # Slow path: full file scan
    seek $fh, 0, 0;
    my $content = do { local $/; <$fh> };
    my $pos = index($content, $patched);
    if ($pos != -1) {
        print "[DockerSW] libmono-2.0-x86_64.dll already patched at 0x" . sprintf("%x", $pos) . "\n";
        close $fh;
        exit 0;
    }
    $pos = index($content, $expected);
    if ($pos != -1) {
        $found_offset = $pos;
    }
}

if ($found_offset == -1) {
    print "[DockerSW][WARN] Could not find Wine-Mono CCW assertion pattern in $target_dll\n";
    close $fh;
    exit 0;
}

# Apply patch
seek $fh, $found_offset, 0;
print $fh $patched;
close $fh;

print "[DockerSW] Successfully applied Wine-Mono CCW release assertion patch to $target_dll at 0x" . sprintf("%x", $found_offset) . "\n";
exit 0;
