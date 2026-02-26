from __future__ import annotations

import logging
import queue
import shutil
import threading
from pathlib import Path

_log = logging.getLogger(__name__)


class NetworkTransport:
    """Copies log files to a network share in a background daemon thread.

    Files are queued for copying and processed one at a time by a worker
    thread. All copy errors are swallowed and logged at DEBUG level so that
    network failures never affect the calling application.
    """

    def __init__(self, network_path: str) -> None:
        """Initialise the transport and start the background worker thread.

        Args:
            network_path: Destination directory path (UNC or mapped drive) to
                which log files will be copied.
        """
        self._network_path = network_path
        self._queue: queue.Queue[Path | None] = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="NetworkTransport")
        self._thread.start()

    def _worker(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                break
            try:
                shutil.copy2(item, self._network_path)
            except Exception as exc:
                _log.debug("NetworkTransport: failed to copy %s: %s", item, exc)

    def enqueue(self, local_path: Path) -> None:
        """Queue a local file for copying to the network path.

        If the worker thread is no longer alive the call is silently ignored.

        Args:
            local_path: Path to the local file that should be copied.
        """
        if not self._thread.is_alive():
            return
        self._queue.put(local_path)

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the worker to stop and wait for it to finish.

        Sends a sentinel value to the queue and joins the thread with the
        given timeout. Returns regardless of whether the thread has exited.

        Args:
            timeout: Seconds to wait for the worker thread to join.
        """
        self._queue.put(None)
        self._thread.join(timeout=timeout)
