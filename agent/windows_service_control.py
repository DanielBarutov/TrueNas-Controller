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
        import win32service
    except ImportError as exc:
        raise RuntimeError("pywin32 is required to register the Windows Service") from exc

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
            if getattr(exc, "winerror", None) != 1056:
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
