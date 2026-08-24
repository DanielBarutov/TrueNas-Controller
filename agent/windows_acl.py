"""Windows ACL adapter for the agent's protected credential file."""

import os
from pathlib import Path


class WindowsCredentialAclError(RuntimeError):
    """The credential file ACL could not be restricted safely."""


class WindowsCredentialFileSecurity:
    """Allow only LocalSystem and local administrators to access the file."""

    def secure(self, path: Path) -> None:
        if os.name != "nt":
            raise WindowsCredentialAclError("Windows credential ACL is available only on Windows")
        try:
            import ntsecuritycon
            import win32security
        except ImportError as exc:
            raise WindowsCredentialAclError("pywin32 is required for credential ACL setup") from exc

        operation = "resolve protected Windows principals"
        try:
            dacl = win32security.ACL()
            access_mask = (
                ntsecuritycon.FILE_GENERIC_READ
                | ntsecuritycon.FILE_GENERIC_WRITE
                | ntsecuritycon.DELETE
            )
            for sid_type in (
                win32security.WinLocalSystemSid,
                win32security.WinBuiltinAdministratorsSid,
            ):
                sid = win32security.CreateWellKnownSid(sid_type, None)
                dacl.AddAccessAllowedAce(win32security.ACL_REVISION, access_mask, sid)
            operation = "apply protected file DACL"
            win32security.SetNamedSecurityInfo(
                str(path),
                win32security.SE_FILE_OBJECT,
                win32security.DACL_SECURITY_INFORMATION
                | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
                None,
                None,
                dacl,
                None,
            )
        except Exception as exc:
            error_code = getattr(exc, "winerror", None)
            details = f" ({type(exc).__name__}"
            if error_code is not None:
                details += f", Windows error {error_code}"
            if isinstance(exc, AttributeError):
                details += f": {exc}"
            details += ")"
            raise WindowsCredentialAclError(
                f"credential file ACL setup failed while trying to {operation}{details}"
            ) from exc
