"""
Skrypt do budowania exe z obfuskacją kodu
Używa PyInstaller + PyArmor do ochrony kodu
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

def build_exe():
    """Buduje exe z obfuskacją"""
    
    # Zmienne do śledzenia statusu
    obfuscation_success = False
    obfuscation_warnings = []
    build_success = False
    build_warnings = []
    
    print("=" * 60)
    print("Budowanie M2Watcher.exe z obfuskacją")
    print("=" * 60)
    
    # Sprawdź czy PyArmor jest zainstalowany
    try:
        import pyarmor
        print("✓ PyArmor zainstalowany")
    except ImportError:
        print("✗ PyArmor nie jest zainstalowany")
        print("Instalowanie PyArmor...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyarmor"], check=True)
    
    # Sprawdź czy PyInstaller jest zainstalowany
    try:
        import PyInstaller
        print("✓ PyInstaller zainstalowany")
    except ImportError:
        print("✗ PyInstaller nie jest zainstalowany")
        print("Instalowanie PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # Krok 1: Obfuskacja kodu (opcjonalna)
    print("\n[1/3] Obfuskacja kodu...")
    
    # Sprawdź czy pyarmor jest dostępny jako komenda
    try:
        result = subprocess.run(["pyarmor", "--version"], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        pyarmor_available = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pyarmor_available = False
    
    if not pyarmor_available:
        print("  ⚠ PyArmor nie jest dostępny jako komenda - pomijam obfuskację")
        print("  💡 Aby użyć obfuskacji, zainstaluj PyArmor i upewnij się że jest w PATH")
        print("  💡 Lub użyj: pip install pyarmor && pyarmor gen --help")
        obfuscated_dir = None
        obfuscation_warnings.append("PyArmor nie jest dostępny - kod nie został zobfuskowany")
    else:
        obfuscated_dir = Path("obfuscated")
        if obfuscated_dir.exists():
            shutil.rmtree(obfuscated_dir)
        
        # Obfuskuj główne pliki
        files_to_obfuscate = ["m2watcher.py", "config.py", "notifications.py"]
        obfuscated_files = []
        failed_files = []
        
        for file in files_to_obfuscate:
            if Path(file).exists():
                print(f"  Obfuskowanie {file}...")
                try:
                    subprocess.run([
                        "pyarmor", "gen",
                        "--output", str(obfuscated_dir),
                        file
                    ], check=True, timeout=60)
                    obfuscated_files.append(file)
                except subprocess.CalledProcessError as e:
                    print(f"  ⚠ Błąd obfuskacji {file}: {e}")
                    print("  💡 Kontynuuję bez obfuskacji tego pliku")
                    failed_files.append(file)
                    obfuscation_warnings.append(f"Nie udało się zobfuskowac {file}")
                except subprocess.TimeoutExpired:
                    print(f"  ⚠ Timeout podczas obfuskacji {file}")
                    print("  💡 Kontynuuję bez obfuskacji tego pliku")
                    failed_files.append(file)
                    obfuscation_warnings.append(f"Timeout podczas obfuskacji {file}")
        
        # Sprawdź czy obfuskacja się powiodła
        if obfuscated_files and obfuscated_dir.exists():
            main_obfuscated = obfuscated_dir / "m2watcher.py"
            if main_obfuscated.exists():
                obfuscation_success = True
                print(f"  ✓ Zobfuskowano {len(obfuscated_files)}/{len(files_to_obfuscate)} plików")
            else:
                obfuscation_warnings.append("Główny plik m2watcher.py nie został zobfuskowany")
        else:
            obfuscation_warnings.append("Obfuskacja nie powiodła się - używane będą oryginalne pliki")
    
    # Krok 2: Budowanie exe
    print("\n[2/3] Budowanie exe...")
    
    # Określ pliki źródłowe (obfuskowane lub oryginalne)
    if obfuscated_dir and obfuscated_dir.exists():
        main_file = obfuscated_dir / "m2watcher.py"
        config_file = obfuscated_dir / "config.py"
        notifications_file = obfuscated_dir / "notifications.py"
        
        if not main_file.exists():
            print("  ⚠ Obfuskowany plik główny nie istnieje, używam oryginalnego")
            main_file = Path("m2watcher.py")
    else:
        main_file = Path("m2watcher.py")
        config_file = Path("config.py")
        notifications_file = Path("notifications.py")
    
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
    
    # Dodaj pliki pomocnicze jeśli istnieją
    additional_files = []
    for file_path, name in [
        (config_file, "config.py"),
        (notifications_file, "notifications.py")
    ]:
        if file_path.exists():
            # Format dla Windows: "source;destination"
            additional_files.append(f"{file_path};.")
    
    if additional_files:
        for file_data in additional_files:
            pyinstaller_args.extend(["--add-data", file_data])
    
    # Dodaj ukryte importy - wszystkie wymagane moduły
    hidden_imports = [
        "config",
        "notifications",
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
    
    # Krok 3: Czyszczenie
    print("\n[3/3] Czyszczenie...")
    
    # Usuń tymczasowe pliki (opcjonalnie - można zostawić dla debugowania)
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
    
    # Status obfuskacji
    print(f"\n📦 STATUS OBFUSKACJI:")
    if obfuscation_success:
        print("  ✓ Kod został zobfuskowany")
    else:
        print("  ⚠ Kod NIE został zobfuskowany")
        if obfuscation_warnings:
            print("  Powody:")
            for warning in obfuscation_warnings:
                print(f"    • {warning}")
        print("  ⚠ UWAGA: Plik exe zawiera nieobfuskowany kod źródłowy!")
        print("  💡 Aby włączyć obfuskację:")
        print("     1. Zainstaluj PyArmor: pip install pyarmor")
        print("     2. Upewnij się że 'pyarmor' jest w PATH")
        print("     3. Uruchom ponownie: python build_exe.py")
    
    # Ostrzeżenia budowania
    if build_warnings:
        print(f"\n⚠ OSTRZEŻENIA BUDOWANIA:")
        for warning in build_warnings:
            print(f"  • {warning}")
    
    # Podsumowanie
    print(f"\n{'=' * 60}")
    if build_success and exe_exists:
        if obfuscation_success:
            print("✓ Budowanie zakończone pomyślnie z obfuskacją!")
        else:
            print("✓ Budowanie zakończone pomyślnie (BEZ obfuskacji)")
            print("⚠ Kod źródłowy nie jest chroniony przed dekompilacją")
    else:
        print("✗ Budowanie zakończone z błędami")
        print("  Sprawdź komunikaty powyżej i popraw błędy")
    print("=" * 60)

if __name__ == "__main__":
    build_exe()

