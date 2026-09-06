"""Windows printer service using pywin32 with deferred import."""

import sys
import logging

logger = logging.getLogger(__name__)


class PrinterError(Exception):
    """Public error for printer operations."""


class PrinterUnavailableError(PrinterError):
    """Raised when printing is not available on this system."""


_win32print = None
_win32con = None

if sys.platform == "win32":
    try:
        import win32print as _win32print_mod
        import win32con as _win32con_mod
        _win32print = _win32print_mod
        _win32con = _win32con_mod
    except ImportError:
        _win32print = None
        _win32con = None


def is_available():
    return _win32print is not None


def _require_win32():
    if _win32print is None:
        raise PrinterUnavailableError(
            "Impresion directa no disponible. Instale el controlador de impresora en Windows."
        )


def list_printers():
    """Return list of installed printers."""
    _require_win32()
    try:
        printers = []
        flags = _win32print.PRINTER_ENUM_LOCAL | _win32print.PRINTER_ENUM_CONNECTIONS
        for name in _win32print.EnumPrinters(flags, None, 1):
            printers.append(name[2])
        return printers
    except Exception as e:
        raise PrinterError("No se pudieron listar las impresoras") from e


def get_default_printer():
    """Return the default printer name or None."""
    _require_win32()
    try:
        return _win32print.GetDefaultPrinter()
    except Exception:
        return None


def get_printer_status(printer_name):
    """Return a human-readable status string for the given printer."""
    _require_win32()
    try:
        handle = _win32print.OpenPrinter(printer_name)
        try:
            info = _win32print.GetPrinter(handle, 2)
            status_code = info[5]
            if status_code == 0:
                return "Lista"
            if status_code & _win32print.PRINTER_STATUS_ERROR:
                return "Error"
            if status_code & _win32print.PRINTER_STATUS_OUT_OF_PAPER:
                return "Sin papel"
            if status_code & _win32print.PRINTER_STATUS_NOT_AVAILABLE:
                return "No disponible"
            if status_code & _win32print.PRINTER_STATUS_OFFLINE:
                return "Fuera de linea"
            return "Ocupada"
        finally:
            _win32print.ClosePrinter(handle)
    except Exception:
        return "Desconocido"


def validate_printer_name(printer_name):
    """Check if a printer name matches an installed printer exactly."""
    _require_win32()
    installed = list_printers()
    return printer_name in installed


def print_raw(printer_name, data):
    """Send raw bytes to a Windows printer.

    Args:
        printer_name: Exact name of an installed printer.
        data: Raw bytes to print.

    Raises:
        PrinterError: On any failure.
    """
    _require_win32()

    if not validate_printer_name(printer_name):
        raise PrinterError(f"Impresora '{printer_name}' no encontrada")

    if not data:
        raise PrinterError("Los datos de impresion estan vacios")

    handle = None
    doc_handle = None
    try:
        handle = _win32print.OpenPrinter(printer_name)
        doc_handle = _win32print.StartDocPrinter(handle, 1, ("Ticket", None, "RAW"))
        _win32print.StartPagePrinter(handle)
        written = _win32print.WritePrinter(handle, data)
        if written != len(data):
            raise PrinterError("Escritura incompleta en la impresora")
        _win32print.EndPagePrinter(handle)
        _win32print.EndDocPrinter(handle)
        doc_handle = None
    except PrinterError:
        raise
    except Exception as e:
        raise PrinterError("Error al imprimir") from e
    finally:
        if doc_handle is not None:
            try:
                _win32print.EndDocPrinter(handle)
            except Exception:
                pass
        if handle is not None:
            try:
                _win32print.ClosePrinter(handle)
            except Exception:
                pass


def list_printers_safe():
    """Return printers list or empty list if unavailable."""
    if not is_available():
        return []
    try:
        return list_printers()
    except PrinterError:
        return []


def get_default_printer_safe():
    """Return default printer or None if unavailable."""
    if not is_available():
        return None
    try:
        return get_default_printer()
    except PrinterError:
        return None


def get_printer_status_safe(printer_name):
    """Return status or 'Desconocido' if unavailable."""
    if not is_available():
        return "Impresion directa no disponible"
    try:
        return get_printer_status(printer_name)
    except PrinterError:
        return "Desconocido"
