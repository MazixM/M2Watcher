#!/usr/bin/env python3
"""Wysyła plik na VirusTotal i wypisuje liczbę wykryć — informacyjnie w CI.

    VT_API_KEY=... python vt_scan.py <ścieżka-do-pliku>

Nie przerywa builda przy błędzie ani przy wykryciach: celem jest pomiar (ile silników oznacza
świeży exe), żeby było widać, czy zmiany zmniejszają fałszywe alarmy. Wynik trafia do
podsumowania joba i do wyjść kroku (``result``, ``url``), które komentarz w PR pokazuje przy
linku do pobrania. Używa publicznego API VirusTotal (darmowe konto: 4 zapytania/min, 500/dzień).
"""
import hashlib
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Optional

API = "https://www.virustotal.com/api/v3"


def _req(url: str, key: str, data: Optional[bytes] = None, headers: Optional[dict] = None) -> dict:
    import json
    req = urllib.request.Request(url, data=data, headers={"x-apikey": key, **(headers or {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def _emit(result: str, url: str = "") -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"result={result}\n")
            f.write(f"url={url}\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            link = f"[{result}]({url})" if url else result
            f.write(f"### 🛡️ VirusTotal: {link}\n")
    print(f"VirusTotal: {result} {url}".strip())


def main(argv) -> int:
    key = os.environ.get("VT_API_KEY", "")
    if not key or len(argv) < 2:
        _emit("pominięto (brak klucza lub pliku)")
        return 0
    path = argv[1]
    try:
        data = open(path, "rb").read()
    except OSError as e:
        _emit(f"nie odczytano pliku ({e})")
        return 0

    sha256 = hashlib.sha256(data).hexdigest()
    gui_url = f"https://www.virustotal.com/gui/file/{sha256}"

    try:
        # Najpierw sprawdź, czy plik już jest znany (bez zużywania limitu na upload)
        try:
            report = _req(f"{API}/files/{sha256}", key)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            report = None

        if report is None:
            # Nowy plik — wyślij do analizy
            boundary = "----m2watcherVT"
            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(path)}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
            up = _req(f"{API}/files", key, data=body,
                      headers={"content-type": f"multipart/form-data; boundary={boundary}"})
            analysis_id = up["data"]["id"]
            deadline = time.time() + 300
            while time.time() < deadline:
                time.sleep(20)
                an = _req(f"{API}/analyses/{analysis_id}", key)
                if an["data"]["attributes"]["status"] == "completed":
                    break
            report = _req(f"{API}/files/{sha256}", key)

        stats = report["data"]["attributes"]["last_analysis_stats"]
        mal = stats.get("malicious", 0)
        total = sum(v for k, v in stats.items() if k in ("malicious", "undetected", "suspicious", "harmless"))
        result = f"{mal}/{total} wykryć"
        if mal:
            results = report["data"]["attributes"].get("last_analysis_results", {})
            flagged = sorted(k for k, v in results.items() if v.get("category") in ("malicious", "suspicious"))
            result += " (" + ", ".join(flagged[:8]) + ")"
        _emit(result, gui_url)
    except Exception as e:  # noqa: BLE001 — skan nie może wywalić builda
        _emit(f"błąd skanu ({e.__class__.__name__})", gui_url)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
