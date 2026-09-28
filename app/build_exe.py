"""
Buduje M2Watcher (PyInstaller) w trybie katalogowym (``--onedir``), bez okna konsoli.

    pip install -r requirements-build.txt
    python build_exe.py

Dlaczego ``--onedir``, a nie jeden plik: exe z ``--onefile`` przy starcie rozpakowuje się do
``%TEMP%`` i ma doklejone archiwum na końcu pliku (overlay). To wzorzec dropperów, który
podbija fałszywe alarmy antywirusów. Tryb katalogowy tego nie robi. Do dystrybucji cały
katalog ``dist/M2Watcher`` pakujemy w zip (robi to CI); użytkownik rozpakowuje i uruchamia
``M2Watcher.exe`` w środku.

Plik dostaje też metadane wersji (autor, opis, wersja) i ikonę — bez nich exe jest anonimowy,
co również zwiększa nieufność heurystyk. Podpis cyfrowy nakłada dopiero CI (osobny krok).
"""
import shutil
import subprocess
import sys
from pathlib import Path

from version import __version__

HERE = Path(__file__).resolve().parent
ICON = HERE / "assets" / "m2watcher.ico"

COMPANY = "MazixM"
PRODUCT = "M2Watcher"
DESCRIPTION = "M2Watcher — monitor klientów Metin2 (powiadomienia Discord, optymalizacja)"
COPYRIGHT = "© MazixM. Open Source (M2Watcher). https://github.com/MazixM/M2Watcher"


def version_tuple(version: str) -> tuple:
    """"2.1.0-dev+abc1234" → (2, 1, 0, 0). Cztery liczby, tak wymaga zasób wersji Windows."""
    core = version.lstrip("v.").split("-")[0].split("+")[0]
    parts = []
    for piece in core.split(".")[:4]:
        digits = "".join(c for c in piece if c.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def write_version_file(path: Path, version: str) -> None:
    """Zapisuje zasób VSVersionInfo (metadane widoczne we właściwościach pliku w Windows)."""
    v = version_tuple(version)
    path.write_text(f'''# Wygenerowane przez build_exe.py — metadane wersji exe
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={v},
    prodvers={v},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable(
        "041504b0",  # polski (0x0415), Unicode
        [
          StringStruct("CompanyName", "{COMPANY}"),
          StringStruct("FileDescription", "{DESCRIPTION}"),
          StringStruct("FileVersion", "{version}"),
          StringStruct("InternalName", "M2Watcher"),
          StringStruct("LegalCopyright", "{COPYRIGHT}"),
          StringStruct("OriginalFilename", "M2Watcher.exe"),
          StringStruct("ProductName", "{PRODUCT}"),
          StringStruct("ProductVersion", "{version}"),
        ],
      )
    ]),
    VarFileInfo([VarStruct("Translation", [0x0415, 1200])]),
  ],
)
''', encoding="utf-8")


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Brak PyInstallera: pip install -r requirements-build.txt")
        return 1

    version_file = HERE / "version_info.txt"
    write_version_file(version_file, __version__)

    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--windowed",
        "--name", "M2Watcher",
        # UPX podbija fałszywe alarmy (kompresja kojarzona z malware) — wyłączamy jawnie
        "--noupx",
        "--version-file", str(version_file),
        # pywin32 bywa pomijany przez analizę importów
        "--hidden-import", "win32gui", "--hidden-import", "win32process", "--hidden-import", "pywintypes",
        "--hidden-import", "winsound",
        "--exclude-module", "numpy", "--exclude-module", "matplotlib", "--exclude-module", "PIL",
        "main.py",
    ]
    if ICON.exists():
        args[args.index("main.py"):args.index("main.py")] = ["--icon", str(ICON)]
    print("Budowanie:", " ".join(args[3:]))
    result = subprocess.run(args, cwd=HERE)
    version_file.unlink(missing_ok=True)
    if result.returncode != 0:
        print("✗ PyInstaller zakończył się błędem")
        return result.returncode

    exe_name = "M2Watcher.exe" if sys.platform == "win32" else "M2Watcher"
    exe = HERE / "dist" / "M2Watcher" / exe_name
    if not exe.exists():
        print(f"✗ Nie znaleziono {exe}")
        return 1
    shutil.rmtree(HERE / "build", ignore_errors=True)
    for spec in HERE.glob("*.spec"):
        spec.unlink()
    folder = HERE / "dist" / "M2Watcher"
    total = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
    print(f"✓ Gotowe: {folder} ({total / 1024 / 1024:.1f} MB, exe: {exe.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
