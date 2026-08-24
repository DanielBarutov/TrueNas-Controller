"""Windows DPAPI adapter for the agent credential store."""

import ctypes
from ctypes import wintypes
import os


class DpapiCredentialError(RuntimeError):
    """Windows DPAPI could not protect or recover the credential blob."""


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class DpapiCredentialProtector:
    """Protect bytes with non-interactive Windows user- or machine-scope DPAPI.

    User scope remains available for legacy migration. Production composition
    selects machine scope because the service runs under LocalSystem.
    """

    _CRYPTPROTECT_UI_FORBIDDEN = 0x1
    _CRYPTPROTECT_LOCAL_MACHINE = 0x4

    def __init__(self, *, local_machine_scope: bool = False) -> None:
        if os.name != "nt":
            raise DpapiCredentialError("Windows DPAPI is available only on Windows")
        try:
            crypt32 = ctypes.WinDLL("Crypt32.dll", use_last_error=True)
            kernel32 = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
            self._protect = crypt32.CryptProtectData
            self._unprotect = crypt32.CryptUnprotectData
            self._local_free = kernel32.LocalFree
        except (AttributeError, OSError) as exc:
            raise DpapiCredentialError("Windows DPAPI functions are unavailable") from exc

        blob_type = ctypes.POINTER(_DataBlob)
        for function in (self._protect, self._unprotect):
            function.argtypes = [
                blob_type,
                wintypes.LPCWSTR,
                blob_type,
                ctypes.c_void_p,
                ctypes.c_void_p,
                wintypes.DWORD,
                blob_type,
            ]
            function.restype = wintypes.BOOL
        self._local_free.argtypes = [ctypes.c_void_p]
        self._local_free.restype = ctypes.c_void_p
        self._flags = self._CRYPTPROTECT_UI_FORBIDDEN
        if local_machine_scope:
            self._flags |= self._CRYPTPROTECT_LOCAL_MACHINE

    def protect(self, value: bytes) -> bytes:
        return self._transform(self._protect, value, operation="protect")

    def unprotect(self, value: bytes) -> bytes:
        return self._transform(self._unprotect, value, operation="unprotect")

    def _transform(self, function, value: bytes, *, operation: str) -> bytes:
        if not value:
            raise DpapiCredentialError(f"cannot {operation} an empty blob")
        input_blob, _input_buffer = _make_blob(value)
        output_blob = _DataBlob()
        if not function(
            ctypes.byref(input_blob),
            None,
            None,
            None,
            None,
            self._flags,
            ctypes.byref(output_blob),
        ):
            error_code = ctypes.get_last_error()
            raise DpapiCredentialError(f"Windows DPAPI {operation} failed with error {error_code}")
        try:
            if not output_blob.pbData or not output_blob.cbData:
                raise DpapiCredentialError(f"Windows DPAPI {operation} returned an empty blob")
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            self._local_free(output_blob.pbData)


def _make_blob(value: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(value, len(value))
    blob = _DataBlob(
        cbData=len(value),
        pbData=ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    return blob, buffer
