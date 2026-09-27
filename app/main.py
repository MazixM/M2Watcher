"""
M2Watcher — punkt startowy.

    python main.py             # okno aplikacji (domyślnie)
    python main.py --console   # tryb tekstowy, bez okna
    python main.py --setup     # wymuś kreator konfiguracji
"""
import argparse
import logging
import socket
import sys
import threading

from version import __version__

log = logging.getLogger("m2watcher")

SINGLE_INSTANCE_PORT = 47819
_instance_socket = None


def acquire_single_instance() -> bool:
    """Blokuje port na localhost — druga kopia aplikacji dałaby podwójne alarmy."""
    global _instance_socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if sys.platform == "win32":
            s.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_EXCLUSIVEADDRUSE", 0xFFFFFFFB), 1)
        s.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        s.listen(1)
    except OSError:
        s.close()
        return False
    _instance_socket = s
    return True


def show_fatal(message: str) -> None:
    log.critical(message)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("M2Watcher", message)
        root.destroy()
    except Exception:
        print(message, file=sys.stderr)


def run_gui(config, args) -> int:
    import tkinter as tk

    from controller import AppController
    from gui import theme
    from gui.main_window import MainWindow

    root = tk.Tk()
    root.withdraw()
    theme.apply(root)
    controller = AppController(config)
    window = MainWindow(root, controller, __version__)
    if config.load_error:
        window.add_event(f"⚠  {config.load_error}", "closed")

    def start():
        controller.start()
        window.add_event("Monitorowanie uruchomione")
        if config.get("start_minimized", False) and not first_run:
            root.iconify()
        else:
            root.deiconify()

    first_run = config.is_first_run or args.setup
    if first_run:
        window.run_wizard(on_done=start)
    else:
        start()
    try:
        root.mainloop()
    finally:
        controller.shutdown()
    return 0


def run_console(config) -> int:
    from controller import AppController

    controller = AppController(config)

    def printer():
        while True:
            kind, payload = controller.ui_queue.get()
            if kind == "event":
                print(f"[{payload.time:%H:%M:%S}] {controller.event_text(payload)}")
            elif kind == "discord" and payload.state == "offline":
                print(f"[Discord] brak połączenia — {payload.pending} w kolejce")
            elif kind == "alarm" and payload:
                print("[ALARM] Naciśnij Enter, aby zatrzymać dźwięk")

    threading.Thread(target=printer, name="ConsolePrinter", daemon=True).start()
    controller.start()
    print(f"M2Watcher {__version__} — tryb konsolowy. Urządzenie: {config.get('device_name')}")
    print("Enter = zatrzymaj alarm, Ctrl+C = zakończ\n")
    try:
        while True:
            input()
            controller.stop_alarm()
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        controller.shutdown()
    return 0


def self_test() -> int:
    """Sprawdza, czy w exe są wszystkie moduły potrzebne w działaniu (uruchamiane w CI).

    Wynik trafia do logu i do kodu wyjścia (0 = OK) — exe nie ma konsoli.
    """
    import importlib
    problems = []
    modules = ["tkinter", "psutil", "requests", "controller", "gui.main_window", "gui.settings"]
    if sys.platform == "win32":
        modules += ["winsound", "win32gui", "win32process", "pywintypes"]
    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as e:
            problems.append(f"{name}: {e}")
    try:
        import tempfile
        from pathlib import Path

        import sounds
        player = sounds.SoundPlayer(lambda: {}, cache_dir=Path(tempfile.mkdtemp()))
        for name in sounds.BUILTIN_SOUNDS:
            player.resolve_file(f"builtin:{name}", "", 50)
        if sys.platform == "win32" and sounds.winsound is None:
            problems.append("sounds.winsound nie został załadowany")
    except Exception as e:
        problems.append(f"sounds: {e}")
    for p in problems:
        log.error("Self-test: %s", p)
    log.info("Self-test: %s", "OK" if not problems else f"{len(problems)} problemów")
    return 1 if problems else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="M2Watcher — monitor klientów Metin2")
    parser.add_argument("--console", action="store_true", help="tryb tekstowy bez okna")
    parser.add_argument("--setup", action="store_true", help="pokaż kreator konfiguracji")
    parser.add_argument("--self-test", action="store_true", help="sprawdź spakowane moduły i zakończ")
    args = parser.parse_args(argv)

    # Konfiguracja przed logiem, bo poziom logowania zależy od ustawienia "debug"
    from app_logging import setup_logging
    from config import Config

    config = Config()
    log_path = setup_logging(debug=bool(config.get("debug", False)), version=__version__)
    log.info("Plik konfiguracji: %s | log: %s", config.path, log_path)
    if config.load_error:
        log.error(config.load_error)

    if args.self_test:
        return self_test()

    if not acquire_single_instance():
        show_fatal("M2Watcher jest już uruchomiony.\nSprawdź pasek zadań.")
        return 1

    try:
        if args.console:
            return run_console(config)
        return run_gui(config, args)
    except Exception as e:
        log.exception("Błąd krytyczny")
        show_fatal(f"Wystąpił błąd krytyczny:\n{e}\n\nSzczegóły zapisano w pliku:\n{log_path}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
