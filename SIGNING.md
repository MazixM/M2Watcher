# Podpis cyfrowy M2Watcher (darmowo, dla open source)

Niepodpisany `M2Watcher.exe` bywa oznaczany przez antywirusy i blokowany przez SmartScreen/Chrome —
to fałszywe alarmy (patrz [issue #7](https://github.com/MazixM/M2Watcher/issues/7)). Zmiany w buildzie
(brak UPX, bootloader ze źródeł, metadane) je ograniczają, ale **jedyne, co realnie daje „zero ostrzeżeń”,
to podpis cyfrowy**. Kupno certyfikatu code signing kosztuje ~300–500 zł/rok; ten dokument opisuje, jak
zdobyć go **za darmo** przez program dla projektów open source i włączyć podpisywanie w CI.

## 1. Wniosek do SignPath Foundation (darmowy podpis dla OSS)

[SignPath](https://about.signpath.io/product/open-source) podpisuje builds projektów open source swoim
certyfikatem i swoją infrastrukturą, za darmo. Warunki (M2Watcher je spełnia):

- publiczne repozytorium na GitHubie (OSI-zgodna licencja — warto dopisać `LICENSE`, np. MIT),
- build w publicznym CI (mamy GitHub Actions `build.yml`),
- brak płatnego/komercyjnego charakteru.

Kroki:

1. Dodaj do repo plik `LICENSE` z jasną licencją open source (SignPath tego wymaga; dziś README mówi
   tylko „Open Source”). Bez tego wniosek odpadnie.
2. Wejdź na <https://about.signpath.io/product/open-source> i złóż wniosek (formularz „Apply”).
   Podaj link do repo `MazixM/M2Watcher` i do workflow `build.yml`.
3. Po akceptacji SignPath utworzy dla Ciebie:
   - **Organization ID** (GUID),
   - **Project** (slug, np. `m2watcher`),
   - **Signing Policy** (slug, np. `release-signing`),
   - **API token** (do CI).

## 2. Konfiguracja w repo (po akceptacji)

W ustawieniach repo GitHub (**Settings → Secrets and variables → Actions**) dodaj:

| Nazwa | Typ | Wartość |
|---|---|---|
| `SIGNPATH_API_TOKEN` | Secret | token z SignPath |
| `SIGNPATH_ORGANIZATION_ID` | Variable | Organization ID (GUID) |
| `SIGNPATH_PROJECT_SLUG` | Variable | slug projektu |
| `SIGNPATH_POLICY_SLUG` | Variable | slug polityki podpisu |

## 3. Krok podpisywania w CI (gotowy do wklejenia)

Dopiero **po** dodaniu sekretów wstaw ten job do `.github/workflows/build.yml` (między `build`
a `release`). Dopóki `SIGNPATH_API_TOKEN` jest pusty, job się pomija — nie psuje CI:

```yaml
  sign:
    needs: build
    if: ${{ github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository }}
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write   # SignPath weryfikuje pochodzenie builda po OIDC
    steps:
    - name: Podpisz M2Watcher.exe (SignPath)
      id: sign
      if: ${{ secrets.SIGNPATH_API_TOKEN != '' }}
      uses: signpath/github-action-submit-signing-request@v1
      with:
        api-token: ${{ secrets.SIGNPATH_API_TOKEN }}
        organization-id: ${{ vars.SIGNPATH_ORGANIZATION_ID }}
        project-slug: ${{ vars.SIGNPATH_PROJECT_SLUG }}
        signing-policy-slug: ${{ vars.SIGNPATH_POLICY_SLUG }}
        github-artifact-id: ${{ needs.build.outputs.artifact_id }}   # patrz niżej
        wait-for-completion: true
        output-artifact-directory: signed
    - name: Wyślij podpisany artefakt
      if: ${{ steps.sign.outcome == 'success' }}
      uses: actions/upload-artifact@v4
      with:
        name: M2Watcher.exe   # nadpisuje niepodpisany
        path: signed/M2Watcher.exe
```

Do tego w jobie `build` trzeba wystawić `artifact_id` (SignPath pobiera artefakt po ID):

```yaml
    outputs:
      artifact_id: ${{ steps.upload.outputs.artifact-id }}
```

A job `release` powinien pobierać artefakt **po podpisaniu** (dodać `needs: [build, sign]`).

> Dokładne nazwy wejść potwierdź w README akcji `signpath/github-action-submit-signing-request` w wersji,
> którą przypniesz — API bywa aktualizowane, a slugi/ID dostajesz dopiero przy akceptacji.

## 4. Weryfikacja

Po podpisaniu:

- `M2Watcher.exe` ma zakładkę **Podpisy cyfrowe** we właściwościach pliku (Windows),
- SmartScreen przestaje straszyć „nieznany wydawca” (reputacja podpisanego wydawcy rośnie z pobraniami),
- liczba wykryć na VirusTotal spada — większość silników ML mocno ufa podpisanym plikom.

## Alternatywy (gdyby SignPath odmówił)

- **Azure Trusted Signing** — ~10 USD/mies., certyfikat zarządzany przez Microsoft (nie „za darmo”, ale tanio).
- **Certum Open Source Code Signing** — tani certyfikat dla OSS (kilkadziesiąt zł/rok), na karcie/w chmurze.
