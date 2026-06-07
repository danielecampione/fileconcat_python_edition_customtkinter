# gui.py
import os
import re
import threading
import customtkinter as ctk
from tkinter import filedialog
from tkinterdnd2 import TkinterDnD, DND_FILES
from business_logic import merge_files, scan_extensions

# ── Tema ───────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

BG        = "#f7f5f2"
SURFACE   = "#ffffff"
CARD      = "#ffffff"
ACCENT    = "#e05c2a"
ACCENT_H  = "#c94d1f"
DROP_BG   = "#fff8f5"
DROP_ACT  = "#fde8df"
SUCCESS   = "#2d9e6b"
ERROR     = "#d63b3b"
TEXT      = "#1a1a1a"
MUTED     = "#888077"
BORDER    = "#ddd8d0"

EXTENSIONS = [
    "txt", "md",   "py",   "js",  "ts",
    "json","java", "c",    "cpp", "html",
    "css", "xml",  "yaml", "yml", "sh",
]

# Estensioni attive di default
DEFAULT_ON = {"txt", "md"}


def _parse_paths(data: str) -> list[str]:
    """Converte la stringa di drop di tkinterdnd2 in lista di percorsi."""
    paths = []
    # I percorsi con spazi sono avvolti in {}
    for match in re.finditer(r'\{([^}]+)\}|(\S+)', data):
        p = match.group(1) or match.group(2)
        if p:
            paths.append(p)
    return paths


# ── GUI ────────────────────────────────────────────────────────────────────────
class MergeGUI(TkinterDnD.Tk):
    """
    Usa TkinterDnD.Tk come base (invece di ctk.CTk) per abilitare il
    drag & drop nativo; i widget CTk funzionano ugualmente.
    """

    def __init__(self):
        super().__init__()
        self.wm_attributes("-alpha", 0.0)   # nascosto subito, prima di tutto

        # Applica il tema CTk dopo l'init
        self.configure(bg=BG)
        ctk.set_appearance_mode("light")

        self.title("Unisci File")
        self.geometry("600x820")
        self.minsize(560, 720)
        self.resizable(True, True)

        # Font (creati dopo che la finestra esiste)
        self.F_TITLE = ctk.CTkFont("Georgia",   26, "bold")
        self.F_LABEL = ctk.CTkFont("Georgia",   15)
        self.F_BODY  = ctk.CTkFont("Helvetica", 14)
        self.F_SMALL = ctk.CTkFont("Helvetica", 12)
        self.F_BTN   = ctk.CTkFont("Helvetica", 16, "bold")

        self.output_var  = ctk.StringVar(value="output.txt")
        self.ext_vars    = {e: ctk.IntVar(value=1 if e in DEFAULT_ON else 0)
                            for e in EXTENSIONS}
        self._sources    = []   # lista percorsi droppati o scelti
        self._running    = False

        self._build()

        # ── Animazione avvio ────────────────────────────────────────────────────
        self._anim_open()

        # Intercetta la chiusura per animare l'uscita
        self.protocol("WM_DELETE_WINDOW", self._anim_close)

    # ── Animazioni ─────────────────────────────────────────────────────────────
    def _ease_out(self, t: float) -> float:
        """Curva ease-out cubica: scatta subito, decelera alla fine."""
        return 1 - (1 - t) ** 3

    def _ease_in(self, t: float) -> float:
        """Curva ease-in cubica: parte piano, accelera."""
        return t ** 2

    def _anim_open(self, step: int = 0):
        """Fade-in puro. Totale ~220 ms, 22 step da 10 ms."""
        STEPS    = 40
        INTERVAL = 12

        if step > STEPS:
            self.wm_attributes("-alpha", 1.0)
            return

        t    = step / STEPS
        ease = self._ease_out(t)
        self.wm_attributes("-alpha", ease)
        self.after(INTERVAL, self._anim_open, step + 1)

    def _anim_close(self, step: int = 0):
        """Fade-out + leggero slide verso il basso. Totale ~130 ms."""
        STEPS    = 13
        INTERVAL = 10
        SLIDE_PX = 14

        if step > STEPS:
            self.destroy()
            return

        t    = step / STEPS
        ease = self._ease_in(t)

        self.wm_attributes("-alpha", 1.0 - ease)

        x = self.winfo_x()
        y = self.winfo_y()
        offset = int(SLIDE_PX * ease)
        self.geometry(f"+{x}+{y + offset}")

        self.after(10, self._anim_close, step + 1)

    # ── Layout ─────────────────────────────────────────────────────────────────
    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="📄  Unisci File",
                     font=self.F_TITLE, text_color=ACCENT, anchor="w"
                     ).pack(side="left", padx=28, pady=20)
        ctk.CTkLabel(hdr, text="Raccoglie i tuoi file di testo in uno solo",
                     font=self.F_SMALL, text_color=MUTED, anchor="w"
                     ).pack(side="left", padx=4)
        ctk.CTkFrame(self, fg_color=BORDER, height=1,
                     corner_radius=0).pack(fill="x")

        # Corpo
        body = ctk.CTkScrollableFrame(self, fg_color=BG,
                                      scrollbar_button_color=BORDER,
                                      scrollbar_button_hover_color=MUTED)
        body.pack(fill="both", expand=True, padx=24, pady=20)

        # ── 1. Zona drop ────────────────────────────────────────────────────────
        self._label(body, "Trascina qui file, cartelle o archivi .zip")

        self._drop_frame = ctk.CTkFrame(
            body, fg_color=DROP_BG, corner_radius=14,
            border_width=2, border_color=BORDER
        )
        self._drop_frame.pack(fill="x", pady=(4, 4))

        self._drop_label = ctk.CTkLabel(
            self._drop_frame,
            text="⬇   Trascina qui\nfile · cartelle · .zip",
            font=self.F_BODY, text_color=MUTED,
            justify="center"
        )
        self._drop_label.pack(pady=28)

        # Registra drop target sul frame e sulla label
        for widget in (self._drop_frame, self._drop_label):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>",         self._on_drop)
            widget.dnd_bind("<<DragEnter>>",    self._on_drag_enter)
            widget.dnd_bind("<<DragLeave>>",    self._on_drag_leave)

        # oppure usa il bottone per sfogliare
        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x", pady=(6, 0))

        ctk.CTkButton(
            btn_row, text="Scegli cartella…",
            font=self.F_SMALL, height=36, width=170,
            fg_color=BORDER, hover_color="#ccc9c0",
            text_color=TEXT, corner_radius=8,
            command=self._choose_folder
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="Scegli file…",
            font=self.F_SMALL, height=36, width=140,
            fg_color=BORDER, hover_color="#ccc9c0",
            text_color=TEXT, corner_radius=8,
            command=self._choose_files
        ).pack(side="left")

        # ── 2. Nome output ───────────────────────────────────────────────────────
        self._label(body, "Nome del file da creare")
        out_card = self._card(body)
        ctk.CTkEntry(
            out_card, textvariable=self.output_var,
            font=self.F_BODY, height=48, corner_radius=8,
            fg_color=BG, border_color=BORDER, border_width=2,
            text_color=TEXT
        ).pack(fill="x", padx=14, pady=14)

        # ── 3. Estensioni ────────────────────────────────────────────────────────
        self._label(body, "Che tipo di file vuoi raccogliere?")
        ext_card = self._card(body)

        grid = ctk.CTkFrame(ext_card, fg_color="transparent")
        grid.pack(fill="x", padx=14, pady=(14, 6))

        for i, ext in enumerate(EXTENSIONS):
            ctk.CTkCheckBox(
                grid, text=f".{ext}",
                variable=self.ext_vars[ext],
                font=self.F_BODY,
                fg_color=ACCENT, hover_color=ACCENT_H,
                checkmark_color="#fff",
                border_color=BORDER,
                text_color=TEXT, corner_radius=5
            ).grid(row=i // 5, column=i % 5, sticky="w", padx=10, pady=6)

        ctrl = ctk.CTkFrame(ext_card, fg_color="transparent")
        ctrl.pack(fill="x", padx=14, pady=(4, 14))
        for lbl, val in [("Seleziona tutti", 1), ("Deseleziona tutti", 0)]:
            ctk.CTkButton(
                ctrl, text=lbl,
                font=self.F_SMALL, height=34, width=160,
                fg_color=BORDER, hover_color="#ccc9c0",
                text_color=MUTED, corner_radius=6,
                command=lambda v=val: self._set_all(v)
            ).pack(side="left", padx=(0, 8))

        # ── Avanzamento ──────────────────────────────────────────────────────────
        self._progress = ctk.CTkProgressBar(
            body, fg_color=BORDER, progress_color=ACCENT,
            height=6, corner_radius=3
        )
        self._progress.set(0)

        # ── Stato ────────────────────────────────────────────────────────────────
        self._status = ctk.CTkLabel(
            body, text="", font=self.F_SMALL,
            text_color=MUTED, anchor="w", wraplength=520
        )
        self._status.pack(fill="x", pady=(12, 4))

        # ── Bottone principale ───────────────────────────────────────────────────
        self._run_btn = ctk.CTkButton(
            body, text="Unisci i file  →",
            font=self.F_BTN, height=58, corner_radius=12,
            fg_color=ACCENT, hover_color=ACCENT_H,
            text_color="#fff", command=self._run
        )
        self._run_btn.pack(fill="x", pady=(8, 4))

    # ── Widget helpers ──────────────────────────────────────────────────────────
    def _label(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=self.F_LABEL,
                     text_color=TEXT, anchor="w"
                     ).pack(fill="x", pady=(16, 4))

    def _card(self, parent):
        f = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=12,
                         border_width=1, border_color=BORDER)
        f.pack(fill="x", pady=(0, 4))
        return f

    # ── Drag & drop ─────────────────────────────────────────────────────────────
    def _on_drag_enter(self, event):
        self._drop_frame.configure(fg_color=DROP_ACT, border_color=ACCENT)

    def _on_drag_leave(self, event):
        self._drop_frame.configure(fg_color=DROP_BG, border_color=BORDER)

    def _on_drop(self, event):
        self._drop_frame.configure(fg_color=DROP_BG, border_color=BORDER)
        paths = _parse_paths(event.data)
        if not paths:
            return
        self._set_sources(paths)

    def _set_sources(self, paths: list[str]):
        self._sources = paths

        # Aggiorna label drop zone
        if len(paths) == 1:
            name = os.path.basename(paths[0]) or paths[0]
            self._drop_label.configure(
                text=f"✓  {name}",
                text_color=SUCCESS
            )
        else:
            self._drop_label.configure(
                text=f"✓  {len(paths)} elementi selezionati",
                text_color=SUCCESS
            )

        # Scansiona le estensioni in background e spunta quelle trovate
        self._set_status("Scansione estensioni…", MUTED)
        threading.Thread(target=self._scan_and_check,
                         args=(paths,), daemon=True).start()

    def _scan_and_check(self, paths):
        try:
            found = scan_extensions(paths)
        except Exception:
            found = []
        self.after(0, self._apply_found_extensions, found)

    def _apply_found_extensions(self, found: list[str]):
        # Deseleziona tutto, poi spunta solo le estensioni trovate
        # che sono nella nostra lista
        for ext, var in self.ext_vars.items():
            var.set(1 if ext in found else 0)

        matched = [e for e in EXTENSIONS if e in found]
        if matched:
            self._set_status(
                f"Trovate: {', '.join('.' + e for e in matched)}",
                SUCCESS
            )
        else:
            self._set_status(
                "Nessuna estensione riconosciuta. Seleziona manualmente.", MUTED
            )

    # ── Scegli con dialogo ──────────────────────────────────────────────────────
    def _choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self._set_sources([folder])

    def _choose_files(self):
        files = filedialog.askopenfilenames()
        if files:
            self._set_sources(list(files))

    # ── Estensioni ──────────────────────────────────────────────────────────────
    def _set_all(self, v):
        for var in self.ext_vars.values():
            var.set(v)

    # ── Stato ───────────────────────────────────────────────────────────────────
    def _set_status(self, msg, color=MUTED):
        self._status.configure(text=msg, text_color=color)

    # ── Esecuzione ──────────────────────────────────────────────────────────────
    def _run(self):
        if self._running:
            return

        if not self._sources:
            self._set_status("⚠  Scegli o trascina almeno un file o cartella.", ERROR)
            return

        selected = [e for e, v in self.ext_vars.items() if v.get() == 1]
        if not selected:
            self._set_status("⚠  Scegli almeno un tipo di file.", ERROR)
            return

        out_name = self.output_var.get().strip() or "output.txt"
        self._running = True
        self._run_btn.configure(state="disabled", text="⏳  Un momento…")
        self._progress.pack(fill="x", pady=(0, 6))
        self._progress.start()
        self._set_status("Raccolta file in corso…", MUTED)

        threading.Thread(
            target=self._worker,
            args=(list(self._sources), selected, out_name),
            daemon=True
        ).start()

    def _worker(self, sources, exts, out_name):
        try:
            path = merge_files(sources, exts, out_name)
            self.after(0, self._on_success, path)
        except Exception as e:
            self.after(0, self._on_error, str(e))

    def _on_success(self, path):
        self._progress.stop()
        self._progress.set(1)
        size_kb = os.path.getsize(path) / 1024
        self._set_status(
            f"✓  Fatto! Salvato: {path}  ({size_kb:.1f} KB)",
            SUCCESS
        )
        self._run_btn.configure(state="normal", text="Unisci i file  →")
        self._running = False

    def _on_error(self, msg):
        self._progress.stop()
        self._progress.set(0)
        self._set_status(f"✗  Errore: {msg}", ERROR)
        self._run_btn.configure(state="normal", text="Unisci i file  →")
        self._running = False
