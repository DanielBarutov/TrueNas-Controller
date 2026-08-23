"""Optional pywin32 wrapper around the platform-neutral agent service."""

import asyncio
from collections.abc import Callable
import os
from threading import Event
from typing import Any

from agent.service import AgentService


class WindowsServiceError(RuntimeError):
    """The Windows Service Control Manager adapter is unavailable or unsafe."""


class WindowsServiceHost:
    """Thread-safe stop bridge from SCM callbacks into asyncio."""

    def __init__(self, stop_event: Event | None = None) -> None:
        self._stop_event = stop_event or Event()

    async def wait_for_stop(self) -> None:
        await asyncio.to_thread(self._stop_event.wait)

    def request_stop(self) -> None:
        self._stop_event.set()


class PyWin32ServiceRuntime:
    """Run ``AgentService`` under the Windows Service Control Manager.

    pywin32 is imported only when this entrypoint is executed on Windows.  The
    agent's composition root remains responsible for constructing the actual
    heartbeat and passing a fresh ``AgentService`` instance to this adapter.
    """

    def __init__(
        self,
        *,
        service_name: str,
        display_name: str,
        build_service: Callable[[], AgentService],
    ) -> None:
        if not service_name or not display_name:
            raise ValueError("Windows service name and display name are required")
        self._service_name = service_name
        self._display_name = display_name
        self._build_service = build_service

    def run(self) -> None:
        """Delegate command handling and lifecycle callbacks to pywin32."""

        if os.name != "nt":
            raise WindowsServiceError("Windows Service runtime is available only on Windows")
        try:
            import win32service
            import win32serviceutil
        except ImportError as exc:
            raise WindowsServiceError(
                "pywin32 is required for the Windows Service wrapper"
            ) from exc

        runtime = self

        class _AgentWindowsService(win32serviceutil.ServiceFramework):
            _svc_name_ = runtime._service_name
            _svc_display_name_ = runtime._display_name
            _svc_description_ = "TrueNAS Controller station agent"

            def __init__(self, args: Any) -> None:
                super().__init__(args)
                self._host = WindowsServiceHost()
                self._service = runtime._build_service()

            def SvcStop(self) -> None:
                self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
                self._host.request_stop()

            def SvcDoRun(self) -> None:
                asyncio.run(self._service.run(self._host))

        win32serviceutil.HandleCommandLine(_AgentWindowsService)
