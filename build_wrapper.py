"""
Build wrapper that monkey-patches Python 3.10.0's dis._get_const_info
to avoid IndexError: tuple index out of range during PyInstaller analysis.
"""
import dis
import sys

if sys.version_info[:3] == (3, 10, 0):
    _orig_get_const_info = dis._get_const_info

    def _safe_get_const_info(const_index, constants):
        try:
            return _orig_get_const_info(const_index, constants)
        except IndexError:
            return const_index, repr(const_index)

    dis._get_const_info = _safe_get_const_info

    _orig_get_instructions_bytes = dis._get_instructions_bytes

    def _safe_get_instructions_bytes(*args, **kwargs):
        try:
            yield from _orig_get_instructions_bytes(*args, **kwargs)
        except (IndexError, ValueError):
            return

    dis._get_instructions_bytes = _safe_get_instructions_bytes

from PyInstaller.__main__ import run

if __name__ == '__main__':
    sys.exit(run())
