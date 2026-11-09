"""Restore the OS loader path in a deliberately minimal native-door env."""

import os


def restore_system_root() -> None:
    if os.name != "nt" or os.environ.get("SystemRoot"):
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetWindowsDirectoryW.argtypes = (wintypes.LPWSTR, wintypes.UINT)
    kernel.GetWindowsDirectoryW.restype = wintypes.UINT
    buffer = ctypes.create_unicode_buffer(32768)
    size = kernel.GetWindowsDirectoryW(buffer, len(buffer))
    if not 0 < size < len(buffer):
        raise ctypes.WinError(ctypes.get_last_error())
    os.environ["SystemRoot"] = buffer.value
