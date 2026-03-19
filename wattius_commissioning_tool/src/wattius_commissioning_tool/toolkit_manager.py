from __future__ import annotations

import logging
import subprocess

from wbms_api.wbms_toolkit_api import wbms_sign_in
from wbms_api.wbms_toolkit_api import wbms_toolkit_api_poll
from wbms_api.wbms_toolkit_types import wbms_result

logger = logging.getLogger("zabra.commissioning")


class ToolkitManager:
    """Manages the Wattius Toolkit .exe process lifecycle."""

    def __init__(self, toolkit_path: str, username: str, password: str) -> None:
        self._toolkit_path = toolkit_path
        self._username = username
        self._password = password
        self._process: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        """Launch the Toolkit .exe via subprocess.Popen with CREATE_NO_WINDOW flag."""
        if self.is_running():
            logger.debug("Toolkit is already running, skipping start.")
            return
        logger.info("Starting Wattius Toolkit: %s", self._toolkit_path)
        self._process = subprocess.Popen(
            [self._toolkit_path],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def wait_ready(self, timeout: int = 30) -> bool:
        """Poll with wbms_toolkit_api_poll() until ready. Returns True if ready."""
        logger.debug("Waiting for Toolkit to become ready (timeout=%ds).", timeout)
        result = wbms_toolkit_api_poll(timeout)
        ready = result == wbms_result.OK
        if ready:
            logger.info("Toolkit is ready.")
        else:
            logger.warning("Toolkit did not become ready within %ds (result=%s).", timeout, result)
        return ready

    def sign_in(self) -> bool:
        """Sign in with credentials. Returns True on success."""
        logger.info("Signing in to Wattius Toolkit as '%s'.", self._username)
        result = wbms_sign_in(self._username, self._password)
        success = result == wbms_result.OK
        if success:
            logger.info("Sign-in successful.")
        else:
            logger.warning("Sign-in failed (result=%s).", result)
        return success

    def stop(self) -> None:
        """Terminate the Toolkit process."""
        if self._process is None:
            return
        if self._process.poll() is not None:
            logger.debug("Toolkit process already exited.")
            self._process = None
            return
        logger.info("Terminating Wattius Toolkit process.")
        self._process.terminate()
        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning("Toolkit process did not terminate in time; killing.")
            self._process.kill()
        self._process = None

    def is_running(self) -> bool:
        """Check if the process is still alive (process.poll() is None)."""
        return self._process is not None and self._process.poll() is None
