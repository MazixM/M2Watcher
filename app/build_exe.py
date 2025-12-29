"""
Skrypt do budowania exe
Używa PyInstaller do kompilacji aplikacji
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

def build_exe():
    """Buduje exe używając PyInstaller"""
    
    # Ustaw kodowanie UTF-8 dla stdout/stderr (potrzebne w Windows CI)
    if sys.platform == 'win32':
        try:
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except (AttributeError, ImportError):
            pass  # Jeśli nie można zmienić, kontynuuj z domyślnym
    
    build_success = False
    build_warnings = []
    
    print("=" * 60)
    print("Budowanie M2Watcher.exe")
    print("=" * 60)
    
    # Sprawdź czy PyInstaller jest zainstalowany
    try:
        import PyInstaller
        print("✓ PyInstaller zainstalowany")
    except ImportError:
        print("✗ PyInstaller nie jest zainstalowany")
        print("Instalowanie PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # Krok 1: Budowanie exe
    print("\n[1/2] Budowanie exe...")
    
    # Główny plik to main.py
    main_file = Path("main.py")
    
    # Sprawdź czy główny plik istnieje
    if not main_file.exists():
        print(f"  ✗ Błąd: Nie znaleziono pliku {main_file}")
        return
    
    # Przygotuj argumenty dla PyInstaller
    pyinstaller_args = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--onefile",
        "--name", "M2Watcher",
        "--console",
    ]
    
    # Dodaj ukryte importy - wszystkie wymagane moduły
    hidden_imports = [
        "main",
        "m2watcher",
        "config",
        "notifications",
        "discord_bot",
        "psutil",
        "psutil._pswindows",
        "psutil._psutil_windows",
        "psutil._psutil_linux",
        "psutil._psutil_osx",
        "win32gui",
        "win32process",
        "win32con",
        "win32api",
        "winsound",
        "requests",
        "requests.packages.urllib3",
        "discord",
        "discord.ext.commands",
        "discord.ext.tasks",
        "pywintypes",
    ]
    
    for module in hidden_imports:
        pyinstaller_args.extend(["--hidden-import", module])
    
    # Dodaj kolekcje danych (dla psutil i innych modułów z dodatkowymi plikami)
    pyinstaller_args.extend([
        "--collect-all", "psutil",
        "--collect-all", "requests",
        "--collect-all", "discord",
    ])
    
    # Wyklucz niepotrzebne moduły aby zmniejszyć rozmiar
    excludes = [
        "matplotlib",
        "numpy",
        "pandas",
        "PIL",
        "tkinter",
    ]
    
    for exclude in excludes:
        pyinstaller_args.extend(["--exclude-module", exclude])
    
    # Dodaj główny plik
    pyinstaller_args.append(str(main_file))
    
    print(f"  Budowanie z pliku: {main_file}")
    print(f"  Argumenty: {' '.join(pyinstaller_args[3:])}")  # Pomiń python -m PyInstaller
    
    # Uruchom PyInstaller
    try:
        result = subprocess.run(pyinstaller_args, check=True, capture_output=True, text=True)
        build_success = True
        print("  ✓ PyInstaller zakończył się sukcesem")
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Błąd podczas budowania exe: {e}")
        print("  💡 Sprawdź czy wszystkie zależności są zainstalowane")
        if e.stdout:
            print(f"  Output: {e.stdout[:500]}")
        if e.stderr:
            print(f"  Errors: {e.stderr[:500]}")
        build_warnings.append(f"Błąd budowania: {e}")
        return
    
    # Krok 2: Czyszczenie
    print("\n[2/2] Czyszczenie...")
    
    # Sprawdź czy jesteśmy w trybie CI (nieinteraktywnym)
    is_ci = os.getenv("CI") == "true" or os.getenv("NON_INTERACTIVE") == "true"
    
    # Usuń tymczasowe pliki (opcjonalnie - można zostawić dla debugowania)
    if is_ci:
        # W trybie CI zawsze czyść pliki tymczasowe
        cleanup = 'y'
        print("  Tryb CI wykryty - automatyczne czyszczenie plików tymczasowych")
    else:
        cleanup = input("  Czy usunąć pliki tymczasowe (build, *.spec)? [T/n]: ").strip().lower()
    
    if cleanup != 'n':
        if Path("build").exists():
            shutil.rmtree("build")
            print("  ✓ Usunięto katalog build/")
        
        # Usuń pliki .spec
        for spec_file in Path(".").glob("*.spec"):
            spec_file.unlink()
            print(f"  ✓ Usunięto {spec_file}")
    else:
        print("  ⚠ Pliki tymczasowe zachowane")
    
    print("\n" + "=" * 60)
    print("PODSUMOWANIE BUDOWANIA")
    print("=" * 60)
    
    # Sprawdź wynik
    exe_path = Path("dist") / "M2Watcher.exe"
    exe_exists = exe_path.exists()
    
    if exe_exists:
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n✓ SUKCES: Plik exe został utworzony")
        print(f"  Lokalizacja: {exe_path.absolute()}")
        print(f"  Rozmiar: {size_mb:.2f} MB")
        build_success = True
    else:
        print(f"\n✗ BŁĄD: Plik exe nie został utworzony")
        build_warnings.append("Plik exe nie istnieje w katalogu dist/")
    
    # Ostrzeżenia budowania
    if build_warnings:
        print(f"\n⚠ OSTRZEŻENIA BUDOWANIA:")
        for warning in build_warnings:
            print(f"  • {warning}")
    
    # Podsumowanie
    print(f"\n{'=' * 60}")
    if build_success and exe_exists:
        print("✓ Budowanie zakończone pomyślnie!")
    else:
        print("✗ Budowanie zakończone z błędami")
        print("  Sprawdź komunikaty powyżej i popraw błędy")
    print("=" * 60)

if __name__ == "__main__":
    build_exe()
