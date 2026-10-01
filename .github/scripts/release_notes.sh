#!/usr/bin/env bash
# Generuje opis release'u w formacie dotychczasowych wydań (v.1.0.x).
# Użycie: release_notes.sh <tag> <sha> <owner/repo> <nazwa_assetu_zip> [vt_result] [vt_url]
set -euo pipefail

TAG="$1"; SHA="$2"; REPO="$3"; ASSET="$4"
VT_RESULT="${5:-}"
VT_URL="${6:-}"
URL="https://github.com/${REPO}"

# Poprzedni tag w formacie v.X.Y.Z (najwyższy, różny od bieżącego)
PREV=$(git tag --list 'v*' | grep -E '^v\.?[0-9]+\.[0-9]+\.[0-9]+$' | grep -vx "$TAG" | sort -V | tail -n1 || true)

echo "## M2Watcher ${TAG}"
echo
echo "Automatycznie wygenerowany build z commit: \`${SHA}\`"
echo
echo "### 📦 Pobierz"
echo
echo "Pobierz plik **${ASSET}** z sekcji Assets poniżej, albo zawsze najnowszą wersję pod stałym linkiem:"
echo
echo "${URL}/releases/latest/download/${ASSET}"
echo

if [ -n "$VT_RESULT" ]; then
  echo "### 🛡️ VirusTotal"
  echo
  if [ -n "$VT_URL" ]; then
    echo "[${VT_RESULT}](${VT_URL})"
  else
    echo "${VT_RESULT}"
  fi
  echo
fi

echo "### 📝 Zmiany"
echo
if [ -n "$PREV" ]; then
  CHANGES=$(git log --no-merges --pretty='format:- %s' "${PREV}..${SHA}" || true)
  echo "${CHANGES:-- drobne poprawki}"
  echo
  echo "Zobacz [commity](${URL}/compare/${PREV}...${SHA})"
else
  echo "Zobacz [commity](${URL}/commits/${SHA})"
fi
echo
echo "### ⚙️ Instalacja"
echo
echo "1. Pobierz ${ASSET} i rozpakuj **cały** folder \`M2Watcher\` (exe + \`_internal\`) w dowolne miejsce"
echo "2. Uruchom \`M2Watcher.exe\` z tego folderu. Nie kopiuj samego exe gdzie indziej — bez \`_internal\` nie wystartuje (błąd \`python312.dll\`)"
echo "3. Przejdź kreator pierwszego uruchomienia — [instrukcja konfiguracji Discord](${URL}/blob/main/app/DISCORD_SETUP.md)"
echo
echo "Aktualizacja ze starszej wersji: zamknij M2Watcher i podmień cały folder — ustawienia są w \`%USERPROFILE%\\.m2watcher\` i zostaną zachowane."
