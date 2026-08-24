"""Windows ACL adapter for the agent's protected credential file."""

import os
from pathlib import Path


class WindowsCredentialAclError(RuntimeError):
    """The credential file ACL could not be restricted safely."""


class WindowsCredentialFileSecurity:
    """Allow only the account running the agent to access the credential file."""

    def secure(self, path: Path) -> None:
        if os.name != "nt":
            raise WindowsCredentialAclError("Windows credential ACL is available only on Windows")
        try:
            import ntsecuritycon
            import win32api
            import win32security
        except ImportError as exc:
            raise WindowsCredentialAclError("pywin32 is required for credential ACL setup") from exc

        operation = "resolve current Windows account"
        try:
            account_name = win32api.GetUserName()
            user_sid, _, _ = win32security.LookupAccountName(None, account_name)
            dacl = win32security.ACL()
            access_mask = (
                ntsecuritycon.FILE_GENERIC_READ
                | ntsecuritycon.FILE_GENERIC_WRITE
                | ntsecuritycon.DELETE
            )
            dacl.AddAccessAllowedAce(ntsecuritycon.ACL_REVISION, access_mask, user_sid)
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
            details = f" (Windows error {error_code})" if error_code is not None else ""
            raise WindowsCredentialAclError(
                f"credential file ACL setup failed while trying to {operation}{details}"
            ) from exc
