#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DockerSW Path Translation Utilities (sw_paths.py)
Bidirectional path mapping between Linux container filesystem and Wine/Windows filesystem.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def to_win_path(path_str: str | Path, wineprefix: Optional[str] = None) -> str:
    """
    Convert Linux path to Wine Windows path.
    - Linux root paths (/workspace/...) map to Wine Z: drive (Z:\\workspace\\...).
    - Paths within Wineprefix drive_c map to native C:\\ to avoid internal errors
      when SolidWorks opens documents through the Z: drive prefix.
    - Existing Windows drive paths (C:\\..., D:\\...) are preserved with backslashes.
    """
    s = str(path_str).strip()
    if not s:
        return s

    normalized = s.replace("\\", "/")
    prefix = (wineprefix or os.environ.get("WINEPREFIX") or "/root/.wine").replace("\\", "/").rstrip("/")
    drive_c_candidates = [f"{prefix}/drive_c"]
    if prefix.startswith("/"):
        drive_c_candidates.append(f"Z:{prefix}/drive_c")

    for drive_c in drive_c_candidates:
        normalized_folded = normalized.casefold()
        drive_c_folded = drive_c.casefold()
        if normalized_folded == drive_c_folded:
            return "C:\\"
        if normalized_folded.startswith(f"{drive_c_folded}/"):
            suffix = normalized[len(drive_c):].replace("/", "\\")
            return f"C:{suffix}"

    # Already has Windows drive letter (e.g. C:, D:)
    if len(s) >= 2 and s[1] == ":" and s[0].isalpha():
        return s.replace("/", "\\")

    # Linux absolute path maps to Wine Z:
    if s.startswith("/"):
        return "Z:" + s.replace("/", "\\")

    # Relative path converts forward slashes to backslashes
    return s.replace("/", "\\")


# Alias for backward compatibility
to_windows_path = to_win_path


def to_linux_path(win_path_str: str | Path, wineprefix: Optional[str] = None) -> str:
    """
    Convert Windows/Wine path to Linux path.
    - Z:\\workspace\\... maps to /workspace/...
    - C:\\... maps to $WINEPREFIX/drive_c/...
    """
    s = str(win_path_str).strip().replace("\\", "/")
    if not s:
        return s

    prefix = (wineprefix or os.environ.get("WINEPREFIX") or "/root/.wine").rstrip("/")

    # Z:/... mapped to root /...
    if len(s) >= 2 and s[0].upper() == "Z" and s[1] == ":":
        rest = s[2:]
        return rest if rest.startswith("/") else "/" + rest

    # C:/... mapped to $WINEPREFIX/drive_c/...
    if len(s) >= 2 and s[0].upper() == "C" and s[1] == ":":
        rest = s[2:]
        return f"{prefix}/drive_c{rest}"

    return s
