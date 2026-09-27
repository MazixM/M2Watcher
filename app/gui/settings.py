"""
Formularz ustawień — używany w dwóch miejscach:

* ``SetupWizard`` — kreator przy pierwszym uruchomieniu (krok po kroku),
* ``SettingsWindow`` — edycja ustawień z zakładkami.
"""
import copy
import logging
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

from config import EVENT_LABELS, EVENTS, default_device_name
from discord_client import validate_settings
from gui import theme
from sounds import CUSTOM_SOUND, NONE_SOUND, sound_choices, validate_wav

log = logging.getLogger(__name__)

HELP_URL = "https://github.com/MazixM/M2Watcher/blob/main/app/DISCORD_SETUP.md"
METHODS = [
    ("webhook", "Webhook (zalecane — wystarczy wkleić jeden adres)"),
    ("bot", "Bot Discord (wiadomość prywatna lub kanał)"),
    ("none", "Bez powiadomień Discord"),
]


def card(parent, title: str, hint: str = "") -> ttk.Frame:
    outer = ttk.Frame(parent, style="Card.TFrame", padding=16)
    outer.pack(fill="x", pady=(0, 12))
    ttk.Label(outer, text=title, style="CardH2.TLabel").pack(anchor="w")
    if hint:
        ttk.Label(outer, text=hint, style="CardHint.TLabel", wraplength=560, justify="left").pack(
            anchor="w", pady=(2, 8))
    body = ttk.Frame(outer, style="Card.TFrame", borderwidth=0)
    body.configure(relief="flat")
    body.pack(fill="x")
    return body


def field_label(parent, row: int, text: str) -> None:
    ttk.Label(parent, text=text, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 12))


class SettingsForm:
    """Trzyma zmienne tk powiązane z kopią konfiguracji i buduje sekcje formularza."""

    def __init__(self, master: tk.Misc, data: Dict, sender, sounds):
        self.master = master
        self.data = copy.deepcopy(data)
        self.sender = sender
        self.sounds = sounds
        d, s = self.data["discord"], self.data["sounds"]

        self.device_name = tk.StringVar(value=self.data.get("device_name") or default_device_name())
        self.process_names = tk.StringVar(value=", ".join(self.data.get("process_names") or []))
        self.check_interval = tk.DoubleVar(value=self.data.get("check_interval", 2.0))
        self.grace = tk.DoubleVar(value=self.data.get("logout_grace_seconds", 5.0))
        self.debug = tk.BooleanVar(value=self.data.get("debug", False))
        self.start_minimized = tk.BooleanVar(value=self.data.get("start_minimized", False))

        self.method = tk.StringVar(value=d.get("method", "none"))
        self.webhook_url = tk.StringVar(value=d.get("webhook_url", ""))
        self.bot_token = tk.StringVar(value=d.get("bot_token", ""))
        self.channel_id = tk.StringVar(value=d.get("channel_id", ""))
        self.user_id = tk.StringVar(value=d.get("user_id", ""))
        self.mention_user = tk.BooleanVar(value=d.get("mention_user", True))
        self.notify = {e: tk.BooleanVar(value=d.get("notify_events", {}).get(e, True)) for e in EVENTS}

        self.sound_enabled = tk.BooleanVar(value=s.get("enabled", True))
        self.volume = tk.IntVar(value=s.get("volume", 80))
        self.repeat = tk.BooleanVar(value=s.get("repeat_until_ack", True))
        self.max_alarm = tk.IntVar(value=s.get("max_alarm_seconds", 300))
        self.choices = sound_choices()
        self.sound_spec = {}
        self.sound_file = {}
        for e in EVENTS:
            ev = s.get("events", {}).get(e, {})
            spec = ev.get("sound", NONE_SOUND)
            self.sound_spec[e] = tk.StringVar(value=self.choices.get(spec, self.choices[NONE_SOUND]))
            self.sound_file[e] = tk.StringVar(value=ev.get("file", ""))

        self.test_status = tk.StringVar()
        self._method_frames: Dict[str, Any] = {}
        self._common_frame: Any = None

    # ---------------------------------------------------------------- sekcje
    def build_general(self, parent, advanced: bool = True) -> None:
        body = card(parent, "Nazwa tego urządzenia",
                    "Pojawi się w każdym powiadomieniu na Discordzie — dzięki temu od razu wiesz, "
                    "z którego komputera przyszedł alert (np. „Laptop”, „PC w pokoju”).")
        entry = ttk.Entry(body, textvariable=self.device_name, width=40)
        entry.pack(anchor="w", fill="x")

        body = card(parent, "Gra")
        body.columnconfigure(1, weight=1)
        field_label(body, 0, "Nazwa pliku gry (.exe)")
        ttk.Entry(body, textvariable=self.process_names).grid(row=0, column=1, sticky="ew")
        ttk.Label(body, style="CardHint.TLabel", wraplength=520, justify="left",
                  text="Domyślnie metin2client.exe. Serwer prywatny może mieć inną nazwę — sprawdzisz ją "
                       "w Menedżerze zadań → Szczegóły. Kilka nazw oddziel przecinkami.").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        if not advanced:
            return

        body = card(parent, "Monitorowanie")
        body.columnconfigure(1, weight=1)
        field_label(body, 0, "Sprawdzaj co (sekundy)")
        ttk.Spinbox(body, from_=0.5, to=30, increment=0.5, textvariable=self.check_interval, width=8).grid(
            row=0, column=1, sticky="w")
        field_label(body, 1, "Wylogowanie po braku połączenia (s)")
        ttk.Spinbox(body, from_=1, to=120, increment=1, textvariable=self.grace, width=8).grid(
            row=1, column=1, sticky="w")
        ttk.Label(body, style="CardHint.TLabel", wraplength=520, justify="left",
                  text="Jeśli dostajesz fałszywe alarmy przy chwilowych lagach, zwiększ drugą wartość "
                       "(np. do 15 s).").grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 8))
        ttk.Checkbutton(body, text="Uruchamiaj zminimalizowane", variable=self.start_minimized,
                        style="Card.TCheckbutton").grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(body, text="Szczegółowe logi (do zgłaszania błędów)", variable=self.debug,
                        style="Card.TCheckbutton").grid(row=4, column=0, columnspan=2, sticky="w")

    def build_discord(self, parent) -> None:
        body = card(parent, "Jak wysyłać powiadomienia?")
        for value, label in METHODS:
            ttk.Radiobutton(body, text=label, value=value, variable=self.method, style="Card.TRadiobutton",
                            command=self._update_method).pack(anchor="w", pady=1)
        link = ttk.Label(body, text="→ Instrukcja krok po kroku (otwiera przeglądarkę)",
                         style="Card.TLabel", foreground=theme.ACCENT, cursor="hand2")
        link.pack(anchor="w", pady=(8, 0))
        link.bind("<Button-1>", lambda _e: webbrowser.open(HELP_URL))

        # Webhook
        wh = card(parent, "Webhook",
                  "Discord → Twój serwer → ustawienia kanału → Integracje → Webhooki → Nowy webhook → "
                  "„Kopiuj adres URL webhooka”. Wklej go poniżej.")
        wh.columnconfigure(1, weight=1)
        field_label(wh, 0, "Adres URL webhooka")
        ttk.Entry(wh, textvariable=self.webhook_url).grid(row=0, column=1, sticky="ew")
        self._method_frames["webhook"] = wh.master

        # Bot
        bot = card(parent, "Bot Discord",
                   "Podaj ID kanału albo zostaw puste — wtedy bot napisze do Ciebie prywatnie "
                   "(wymaga ID użytkownika poniżej i wspólnego serwera z botem).")
        bot.columnconfigure(1, weight=1)
        field_label(bot, 0, "Token bota")
        token_entry = ttk.Entry(bot, textvariable=self.bot_token, show="•")
        token_entry.grid(row=0, column=1, sticky="ew")
        show = tk.BooleanVar(value=False)
        ttk.Checkbutton(bot, text="pokaż", variable=show, style="Card.TCheckbutton",
                        command=lambda: token_entry.configure(show="" if show.get() else "•")).grid(
            row=0, column=2, padx=(8, 0))
        field_label(bot, 1, "ID kanału (opcjonalnie)")
        ttk.Entry(bot, textvariable=self.channel_id).grid(row=1, column=1, sticky="ew")
        self._method_frames["bot"] = bot.master

        # Wspólne
        common = card(parent, "Oznaczanie i zdarzenia")
        common.columnconfigure(1, weight=1)
        field_label(common, 0, "Twoje ID użytkownika")
        ttk.Entry(common, textvariable=self.user_id).grid(row=0, column=1, sticky="ew")
        ttk.Label(common, style="CardHint.TLabel", text="Ustawienia Discorda → Zaawansowane → Tryb dewelopera, "
                  "potem prawy klik na siebie → „Kopiuj ID użytkownika”.", wraplength=520,
                  justify="left").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 4))
        ttk.Checkbutton(common, text="Oznaczaj mnie (@) — telefon zadzwoni nawet przy wyciszonym kanale",
                        variable=self.mention_user, style="Card.TCheckbutton").grid(
            row=2, column=0, columnspan=2, sticky="w")
        events = ttk.Frame(common, style="Card.TFrame", borderwidth=0)
        events.configure(relief="flat")
        events.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(events, text="Wysyłaj przy:", style="Card.TLabel").pack(side="left", padx=(0, 8))
        for e in EVENTS:
            ttk.Checkbutton(events, text=EVENT_LABELS[e], variable=self.notify[e],
                            style="Card.TCheckbutton").pack(side="left", padx=(0, 10))
        self._common_frame = common.master

        test = ttk.Frame(common, style="Card.TFrame", borderwidth=0)
        test.configure(relief="flat")
        test.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self.test_button = ttk.Button(test, text="Wyślij wiadomość testową", command=self.send_test)
        self.test_button.pack(side="left")
        self.test_label = ttk.Label(test, textvariable=self.test_status, style="CardMuted.TLabel",
                                    wraplength=380, justify="left")
        self.test_label.pack(side="left", padx=10)
        self._update_method()

    def build_sounds(self, parent) -> None:
        body = card(parent, "Dźwięk alarmu",
                    "M2Watcher odtwarza własne dźwięki (nie systemowe). W mikserze głośności Windows "
                    "widać go jako osobną aplikację, więc możesz ustawić mu głośność niezależnie od gry.")
        body.columnconfigure(1, weight=1)
        ttk.Checkbutton(body, text="Odtwarzaj dźwięki", variable=self.sound_enabled,
                        style="Card.TCheckbutton").grid(row=0, column=0, columnspan=3, sticky="w")
        field_label(body, 1, "Głośność")
        vol_label = ttk.Label(body, style="Card.TLabel", width=5)
        scale = ttk.Scale(body, from_=0, to=100, orient="horizontal",
                          command=lambda v: (self.volume.set(int(float(v))),
                                             vol_label.configure(text=f"{int(float(v))}%")))
        scale.set(self.volume.get())
        scale.grid(row=1, column=1, sticky="ew")
        vol_label.configure(text=f"{self.volume.get()}%")
        vol_label.grid(row=1, column=2, padx=(8, 0))
        ttk.Checkbutton(body, text="Powtarzaj alarm, aż kliknę „Zatrzymaj alarm”", variable=self.repeat,
                        style="Card.TCheckbutton").grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        field_label(body, 3, "Wycisz sam po (s, 0 = nigdy)")
        ttk.Spinbox(body, from_=0, to=3600, increment=30, textvariable=self.max_alarm, width=8).grid(
            row=3, column=1, sticky="w")

        per = card(parent, "Dźwięk dla każdego zdarzenia", "Obsługiwane są pliki .wav.")
        per.columnconfigure(2, weight=1)
        names = list(self.choices.values())
        for row, e in enumerate(EVENTS):
            field_label(per, row, EVENT_LABELS[e])
            combo = ttk.Combobox(per, values=names, textvariable=self.sound_spec[e], state="readonly", width=24)
            combo.grid(row=row, column=1, sticky="w", pady=4)
            file_entry = ttk.Entry(per, textvariable=self.sound_file[e])
            file_entry.grid(row=row, column=2, sticky="ew", padx=(8, 4))
            browse = ttk.Button(per, text="…", width=3, command=lambda ev=e: self._browse(ev))
            browse.grid(row=row, column=3)
            ttk.Button(per, text="Odsłuchaj", command=lambda ev=e: self._preview(ev)).grid(
                row=row, column=4, padx=(4, 0))

            def toggle(_=None, ev=e, fe=file_entry, b=browse):
                custom = self._spec_value(ev) == CUSTOM_SOUND
                fe.configure(state="normal" if custom else "disabled")
                b.configure(state="normal" if custom else "disabled")
            combo.bind("<<ComboboxSelected>>", toggle)
            toggle()

    # ---------------------------------------------------------------- akcje
    def _update_method(self) -> None:
        method = self.method.get()
        for key, frame in self._method_frames.items():
            if key == method:
                frame.pack(fill="x", pady=(0, 12), before=self._common_frame)
            else:
                frame.pack_forget()
        if method == "none":
            self._common_frame.pack_forget()
        elif not self._common_frame.winfo_manager():
            self._common_frame.pack(fill="x", pady=(0, 12))

    def _spec_value(self, event: str) -> str:
        label = self.sound_spec[event].get()
        return next((k for k, v in self.choices.items() if v == label), NONE_SOUND)

    def _browse(self, event: str) -> None:
        path = filedialog.askopenfilename(parent=self.master, title="Wybierz plik dźwiękowy",
                                          filetypes=[("Pliki WAV", "*.wav"), ("Wszystkie pliki", "*.*")])
        if path:
            self.sound_file[event].set(path)

    def _preview(self, event: str) -> None:
        spec = self._spec_value(event)
        if spec == CUSTOM_SOUND:
            problem = validate_wav(self.sound_file[event].get())
            if problem:
                messagebox.showwarning("Dźwięk", problem, parent=self.master)
                return
        if not self.sounds.preview(spec, self.sound_file[event].get(), self.volume.get()):
            if spec != NONE_SOUND:
                messagebox.showwarning("Dźwięk", "Nie udało się odtworzyć dźwięku — szczegóły w logu.",
                                       parent=self.master)

    def send_test(self) -> None:
        cfg = self.collect()["discord"]
        device = self.device_name.get().strip() or default_device_name()
        self.test_button.configure(state="disabled")
        self.test_status.set("Wysyłanie…")
        self.test_label.configure(foreground=theme.MUTED)

        def work():
            ok, msg = self.sender.send_test(device, cfg)
            self.master.after(0, lambda: self._test_done(ok, msg))

        threading.Thread(target=work, name="DiscordTest", daemon=True).start()

    def _test_done(self, ok: bool, msg: str) -> None:
        try:
            self.test_button.configure(state="normal")
            self.test_status.set(("✔ " if ok else "✖ ") + msg)
            self.test_label.configure(foreground=theme.OK if ok else theme.DANGER)
        except tk.TclError:
            pass  # okno zamknięte w trakcie

    # ---------------------------------------------------------------- dane
    def collect(self) -> Dict:
        data = copy.deepcopy(self.data)
        data["device_name"] = self.device_name.get().strip() or default_device_name()
        names = [n.strip() for n in self.process_names.get().split(",") if n.strip()]
        data["process_names"] = names or ["metin2client.exe"]
        data["check_interval"] = _num(self.check_interval, 2.0, 0.5, 30)
        data["logout_grace_seconds"] = _num(self.grace, 5.0, 1, 120)
        data["debug"] = self.debug.get()
        data["start_minimized"] = self.start_minimized.get()
        d = data["discord"]
        d.update(method=self.method.get(), webhook_url=self.webhook_url.get().strip(),
                 bot_token=self.bot_token.get().strip(), channel_id=self.channel_id.get().strip(),
                 user_id=self.user_id.get().strip(), mention_user=self.mention_user.get(),
                 notify_events={e: v.get() for e, v in self.notify.items()})
        s = data["sounds"]
        s.update(enabled=self.sound_enabled.get(), volume=int(self.volume.get()),
                 repeat_until_ack=self.repeat.get(), max_alarm_seconds=int(_num(self.max_alarm, 300, 0, 3600)))
        s["events"] = {e: {"sound": self._spec_value(e), "file": self.sound_file[e].get().strip()}
                       for e in EVENTS}
        return data

    def problems(self, sections=("general", "discord", "sounds")) -> List[str]:
        data = self.collect()
        out = []
        if "discord" in sections:
            out += validate_settings(data["discord"])
        if "sounds" in sections:
            for e in EVENTS:
                ev = data["sounds"]["events"][e]
                if ev["sound"] == CUSTOM_SOUND:
                    problem = validate_wav(ev["file"])
                    if problem:
                        out.append(f"Dźwięk „{EVENT_LABELS[e]}”: {problem}")
        return out


def _num(var: tk.Variable, default: float, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(var.get())))
    except (tk.TclError, ValueError):
        return default


class _Base(tk.Toplevel):
    def __init__(self, master, title: str, data: Dict, sender, sounds, on_save: Callable[[Dict], None]):
        super().__init__(master)
        self.withdraw()
        self.title(title)
        self.configure(bg=theme.BG)
        self.on_save = on_save
        self.form = SettingsForm(self, data, sender, sounds)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.minsize(640, 520)

    def show(self, width=700, height=680) -> None:
        self.update_idletasks()
        master = self.master
        x = master.winfo_rootx() + max(0, (master.winfo_width() - width) // 2)
        y = master.winfo_rooty() + max(0, (master.winfo_height() - height) // 3)
        if not master.winfo_viewable():
            x = (self.winfo_screenwidth() - width) // 2
            y = (self.winfo_screenheight() - height) // 3
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
        self.deiconify()
        self.lift()
        self.focus_force()
        if master.winfo_viewable():
            self.transient(master)  # type: ignore[arg-type]
        self.grab_set()

    def cancel(self) -> None:
        self.form.sounds.stop()
        self.grab_release()
        self.destroy()


def scrollable(parent) -> ttk.Frame:
    """Ramka z pionowym paskiem przewijania (kółko myszy działa)."""
    canvas = tk.Canvas(parent, bg=theme.BG, highlightthickness=0, borderwidth=0)
    bar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas, padding=(20, 16, 20, 4))
    window = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
    canvas.configure(yscrollcommand=bar.set)
    canvas.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")

    def wheel(event):
        if canvas.winfo_exists():
            delta = -1 if (getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4) else 1
            canvas.yview_scroll(delta * 3, "units")

    def bind(_e):
        canvas.bind_all("<MouseWheel>", wheel)
        canvas.bind_all("<Button-4>", wheel)
        canvas.bind_all("<Button-5>", wheel)

    def unbind(_e):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    canvas.bind("<Enter>", bind)
    canvas.bind("<Leave>", unbind)
    return inner


class SettingsWindow(_Base):
    def __init__(self, master, data, sender, sounds, on_save, tab: str = "general"):
        super().__init__(master, "M2Watcher — Ustawienia", data, sender, sounds, on_save)
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=(12, 0))
        tabs = {}
        for key, label, builder in (("general", "  Ogólne  ", self.form.build_general),
                                    ("discord", "  Discord  ", self.form.build_discord),
                                    ("sounds", "  Dźwięki  ", self.form.build_sounds)):
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=label)
            builder(scrollable(frame))
            tabs[key] = frame
        notebook.select(tabs.get(tab, tabs["general"]))

        buttons = ttk.Frame(self, padding=12)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Zapisz", style="Accent.TButton", command=self.save).pack(side="right")
        ttk.Button(buttons, text="Anuluj", command=self.cancel).pack(side="right", padx=8)
        self.bind("<Escape>", lambda _e: self.cancel())
        self.show()

    def save(self) -> None:
        problems = self.form.problems()
        if problems:
            messagebox.showwarning("Popraw ustawienia", "\n\n".join(problems), parent=self)
            return
        data = self.form.collect()
        data["setup_completed"] = True
        self.on_save(data)
        self.cancel()


class SetupWizard(_Base):
    """Kreator pierwszego uruchomienia: Witaj → Discord → Dźwięki → Gotowe."""

    STEPS = ("Witaj", "Discord", "Dźwięki", "Gotowe")

    def __init__(self, master, data, sender, sounds, on_save, on_cancel: Optional[Callable[[], None]] = None):
        super().__init__(master, "M2Watcher — Pierwsze uruchomienie", data, sender, sounds, on_save)
        self.on_cancel = on_cancel
        if self.form.method.get() == "none":
            self.form.method.set("webhook")  # zalecana, najprostsza opcja
        self.step = 0

        header = ttk.Frame(self, padding=(20, 16, 20, 0))
        header.pack(fill="x")
        ttk.Label(header, text="Konfiguracja M2Watcher", style="Title.TLabel").pack(anchor="w")
        self.steps_label = ttk.Label(header, style="Muted.TLabel")
        self.steps_label.pack(anchor="w", pady=(2, 0))

        self.pages = []
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        for builder in (self._page_welcome, self.form.build_discord, self.form.build_sounds, self._page_done):
            page = ttk.Frame(container)
            builder(scrollable(page))
            self.pages.append(page)

        nav = ttk.Frame(self, padding=12)
        nav.pack(fill="x")
        self.next_btn = ttk.Button(nav, style="Accent.TButton", command=self.next)
        self.next_btn.pack(side="right")
        self.back_btn = ttk.Button(nav, text="Wstecz", command=self.back)
        self.back_btn.pack(side="right", padx=8)
        ttk.Label(nav, text="Wszystko zmienisz później w Ustawieniach.", style="Hint.TLabel").pack(side="left")
        self._render()
        self.show()

    def _page_welcome(self, parent) -> None:
        ttk.Label(parent, wraplength=600, justify="left", text=(
            "M2Watcher pilnuje Twoich klientów Metin2 i daje znać, gdy któryś się wyloguje "
            "albo zamknie — dźwiękiem na komputerze i wiadomością na Discordzie.\n\n"
            "Konfiguracja zajmie 2 minuty."
        )).pack(anchor="w", pady=(0, 12))
        self.form.build_general(parent, advanced=False)

    def _page_done(self, parent) -> None:
        body = card(parent, "Gotowe!")
        self.summary = ttk.Label(body, style="Card.TLabel", justify="left", wraplength=560)
        self.summary.pack(anchor="w")
        ttk.Label(body, style="CardHint.TLabel", wraplength=560, justify="left", text=(
            "\nPo kliknięciu „Zakończ” monitorowanie ruszy od razu. Zostaw M2Watcher uruchomiony — "
            "możesz go zminimalizować. Gdy przyjdzie alarm, kliknij „Zatrzymaj alarm” w oknie aplikacji."
        )).pack(anchor="w")

    def _render(self) -> None:
        for i, page in enumerate(self.pages):
            if i == self.step:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()
        self.steps_label.configure(text="   ›   ".join(
            f"[{i + 1}. {name}]" if i == self.step else f"{i + 1}. {name}" for i, name in enumerate(self.STEPS)))
        self.back_btn.configure(state="normal" if self.step else "disabled")
        last = self.step == len(self.pages) - 1
        self.next_btn.configure(text="Zakończ" if last else "Dalej")
        if last:
            data = self.form.collect()
            method = {"webhook": "webhook", "bot": "bot", "none": "wyłączone"}[data["discord"]["method"]]
            sound = "włączone" if data["sounds"]["enabled"] else "wyłączone"
            self.summary.configure(text=(
                f"Urządzenie:  {data['device_name']}\n"
                f"Discord:  {method}\n"
                f"Dźwięki:  {sound} (głośność {data['sounds']['volume']}%)"))

    def next(self) -> None:
        section = {1: ("discord",), 2: ("sounds",)}.get(self.step, ())
        problems = self.form.problems(section) if section else []
        if problems:
            messagebox.showwarning("Popraw ustawienia", "\n\n".join(problems), parent=self)
            return
        if self.step == 1 and self.form.method.get() == "none":
            if not messagebox.askyesno("Bez Discorda?", "Nie ustawiono powiadomień Discord — dostaniesz tylko "
                                       "alarm dźwiękowy na tym komputerze. Kontynuować?", parent=self):
                return
        if self.step < len(self.pages) - 1:
            self.step += 1
            self._render()
            return
        data = self.form.collect()
        data["setup_completed"] = True
        self.on_save(data)
        super().cancel()

    def back(self) -> None:
        if self.step:
            self.step -= 1
            self._render()

    def cancel(self) -> None:
        if messagebox.askyesno("Przerwać konfigurację?", "Aplikacja uruchomi się z ustawieniami domyślnymi "
                               "(bez Discorda). Kreator pokaże się ponownie przy następnym starcie.",
                               parent=self):
            super().cancel()
            if self.on_cancel:
                self.on_cancel()
