"""System checks for the Lobby NL OSINT pipeline."""

import sys
import platform


def check_python_version() -> bool:
    v = sys.version_info
    if v.major != 3 or v.minor not in (10, 11, 12):
        raise SystemError(
            f"Python {v.major}.{v.minor} niet ondersteund. "
            "Gebruik Python 3.10, 3.11 of 3.12. "
            "Download: https://python.org/downloads/"
        )
    return True


def check_platform() -> str:
    return platform.system()
