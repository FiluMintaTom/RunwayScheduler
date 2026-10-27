"""
Smart Airport Runway Scheduling System - interactive Tkinter GUI.

Run:      python runway_gui.py
Requires: Python 3.8+ (tkinter is included with the standard Windows and macOS installers)

Quick guide
  1. Pick a scenario, or add your own flights on the left.
  2. Press Play (or Step) to watch the greedy scheduler work.
  3. Hover over a landing block to see its details; click it to find the flight in the list.
  4. Double-click a flight in the list to edit it.

Keyboard shortcuts (when no text field is focused)
  Space        play / pause
  Right arrow  next step
  R            reset
"""

import csv
import random
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from runway_scheduler import CATEGORIES, make_flight, schedule

# ------------------------------------------------------------------ data
SAMPLE_ROWS = [
    ("BA101", "H", 0, 20),
    ("EK202", "M", 2, 30),
    ("AI303", "L", 3, 25),
    ("QR404", "H", 5, 40),
    ("6E505", "M", 6, 22),
    ("SQ606", "L", 10, 35),
]

BUSY_ROWS = [
    ("LH401", "H", 0, 25), ("AI110", "M", 1, 20), ("EK212", "H", 2, 30),
    ("6E330", "L", 3, 18), ("BA777", "M", 4, 28), ("SQ215", "M", 5, 24),
    ("QR640", "H", 6, 35), ("UK811", "L", 7, 20), ("AI305", "M", 8, 26),
    ("EK604", "M", 9, 32), ("6E118", "L", 10, 22), ("BA239", "H", 12, 40),
]


def random_rows(n=10):
    rng = random.Random()
    prefixes = ["AI", "BA", "EK", "QR", "SQ", "6E", "LH", "UK"]
    rows, used = [], set()
    while len(rows) < n:
        code = f"{rng.choice(prefixes)}{rng.randint(100, 999)}"
        if code in used:
            continue
        used.add(code)
        cat = rng.choices(["H", "M", "L"], weights=[2, 5, 3])[0]
        earliest = rng.randint(0, 50)
        rows.append((code, cat, earliest, earliest + rng.randint(8, 30)))
    return rows


# name -> (rows or None for random, description)
SCENARIOS = {
    "Sample (6 flights)": (SAMPLE_ROWS, "Six flights that all fit. A good first demo."),
    "Busy morning (12 flights)": (BUSY_ROWS,
                                  "Dense traffic. Fits on 2-3 runways with delays; "
                                  "on 1 runway one flight becomes UNSCHEDULED."),
    "Random (10 flights)": (None, "A new random set of flights each time you load it."),
}

# ------------------------------------------------------------------ theme
BG = "#0b1220"          # window background
PANEL = "#111a2e"       # cards
PANEL2 = "#17223b"      # inputs, lists, canvas lanes
BORDER = "#25314d"
TEXT = "#e6edf7"
MUTED = "#8b98b0"
ACCENT = "#38bdf8"
ACCENT_HI = "#0ea5e9"
GOOD = "#34d399"
BAD = "#f87171"
WARN = "#fbbf24"
GHOST = "#1e2a47"
DANGER_BG = "#3b1d24"
DANGER_HI = "#5a2a35"
CAT_COLOURS = {"H": "#f87171", "M": "#60a5fa", "L": "#4ade80"}
CAT_NAMES = {"H": "Heavy", "M": "Medium", "L": "Light"}
FONT = "Segoe UI"
MONO = "Consolas"

# ------------------------------------------------------------------ timeline layout
OCC = 2            # minutes a landing occupies the runway (drawing only)
LANE_H = 56
LEFT = 84
TOP = 26
AXIS_H = 34
DEFAULT_INFO = "Hover over a landing for details. Click it to find the flight in the list."


# ------------------------------------------------------------------ widget helpers
class Tooltip:
    """Small hover tooltip shown below a widget."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, _event):
        if self.tip:
            return
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg=GHOST, fg=TEXT, font=(FONT, 9),
                 padx=8, pady=4, bd=0).pack()

    def _hide(self, _event):
        if self.tip:
            self.tip.destroy()
            self.tip = None


def make_button(parent, text, command, kind="ghost", tip=None):
    colours = {
        "primary": (ACCENT, ACCENT_HI, "#04111d"),
        "ghost": (GHOST, BORDER, TEXT),
        "danger": (DANGER_BG, DANGER_HI, "#fecaca"),
    }
    bg, hover, fg = colours[kind]
    btn = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                    activebackground=hover, activeforeground=fg, relief="flat", bd=0,
                    padx=12, pady=7, cursor="hand2",
                    font=(FONT, 10, "bold" if kind == "primary" else "normal"))
    btn.bind("<Enter>", lambda e: btn.config(bg=hover), add="+")
    btn.bind("<Leave>", lambda e: btn.config(bg=bg), add="+")
    if tip:
        Tooltip(btn, tip)
    return btn


def make_entry(parent, var, width=16):
    return tk.Entry(parent, textvariable=var, width=width, bg=PANEL2, fg=TEXT,
                    insertbackground=ACCENT, relief="flat", font=(FONT, 10),
                    highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)


def make_scale(parent, from_, to, var, command=None, length=None, showvalue=False):
    kwargs = {}
    if length:
        kwargs["length"] = length
    return tk.Scale(parent, from_=from_, to=to, orient="horizontal", variable=var,
                    command=command, showvalue=showvalue, bg=PANEL, fg=TEXT,
                    troughcolor=PANEL2, activebackground=ACCENT, highlightthickness=0,
                    bd=0, sliderrelief="flat", **kwargs)


def make_card(parent, title, hint=None):
    outer = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
    head = tk.Frame(outer, bg=PANEL)
    head.pack(fill="x", padx=14, pady=(12, 8))
    tk.Label(head, text=title.upper(), bg=PANEL, fg=MUTED, font=(FONT, 8, "bold")).pack(side="left")
    if hint:
        tk.Label(head, text=hint, bg=PANEL, fg=MUTED, font=(FONT, 8)).pack(side="right")
    body = tk.Frame(outer, bg=PANEL)
    body.pack(fill="both", expand=True, padx=14, pady=(0, 14))
    return outer, body


# ------------------------------------------------------------------ application
class RunwayApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Smart Airport Runway Scheduler")
        self.geometry("1340x880")
        self.minsize(1140, 740)
        self.configure(bg=BG)
        self._apply_theme()

        # scheduling state
        self.flights = []
        self.result = None
        self.steps = []
        self.step_index = 0
        self.placed = []
        self.unscheduled = []
        self.playing = False
        self.job = None
        self.editing = None          # index of the flight being edited, or None

        # tk variables
        self.scenario_var = tk.StringVar(value=list(SCENARIOS)[0])
        self.runways_var = tk.IntVar(value=2)
        self.zoom_var = tk.IntVar(value=8)
        self.speed_var = tk.IntVar(value=5)
        self.code_var = tk.StringVar()
        self.cat_var = tk.StringVar(value="M")
        self.earliest_var = tk.StringVar()
        self.latest_var = tk.StringVar()
        self.info_var = tk.StringVar(value=DEFAULT_INFO)
        self.status_var = tk.StringVar()
        self.speed_text = tk.StringVar()
        self.stat_vars = {k: tk.StringVar(value="0") for k in
                          ("scheduled", "unscheduled", "total_delay", "avg_delay")}

        self._build_header()
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=(12, 0))
        sidebar = tk.Frame(body, bg=BG, width=350)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        main = tk.Frame(body, bg=BG)
        main.pack(side="left", fill="both", expand=True, padx=(14, 0))
        self._build_sidebar(sidebar)
        self._build_main(main)
        self._build_statusbar()
        self._bind_keys()

        self.load_scenario(list(SCENARIOS)[0])

    # ------------------------------------------------------------ theme
    def _apply_theme(self):
        self.option_add("*TCombobox*Listbox.background", PANEL2)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", "#04111d")
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TCombobox", fieldbackground=PANEL2, background=PANEL2,
                        foreground=TEXT, arrowcolor=TEXT, bordercolor=BORDER,
                        lightcolor=PANEL2, darkcolor=PANEL2, selectbackground=PANEL2,
                        selectforeground=TEXT)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL2)],
                  foreground=[("readonly", TEXT)], selectbackground=[("readonly", PANEL2)])
        style.configure("Treeview", rowheight=28, font=(FONT, 9), background=PANEL2,
                        fieldbackground=PANEL2, foreground=TEXT, borderwidth=0)
        style.configure("Treeview.Heading", font=(FONT, 9, "bold"), background=PANEL,
                        foreground=MUTED, relief="flat", borderwidth=0)
        style.map("Treeview", background=[("selected", "#1d3a5c")],
                  foreground=[("selected", TEXT)])
        style.map("Treeview.Heading", background=[("active", GHOST)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=MUTED,
                        padding=(16, 7), font=(FONT, 10), borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", PANEL2)],
                  foreground=[("selected", ACCENT)])
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=PANEL2,
                        bordercolor=PANEL2, lightcolor=ACCENT, darkcolor=ACCENT)
        style.configure("Vertical.TScrollbar", background=GHOST, troughcolor=PANEL2,
                        bordercolor=PANEL2, arrowcolor=MUTED)
        style.configure("Horizontal.TScrollbar", background=GHOST, troughcolor=PANEL2,
                        bordercolor=PANEL2, arrowcolor=MUTED)

    # ------------------------------------------------------------ header and status bar
    def _build_header(self):
        hdr = tk.Frame(self, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        hdr.pack(fill="x")
        left = tk.Frame(hdr, bg=PANEL)
        left.pack(side="left", padx=20, pady=14)
        tk.Label(left, text="Smart Airport Runway Scheduler", bg=PANEL, fg=TEXT,
                 font=(FONT, 17, "bold")).pack(anchor="w")
        tk.Label(left, text="Greedy earliest-feasible-landing algorithm  |  Design and Analysis of Algorithms",
                 bg=PANEL, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(2, 0))
        tk.Label(hdr, text="READY FOR TAKEOFF", bg=PANEL, fg=ACCENT,
                 font=(FONT, 9, "bold")).pack(side="right", padx=20)

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        bar.pack(fill="x", side="bottom")
        tk.Label(bar, textvariable=self.status_var, bg=PANEL, fg=TEXT, font=(FONT, 9),
                 anchor="w", padx=14, pady=6).pack(side="left", fill="x", expand=True)
        tk.Label(bar, text="Space play/pause   Right step   R reset   Double-click a flight to edit",
                 bg=PANEL, fg=MUTED, font=(FONT, 8), padx=14).pack(side="right")

    # ------------------------------------------------------------ sidebar
    def _build_sidebar(self, parent):
        # Scenario
        c, body = make_card(parent, "Scenario")
        c.pack(fill="x", pady=(0, 12))
        cb = ttk.Combobox(body, textvariable=self.scenario_var, values=list(SCENARIOS),
                          state="readonly", font=(FONT, 10))
        cb.pack(fill="x")
        cb.bind("<<ComboboxSelected>>", lambda e: self.load_scenario(self.scenario_var.get()))
        self.scenario_desc = tk.Label(body, text="", bg=PANEL, fg=MUTED, font=(FONT, 9),
                                      wraplength=300, justify="left")
        self.scenario_desc.pack(anchor="w", pady=(8, 0))

        # Flight form
        c, body = make_card(parent, "Flight details", hint="H Heavy  M Medium  L Light")
        c.pack(fill="x", pady=(0, 12))
        grid = tk.Frame(body, bg=PANEL)
        grid.pack(fill="x")
        for i, text in enumerate(["Flight code", "Wake category", "Earliest (min)", "Deadline (min)"]):
            tk.Label(grid, text=text, bg=PANEL, fg=TEXT, font=(FONT, 9)).grid(
                row=i, column=0, sticky="w", pady=4)
        self.code_entry = make_entry(grid, self.code_var, width=18)
        self.code_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=2)
        ttk.Combobox(grid, textvariable=self.cat_var, values=CATEGORIES, state="readonly",
                     width=16, font=(FONT, 10)).grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=2)
        make_entry(grid, self.earliest_var, width=18).grid(row=2, column=1, sticky="ew", padx=(10, 0), pady=2)
        make_entry(grid, self.latest_var, width=18).grid(row=3, column=1, sticky="ew", padx=(10, 0), pady=2)
        grid.columnconfigure(1, weight=1)

        row = tk.Frame(body, bg=PANEL)
        row.pack(fill="x", pady=(10, 0))
        self.save_btn = make_button(row, "Add flight", self.save_flight, kind="primary",
                                    tip="Add this flight to the list (Enter)")
        self.save_btn.pack(side="left", fill="x", expand=True)
        make_button(row, "Clear", self._clear_form, tip="Empty the form").pack(
            side="left", fill="x", expand=True, padx=(8, 0))
        self.code_entry.bind("<Return>", lambda e: self.save_flight())

        # Flight list
        c, body = make_card(parent, "Flights", hint="double-click to edit")
        c.pack(fill="both", expand=True, pady=(0, 12))
        list_frame = tk.Frame(body, bg=PANEL)
        list_frame.pack(fill="both", expand=True)
        self.flight_tree = ttk.Treeview(list_frame, columns=("code", "cat", "earliest", "latest"),
                                        show="headings", height=5, selectmode="extended")
        for col, text, w in [("code", "Code", 90), ("cat", "Cat", 60),
                             ("earliest", "Earliest", 90), ("latest", "Deadline", 90)]:
            self.flight_tree.heading(col, text=text)
            self.flight_tree.column(col, width=w, anchor="center")
        vs = ttk.Scrollbar(list_frame, orient="vertical", command=self.flight_tree.yview)
        self.flight_tree.configure(yscrollcommand=vs.set)
        self.flight_tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.flight_tree.bind("<Double-1>", self._on_tree_double)
        make_button(body, "Delete selected flights", self.delete_selected, kind="danger",
                    tip="Remove the highlighted flights from the list").pack(fill="x", pady=(10, 0))

        # Settings
        c, body = make_card(parent, "Settings")
        c.pack(fill="x", pady=(0, 12))
        tk.Label(body, text="Runways", bg=PANEL, fg=TEXT, font=(FONT, 9)).pack(anchor="w")
        make_scale(body, 1, 6, self.runways_var, command=lambda _v: self._runways_changed(),
                   length=300).pack(fill="x")
        speed_row = tk.Frame(body, bg=PANEL)
        speed_row.pack(fill="x", pady=(6, 0))
        tk.Label(speed_row, text="Playback speed", bg=PANEL, fg=TEXT, font=(FONT, 9)).pack(side="left")
        tk.Label(speed_row, textvariable=self.speed_text, bg=PANEL, fg=ACCENT,
                 font=(FONT, 9, "bold")).pack(side="right")
        make_scale(body, 1, 10, self.speed_var, command=lambda _v: self._update_speed_text(),
                   length=300).pack(fill="x")
        self._update_speed_text()

        # Playback
        c, body = make_card(parent, "Playback")
        c.pack(fill="x")
        row = tk.Frame(body, bg=PANEL)
        row.pack(fill="x")
        self.play_btn = make_button(row, "Play", self.toggle_play, kind="primary",
                                    tip="Play / pause the schedule (Space)")
        self.play_btn.pack(side="left", fill="x", expand=True)
        make_button(row, "Step", self.step_once, tip="Run one flight (Right arrow)").pack(
            side="left", fill="x", expand=True, padx=8)
        make_button(row, "Reset", self.reset, tip="Clear the schedule (R)").pack(
            side="left", fill="x", expand=True)
        self.progress = ttk.Progressbar(body, mode="determinate", maximum=1)
        self.progress.pack(fill="x", pady=(12, 0))

    # ------------------------------------------------------------ main area
    def _build_main(self, parent):
        # Stat cards
        stats = tk.Frame(parent, bg=BG)
        stats.pack(fill="x")
        specs = [
            ("scheduled", "Scheduled", GOOD),
            ("unscheduled", "Unscheduled", BAD),
            ("total_delay", "Total delay (min)", WARN),
            ("avg_delay", "Average delay (min)", ACCENT),
        ]
        for key, title, colour in specs:
            box = tk.Frame(stats, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
            box.pack(side="left", fill="x", expand=True, padx=(0, 10))
            tk.Frame(box, bg=colour, width=4).pack(side="left", fill="y")
            inner = tk.Frame(box, bg=PANEL)
            inner.pack(side="left", fill="both", expand=True, padx=14, pady=10)
            tk.Label(inner, text=title, bg=PANEL, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
            tk.Label(inner, textvariable=self.stat_vars[key], bg=PANEL, fg=TEXT,
                     font=(FONT, 20, "bold")).pack(anchor="w")

        # Timeline
        c, body = make_card(parent, "Runway timeline")
        c.pack(fill="x", pady=(12, 12))
        top = tk.Frame(body, bg=PANEL)
        top.pack(fill="x")
        legend = tk.Frame(top, bg=PANEL)
        legend.pack(side="left")
        for code in CATEGORIES:
            tk.Frame(legend, bg=CAT_COLOURS[code], width=12, height=12).pack(side="left", padx=(0, 6))
            tk.Label(legend, text=CAT_NAMES[code], bg=PANEL, fg=TEXT, font=(FONT, 9)).pack(
                side="left", padx=(0, 14))
        tk.Label(top, text="Zoom", bg=PANEL, fg=MUTED, font=(FONT, 9)).pack(side="right", padx=(8, 0))
        make_scale(top, 4, 20, self.zoom_var, command=lambda _v: self.draw(),
                   length=160).pack(side="right")

        tl = tk.Frame(body, bg=PANEL)
        tl.pack(fill="x", pady=(10, 0))
        self.canvas = tk.Canvas(tl, bg="#0a1222", highlightthickness=0, height=220)
        xbar = ttk.Scrollbar(tl, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=xbar.set)
        self.canvas.pack(fill="x")
        xbar.pack(fill="x")
        tk.Label(body, textvariable=self.info_var, bg=PANEL, fg=TEXT, font=(FONT, 9),
                 anchor="w").pack(fill="x", pady=(8, 0))

        # Tabs
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True)

        log_tab = tk.Frame(self.notebook, bg=PANEL)
        self.log = tk.Text(log_tab, wrap="word", state="disabled", font=(MONO, 9), bg=PANEL2,
                           fg=TEXT, relief="flat", padx=14, pady=10, highlightthickness=0)
        self.log.tag_configure("step", foreground=ACCENT, font=(MONO, 9, "bold"))
        self.log.tag_configure("muted", foreground=MUTED)
        self.log.tag_configure("ok", foreground=GOOD)
        self.log.tag_configure("bad", foreground=BAD)
        self.log.tag_configure("head", foreground=TEXT, font=(MONO, 10, "bold"))
        self.log.pack(fill="both", expand=True)
        self.notebook.add(log_tab, text="  Step log  ")

        res_tab = tk.Frame(self.notebook, bg=PANEL)
        self.results_tree = ttk.Treeview(res_tab, columns=("flight", "rwy", "landing", "delay", "status"),
                                         show="headings")
        for col, text, w in [("flight", "Flight", 110), ("rwy", "Runway", 110),
                             ("landing", "Landing (min)", 130), ("delay", "Delay (min)", 120),
                             ("status", "Status", 150)]:
            self.results_tree.heading(col, text=text)
            self.results_tree.column(col, width=w, anchor="center")
        self.results_tree.tag_configure("ok", foreground=GOOD)
        self.results_tree.tag_configure("bad", foreground=BAD)
        self.results_tree.pack(fill="both", expand=True, padx=12, pady=12)
        bar = tk.Frame(res_tab, bg=PANEL)
        bar.pack(fill="x", padx=12, pady=(0, 12))
        make_button(bar, "Export CSV", self.export_csv, kind="primary",
                    tip="Save the results as a .csv file").pack(side="right")
        self.notebook.add(res_tab, text="  Results  ")

        guide_tab = tk.Frame(self.notebook, bg=PANEL)
        guide = tk.Text(guide_tab, wrap="word", font=(FONT, 10), bg=PANEL2, fg=TEXT,
                        relief="flat", padx=20, pady=16, highlightthickness=0, spacing3=4)
        guide.tag_configure("h", foreground=ACCENT, font=(FONT, 12, "bold"), spacing1=10)
        guide.tag_configure("b", foreground=TEXT)
        for tag, line in GUIDE_LINES:
            guide.insert("end", line + "\n", tag)
        guide.config(state="disabled")
        guide.pack(fill="both", expand=True)
        self.notebook.add(guide_tab, text="  How it works  ")

    # ------------------------------------------------------------ keys
    def _bind_keys(self):
        self.bind("<space>", lambda e: self._key(self.toggle_play))
        self.bind("<Right>", lambda e: self._key(self.step_once))
        self.bind("<r>", lambda e: self._key(self.reset))
        self.bind("<R>", lambda e: self._key(self.reset))

    def _key(self, action):
        w = self.focus_get()
        if isinstance(w, (tk.Entry, ttk.Entry, ttk.Combobox, ttk.Spinbox, tk.Text, tk.Scale)):
            return None
        action()
        return "break"

    # ------------------------------------------------------------ form and list
    def _set_status(self, text):
        self.status_var.set(text)

    def _update_speed_text(self):
        self.speed_text.set(f"{self.speed_var.get()} / 10")

    def _runways_changed(self):
        n = self.runways_var.get()
        self.reset()
        self._set_status(f"Runways set to {n}. Press Play or Step to reschedule.")

    def _refresh_table(self):
        self.flight_tree.delete(*self.flight_tree.get_children())
        for i, f in enumerate(self.flights):
            self.flight_tree.insert("", "end", iid=str(i),
                                    values=(f.code, f.category, f"{f.earliest:g}", f"{f.latest:g}"))

    def _mark_custom(self):
        self.scenario_var.set("Custom")
        self.scenario_desc.config(text="Your own flight list.")

    def _clear_form(self):
        self.editing = None
        self.code_var.set("")
        self.cat_var.set("M")
        self.earliest_var.set("")
        self.latest_var.set("")
        self.save_btn.config(text="Add flight")
        self.code_entry.focus_set()

    def _on_tree_double(self, _event):
        sel = self.flight_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        f = self.flights[idx]
        self.editing = idx
        self.code_var.set(f.code)
        self.cat_var.set(f.category)
        self.earliest_var.set(f"{f.earliest:g}")
        self.latest_var.set(f"{f.latest:g}")
        self.save_btn.config(text="Save changes")
        self._set_status(f"Editing {f.code}. Change the details and press Save changes.")

    def save_flight(self):
        try:
            f = make_flight(self.code_var.get(), self.cat_var.get(),
                            self.earliest_var.get(), self.latest_var.get())
        except ValueError as exc:
            messagebox.showerror("Check the flight details", str(exc))
            return
        for j, other in enumerate(self.flights):
            if other.code == f.code and j != self.editing:
                messagebox.showerror("Duplicate flight", f"Flight {f.code} is already in the list.")
                return
        if self.editing is None:
            self.flights.append(f)
            msg = f"Added {f.code}."
        else:
            self.flights[self.editing] = f
            msg = f"Updated {f.code}."
        self._clear_form()
        self._mark_custom()
        self._refresh_table()
        self.reset()
        self._set_status(f"{msg} {len(self.flights)} flight(s) in the list.")

    def delete_selected(self):
        sel = self.flight_tree.selection()
        if not sel:
            self._set_status("Select one or more flights in the list first.")
            return
        for i in sorted((int(s) for s in sel), reverse=True):
            del self.flights[i]
        self._clear_form()
        self._mark_custom()
        self._refresh_table()
        self.reset()
        self._set_status(f"Deleted {len(sel)} flight(s).")

    def load_scenario(self, name):
        rows, desc = SCENARIOS[name]
        if rows is None:
            rows = random_rows()
        self.scenario_var.set(name)
        self.scenario_desc.config(text=desc)
        self.flights = [make_flight(*r) for r in rows]
        self._clear_form()
        self._refresh_table()
        self.reset()
        self._set_status(f"Loaded '{name}'. Press Play or Step to schedule.")

    # ------------------------------------------------------------ playback
    def _ensure_started(self):
        if self.steps:
            return True
        if not self.flights:
            messagebox.showinfo("No flights", "Add at least one flight before scheduling.")
            return False
        self.result = schedule(self.flights, self.runways_var.get())
        self.steps = self.result.steps
        self.step_index = 0
        self.placed = []
        self.unscheduled = []
        self.log_clear()
        self.results_tree.delete(*self.results_tree.get_children())
        self.progress.config(maximum=max(len(self.steps), 1), value=0)
        self.log_write(f"Greedy schedule started: {len(self.flights)} flight(s), "
                       f"{self.runways_var.get()} runway(s)", "head")
        self.log_write("Flights are processed in order of earliest acceptable landing time.\n", "muted")
        self.draw()
        self._update_stats()
        return True

    def toggle_play(self):
        if self.playing:
            self._pause()
            return
        if self.steps and self.step_index >= len(self.steps):
            self.reset()
        if not self._ensure_started():
            return
        self.playing = True
        self.play_btn.config(text="Pause")
        self._set_status("Playing. Press Space to pause.")
        self._tick()

    def _pause(self):
        self.playing = False
        if self.job is not None:
            self.after_cancel(self.job)
            self.job = None
        self.play_btn.config(text="Play")

    def _delay_ms(self):
        # speed 1 -> 1300 ms per step, speed 10 -> 130 ms per step
        return int(1300 - (self.speed_var.get() - 1) * 130)

    def _tick(self):
        self.job = None
        if not self.playing:
            return
        if self.step_index >= len(self.steps):
            self._pause()
            return
        self._advance()
        if self.step_index >= len(self.steps):
            self._pause()
            return
        self.job = self.after(self._delay_ms(), self._tick)

    def step_once(self):
        self._pause()
        if not self._ensure_started():
            return
        if self.step_index >= len(self.steps):
            self._set_status("Schedule complete. Press Reset to try another scenario.")
            return
        self._advance()

    def reset(self):
        self._pause()
        self.steps = []
        self.step_index = 0
        self.placed = []
        self.unscheduled = []
        self.result = None
        self.log_clear()
        self.results_tree.delete(*self.results_tree.get_children())
        self.progress.config(value=0, maximum=1)
        self.info_var.set(DEFAULT_INFO)
        self.draw()
        self._update_stats()
        self.log_write("Ready. Press Play or Step to begin.", "muted")

    def _advance(self):
        step = self.steps[self.step_index]
        self.step_index += 1
        f = step.flight
        self.log_write(f"Step {self.step_index}   {f.code}  ({CAT_NAMES[f.category]}, "
                       f"window {f.earliest:g}-{f.latest:g} min)", "step")
        cands = ", ".join(
            f"RWY {r + 1} at {t:g}" + ("" if t <= f.latest else " (too late)")
            for r, t in step.options)
        self.log_write(f"    options: {cands}", "muted")
        if step.assignment:
            self.log_write(f"    -> {step.message}\n", "ok")
            self.placed.append(step.assignment)
        else:
            self.log_write(f"    -> {step.message}\n", "bad")
            self.unscheduled.append(f)

        self.progress.config(value=self.step_index)
        self.draw(highlight=f)
        self._update_stats()
        if self.step_index == len(self.steps):
            self._finish()

    def _finish(self):
        self.results_tree.delete(*self.results_tree.get_children())
        for a in self.result.assignments:
            self.results_tree.insert("", "end", tags=("ok",),
                                     values=(a.flight.code, f"RWY {a.runway + 1}", f"{a.time:g}",
                                             f"{a.delay:g}", "Scheduled"))
        for f in self.result.unscheduled:
            self.results_tree.insert("", "end", tags=("bad",),
                                     values=(f.code, "-", "-", "-", "Unscheduled"))
        self._set_status(f"Finished: {len(self.result.assignments)} of {len(self.flights)} "
                         f"flight(s) scheduled. See the Results tab.")
        self.notebook.select(1)

    def _update_stats(self):
        n_ok = len(self.placed)
        total = sum(a.delay for a in self.placed)
        self.stat_vars["scheduled"].set(f"{n_ok}/{len(self.flights)}" if self.flights else "0")
        self.stat_vars["unscheduled"].set(str(len(self.unscheduled)))
        self.stat_vars["total_delay"].set(f"{total:g}")
        self.stat_vars["avg_delay"].set(f"{(total / n_ok if n_ok else 0):.2f}")

    # ------------------------------------------------------------ timeline
    def draw(self, highlight=None):
        c = self.canvas
        c.delete("all")
        n = max(1, int(self.runways_var.get()))
        ppm = self.zoom_var.get()
        horizon = max([f.latest for f in self.flights] + [60]) + 10
        plot_w = int(horizon * ppm)
        axis_y = TOP + n * LANE_H
        total_h = axis_y + AXIS_H
        total_w = LEFT + plot_w + 40
        c.config(height=total_h, scrollregion=(0, 0, total_w, total_h))

        if not self.flights:
            c.create_text(total_w / 2, total_h / 2, text="No flights yet. Add some on the left.",
                          fill=MUTED, font=(FONT, 11))
            return

        counts = [0] * n
        for a in self.placed:
            counts[a.runway] += 1

        # runway lanes
        for r in range(n):
            y = TOP + r * LANE_H
            c.create_rectangle(LEFT, y, LEFT + plot_w, y + LANE_H - 8, fill=PANEL2, outline=BORDER)
            c.create_text(12, y + (LANE_H - 8) / 2, text=f"RWY {r + 1}", anchor="w",
                          font=(FONT, 10, "bold"), fill=TEXT)
            c.create_text(LEFT + plot_w - 8, y + 6, text=f"{counts[r]} landed", anchor="ne",
                          font=(FONT, 8), fill=MUTED)

        # time axis
        for t in range(0, int(horizon) + 1, 5):
            x = LEFT + t * ppm
            major = t % 10 == 0
            c.create_line(x, axis_y - (8 if major else 4), x, axis_y, fill="#3a4766")
            if major:
                c.create_text(x, axis_y + 10, text=str(t), font=(FONT, 8), fill=MUTED)
        c.create_text(LEFT + plot_w / 2, axis_y + 26, text="minutes", font=(FONT, 8), fill=MUTED)

        # landings (hover to inspect, click to select in the list)
        for a in self.placed:
            x1 = LEFT + a.time * ppm
            x2 = max(x1 + 6, LEFT + (a.time + OCC) * ppm)
            y = TOP + a.runway * LANE_H
            colour = CAT_COLOURS[a.flight.category]
            rect = c.create_rectangle(x1, y + 5, x2, y + LANE_H - 13, fill=colour, outline="", width=2)
            label = c.create_text(x1 + 4, y + (LANE_H - 8) / 2, text=a.flight.code, anchor="w",
                                  font=(FONT, 8, "bold"), fill="#04111d")
            for item in (rect, label):
                c.tag_bind(item, "<Enter>", lambda e, a=a, r=rect: self._on_block_enter(a, r))
                c.tag_bind(item, "<Leave>", lambda e, r=rect: self._on_block_leave(r))
                c.tag_bind(item, "<Button-1>", lambda e, a=a: self._select_in_table(a.flight.code))

        # current flight markers
        if highlight is not None:
            xe = LEFT + highlight.earliest * ppm
            xl = LEFT + highlight.latest * ppm
            c.create_line(xe, TOP - 4, xe, axis_y, fill="#22c55e", dash=(4, 3), width=2)
            c.create_line(xl, TOP - 4, xl, axis_y, fill=BAD, dash=(4, 3), width=2)
            c.create_text(xl + 5, TOP - 6, text=f"{highlight.code} deadline", anchor="sw",
                          fill=BAD, font=(FONT, 8, "bold"))
            c.create_text(xe + 5, TOP - 6, text="earliest", anchor="sw", fill=GOOD, font=(FONT, 8))

    def _on_block_enter(self, a, rect):
        self.canvas.config(cursor="hand2")
        self.canvas.itemconfig(rect, outline="white")
        f = a.flight
        self.info_var.set(
            f"{f.code}   {CAT_NAMES[f.category]}   RWY {a.runway + 1} at {a.time:g} min   "
            f"window {f.earliest:g}-{f.latest:g}   delay {a.delay:g} min")

    def _on_block_leave(self, rect):
        self.canvas.config(cursor="")
        self.canvas.itemconfig(rect, outline="")
        self.info_var.set(DEFAULT_INFO)

    def _select_in_table(self, code):
        for iid in self.flight_tree.get_children():
            if self.flight_tree.item(iid, "values")[0] == code:
                self.flight_tree.selection_set(iid)
                self.flight_tree.see(iid)
                break
        self._set_status(f"Selected {code} in the flight list.")

    # ------------------------------------------------------------ export and logs
    def export_csv(self):
        if not self.result:
            messagebox.showinfo("Nothing to export", "Run the schedule first (Play, Step or Run).")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="runway_schedule.csv",
                                            filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["Flight", "Category", "Earliest", "Deadline", "Runway", "Landing", "Delay", "Status"])
            for a in self.result.assignments:
                f = a.flight
                w.writerow([f.code, f.category, f.earliest, f.latest, a.runway + 1, a.time, a.delay, "Scheduled"])
            for f in self.result.unscheduled:
                w.writerow([f.code, f.category, f.earliest, f.latest, "", "", "", "Unscheduled"])
        self._set_status(f"Saved results to {path}")

    def log_write(self, text, tag=None):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n", tag or ())
        self.log.see("end")
        self.log.config(state="disabled")

    def log_clear(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")


GUIDE_LINES = [
    ("h", "How the greedy scheduler works"),
    ("b", "1. Sort the flights by their earliest acceptable landing time. Ties go to the earlier deadline, then the flight code."),
    ("b", "2. For each flight, in that order, find the earliest time it could land on every runway. The wake-turbulence separation from the last aircraft on that runway is included. For example, Heavy followed by Light needs 4 minutes."),
    ("b", "3. Choose the runway with the earliest feasible landing. If that time is after the flight's deadline, no runway can take it, so it is marked Unscheduled."),
    ("h", "What the screen shows"),
    ("b", "Stat cards: scheduled count, unscheduled count, total and average delay, updated as the schedule runs."),
    ("b", "Timeline: one lane per runway. Coloured blocks are landings (red Heavy, blue Medium, green Light). The green dashed line is the current flight's earliest time and the red dashed line is its deadline. Hover over a block for details, and click it to select the flight in the list."),
    ("b", "Step log: each decision and the options that were considered, colour-coded (green = assigned, red = unscheduled)."),
    ("b", "Results: the final table, which you can export to CSV."),
    ("h", "Complexity"),
    ("b", "Let n be the number of flights and m the number of runways. Time is O(n log n) for sorting plus O(n x m) to check every runway for every flight, so O(n log n + nm) overall. Space is O(n + m) for the schedule state; keeping the full step trace takes O(nm)."),
    ("h", "Limitation"),
    ("b", "Greedy is a fast heuristic. It always produces a conflict-free schedule, but it is not guaranteed to minimise total delay for every input."),
    ("h", "Shortcuts"),
    ("b", "Space: play or pause.   Right arrow: next step.   R: reset.   Double-click a flight in the list to edit it."),
]


if __name__ == "__main__":
    RunwayApp().mainloop()
