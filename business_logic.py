# business_logic.py
import os
import zipfile
import tempfile
import shutil
from typing import List


def _collect_files(path: str, extensions: List[str], out: list, tmp_dirs: list):
    """Raccoglie ricorsivamente i file corrispondenti alle estensioni."""
    if os.path.isdir(path):
        for root, _dirs, files in os.walk(path):
            for f in sorted(files):
                fp = os.path.join(root, f)
                if f.lower().endswith(".zip"):
                    _collect_files(fp, extensions, out, tmp_dirs)
                elif any(f.lower().endswith("." + e) for e in extensions):
                    out.append(fp)

    elif zipfile.is_zipfile(path):
        tmp = tempfile.mkdtemp(prefix="unisci_")
        tmp_dirs.append(tmp)
        with zipfile.ZipFile(path, "r") as z:
            z.extractall(tmp)
        _collect_files(tmp, extensions, out, tmp_dirs)

    elif os.path.isfile(path):
        if any(path.lower().endswith("." + e) for e in extensions):
            out.append(path)


def scan_extensions(sources: List[str]) -> List[str]:
    """
    Scansiona le sorgenti (cartelle, file, zip) e restituisce
    la lista delle estensioni trovate (senza punto, lowercase).
    """
    found = set()
    tmp_dirs = []

    def _scan(path):
        if os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                for f in files:
                    if f.lower().endswith(".zip"):
                        _scan(os.path.join(root, f))
                    else:
                        ext = os.path.splitext(f)[1].lstrip(".").lower()
                        if ext:
                            found.add(ext)
        elif zipfile.is_zipfile(path):
            with zipfile.ZipFile(path, "r") as z:
                for name in z.namelist():
                    ext = os.path.splitext(name)[1].lstrip(".").lower()
                    if ext:
                        found.add(ext)
        elif os.path.isfile(path):
            ext = os.path.splitext(path)[1].lstrip(".").lower()
            if ext:
                found.add(ext)

    for s in sources:
        _scan(s)

    for d in tmp_dirs:
        shutil.rmtree(d, ignore_errors=True)

    return sorted(found)


def merge_files(
    sources: List[str],
    extensions: List[str],
    output_name: str = "output.txt"
) -> str:
    """
    Unisce tutti i file corrispondenti a `extensions` trovati in `sources`.
    `sources` può contenere: cartelle, file singoli, archivi .zip.
    Restituisce il percorso assoluto del file generato.
    """
    # Trova la cartella genitore comune a tutte le sorgenti
    abs_sources = [os.path.abspath(s) for s in sources]
    dirs = [s if os.path.isdir(s) else os.path.dirname(s) for s in abs_sources]
    base_dir = os.path.commonpath(dirs) if len(dirs) > 1 else dirs[0]
    # Se commonpath punta a una sottocartella inclusa nelle sorgenti, sali di un livello
    for s in abs_sources:
        if os.path.isdir(s) and os.path.abspath(s) == os.path.abspath(base_dir):
            parent = os.path.dirname(base_dir)
            if parent and parent != base_dir:
                base_dir = parent
            break
    output_path = os.path.abspath(os.path.join(base_dir, output_name))

    tmp_dirs: list = []
    files_to_merge: list = []

    for source in sources:
        _collect_files(source, extensions, files_to_merge, tmp_dirs)

    # Rimuovi duplicati mantenendo ordine, escludi l'output stesso
    seen = set()
    unique_files = []
    for f in files_to_merge:
        key = os.path.abspath(f)
        if key != os.path.abspath(output_path) and key not in seen:
            seen.add(key)
            unique_files.append(f)

    try:
        with open(output_path, "w", encoding="utf-8") as out:
            out.write("=" * 72 + "\n")
            out.write(f"  FileFusion  |  {len(unique_files)} file\n")
            out.write("=" * 72 + "\n\n")

            for fp in unique_files:
                try:
                    rel = os.path.relpath(fp, base_dir)
                except ValueError:
                    rel = fp
                out.write(f"┌{'─' * 70}┐\n")
                out.write(f"│  {rel:<68}│\n")
                out.write(f"└{'─' * 70}┘\n")
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as src:
                        content = src.read()
                        out.write(content)
                        if not content.endswith("\n"):
                            out.write("\n")
                except Exception as e:
                    out.write(f"[ERRORE LETTURA: {e}]\n")
                out.write("\n")

            out.write("\n" + "=" * 72 + "\n")
            out.write(f"  {len(unique_files)} file uniti\n")
            out.write("=" * 72 + "\n")
    finally:
        for d in tmp_dirs:
            shutil.rmtree(d, ignore_errors=True)

    return output_path
