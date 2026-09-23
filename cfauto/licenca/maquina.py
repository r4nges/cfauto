import hashlib
import platform
import sys


def _serial_volume() -> str:
    if sys.platform != "win32":
        return ""
    import ctypes

    serial = ctypes.c_ulong(0)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(  # type: ignore[attr-defined]
        ctypes.c_wchar_p("C:\\"), None, 0, ctypes.byref(serial), None, None, None, 0
    )
    return str(serial.value) if ok else ""


def id_maquina() -> str:
    base = f"{platform.node()}|{_serial_volume()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]
