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
    # Testo / markup
    "txt", "md",   "rst",  "tex",  "html", "htm",
    "css", "xml",  "yaml", "yml",  "toml", "ini",
    "json","csv",
    # Script / shell
    "sh",  "bash", "zsh",  "bat",  "cmd",  "ps1",
    # Python
    "py",  "pyw",
    # Web / frontend
    "js",  "ts",   "jsx",  "tsx",  "vue",  "svelte",
    # JVM
    "java","kt",   "scala","groovy",
    # C family
    "c",   "cpp",  "cc",   "cxx",  "h",    "hpp",
    # C# / .NET
    "cs",  "vb",
    # Database
    "sql",
    # Sistemi / infra
    "tf",  "hcl",  "env",  "dockerfile",
    # Altri linguaggi popolari
    "go",  "rs",   "swift","dart",
    "rb",  "php",  "pl",   "pm",
    "r",   "lua",  "ex",   "exs",
    # Config
    "conf","cfg",  "properties","prefs",
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
            btn_row, text="Scegli cartella\u2026",
            font=self.F_SMALL, height=36, width=170,
            fg_color=BORDER, hover_color="#ccc9c0",
            text_color=TEXT, corner_radius=8,
            command=self._choose_folder
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="Scegli file\u2026",
            font=self.F_SMALL, height=36, width=140,
            fg_color=BORDER, hover_color="#ccc9c0",
            text_color=TEXT, corner_radius=8,
            command=self._choose_files
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="\U0001f5d1  Svuota lista",
            font=self.F_SMALL, height=36, width=140,
            fg_color="#fde8df", hover_color="#f9cfc0",
            text_color=ACCENT, corner_radius=8,
            command=self._clear_sources
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

        # Sottosezione scrollabile per le checkbox — altezza fissa, scorribile
        scroll_frame = ctk.CTkScrollableFrame(
            ext_card,
            fg_color="transparent",
            height=180,                           # altezza visibile
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=MUTED,
        )
        scroll_frame.pack(fill="x", padx=14, pady=(14, 6))

        # --- INIZIO GESTIONE GRIGLIA DINAMICA ---
        self._ext_checkboxes = []
        
        # 1. Creiamo le checkbox e le salviamo in una lista (senza posizionarle subito)
        for ext in EXTENSIONS:
            cb = ctk.CTkCheckBox(
                scroll_frame, text=f".{ext}",
                variable=self.ext_vars[ext],
                font=self.F_BODY,
                fg_color=ACCENT, hover_color=ACCENT_H,
                checkmark_color="#fff",
                border_color=BORDER,
                text_color=TEXT, corner_radius=5
            )
            self._ext_checkboxes.append(cb)

        self._current_cols = 0

        # 2. Funzione che ricalcola e riposiziona la griglia in base alla larghezza
        def reflow_grid(event):
            # Aumentiamo i margini di sicurezza (40px invece di 28px)
            available_width = event.width - 40 
            
            # Portiamo l'ingombro stimato a 140px per colonna. 
            # In questo modo la colonna scatta SOLO quando c'è spazio abbondante 
            # anche per i testi più lunghi.
            cols = max(1, available_width // 140)

            # Ridisegniamo la griglia solo se il numero di colonne è cambiato
            if cols != self._current_cols:
                self._current_cols = cols
                for i, cb in enumerate(self._ext_checkboxes):
                    cb.grid(row=i // cols, column=i % cols, sticky="w", padx=10, pady=6)

        # 3. Leghiamo l'evento di ridimensionamento alla "ext_card" madre
        ext_card.bind("<Configure>", reflow_grid)
        # --- FINE GESTIONE GRIGLIA DINAMICA ---

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
        # Aggiunge i nuovi path a quelli già presenti, senza duplicati
        existing = set(os.path.abspath(p) for p in self._sources)
        for p in paths:
            ap = os.path.abspath(p)
            if ap not in existing:
                existing.add(ap)
                self._sources.append(p)

        self._refresh_drop_label()

        # Scansiona le estensioni su TUTTE le sorgenti accumulate
        self._set_status("Scansione estensioni…", MUTED)
        threading.Thread(target=self._scan_and_check,
                         args=(list(self._sources),), daemon=True).start()

    def _refresh_drop_label(self):
        """Aggiorna la label della drop zone in base alle sorgenti accumulate."""
        n = len(self._sources)
        if n == 0:
            self._drop_label.configure(
                text="⬇   Trascina qui\nfile · cartelle · .zip",
                text_color=MUTED
            )
        elif n == 1:
            name = os.path.basename(self._sources[0]) or self._sources[0]
            self._drop_label.configure(
                text=f"✓  {name}",
                text_color=SUCCESS
            )
        else:
            self._drop_label.configure(
                text=f"✓  {n} elementi in lista",
                text_color=SUCCESS
            )

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

    # ── Svuota lista ────────────────────────────────────────────
    def _clear_sources(self):
        self._sources = []
        self._refresh_drop_label()
        for ext, var in self.ext_vars.items():
            var.set(1 if ext in DEFAULT_ON else 0)
        self._set_status("Lista svuotata.", MUTED)

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
