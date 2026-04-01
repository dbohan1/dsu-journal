"""
MessageLog — A 140-character message logger with timestamp persistence.
Messages are saved to messages.json, sorted by date, for easy consumption
by other applications.

Styled after the journal from The Elder Scrolls III: Morrowind.
"""

import ctypes
import ctypes.wintypes
import json
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
    ICON_PATH = Path(sys._MEIPASS) / "messagelog.ico"
else:
    BASE_DIR = Path(__file__).parent
    ICON_PATH = BASE_DIR / "messagelog.ico"

DATA_FILE   = BASE_DIR / "messages.json"
SOUND_OPEN  = BASE_DIR / "sound" / "book_open.mp3"
SOUND_CLOSE = BASE_DIR / "sound" / "book_close.mp3"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CHARS = 140
ENTRIES_PER_PAGE = 5
FOCUSED_ALPHA = 1.0
UNFOCUSED_ALPHA = 0.65

# Global hotkey: Ctrl+`
_MOD_CTRL    = 0x0002
_VK_BACKTICK = 0x00C0   # VK_OEM_3
_WM_HOTKEY   = 0x0312
_HOTKEY_ID   = 1

# Morrowind Journal palette
MW = {
    "leather":      "#1a0e05",
    "leather_lt":   "#2e1a0c",
    "gilt":         "#6e5a28",
    "parchment":    "#c4a464",
    "parchment_lt": "#d0b474",
    "ink":          "#261408",
    "ink_date":     "#4e3018",
    "ink_faded":    "#6e4e30",
    "separator":    "#8e6e40",
    "counter_ok":   "#4e3018",
    "counter_warn": "#8b1a1a",
}

FONT_TITLE   = ("Palatino Linotype", 20)
FONT_DATE    = ("Palatino Linotype", 9, "italic")
FONT_BODY    = ("Palatino Linotype", 10)
FONT_UI      = ("Palatino Linotype", 9)
FONT_NAV     = ("Palatino Linotype", 10)
FONT_COUNTER = ("Palatino Linotype", 9)
FONT_STATUS  = ("Palatino Linotype", 8, "italic")


# ---------------------------------------------------------------------------
# Data layer
# ---------------------------------------------------------------------------

def load_messages() -> list:
    if not DATA_FILE.exists():
        return []
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_message(text: str) -> dict:
    messages = load_messages()
    now = datetime.now()
    entry = {
        "id": now.strftime("%Y%m%d%H%M%S%f"),
        "date": now.date().isoformat(),
        "timestamp": now.isoformat(),
        "message": text,
    }
    messages.append(entry)
    messages.sort(key=lambda m: m["timestamp"])
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)
    return entry


def delete_message(msg_id: str) -> None:
    messages = load_messages()
    messages = [m for m in messages if m["id"] != msg_id]
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ordinal(n: int) -> str:
    """Return day with ordinal suffix: 1st, 2nd, 3rd, etc."""
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{['th','st','nd','rd','th','th','th','th','th','th'][n % 10]}"


def format_journal_date(iso_ts: str) -> str:
    """Format as '23rd of March, 2026 — 09:46'."""
    dt = datetime.fromisoformat(iso_ts)
    return f"{_ordinal(dt.day)} of {dt.strftime('%B')}, {dt.year} — {dt.strftime('%H:%M')}"


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class MessageLogApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self._current_page = 0
        self._displayed = []
        self._visible = True

        root.overrideredirect(True)
        root.configure(bg=MW["leather"])
        root.attributes("-alpha", FOCUSED_ALPHA)
        root.attributes("-topmost", True)

        if ICON_PATH.exists():
            try:
                root.iconbitmap(str(ICON_PATH))
            except Exception:
                pass

        self._build_ui()
        self._refresh_feed()
        self._preload_sounds()
        self._register_hotkey()

        root.bind("<FocusIn>",  self._on_focus_in)
        root.bind("<FocusOut>", self._on_focus_out)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Nested frames simulate a leather-bound book border
        leather = tk.Frame(self.root, bg=MW["leather"])
        leather.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        bevel = tk.Frame(leather, bg=MW["leather_lt"])
        bevel.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        gilt = tk.Frame(bevel, bg=MW["gilt"])
        gilt.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        page = tk.Frame(gilt, bg=MW["parchment"])
        page.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # ── Window controls (subtle, top-right) ──────────────────────
        ctrl = tk.Frame(page, bg=MW["parchment"])
        ctrl.pack(fill=tk.X, padx=10, pady=(4, 0))

        for sym, cmd in [("\u2715", self._close)]:
            tk.Button(
                ctrl, text=sym,
                font=("Palatino Linotype", 7),
                fg=MW["ink_faded"], bg=MW["parchment"],
                activebackground=MW["parchment_lt"],
                activeforeground=MW["ink"],
                relief=tk.FLAT, bd=0, cursor="arrow",
                command=cmd,
            ).pack(side=tk.RIGHT, padx=1)

        # ── "Journal" title ──────────────────────────────────────────
        title_area = tk.Frame(page, bg=MW["parchment"])
        title_area.pack(fill=tk.X, padx=20)

        title_lbl = tk.Label(
            title_area, text="Journal",
            font=FONT_TITLE, fg=MW["ink"], bg=MW["parchment"],
        )
        title_lbl.pack(anchor="center")

        self._make_sep(page)

        # ── Journal entry rows ───────────────────────────────────────
        content = tk.Frame(page, bg=MW["parchment"])
        content.pack(fill=tk.BOTH, expand=True, padx=28, pady=(4, 0))

        self._entry_widgets = []
        for i in range(ENTRIES_PER_PAGE):
            ef = tk.Frame(content, bg=MW["parchment"])
            ef.pack(fill=tk.X, pady=(0, 8))
            ef.columnconfigure(0, weight=1)

            dl = tk.Label(
                ef, text="", font=FONT_DATE,
                fg=MW["ink_date"], bg=MW["parchment"], anchor="w",
            )
            dl.grid(row=0, column=0, sticky="w")

            ml = tk.Label(
                ef, text="", font=FONT_BODY,
                fg=MW["ink"], bg=MW["parchment"],
                anchor="w", justify=tk.LEFT, wraplength=0,
            )
            ml.grid(row=1, column=0, sticky="ew", padx=(10, 0))

            db = tk.Button(
                ef, text="[remove]",
                font=("Palatino Linotype", 7, "italic"),
                fg=MW["ink_faded"], bg=MW["parchment"],
                activebackground=MW["parchment"],
                activeforeground=MW["ink"],
                relief=tk.FLAT, bd=0, cursor="arrow",
                command=lambda idx=i: self._delete_row(idx),
            )
            db.grid(row=0, column=1, rowspan=2, sticky="ne", padx=(4, 0))
            db.grid_remove()

            self._entry_widgets.append((ef, dl, ml, db))

        # ── Page navigation ──────────────────────────────────────────
        nav = tk.Frame(page, bg=MW["parchment"])
        nav.pack(fill=tk.X, padx=28, pady=(0, 4))

        self._prev_btn = tk.Button(
            nav, text="\u25c4 Prev", font=FONT_NAV,
            fg=MW["ink_date"], bg=MW["parchment"],
            activebackground=MW["parchment_lt"],
            activeforeground=MW["ink"],
            relief=tk.FLAT, bd=0, cursor="arrow",
            command=self._prev_page,
        )
        self._prev_btn.pack(side=tk.LEFT)

        self._page_lbl = tk.Label(
            nav, text="", font=FONT_UI,
            fg=MW["ink_faded"], bg=MW["parchment"],
        )
        self._page_lbl.pack(side=tk.LEFT, expand=True)

        self._next_btn = tk.Button(
            nav, text="Next \u25ba", font=FONT_NAV,
            fg=MW["ink_date"], bg=MW["parchment"],
            activebackground=MW["parchment_lt"],
            activeforeground=MW["ink"],
            relief=tk.FLAT, bd=0, cursor="arrow",
            command=self._next_page,
        )
        self._next_btn.pack(side=tk.RIGHT)

        self._make_sep(page)

        # ── Input ────────────────────────────────────────────────────
        inp = tk.Frame(page, bg=MW["parchment"])
        inp.pack(fill=tk.X, padx=28, pady=(6, 2))
        inp.columnconfigure(0, weight=1)

        self.char_var = tk.StringVar()
        self.char_var.trace_add("write", self._on_char_change)

        self.entry = tk.Entry(
            inp, textvariable=self.char_var, font=FONT_BODY,
            bg=MW["parchment_lt"], fg=MW["ink"],
            insertbackground=MW["ink"],
            relief=tk.FLAT, bd=0,
            highlightthickness=1,
            highlightcolor=MW["gilt"],
            highlightbackground=MW["separator"],
        )
        self.entry.grid(row=0, column=0, sticky="ew", ipady=4, padx=(0, 8))
        self.entry.bind("<Return>", self._on_submit)
        self.entry.focus_set()

        self.counter_label = tk.Label(
            inp, text=str(MAX_CHARS), font=FONT_COUNTER,
            fg=MW["counter_ok"], bg=MW["parchment"],
            width=4, anchor="e",
        )
        self.counter_label.grid(row=0, column=1, sticky="e")

        # ── Status ───────────────────────────────────────────────────
        self.status_lbl = tk.Label(
            page, text="", font=FONT_STATUS,
            fg=MW["ink_faded"], bg=MW["parchment"], anchor="w",
        )
        self.status_lbl.pack(fill=tk.X, padx=28, pady=(2, 10))

        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        h  = self.root.winfo_reqheight()
        self.root.geometry(f"{sw}x{h}+0+0")
        self.root.resizable(False, False)

    # ------------------------------------------------------------------
    # Decorative separator
    # ------------------------------------------------------------------

    def _make_sep(self, parent):
        c = tk.Canvas(parent, height=2, bg=MW["parchment"], highlightthickness=0)
        c.pack(fill=tk.X, padx=24, pady=(4, 4))

        def _draw(event, canvas=c):
            canvas.delete("all")
            canvas.create_line(
                0, 1, canvas.winfo_width(), 1, fill=MW["separator"],
            )

        c.bind("<Configure>", _draw)

    # ------------------------------------------------------------------
    # Window controls & hotkey
    # ------------------------------------------------------------------

    def _close(self):
        self.root.destroy()

    def _on_focus_in(self, _event=None):
        self.root.attributes("-alpha", FOCUSED_ALPHA)

    def _on_focus_out(self, _event=None):
        self.root.attributes("-alpha", UNFOCUSED_ALPHA)

    def _register_hotkey(self):
        t = threading.Thread(target=self._hotkey_loop, daemon=True)
        t.start()

    def _hotkey_loop(self):
        """Runs on a background thread. RegisterHotKey + GetMessageW must share a thread."""
        if not ctypes.windll.user32.RegisterHotKey(None, _HOTKEY_ID, _MOD_CTRL, _VK_BACKTICK):
            return
        msg = ctypes.wintypes.MSG()
        while True:
            ret = ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break
            if msg.message == _WM_HOTKEY and msg.wParam == _HOTKEY_ID:
                self.root.after(0, self._toggle_visibility)
        ctypes.windll.user32.UnregisterHotKey(None, _HOTKEY_ID)

    def _preload_sounds(self):
        """Open both MP3s once via MCI so playback is instant."""
        winmm = ctypes.windll.winmm
        for alias, path in (("snd_open", SOUND_OPEN), ("snd_close", SOUND_CLOSE)):
            winmm.mciSendStringW(f'open "{path}" alias {alias}', None, 0, None)

    @staticmethod
    def _play_sound(alias: str, volume: int = 1000):
        """Rewind and play a pre-loaded MCI alias. volume is 0–1000."""
        winmm = ctypes.windll.winmm
        winmm.mciSendStringW(f'seek {alias} to start', None, 0, None)
        winmm.mciSendStringW(f'setaudio {alias} volume to {volume}', None, 0, None)
        winmm.mciSendStringW(f'play {alias}', None, 0, None)

    def _toggle_visibility(self):
        if self._visible:
            self._play_sound("snd_close", 600)
            self.root.withdraw()
            self._visible = False
        else:
            self._play_sound("snd_open")
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self.root.lift()
            self.root.focus_force()
            self.entry.focus_set()
            self._visible = True

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def _total_pages(self):
        n = len(load_messages())
        return max(1, -(-n // ENTRIES_PER_PAGE))

    def _page_entries(self, page):
        """Return entries for *page* (0 = most-recent)."""
        msgs = load_messages()
        tp = self._total_pages()
        real = tp - 1 - page
        s = real * ENTRIES_PER_PAGE
        return msgs[s : s + ENTRIES_PER_PAGE]

    def _prev_page(self):
        if self._current_page < self._total_pages() - 1:
            self._current_page += 1
            self._refresh_feed()

    def _next_page(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._refresh_feed()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_char_change(self, *_):
        text = self.char_var.get()
        remaining = MAX_CHARS - len(text)
        if remaining < 0:
            self.char_var.set(text[:MAX_CHARS])
            remaining = 0
        self.counter_label.config(
            text=str(remaining),
            fg=MW["counter_ok"] if remaining > 20 else MW["counter_warn"],
        )

    def _on_submit(self, _event=None):
        text = self.char_var.get().strip()
        if not text:
            return
        save_message(text)
        self.char_var.set("")
        self._current_page = 0
        self._refresh_feed()
        self.status_lbl.config(text="Entry recorded.")
        self.root.after(3000, lambda: self.status_lbl.config(text=""))

    def _delete_row(self, idx):
        if idx >= len(self._displayed):
            return
        entry = self._displayed[idx]
        if entry is None:
            return
        delete_message(entry["id"])
        if self._current_page >= self._total_pages():
            self._current_page = max(0, self._total_pages() - 1)
        self._refresh_feed()
        self.status_lbl.config(text="Entry stricken.")
        self.root.after(3000, lambda: self.status_lbl.config(text=""))

    def _refresh_feed(self):
        entries = self._page_entries(self._current_page)
        self._displayed = entries[:]

        for i, (_, dl, ml, db) in enumerate(self._entry_widgets):
            if i < len(entries):
                dl.config(text=format_journal_date(entries[i]["timestamp"]))
                ml.config(text=entries[i]["message"])
                db.grid()
            else:
                dl.config(text="")
                ml.config(text="")
                db.grid_remove()

        tp = self._total_pages()
        disp = tp - self._current_page
        self._page_lbl.config(text=f"\u2014 Page {disp} of {tp} \u2014")

        can_prev = self._current_page < tp - 1
        can_next = self._current_page > 0
        self._prev_btn.config(
            state=tk.NORMAL if can_prev else tk.DISABLED,
            fg=MW["ink_date"] if can_prev else MW["ink_faded"],
        )
        self._next_btn.config(
            state=tk.NORMAL if can_next else tk.DISABLED,
            fg=MW["ink_date"] if can_next else MW["ink_faded"],
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    root = tk.Tk()
    MessageLogApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
