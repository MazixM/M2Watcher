"""Główne okno aplikacji."""
import ctypes
import logging
import os
import platform
import queue
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Optional

from app_logging import log_dir
from controller import AppController
from discord_client import (STATE_CONFIG_ERROR, STATE_DISABLED, STATE_OFFLINE, STATE_OK, STATE_SENDING,
                            SenderStatus)
from gui import theme
from gui.optimization import OptimizationTab
from gui.settings import SettingsWindow, SetupWizard
from m2watcher import WatchEvent

log = logging.getLogger(__name__)

# Tylko znaki z BMP — Tk 8.6 na Windowsie nie zawsze rysuje emoji spoza BMP
EVENT_ICONS = {"new": "+", "logout": "●", "closed": "⚠", "reconnect": "●"}
MAX_EVENTS = 300


class MainWindow:
    def __init__(self, root: tk.Tk, controller: AppController, version: str):
        self.root = root
        self.c = controller
        self.version = version
        self._icon = theme.make_icon(root)
        root.iconphoto(True, self._icon)
        root.title("M2Watcher")
        root.geometry("940x720")
        root.minsize(760, 520)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.report_callback_exception = self._tk_error

        self._build()
        self._refresh_header()
        self._update_discord(controller.discord_status())
        self._set_alarm(False)
        root.after(200, self._poll)
        root.after(1000, self._tick)

    # ---------------------------------------------------------------- układ
    def _build(self) -> None:
        root = self.root
        header = self.header = ttk.Frame(root, padding=(20, 16, 20, 8))
        header.pack(fill="x")
        left = ttk.Frame(header)
        left.pack(side="left")
        ttk.Label(left, text="M2Watcher", style="Title.TLabel").pack(anchor="w")
        self.device_label = ttk.Label(left, style="Muted.TLabel")
        self.device_label.pack(anchor="w")
        ttk.Button(header, text="⚙  Ustawienia", command=self.open_settings).pack(side="right")

        # Pasek alarmu
        self.alarm_bar = tk.Frame(root, bg=theme.DANGER_BG, highlightbackground=theme.DANGER,
                                  highlightthickness=1)
        self.alarm_text = tk.Label(self.alarm_bar, bg=theme.DANGER_BG, fg=theme.DANGER, anchor="w",
                                   font=(theme.FAMILY, 11, "bold"), justify="left")
        self.alarm_text.pack(side="left", fill="x", expand=True, padx=14, pady=10)
        ttk.Button(self.alarm_bar, text="Zatrzymaj alarm", style="Danger.TButton",
                   command=self.c.stop_alarm).pack(side="right", padx=10, pady=8)

        # Karty statusu
        self.cards = ttk.Frame(root, padding=(20, 4, 20, 8))
        self.cards.pack(fill="x")
        for i in range(3):
            self.cards.columnconfigure(i, weight=1, uniform="cards")
        self.clients_value, self.clients_hint = self._status_card(0, "Klienci Metin2")
        self.discord_value, self.discord_hint = self._status_card(1, "Discord")
        self.sound_value, self.sound_hint = self._status_card(2, "Dźwięk")
        self.discord_retry = ttk.Button(self.discord_hint.master, text="Ponów teraz",
                                        command=self.c.sender.retry_now)

        footer = ttk.Frame(root, padding=(20, 10, 20, 14))
        footer.pack(side="bottom", fill="x")
        ttk.Button(footer, text="Wyślij test na Discord", command=self.send_test).pack(side="left")
        ttk.Button(footer, text="Otwórz folder logów", command=self.open_logs).pack(side="left", padx=8)
        ttk.Label(footer, text=f"wersja {self.version}", style="Hint.TLabel").pack(side="right")

        # Zakładki: monitor (klienci + zdarzenia) i opcjonalna optymalizacja
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(4, 0))
        body = ttk.Frame(self.tabs, padding=(0, 10, 0, 0))
        self.tabs.add(body, text="Monitor")
        self.optimization = OptimizationTab(
            self.tabs, self.c.optimizer,
            get_settings=lambda: self.c.config.get("optimization", {}),
            save_settings=self._save_optimization,
            get_clients=self.c.watcher.snapshot,
        )
        self.tabs.add(self.optimization, text="Optymalizacja")

        # Lista klientów
        ttk.Label(body, text="Klienci", style="H2.TLabel").pack(anchor="w", pady=(0, 6))
        cols = ("status", "title", "pid", "conn", "since")
        table_frame = ttk.Frame(body, style="Card.TFrame", padding=1)
        table_frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_frame, columns=cols, show="headings", height=6, selectmode="none")
        for col, label, width, anchor in (("status", "Status", 130, "w"), ("title", "Okno", 330, "w"),
                                          ("pid", "PID", 80, "center"), ("conn", "Połączenia", 100, "center"),
                                          ("since", "Od", 90, "center")):
            self.table.heading(col, text=label, anchor=anchor)  # type: ignore[arg-type]
            self.table.column(col, width=width, anchor=anchor, stretch=(col == "title"))  # type: ignore[arg-type]
        self.table.tag_configure("in", foreground=theme.OK)
        self.table.tag_configure("out", foreground=theme.DANGER)
        self.table.pack(fill="both", expand=True)
        self.empty_label = ttk.Label(table_frame, style="CardMuted.TLabel",
                                     text="Nie wykryto uruchomionych klientów Metin2.\n"
                                          "Uruchom grę — pojawi się tutaj automatycznie.", justify="center")

        ttk.Label(body, text="Ostatnie zdarzenia", style="H2.TLabel").pack(anchor="w", pady=(14, 6))
        events_frame = ttk.Frame(body, style="Card.TFrame", padding=1)
        events_frame.pack(fill="both", expand=True)
        self.events = ttk.Treeview(events_frame, columns=("time", "text"), show="headings", height=6,
                                   selectmode="browse")
        self.events.heading("time", text="Czas", anchor="w")
        self.events.heading("text", text="Zdarzenie", anchor="w")
        self.events.column("time", width=90, stretch=False)
        self.events.column("text", width=600)
        self.events.tag_configure("logout", foreground=theme.DANGER)
        self.events.tag_configure("closed", foreground=theme.WARN)
        self.events.tag_configure("reconnect", foreground=theme.OK)
        self.events.tag_configure("info", foreground=theme.MUTED)
        scroll = ttk.Scrollbar(events_frame, orient="vertical", command=self.events.yview)
        self.events.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.events.pack(fill="both", expand=True)


    def _status_card(self, column: int, title: str):
        frame = ttk.Frame(self.cards, style="Card.TFrame", padding=(14, 10))
        frame.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 6, 0 if column == 2 else 6))
        ttk.Label(frame, text=title.upper(), style="CardHint.TLabel").pack(anchor="w")
        row = ttk.Frame(frame, style="Card.TFrame", borderwidth=0)
        row.configure(relief="flat")
        row.pack(fill="x", anchor="w")
        value = ttk.Label(row, style="CardValue.TLabel")
        value.pack(side="left", anchor="w")
        hint = ttk.Label(frame, style="CardHint.TLabel", wraplength=250, justify="left")
        hint.pack(anchor="w")
        return value, hint

    # ---------------------------------------------------------------- odświeżanie
    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.c.ui_queue.get_nowait()
                if kind == "event":
                    self._on_event(payload)
                elif kind == "discord":
                    self._update_discord(payload)
                elif kind == "alarm":
                    self._set_alarm(payload)
        except queue.Empty:
            pass
        finally:
            self.root.after(200, self._poll)

    def _tick(self) -> None:
        try:
            self._refresh_clients()
            self._refresh_sound()
            self.optimization.refresh()
        finally:
            self.root.after(1000, self._tick)

    def _refresh_header(self) -> None:
        self.device_label.configure(text=f"Urządzenie: {self.c.config.get('device_name')}")

    def _refresh_clients(self) -> None:
        clients = self.c.watcher.snapshot()
        self.table.delete(*self.table.get_children())
        for cl in clients:
            status = "● Zalogowany" if cl.is_logged_in else "● Wylogowany"
            self.table.insert("", "end", values=(status, cl.window_title, cl.pid, cl.num_connections,
                                                 cl.status_since.strftime("%H:%M:%S")),
                              tags=("in" if cl.is_logged_in else "out",))
        if clients:
            self.empty_label.place_forget()
        else:
            self.empty_label.place(relx=0.5, rely=0.6, anchor="center")
        out = sum(1 for cl in clients if not cl.is_logged_in)
        if not clients:
            self.clients_value.configure(text="Brak", foreground=theme.MUTED)
            self.clients_hint.configure(text="Czekam na uruchomienie gry")
        else:
            self.clients_value.configure(text=f"{len(clients) - out} / {len(clients)} zalogowanych",
                                         foreground=theme.DANGER if out else theme.OK)
            self.clients_hint.configure(text=f"{out} wylogowanych" if out else "Wszystko w porządku")
        if self.c.watcher.last_error:
            self.clients_hint.configure(text=f"Błąd monitora: {self.c.watcher.last_error[:60]}")

    def _refresh_sound(self) -> None:
        s = self.c.config.get("sounds", {})
        if not s.get("enabled", True):
            self.sound_value.configure(text="Wyłączony", foreground=theme.MUTED)
            self.sound_hint.configure(text="Włączysz w Ustawieniach → Dźwięki")
        else:
            self.sound_value.configure(text=f"Włączony • {s.get('volume', 80)}%", foreground=theme.OK)
            self.sound_hint.configure(text="Alarm powtarza się do potwierdzenia" if s.get("repeat_until_ack")
                                      else "Alarm odtwarzany raz")

    def _update_discord(self, st: SenderStatus) -> None:
        pending = f" • {st.pending} w kolejce" if st.pending and st.state != STATE_DISABLED else ""
        text, color, hint = {
            STATE_DISABLED: ("Wyłączony", theme.MUTED, "Skonfigurujesz w Ustawieniach → Discord"),
            STATE_OK: ("Gotowy", theme.OK, ""),
            STATE_SENDING: ("Wysyłanie…", theme.ACCENT, ""),
            STATE_OFFLINE: ("Brak połączenia", theme.WARN,
                            "Powiadomienia czekają i wyjdą, gdy wróci internet"),
            STATE_CONFIG_ERROR: ("Błąd ustawień", theme.DANGER, st.last_error),
        }.get(st.state, (st.state, theme.MUTED, ""))
        if st.state == STATE_OK:
            hint = (f"Ostatnio wysłano {datetime.fromtimestamp(st.last_success):%H:%M:%S}"
                    if st.last_success else "Powiadomienia wyjdą od razu")
        self.discord_value.configure(text=text + pending, foreground=color)
        self.discord_hint.configure(text=hint)
        if st.state in (STATE_OFFLINE, STATE_CONFIG_ERROR):
            self.discord_retry.pack(anchor="w", pady=(6, 0))
        else:
            self.discord_retry.pack_forget()

    def _on_event(self, event: WatchEvent) -> None:
        tag = event.kind if event.kind in ("logout", "closed", "reconnect") else "info"
        text = f"{EVENT_ICONS.get(event.kind, '•')}  {self.c.event_text(event)}"
        self.add_event(text, tag, event.time)
        if event.kind in ("logout", "closed"):
            self._flash_taskbar()
            # Tekst ustawiamy zawsze; pasek pokaże się, gdy odtwarzacz zgłosi aktywny alarm
            self.alarm_text.configure(text=f"{EVENT_ICONS[event.kind]}  {self.c.event_text(event)}"
                                           f"   ({event.time:%H:%M:%S})")

    def add_event(self, text: str, tag: str = "info", when: Optional[datetime] = None) -> None:
        when = when or datetime.now()
        self.events.insert("", 0, values=(when.strftime("%H:%M:%S"), text), tags=(tag,))
        children = self.events.get_children()
        if len(children) > MAX_EVENTS:
            self.events.delete(*children[MAX_EVENTS:])

    def _set_alarm(self, active: bool) -> None:
        if active:
            self.alarm_bar.pack(fill="x", padx=20, pady=(4, 8), after=self.header)
        else:
            self.alarm_bar.pack_forget()

    def _flash_taskbar(self) -> None:
        """Miga ikoną na pasku zadań, nie zabierając fokusu grze."""
        if platform.system() != "Windows":
            return
        try:
            class FLASHWINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("hwnd", ctypes.c_void_p), ("dwFlags", ctypes.c_uint),
                            ("uCount", ctypes.c_uint), ("dwTimeout", ctypes.c_uint)]
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())  # type: ignore[attr-defined]
            info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 0x3 | 0xC, 0, 0)  # ALL | TIMERNOFG
            ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))  # type: ignore[attr-defined]
        except Exception:
            log.debug("FlashWindowEx nie powiodło się", exc_info=True)

    # ---------------------------------------------------------------- akcje
    def open_settings(self, tab: str = "general") -> None:
        SettingsWindow(self.root, self.c.config.as_dict(), self.c.sender, self.c.sounds, self._save, tab)

    def run_wizard(self, on_done=None) -> None:
        def saved(data):
            self._save(data)
            if on_done:
                on_done()
        SetupWizard(self.root, self.c.config.as_dict(), self.c.sender, self.c.sounds, saved, on_cancel=on_done)

    def _save(self, data) -> None:
        try:
            self.c.apply_settings(data)
        except Exception as e:
            log.exception("Nie udało się zapisać ustawień")
            messagebox.showerror("Błąd", f"Nie udało się zapisać ustawień:\n{e}", parent=self.root)
            return
        self._refresh_header()
        self._update_discord(self.c.discord_status())
        self.add_event("✔  Zapisano ustawienia")

    def _save_optimization(self, data) -> None:
        try:
            self.c.save_optimization(data)
        except Exception as e:
            log.exception("Nie udało się zapisać ustawień optymalizacji")
            messagebox.showerror("Błąd", f"Nie udało się zapisać ustawień:\n{e}", parent=self.root)
            return
        self.add_event("✔  Optymalizacja: " + ("włączona" if data.get("enabled") else "wyłączona"))

    def send_test(self) -> None:
        if self.c.config.get("discord.method", "none") == "none":
            if messagebox.askyesno("Discord", "Powiadomienia Discord nie są skonfigurowane. Otworzyć ustawienia?",
                                   parent=self.root):
                self.open_settings("discord")
            return
        self.add_event("→  Wysyłanie wiadomości testowej…")
        device = self.c.config.get("device_name")

        def work():
            ok, msg = self.c.sender.send_test(device)
            self.root.after(0, lambda: self.add_event(("✔  " if ok else "✖  ") + msg.splitlines()[0],
                                                      "reconnect" if ok else "logout"))

        threading.Thread(target=work, name="DiscordTest", daemon=True).start()

    def open_logs(self) -> None:
        path = log_dir()
        path.mkdir(parents=True, exist_ok=True)
        try:
            if platform.system() == "Windows":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception:
            log.exception("Nie udało się otworzyć folderu logów")
            messagebox.showinfo("Logi", f"Logi znajdziesz tutaj:\n{path}", parent=self.root)

    def on_close(self) -> None:
        if messagebox.askyesno("Zamknąć M2Watcher?", "Monitorowanie klientów zostanie zatrzymane.",
                               parent=self.root):
            self.c.shutdown()
            self.root.destroy()

    def _tk_error(self, exc_type, exc, tb) -> None:
        log.error("Błąd interfejsu", exc_info=(exc_type, exc, tb))
        try:
            self.add_event(f"✖  Błąd interfejsu: {exc} (szczegóły w logu)", "logout")
        except Exception:
            pass

