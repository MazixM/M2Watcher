"""
Buduje M2Watcher.exe (PyInstaller, jeden plik, bez okna konsoli).

    pip install -r requirements-build.txt
    python build_exe.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Brak PyInstallera: pip install -r requirements-build.txt")
        return 1

    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "M2Watcher",
        # pywin32 bywa pomijany przez analizę importów
        "--hidden-import", "win32gui", "--hidden-import", "win32process", "--hidden-import", "pywintypes",
        "--exclude-module", "numpy", "--exclude-module", "matplotlib", "--exclude-module", "PIL",
        "main.py",
    ]
    print("Budowanie:", " ".join(args[3:]))
    result = subprocess.run(args, cwd=HERE)
    if result.returncode != 0:
        print("✗ PyInstaller zakończył się błędem")
        return result.returncode

    exe = HERE / "dist" / ("M2Watcher.exe" if sys.platform == "win32" else "M2Watcher")
    if not exe.exists():
        print(f"✗ Nie znaleziono {exe}")
        return 1
    shutil.rmtree(HERE / "build", ignore_errors=True)
    for spec in HERE.glob("*.spec"):
        spec.unlink()
    print(f"✓ Gotowe: {exe} ({exe.stat().st_size / 1024 / 1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
