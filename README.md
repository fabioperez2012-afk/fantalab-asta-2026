# Fantalab Asta 2026/27

Webapp Streamlit per seguire dal vivo l'asta FantaCalcio Mantra 2026/27: cerchi un
nome, vedi subito se prenderlo e fino a quanti crediti spingerti, lo segni come
preso e il budget si aggiorna da solo. Pensata per stare aperta su un secondo
schermo/tablet durante l'asta.

**App online:** _(incolla qui il link dopo il deploy su Streamlit Community Cloud — vedi sotto)_

---

## Cosa c'è dentro

- **Ricerca full-text** tollerante ad accenti/maiuscole, con risultati istantanei.
- **Filtri combinabili**: ruolo Mantra (multi-ruolo gestito correttamente: un
  giocatore "Ds;Dc" compare sia filtrando Ds sia filtrando Dc), squadra, giudizio,
  fascia di crediti max, "nascondi già presi", "solo con consiglio".
- **Budget configurabile** (default 600): cambialo in sidebar e tutti i crediti
  massimi consigliati si ricalcolano all'istante per ogni giocatore.
- **Giudizi con badge colorato**: verde = prendi, rosso = evita/trappola,
  arancio = solo sotto soglia, viola = da verificare, grigio = nessun consiglio
  (i giocatori del listone senza un consiglio esplicito nella guida restano
  comunque visibili e ricercabili, semplicemente "puliti" — nessun colore o
  credito inventato).
- **Tab "Per ruolo"**: giocatori raggruppati per ruolo Mantra, per confrontare al
  volo le alternative in un reparto (replica la logica della guida PDF per ruolo).
- **Tab "In evidenza"**: trappole assolute e occasioni/regali della guida, sempre
  a un tap di distanza.
- **Monitoraggio asta in tempo reale**: segna "Preso da me" (con prezzo pagato) o
  "Preso da altri", contatore di crediti spesi/rimanenti/giocatori presi sempre
  visibile in alto, possibilità di annullare l'ultima assegnazione, esportazione
  della rosa finale in CSV.
- **Stato persistente**: lo stato dell'asta vive in `st.session_state` e viene
  salvato automaticamente in `data/asta_state.json` ad ogni modifica, così se il
  browser si chiude per sbaglio a metà asta non perdi nulla (basta che l'app
  resti in esecuzione sullo stesso hosting).

### Una scelta di design rispetto al prompt originale
Il "Per ruolo" e "La mia rosa" sono implementati come **tab dentro un'unica
pagina** invece che come pagine separate in `pages/`: durante un'asta dal vivo
cambiare tab è istantaneo (nessun reload), mentre le multipage di Streamlit
ricaricano lo script. Tutto il resto segue lo schema richiesto.

---

## Struttura del repo

```
fantalab-asta-2026/
├── app.py                     # entry point Streamlit (UI, tab, orchestrazione)
├── lib/
│   ├── data.py                 # caricamento players.csv con cache
│   ├── state.py                # stato asta live + persistenza JSON
│   └── ui.py                   # CSS, header sticky, filtri, card giocatore
├── scripts/
│   └── build_dataset.py        # merge listone + guida -> data/players.csv
├── data/
│   ├── players.csv             # dataset generato (committato)
│   ├── asta_state.json         # stato live (NON committato, in .gitignore)
│   └── raw/                    # file sorgente originali
│       ├── Quotazioni_Fantacalcio_Stagione_2026_27.xlsx
│       ├── cheat_sheet_alfabetico.txt
│       ├── trappole_assolute.txt
│       └── occasioni_regali.txt
├── requirements.txt
├── .streamlit/config.toml      # tema colori
└── README.md
```

---

## Come lanciarla in locale

```bash
python3 -m venv .venv
source .venv/bin/activate        # su Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Si apre automaticamente su `http://localhost:8501`.

---

## Come aggiornare i dati (listone o guida diversi/nuova stagione)

1. Sostituisci i file in `data/raw/` con le versioni nuove:
   - `Quotazioni_Fantacalcio_Stagione_2026_27.xlsx` (deve avere un foglio
     "Tutti" con colonne `Id, R, RM, Nome, Squadra, ...` e idealmente un foglio
     "Ceduti" con lo stesso formato per i giocatori trasferiti/non più in Serie A).
   - `cheat_sheet_alfabetico.txt`, `trappole_assolute.txt`, `occasioni_regali.txt`:
     trascrizioni pulite pipe-separated (`|`) della guida — se cambia la guida PDF,
     aggiorna questi tre file a mano seguendo lo stesso formato (ogni riga è già
     un esempio). Sono trascrizioni manuali e non estrazione automatica dal PDF
     perché l'impaginazione a due colonne dei PDF guida rende l'estrazione
     automatica del testo poco affidabile (le righe si spezzano in punti
     imprevedibili); farlo a mano garantisce l'accuratezza dei consigli.
2. Rilancia lo script di merge:
   ```bash
   python3 scripts/build_dataset.py
   ```
   Lo script stampa a schermo un report con eventuali nomi della guida non
   trovati nel listone (da verificare a mano) e il numero di giocatori con
   consiglio esplicito.
3. Ricommitta `data/players.csv` (e i file in `data/raw/` se cambiati).

L'app legge sempre e solo `data/players.csv` (con caching `st.cache_data`): non
tocca mai i PDF/Excel originali a runtime.

---

## Come mettere il codice su GitHub (da zero)

Se non hai ancora un repository, apri il terminale nella cartella
`fantalab-asta-2026` ed esegui, in ordine:

```bash
# 1. inizializza git nella cartella del progetto
git init

# 2. aggiungi tutti i file
git add .

# 3. primo commit
git commit -m "Prima versione: webapp asta Fantacalcio Mantra 2026/27"

# 4. crea un repository vuoto su GitHub (via sito, senza README/licenza),
#    poi collega questo repo locale a quello remoto — sostituisci
#    TUO-USERNAME e NOME-REPO con i tuoi:
git branch -M main
git remote add origin https://github.com/TUO-USERNAME/NOME-REPO.git

# 5. push
git push -u origin main
```

Se GitHub ti chiede login, usa un Personal Access Token (non la password) come
password quando richiesto, oppure autenticati con `gh auth login` se hai la
GitHub CLI installata.

---

## Come pubblicarla su Streamlit Community Cloud (gratis)

1. Vai su **https://share.streamlit.io** e accedi con il tuo account GitHub.
2. Clicca **"New app"**.
3. Seleziona il repository appena creato, il branch `main` e come **Main file
   path** scrivi `app.py`.
4. Clicca **"Deploy"**. Il primo deploy impiega 1-2 minuti (installa le
   dipendenze da `requirements.txt`).
5. Ottieni un link pubblico tipo `https://tuo-nome-app.streamlit.app` —
   aprilo da telefono/tablet per l'asta di stasera.

Se aggiorni `data/players.csv` o il codice in futuro, basta fare
`git push`: Streamlit Cloud ridistribuisce l'app automaticamente in pochi secondi.

**Nota sullo stato persistente in cloud**: `data/asta_state.json` vive sul
filesystem dell'istanza Streamlit Cloud, quindi sopravvive a refresh/chiusura
del browser finché l'app resta attiva sulla stessa istanza. Se l'app va in
sleep per inattività prolungata e si riavvia, o se la ridistribuisci con un
nuovo push durante l'asta, lo stato locale si perde: per un'asta live è
comunque una rete di sicurezza in più, ma il vero salvataggio "che conta" resta
`st.session_state` finché il browser è aperto — evita di fare push a metà asta.

---

## Note di trasparenza sui dati

- I giocatori del listone **senza un consiglio esplicito nella guida** restano
  visibili e ricercabili con badge grigio "Nessun consiglio — valutazione
  libera": nessun colore o credito inventato.
- Alcuni nomi della guida non hanno trovato una corrispondenza univoca nel
  listone (es. nomi alternativi incerti come "Diao"/"Dio", o "Israel" a
  Torino): restano comunque visibili con badge "Da verificare" e la nota
  originale della guida, invece di sparire silenziosamente.
- Due nomi della guida ("Bobby Malen"/Leão e Anjorin) risultano tra i
  **giocatori ceduti** nel foglio "Ceduti" del listone: l'app li segnala con
  badge dedicato "Ceduto / non disponibile" invece di un generico "non trovato".
- Quando la guida indicava una squadra diversa da quella nel listone attuale
  (es. un giocatore scambiato dopo la stesura della guida), la motivazione
  mostrata include una nota esplicita del disallineamento.

In bocca al lupo per l'asta! 🏆
