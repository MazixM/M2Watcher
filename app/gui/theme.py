"""Wygląd aplikacji: kolory, czcionki i style ttk."""
import platform
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

BG = "#F3F4F7"
CARD = "#FFFFFF"
BORDER = "#DDE1E8"
TEXT = "#1F2330"
MUTED = "#6B7280"
ACCENT = "#5865F2"
ACCENT_HOVER = "#4752C4"
OK = "#2E9E5B"
WARN = "#D98E04"
DANGER = "#D93F3F"
DANGER_BG = "#FDECEC"
OK_BG = "#E8F6EE"
WARN_BG = "#FFF5E0"

FAMILY = "Segoe UI" if platform.system() == "Windows" else "DejaVu Sans"


def apply(root: tk.Tk) -> None:
    available = set(tkfont.families(root))
    family = FAMILY if FAMILY in available else tkfont.nametofont("TkDefaultFont").actual("family")

    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(name).configure(family=family, size=10)

    root.configure(bg=BG)
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=BG, foreground=TEXT, font=(family, 10), bordercolor=BORDER,
                    focuscolor=ACCENT, lightcolor=BORDER, darkcolor=BORDER)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD, relief="solid", borderwidth=1)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Card.TLabel", background=CARD)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("CardMuted.TLabel", background=CARD, foreground=MUTED)
    style.configure("Title.TLabel", font=(family, 18, "bold"))
    style.configure("H2.TLabel", font=(family, 12, "bold"))
    style.configure("CardH2.TLabel", background=CARD, font=(family, 12, "bold"))
    style.configure("CardValue.TLabel", background=CARD, font=(family, 11, "bold"))
    style.configure("Error.TLabel", foreground=DANGER)
    style.configure("Hint.TLabel", foreground=MUTED, font=(family, 9))
    style.configure("CardHint.TLabel", background=CARD, foreground=MUTED, font=(family, 9))

    style.configure("TButton", padding=(12, 6), background=CARD, borderwidth=1)
    style.map("TButton", background=[("active", "#E9ECF2")])
    style.configure("Accent.TButton", background=ACCENT, foreground="#FFFFFF", borderwidth=0)
    style.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", "#A5ABF5")],
              foreground=[("disabled", "#F0F0F0")])
    style.configure("Danger.TButton", background=DANGER, foreground="#FFFFFF", borderwidth=0,
                    font=(family, 10, "bold"), padding=(16, 8))
    style.map("Danger.TButton", background=[("active", "#B73232")])

    for widget in ("TCheckbutton", "TRadiobutton"):
        style.configure(widget, background=BG)
        style.configure(f"Card.{widget}", background=CARD)
        style.map(f"Card.{widget}", background=[("active", CARD)])
    style.configure("TEntry", padding=5, fieldbackground=CARD)
    style.configure("TCombobox", padding=4)
    style.configure("TSpinbox", padding=4)
    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", padding=(14, 6))
    style.map("TNotebook.Tab", background=[("selected", CARD)])
    style.configure("TLabelframe", background=CARD)
    style.configure("TLabelframe.Label", background=CARD, font=(family, 10, "bold"))
    style.configure("Treeview", rowheight=26, background=CARD, fieldbackground=CARD, borderwidth=0)
    style.configure("Treeview.Heading", font=(family, 10, "bold"), background="#ECEFF4", relief="flat")
    style.configure("Horizontal.TScale", background=CARD)

    root.option_add("*TCombobox*Listbox.font", (family, 10))


def make_icon(root: tk.Tk) -> tk.PhotoImage:
    """Rysuje prostą ikonę (oko w kole) — bez dodatkowych plików."""
    size = 32
    img = tk.PhotoImage(width=size, height=size)
    c = (size - 1) / 2
    for y in range(size):
        row = []
        for x in range(size):
            d = ((x - c) ** 2 + (y - c) ** 2) ** 0.5
            if d <= 15:
                eye = ((x - c) / 13) ** 2 + ((y - c) / 7) ** 2
                if d <= 4:
                    row.append("#1F2330")
                elif eye <= 1:
                    row.append("#FFFFFF")
                else:
                    row.append(ACCENT)
            else:
                row.append("")
        # puste piksele: zostają przezroczyste
        for x, color in enumerate(row):
            if color:
                img.put(color, (x, y))
    return img
