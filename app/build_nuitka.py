"""
Buduje M2Watcher.exe Nuitką — kompilacja Pythona do C (jeden plik, bez okna konsoli).

    pip install -r requirements-nuitka.txt
    python build_nuitka.py

Po co druga ścieżka obok PyInstallera (build_exe.py): Nuitka tłumaczy kod Pythona na C i
kompiluje do prawdziwej binarki. Nie ma archiwum PYZ ani typowego bootloadera PyInstallera,
na którym uczą się modele antywirusowe, więc skompilowany plik zwykle dostaje mniej fałszywych
alarmów. Metadane wersji, ikonę i brak konsoli ustawiamy tak samo jak w PyInstallerze.

Wymaga kompilatora C: na Windowsie MSVC albo pobierane przez Nuitkę MinGW-w64; na Linuksie gcc.
Pierwsza kompilacja jest wolna (kilka–kilkanaście minut).
"""
import subprocess
import sys
from pathlib import Path

from build_exe import COMPANY, COPYRIGHT, DESCRIPTION, PRODUCT, version_tuple
from version import __version__

HERE = Path(__file__).resolve().parent
ICON = HERE / "assets" / "m2watcher.ico"
DIST = HERE / "dist"


def main() -> int:
    try:
        import nuitka  # noqa: F401
    except ImportError:
        print("Brak Nuitki: pip install -r requirements-nuitka.txt")
        return 1

    v = version_tuple(__version__)
    version_str = ".".join(map(str, v))

    args = [
        sys.executable, "-m", "nuitka",
        "--onefile",                       # jeden plik
        "--assume-yes-for-downloads",      # pobierz zależności (np. MinGW/ccache) bez pytania
        "--enable-plugin=tk-inter",        # tkinter (GUI)
        "--include-package=psutil",
        "--windows-console-mode=disable",  # bez okna konsoli (ignorowane poza Windows)
        f"--output-dir={DIST}",
        "--output-filename=M2Watcher.exe",
        "--company-name=" + COMPANY,
        "--product-name=" + PRODUCT,
        "--file-version=" + version_str,
        "--product-version=" + version_str,
        "--file-description=" + DESCRIPTION,
        "--copyright=" + COPYRIGHT,
        "--remove-output",                 # sprzątnij pliki pośrednie
        "main.py",
    ]
    if ICON.exists():
        args.insert(args.index("main.py"), f"--windows-icon-from-ico={ICON}")
    # pywin32 tylko na Windowsie
    if sys.platform == "win32":
        for mod in ("win32gui", "win32process", "pywintypes", "winsound"):
            args.insert(args.index("main.py"), f"--include-module={mod}")

    print("Kompilacja Nuitką:", " ".join(a for a in args[3:] if not a.startswith("--copyright")))
    result = subprocess.run(args, cwd=HERE)
    if result.returncode != 0:
        print("✗ Nuitka zakończyła się błędem")
        return result.returncode

    exe = DIST / ("M2Watcher.exe" if sys.platform == "win32" else "M2Watcher.bin")
    if not exe.exists():
        # Nuitka poza Windows nadaje nazwę z --output-filename bez rozszerzenia .exe czasem inaczej
        candidates = list(DIST.glob("M2Watcher*"))
        exe = candidates[0] if candidates else exe
    if not exe.exists():
        print(f"✗ Nie znaleziono zbudowanego pliku w {DIST}")
        return 1
    print(f"✓ Gotowe: {exe} ({exe.stat().st_size / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
