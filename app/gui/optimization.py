"""Zakładka „Optymalizacja” — limit FPS, rdzenie CPU i priorytet dla wszystkich lub wybranych klientów."""
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional

from gui import theme
from optimizer import (CORES_LIST, CORES_NONE, CORES_SPREAD, MAX_LIMIT_FPS, MIN_FPS, PRIORITIES, PRIORITY_LABELS,
                       PRIORITY_NORMAL, SOURCE_DEFAULT, SOURCE_DISABLED, SOURCE_OFF, SOURCE_OVERRIDE, CpuTopology,
                       Optimizer, Profile, format_cpus, profile_from_dict)

log = logging.getLogger(__name__)

CORE_MODE_LABELS = {
    CORES_NONE: "Bez zmian (decyduje Windows)",
    CORES_LIST: "Tylko wybrane rdzenie",
    CORES_SPREAD: "Rozłóż klienty — każdy na innym rdzeniu",
}
SOURCE_LABELS = {
    SOURCE_DEFAULT: "Wspólne",
    SOURCE_OVERRIDE: "Własne",
    SOURCE_OFF: "Wyłączone",
    SOURCE_DISABLED: "—",
}
CPU_COLUMNS = 8


class ProfileEditor:
    """Formularz jednego zestawu ustawień (Profile) — używany w oknie dialogowym."""

    def __init__(self, parent: tk.Misc, topology: CpuTopology, profile: Profile):
        self.topology = topology
        self.fps = tk.StringVar(value=str(profile.fps_limit))
        self.background_only = tk.BooleanVar(value=profile.fps_background_only)
        self.mode = tk.StringVar(value=CORE_MODE_LABELS[profile.cores_mode])
        self.priority = tk.StringVar(value=PRIORITY_LABELS[profile.background_priority])
        cpus = topology.logical_cpus
        self.cpu_vars = {c: tk.BooleanVar(value=(c in profile.cores) if profile.cores else True) for c in cpus}

        fps_card = _card(parent, "Limit FPS",
                         "Klient Metin2 ma własny limit 60 FPS. Niższy limit oszczędza procesor i kartę "
                         "graficzną. Działa w przybliżeniu: klient jest na ułamki sekundy wstrzymywany, "
                         "więc ograniczonego okna nie używaj do gry.")
        row = _flat(fps_card)
        row.pack(fill="x")
        ttk.Label(row, text="Maksymalnie", style="Card.TLabel").pack(side="left")
        ttk.Spinbox(row, from_=0, to=MAX_LIMIT_FPS, textvariable=self.fps, width=5).pack(side="left", padx=8)
        ttk.Label(row, text=f"FPS   (0 = bez limitu, od {MIN_FPS} do {MAX_LIMIT_FPS})",
                  style="CardMuted.TLabel").pack(side="left")
        ttk.Checkbutton(fps_card, text="Tylko gdy okno klienta jest w tle (zalecane: okno, w które klikniesz, "
                                       "od razu działa płynnie)",
                        variable=self.background_only, style="Card.TCheckbutton").pack(anchor="w", pady=(8, 0))

        cpu_card = _card(parent, "Rdzenie procesora",
                         f"Twój procesor: {topology.summary()}."
                         + (" P = rdzenie wydajne, E = energooszczędne." if topology.hybrid else "")
                         + " „Rozłóż” daje każdemu klientowi inny rdzeń fizyczny z zaznaczonych.")
        combo = ttk.Combobox(cpu_card, textvariable=self.mode, state="readonly", width=42,
                             values=[CORE_MODE_LABELS[m] for m in (CORES_NONE, CORES_LIST, CORES_SPREAD)])
        combo.pack(anchor="w")
        combo.bind("<<ComboboxSelected>>", lambda _e: self._update_cpu_state())
        grid = _flat(cpu_card)
        grid.pack(anchor="w", pady=(8, 0))
        self.cpu_checks: List[ttk.Checkbutton] = []
        for i, cpu in enumerate(cpus):
            kind = topology.cpu_kind(cpu)
            cb = ttk.Checkbutton(grid, text=f"{cpu}{' ' + kind if kind else ''}", variable=self.cpu_vars[cpu],
                                 style="Card.TCheckbutton", width=6)
            cb.grid(row=i // CPU_COLUMNS, column=i % CPU_COLUMNS, sticky="w", padx=(0, 4), pady=1)
            self.cpu_checks.append(cb)
        buttons = _flat(cpu_card)
        buttons.pack(anchor="w", pady=(6, 0))
        self.cpu_buttons = [
            ttk.Button(buttons, text="Zaznacz wszystkie", command=lambda: self._select(lambda c: True)),
            ttk.Button(buttons, text="Bez rdzenia 0 (zostaw dla systemu)",
                       command=lambda: self._select(lambda c: c not in topology.slots()[0])),
        ]
        if topology.hybrid:
            self.cpu_buttons.append(ttk.Button(buttons, text="Tylko rdzenie E",
                                               command=lambda: self._select(lambda c: topology.cpu_kind(c) == "E")))
        for b in self.cpu_buttons:
            b.pack(side="left", padx=(0, 6))

        prio_card = _card(parent, "Priorytet klientów w tle",
                          "Klient, którego okno jest aktywne, zawsze ma swój zwykły priorytet. Niższy priorytet "
                          "pozostałych sprawia, że przy pełnym obciążeniu procesora to one ustępują.")
        ttk.Combobox(prio_card, textvariable=self.priority, state="readonly", width=30,
                     values=[PRIORITY_LABELS[p] for p in PRIORITIES]).pack(anchor="w")
        self._update_cpu_state()

    def _select(self, predicate: Callable[[int], bool]) -> None:
        for cpu, var in self.cpu_vars.items():
            var.set(bool(predicate(cpu)))

    def _mode_value(self) -> str:
        return next(m for m, label in CORE_MODE_LABELS.items() if label == self.mode.get())

    def _update_cpu_state(self) -> None:
        state = ["!disabled"] if self._mode_value() != CORES_NONE else ["disabled"]
        for widget in self.cpu_checks + self.cpu_buttons:
            widget.state(state)

    def get(self) -> Profile:
        """Zwraca ustawienia albo rzuca ValueError z komunikatem dla użytkownika."""
        try:
            fps = int(float(self.fps.get().strip() or 0))
        except ValueError:
            raise ValueError("Limit FPS musi być liczbą (0 = bez limitu).")
        if fps and not MIN_FPS <= fps <= MAX_LIMIT_FPS:
            raise ValueError(f"Limit FPS musi mieścić się między {MIN_FPS} a {MAX_LIMIT_FPS} (albo 0 = bez limitu).")
        mode = self._mode_value()
        cores = sorted(c for c, v in self.cpu_vars.items() if v.get())
        if mode != CORES_NONE and not cores:
            raise ValueError("Zaznacz co najmniej jeden rdzeń procesora.")
        if len(cores) == len(self.cpu_vars):
            cores = []  # wszystkie = bez ograniczenia puli (działa też po zmianie procesora)
        priority = next(p for p, label in PRIORITY_LABELS.items() if label == self.priority.get())
        return profile_from_dict({"fps_limit": fps, "fps_background_only": self.background_only.get(),
                                  "cores_mode": mode, "cores": cores if mode != CORES_NONE else [],
                                  "background_priority": priority})


def _flat(parent: tk.Misc) -> ttk.Frame:
    """Ramka w tle karty, bez własnego obramowania."""
    frame = ttk.Frame(parent, style="Card.TFrame", borderwidth=0)
    frame.configure(relief="flat")
    return frame


def _card(parent: tk.Misc, title: str, hint: str = "") -> ttk.Frame:
    outer = ttk.Frame(parent, style="Card.TFrame", padding=14)
    outer.pack(fill="x", pady=(0, 10))
    ttk.Label(outer, text=title, style="CardH2.TLabel").pack(anchor="w")
    if hint:
        ttk.Label(outer, text=hint, style="CardHint.TLabel", wraplength=560, justify="left").pack(
            anchor="w", pady=(2, 8))
    body = _flat(outer)
    body.pack(fill="x")
    return body


class ProfileDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, title: str, subtitle: str, topology: CpuTopology, profile: Profile,
                 on_save: Callable[[Profile], None]):
        super().__init__(master)
        self.withdraw()
        self.title(title)
        self.configure(bg=theme.BG)
        self.on_save = on_save
        body = ttk.Frame(self, padding=(18, 14, 18, 0))
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=subtitle, style="Muted.TLabel", wraplength=600, justify="left").pack(
            anchor="w", pady=(0, 10))
        self.editor = ProfileEditor(body, topology, profile)
        footer = ttk.Frame(self, padding=(18, 4, 18, 14))
        footer.pack(fill="x")
        ttk.Button(footer, text="Zapisz", style="Accent.TButton", command=self.save).pack(side="right")
        ttk.Button(footer, text="Anuluj", command=self.close).pack(side="right", padx=8)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _e: self.close())
        self.update_idletasks()
        self.geometry(f"+{master.winfo_rootx() + 60}+{max(0, master.winfo_rooty() + 30)}")
        self.deiconify()
        try:
            self.transient(master)  # type: ignore[arg-type]
        except tk.TclError:
            pass
        self.grab_set()

    def save(self) -> None:
        try:
            profile = self.editor.get()
        except ValueError as e:
            messagebox.showwarning("Optymalizacja", str(e), parent=self)
            return
        self.close()
        self.on_save(profile)

    def close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


class OptimizationTab(ttk.Frame):
    def __init__(self, master: tk.Misc, optimizer: Optimizer, get_settings: Callable[[], Dict],
                 save_settings: Callable[[Dict], None], get_clients: Callable[[], list]):
        super().__init__(master, padding=(0, 10, 0, 0))
        self.optimizer = optimizer
        self.get_settings = get_settings
        self.save_settings = save_settings
        self.get_clients = get_clients
        self.enabled = tk.BooleanVar(value=bool(get_settings().get("enabled", False)))
        self._build()
        self.refresh()

    # ---------------------------------------------------------------- układ
    def _build(self) -> None:
        top = ttk.Frame(self, style="Card.TFrame", padding=(14, 10))
        top.pack(fill="x")
        head = _flat(top)
        head.pack(fill="x")
        self.enable_check = ttk.Checkbutton(head, text="Włącz optymalizację klientów", variable=self.enabled,
                                            style="Card.TCheckbutton", command=self._toggle)
        self.enable_check.pack(side="left")
        self.status = ttk.Label(head, style="CardValue.TLabel")
        self.status.pack(side="right")
        ttk.Label(top, style="CardHint.TLabel", wraplength=840, justify="left",
                  text="Przy wielu klientach: niższy limit FPS i priorytet dla okien w tle oraz przypisanie "
                       "klientów do rdzeni procesora. Korzysta tylko z funkcji Windows (jak Menedżer zadań), "
                       "nie zmienia plików gry ani jej pamięci. Po wyłączeniu klienty wracają do "
                       "pierwotnych ustawień.").pack(anchor="w", pady=(4, 0))
        self.problem = ttk.Label(top, style="CardHint.TLabel", foreground=theme.DANGER, wraplength=840,
                                 justify="left")

        default = ttk.Frame(self, style="Card.TFrame", padding=(14, 10))
        default.pack(fill="x", pady=(10, 0))
        ttk.Label(default, text="DLA WSZYSTKICH KLIENTÓW", style="CardHint.TLabel").pack(anchor="w")
        row = _flat(default)
        row.pack(fill="x")
        self.default_label = ttk.Label(row, style="CardValue.TLabel", wraplength=640, justify="left")
        self.default_label.pack(side="left", anchor="w")
        ttk.Button(row, text="Zmień…", command=self.edit_default).pack(side="right")

        head = ttk.Frame(self)
        head.pack(fill="x", pady=(12, 6))
        ttk.Label(head, text="Klienci", style="H2.TLabel").pack(side="left")
        ttk.Label(head, text="Zaznacz kilka z Ctrl lub Shift. Własne ustawienia obowiązują do zamknięcia klienta.",
                  style="Hint.TLabel").pack(side="left", padx=10)

        actions = ttk.Frame(self)
        actions.pack(side="bottom", fill="x", pady=(8, 0))
        self.action_buttons = [
            ttk.Button(actions, text="Własne ustawienia dla zaznaczonych…", command=self.edit_selected),
            ttk.Button(actions, text="Wyłącz dla zaznaczonych", command=self.disable_selected),
            ttk.Button(actions, text="Przywróć wspólne", command=self.reset_selected),
        ]
        for i, b in enumerate(self.action_buttons):
            b.pack(side="left", padx=(0 if i == 0 else 8, 0))

        frame = ttk.Frame(self, style="Card.TFrame", padding=1)
        frame.pack(fill="both", expand=True)
        cols = ("title", "pid", "source", "fps", "cores", "priority", "note")
        self.table = ttk.Treeview(frame, columns=cols, show="headings", height=5, selectmode="extended")
        for col, label, width, anchor, stretch in (
                ("title", "Okno", 180, "w", True), ("pid", "PID", 64, "center", False),
                ("source", "Ustawienia", 90, "center", False), ("fps", "Limit FPS", 90, "center", False),
                ("cores", "Rdzenie", 100, "center", False), ("priority", "Priorytet", 130, "center", False),
                ("note", "Uwagi", 200, "w", True)):
            self.table.heading(col, text=label, anchor=anchor)  # type: ignore[arg-type]
            self.table.column(col, width=width, anchor=anchor, stretch=stretch)  # type: ignore[arg-type]
        self.table.tag_configure("error", foreground=theme.DANGER)
        self.table.tag_configure("off", foreground=theme.MUTED)
        self.table.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", lambda _e: self._update_buttons())
        self.empty = ttk.Label(frame, style="CardMuted.TLabel", justify="center",
                               text="Brak klientów. Uruchom grę — pojawi się tutaj automatycznie.")

        if not self.optimizer.available:
            self.enable_check.state(["disabled"])
            self.problem.configure(text="Optymalizacja działa tylko na Windowsie.")
            self.problem.pack(anchor="w", pady=(4, 0))
        self._update_buttons()

    # ---------------------------------------------------------------- dane
    def _settings(self) -> Dict:
        return self.get_settings() or {}

    def _save(self, **changes) -> None:
        data = self._settings()
        data.update(changes)
        self.save_settings(data)
        self.refresh()

    def _toggle(self) -> None:
        self._save(enabled=bool(self.enabled.get()))

    def _selected_pids(self) -> List[int]:
        return [int(iid) for iid in self.table.selection()]

    def _update_buttons(self) -> None:
        state = ["!disabled"] if self.table.selection() and self.optimizer.available else ["disabled"]
        for b in self.action_buttons:
            b.state(state)

    # ---------------------------------------------------------------- akcje
    def edit_default(self) -> None:
        profile = profile_from_dict(self._settings().get("default"))

        def saved(p: Profile) -> None:
            self._save(default=p.to_dict())
            if not self.enabled.get() and not p.is_noop and self.optimizer.available:
                if messagebox.askyesno("Optymalizacja", "Zapisano. Włączyć optymalizację teraz?", parent=self):
                    self.enabled.set(True)
                    self._toggle()

        ProfileDialog(self.winfo_toplevel(), "Ustawienia dla wszystkich klientów",
                      "Obowiązują każdego klienta, który nie ma własnych ustawień — także uruchomionego później.",
                      self.optimizer.topology, profile, saved)

    def edit_selected(self) -> None:
        pids = self._selected_pids()
        if not pids:
            return
        has, current = self.optimizer.override_of(pids[0])
        profile = current if has and current else profile_from_dict(self._settings().get("default"))

        def saved(p: Profile) -> None:
            self.optimizer.set_override(pids, p)
            if not self.enabled.get() and self.optimizer.available:
                self.enabled.set(True)
                self._toggle()
            self.refresh()

        ProfileDialog(self.winfo_toplevel(), "Własne ustawienia klientów",
                      f"Dotyczy zaznaczonych klientów (PID {', '.join(map(str, pids))}) do ich zamknięcia. "
                      "Nowo uruchomione klienty dostaną ustawienia wspólne.",
                      self.optimizer.topology, profile, saved)

    def disable_selected(self) -> None:
        self.optimizer.set_override(self._selected_pids(), None)
        self.refresh()

    def reset_selected(self) -> None:
        self.optimizer.clear_override(self._selected_pids())
        self.refresh()

    # ---------------------------------------------------------------- odświeżanie (co sekundę)
    def refresh(self) -> None:
        settings = self._settings()
        enabled = bool(settings.get("enabled", False)) and self.optimizer.available
        if self.enabled.get() != bool(settings.get("enabled", False)):
            self.enabled.set(bool(settings.get("enabled", False)))
        summary = profile_from_dict(settings.get("default")).describe()
        self.default_label.configure(text=summary[:1].upper() + summary[1:])

        states = self.optimizer.states()
        clients = self.get_clients()
        seen = set()
        errors = 0
        limited = 0
        for cl in clients:
            iid = str(cl.pid)
            seen.add(iid)
            st = states.get(cl.pid)
            if st is None or not enabled:
                values = (cl.window_title, cl.pid, SOURCE_LABELS[SOURCE_DISABLED], "—", "—", "—", "")
                tag = "off"
            else:
                note = st.error or ("okno aktywne" if st.foreground else "")
                fps = f"{st.fps} FPS" if st.fps else ("pełne" if st.profile.fps_limit and st.foreground else "—")
                cores = format_cpus(st.affinity) if st.affinity else "wszystkie"
                prio = PRIORITY_LABELS[st.priority] if st.priority != PRIORITY_NORMAL else "zwykły"
                values = (cl.window_title, cl.pid, SOURCE_LABELS[st.source], fps, cores, prio, note)
                tag = "error" if st.error else ("off" if st.source == SOURCE_OFF else "")
                errors += bool(st.error)
                limited += bool(st.fps or st.affinity or st.priority != PRIORITY_NORMAL)
            if self.table.exists(iid):
                self.table.item(iid, values=values, tags=(tag,))
            else:
                self.table.insert("", "end", iid=iid, values=values, tags=(tag,))
        for iid in self.table.get_children():
            if iid not in seen:
                self.table.delete(iid)
        if clients:
            self.empty.place_forget()
        else:
            self.empty.place(relx=0.5, rely=0.55, anchor="center")
        self._update_buttons()

        if not self.optimizer.available:
            self.status.configure(text="Niedostępne", foreground=theme.MUTED)
        elif not enabled:
            self.status.configure(text="Wyłączona", foreground=theme.MUTED)
        else:
            self.status.configure(text=f"Aktywna • {limited} z {len(clients)} klientów",
                                  foreground=theme.WARN if errors else theme.OK)
        if self.optimizer.available:
            if errors:
                self.problem.configure(text="Części klientów nie da się zmienić. Jeśli w Uwagach widzisz "
                                            "„brak uprawnień”, uruchom M2Watcher jako administrator "
                                            "(gra działa z wyższymi uprawnieniami).")
                self.problem.pack(anchor="w", pady=(4, 0))
            else:
                self.problem.pack_forget()
