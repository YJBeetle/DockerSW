#!/usr/bin/env perl
# DockerSW: Wine 11.x win32u.so 24-bit DIB OpenGL Off-screen Rendering Patch
#
# Root Cause:
# Wine's dlls/win32u/opengl.c:flush_memory_dc() had two bugs for offscreen DIBs:
# 1. Height calculation: `height = biSizeImage / 4 / width`.
#    For 24bpp DIBs (ColorBits=24), biSizeImage ~ W * 3 * H, causing height = H * 3 / 4 (25% truncated).
# 2. Pixel format: Unconditionally passed GL_BGRA (4 bytes/px) to glDrawPixels/glReadPixels,
#    while the GDI DIB stride is 24bpp (3 bytes/px). Mesa wrote 4 bytes per pixel into 3-byte memory,
#    causing a 4:1 horizontal compression, 4 repeating image tiles, and diagonal scanline skew.
#
# Fix:
# 1. Replace height calculation with width = biWidth, height = abs(biHeight).
# 2. Change GL_BGRA (0x80E1) to GL_BGR (0x80E0) in flush_memory_dc.

use strict;
use warnings;

my @candidates = (
    "/opt/wine-devel/lib/wine/x86_64-unix/win32u.so",
    "/opt/wine-staging/lib/wine/x86_64-unix/win32u.so",
    "/usr/lib/wine/x86_64-unix/win32u.so",
    "/usr/lib/x86_64-linux-gnu/wine/x86_64-unix/win32u.so",
);

my $so = $ARGV[0];
if (!$so) {
    for my $c (@candidates) {
        if (-f $c) {
            $so = $c;
            last;
        }
    }
}

if (!$so || ! -f $so || ! -w $so) {
    # If no file found or not writable, exit cleanly
    exit 0;
}

open my $fh, "+<:raw", $so or exit 0;

my $expected = pack("C*", 0x8b, 0x44, 0x24, 0x74, 0x8b, 0x7c, 0x24, 0x64, 0x31, 0xd2, 0x4c, 0x8b, 0x04, 0x24, 0xc1, 0xe8, 0x02, 0xf7, 0xf7);
my $patched  = pack("C*", 0x8b, 0x7c, 0x24, 0x64, 0x8b, 0x44, 0x24, 0x68, 0x99, 0x31, 0xd0, 0x29, 0xd0, 0x4c, 0x8b, 0x04, 0x24, 0x90, 0x90);

# Fast path: check known Wine 11.16 offset
my $fast_offset = 0xce4ee;
seek $fh, $fast_offset, 0;
my $buf;
read $fh, $buf, 19;

if (defined $buf && $buf eq $patched) {
    print "[DockerSW] win32u.so already patched at 0x" . sprintf("%x", $fast_offset) . "\n";
    close $fh;
    exit 0;
}

my $found_offset = -1;
if (defined $buf && $buf eq $expected) {
    $found_offset = $fast_offset;
} else {
    # Fallback search across binary
    seek $fh, 0, 0;
    local $/;
    my $content = <$fh>;
    my $p_pos = index($content, $patched);
    if ($p_pos != -1) {
        print "[DockerSW] win32u.so already patched at 0x" . sprintf("%x", $p_pos) . "\n";
        close $fh;
        exit 0;
    }
    my $e_pos = index($content, $expected);
    if ($e_pos != -1) {
        $found_offset = $e_pos;
    }
}

if ($found_offset != -1) {
    # Verify GL instruction prefixes within following bytes
    # Offset + 0x1d: ba e1 80 00 00 (mov edx, 0x80e1)
    # Offset + 0x55: b8 e1 80 00 00 (mov eax, 0x80e1)
    seek $fh, $found_offset + 0x1d, 0;
    my $gl1;
    read $fh, $gl1, 2;
    seek $fh, $found_offset + 0x55, 0;
    my $gl2;
    read $fh, $gl2, 2;

    if (defined $gl1 && $gl1 eq pack("C*", 0xba, 0xe1) &&
        defined $gl2 && $gl2 eq pack("C*", 0xb8, 0xe1)) {
        seek $fh, $found_offset, 0;
        print $fh $patched;
        seek $fh, $found_offset + 0x1e, 0;
        print $fh pack("C", 0xe0);
        seek $fh, $found_offset + 0x56, 0;
        print $fh pack("C", 0xe0);
        print "[DockerSW] Successfully applied Wine 11.x 24-bit DIB OpenGL patch to $so at 0x" . sprintf("%x", $found_offset) . "\n";
    } else {
        print "[DockerSW] win32u.so pattern found at 0x" . sprintf("%x", $found_offset) . " but GL opcodes mismatch, skipping.\n";
    }
} else {
    print "[DockerSW] win32u.so target pattern not found or unsupported Wine version, skipping.\n";
}

close $fh;
