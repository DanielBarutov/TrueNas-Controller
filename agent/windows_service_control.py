"""Windows Service Control Manager operations for the packaged agent."""

import time

SERVICE_NAME = "TrueNasControllerAgent"
SERVICE_DISPLAY_NAME = "TrueNAS Controller Agent"


def install_windows_service(
    *,
    command_line: str,
    service_account: str,
    service_password: str,
) -> None:
    """Create or update the agent service using the target Python runtime."""

    try:
        import win32api
        import win32con
        import win32security
        import win32service
    except ImportError as exc:
        raise RuntimeError("pywin32 is required to register the Windows Service") from exc

    _validate_service_credentials(
        win32api,
        win32con,
        win32security,
        service_account,
        service_password,
    )
    manager = win32service.OpenSCManager(
        None,
        None,
        win32service.SC_MANAGER_CONNECT | win32service.SC_MANAGER_CREATE_SERVICE,
    )
    service = None
    try:
        try:
            service = win32service.OpenService(
                manager,
                SERVICE_NAME,
                win32service.SERVICE_CHANGE_CONFIG,
            )
            win32service.ChangeServiceConfig(
                service,
                win32service.SERVICE_NO_CHANGE,
                win32service.SERVICE_AUTO_START,
                win32service.SERVICE_ERROR_NORMAL,
                command_line,
                None,
                0,
                None,
                service_account,
                service_password,
                SERVICE_DISPLAY_NAME,
            )
        except win32service.error as exc:
            if getattr(exc, "winerror", None) != 1060:
                raise RuntimeError("could not update the existing Windows Service") from exc
            service = win32service.CreateService(
                manager,
                SERVICE_NAME,
                SERVICE_DISPLAY_NAME,
                win32service.SERVICE_ALL_ACCESS,
                win32service.SERVICE_WIN32_OWN_PROCESS,
                win32service.SERVICE_AUTO_START,
                win32service.SERVICE_ERROR_NORMAL,
                command_line,
                None,
                0,
                None,
                service_account,
                service_password,
            )
    except win32service.error as exc:
        raise RuntimeError("could not register the Windows Service") from exc
    finally:
        if service is not None:
            win32service.CloseServiceHandle(service)
        win32service.CloseServiceHandle(manager)


def start_windows_service() -> None:
    """Start the agent service and wait until SCM reports it as running."""

    try:
        import win32service
    except ImportError as exc:
        raise RuntimeError("pywin32 is required to start the Windows Service") from exc

    manager = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
    service = win32service.OpenService(
        manager,
        SERVICE_NAME,
        win32service.SERVICE_START | win32service.SERVICE_QUERY_STATUS,
    )
    try:
        try:
            win32service.StartService(service, [])
        except win32service.error as exc:
            error_code = getattr(exc, "winerror", None)
            if error_code == 1056:
                pass
            elif error_code == 1069:
                raise RuntimeError(
                    "could not start the Windows Service: service account logon failed; "
                    "verify the Windows account name and password"
                ) from exc
            elif error_code == 1385:
                raise RuntimeError(
                    "could not start the Windows Service: the account is not granted "
                    "Log on as a service"
                ) from exc
            else:
                raise RuntimeError("could not start the Windows Service") from exc
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            status = win32service.QueryServiceStatus(service)[1]
            if status == win32service.SERVICE_RUNNING:
                return
            if status == win32service.SERVICE_STOPPED:
                raise RuntimeError("Windows Service stopped during startup")
            time.sleep(0.5)
        raise RuntimeError("Windows Service did not reach running state in 30 seconds")
    finally:
        win32service.CloseServiceHandle(service)
        win32service.CloseServiceHandle(manager)


def _validate_service_credentials(
    win32api,
    win32con,
    win32security,
    service_account: str,
    service_password: str,
) -> None:
    """Validate the Windows password before writing it into SCM configuration."""

    domain, username = _split_service_account(service_account)
    try:
        token = win32security.LogonUser(
            username,
            domain,
            service_password,
            win32con.LOGON32_LOGON_INTERACTIVE,
            win32con.LOGON32_PROVIDER_DEFAULT,
        )
    except win32security.error as exc:
        raise RuntimeError(
            "service account credentials were rejected; use the Windows logon "
            "password, not the Controller Basic Auth password; a blank password "
            "is not supported for a Windows service account"
        ) from exc
    try:
        win32api.CloseHandle(token)
    except Exception:
        raise RuntimeError("could not close the temporary service account token") from None


def _split_service_account(service_account: str) -> tuple[str | None, str]:
    if "\\" in service_account:
        domain, username = service_account.split("\\", 1)
        return (domain or None), username
    return None, service_account
