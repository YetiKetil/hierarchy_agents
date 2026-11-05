# HIERARKI med KI-agenter – studentpakke

I lederutviklingsøvelsen HIERARKI skal sju personer i et hierarki med tre nivåer ende opp med fire like kort hver. De kan bare skrive til nærmeste leder eller underordnede, og bare toppsjefen får vite hva oppgaven er.

Med denne pakken spiller sju KI-agenter øvelsen. En spillmotor håndhever reglene, hver agent ser bare sitt eget perspektiv, og hvert spill lagres som en fullstendig logg som kan spilles av, leses og analyseres. Du velger selv hvilken språkmodell som spiller, hva agentene får vite, og hvordan organisasjonen er satt opp.

Dette er kursmateriell. Spør læreren før du deler det utenfor kurset.

## Dette trenger du

- **Python 3.10 eller nyere** på egen maskin, eller Google Colab i nettleseren, uten installasjon.
- **En API-nøkkel** til Gemini (Google AI Studio) eller Claude (Anthropic Console).
  - Et chatabonnement er ikke det samme som API-tilgang. API-bruk settes opp og faktureres for seg hos hver leverandør.
  - Noen leverandører har et gratisnivå med strenge begrensninger.
- **Uten nøkkel** kan du likevel kjøre fasiten og testagentene. Begge er gratis og viser hvordan alt virker.

## Kom i gang

```bash
pip install -r requirements.txt

# Gratis: se fasiten løse oppgaven (norsk versjon)
python run.py betingelser/alle_kjenner_maalet.yaml --answer-key
```

Åpne `replay.html` i nettleseren og dra inn den nye filen fra mappen `logger`.

Deretter legger du inn nøkkelen:
1. Kopier `.env.example` til en ny fil som heter `.env`.
2. Fyll inn `GEMINI_API_KEY=...` eller `ANTHROPIC_API_KEY=...`.
3. Del aldri `.env`-filen.

Så kan du kjøre et kort prøvespill:

```bash
python run.py betingelser/prosedyre_lappet.yaml --model gemini-3.5-flash-lite --max-rounds 10
python run.py betingelser/prosedyre_lappet.yaml --model claude-haiku-5-5
```

De norske betingelsene ligger i `betingelser/`, og de engelske i `betingelser/en/`. Agentene spiller på språket betingelsen er skrevet på.

## Resultater

- **`replay.html`** viser et spill runde for runde, med kort, meldinger, agentenes private tanker og debriefen.
- **`python show_game.py <logg> --thoughts`** viser spillet som tekst.
- **`python summarize.py`** gir en tabell over alle spillene dine.

## Kostnad

Et fullt spill tar omtrent 100–250 API-kall. Sjekk leverandørens priser før du kjører mange spill.
- Begynn med `--answer-key`, og deretter `--max-rounds 10`.
- På et gratisnivå bør du legge til `--concurrent 1`.
- Modellnavn endrer seg, så sjekk leverandørenes modellister.

## Videre

`README.md` (engelsk) har mer om betingelsene og eksemplene. `ADVANCED.md` (engelsk) forklarer hvordan programmet er bygget, hvordan du lager egne betingelser, hvordan du legger til en ny modellleverandør, og gir ideer til eksperimenter. Der finnes også en ordliste over de norske navnene i koden.
