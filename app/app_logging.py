"""
Logowanie do pliku.

Logi trafiają do ``%USERPROFILE%\\.m2watcher\\logs\\m2watcher.log`` (rotacja 5 × 1 MB).
Łapane są też nieobsłużone wyjątki z głównego wątku, wątków w tle i callbacków GUI,
dzięki czemu każdy błąd zostawia ślad z pełnym tracebackiem.
"""
import logging
import logging.handlers
import platform
import sys
import threading
from pathlib import Path

from config import app_dir

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(threadName)s %(name)s: %(message)s"


def log_dir() -> Path:
    return app_dir() / "logs"


def log_file() -> Path:
    return log_dir() / "m2watcher.log"


def setup_logging(debug: bool = False, version: str = "") -> Path:
    """Konfiguruje logger główny. Zwraca ścieżkę do pliku logu."""
    path = log_file()
    path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    file_handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(file_handler)

    # W wersji exe bez konsoli sys.stderr może być None
    if sys.stderr is not None:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
        root.addHandler(console)

    # Biblioteki sieciowe są gadatliwe na poziomie DEBUG
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    install_exception_hooks()
    logging.getLogger("m2watcher").info(
        "Start M2Watcher %s | Python %s | %s", version or "dev", platform.python_version(), platform.platform()
    )
    return path


def set_debug(debug: bool) -> None:
    logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)


def install_exception_hooks() -> None:
    crash_log = logging.getLogger("m2watcher.crash")

    def excepthook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        crash_log.critical("Nieobsłużony wyjątek", exc_info=(exc_type, exc, tb))

    def thread_excepthook(args):
        crash_log.critical(
            "Nieobsłużony wyjątek w wątku %s",
            getattr(args.thread, "name", "?"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = excepthook
    threading.excepthook = thread_excepthook
