"""
build_dataset.py
=================
Unisce il listone ufficiale (Excel) con la guida asta (consigli, crediti, giudizi)
in un unico dataset pulito: data/players.csv

Rilancialo ogni volta che aggiorni il listone o la guida:

    python scripts/build_dataset.py

Input attesi in data/raw/:
    - Quotazioni_Fantacalcio_Stagione_2026_27.xlsx   (foglio "Tutti")
    - cheat_sheet_alfabetico.txt   (trascrizione strutturata della guida CON CREDITI)
    - trappole_assolute.txt
    - occasioni_regali.txt

I tre file .txt sono trascrizioni pulite (pipe-separated, "|") dei rispettivi PDF,
fatte a mano per garantire l'accuratezza (i PDF guida hanno un'impaginazione a due
colonne che rende l'estrazione automatica del testo poco affidabile: le righe che
vanno a capo si spezzano in punti imprevedibili). Se aggiorni la guida PDF il prossimo
anno, aggiorna questi .txt con lo stesso formato (vedi righe di esempio) e rilancia
lo script: non serve toccare il resto del codice.

Output: data/players.csv, con un report a schermo dei nomi non trovati nel listone.
"""

import csv
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "players.csv"

LISTONE_XLSX = RAW / "Quotazioni_Fantacalcio_Stagione_2026_27.xlsx"
CHEAT_SHEET = RAW / "cheat_sheet_alfabetico.txt"
TRAPPOLE = RAW / "trappole_assolute.txt"
OCCASIONI = RAW / "occasioni_regali.txt"

BUDGET_RIFERIMENTO = 600  # budget su cui sono calcolati i crediti nella guida originale

# Ruoli Mantra validi (Por escluso: i portieri non seguono questa logica multiruolo)
RUOLI_MANTRA_VALIDI = ["Dc", "Dd", "Ds", "B", "E", "M", "C", "T", "W", "A", "Pc"]


# --------------------------------------------------------------------------------------
# Normalizzazione nomi (per il match tollerante tra guida e listone)
# --------------------------------------------------------------------------------------
def normalize_name(name: str) -> str:
    """Normalizza un nome per il confronto: minuscolo, senza accenti, senza
    parentesi/punteggiatura, spazi singoli. Gestisce anche apostrofi curvi."""
    if not name:
        return ""
    name = name.replace("’", "'").replace("‘", "'")
    name = re.sub(r"\(corr\.\)", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\([^)]*\)", "", name)  # rimuove altre parentesi es. (Lautaro)
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def split_multi_player_name(raw_name: str):
    """Alcune righe della guida confrontano due giocatori nello stesso slot
    (es. 'Heggem / Theate', 'Raimondo / Bobcek', 'Cristante / Konè M.').
    Le splittiamo in due voci distinte così ognuna trova il proprio match nel listone.
    Le ipotesi di nome alternativo per LO STESSO giocatore (es. 'Bobby Malen/Leao',
    scritte senza spazi attorno alla '/') restano invece un'unica voce irrisolta."""
    if " / " in raw_name:
        return [p.strip() for p in raw_name.split(" / ")]
    return [raw_name.strip()]


# --------------------------------------------------------------------------------------
# Parsing percentuali / crediti dalla guida
# --------------------------------------------------------------------------------------
def _to_float(s: str) -> float:
    return float(s.replace(",", "."))


def parse_pct_max(raw: str):
    """Estrae da una stringa tipo '4-5% (24-30cr)', '<1% (6cr)', '1-2cr', 'pari a Kelly'
    un intervallo di percentuale (pct_min, pct_max) sul budget di riferimento (600),
    così l'app può ricalcolare i crediti per qualsiasi budget a runtime.
    Ritorna (pct_min, pct_max, nota_testuale_se_non_numerico)."""
    if not raw or raw.strip() in ("", "—", "-"):
        return None, None, raw.strip() if raw else ""

    raw_clean = raw.strip()

    # Range di percentuale: "4-5%" o "2-2,5%"
    m = re.search(r"(\d+(?:,\d+)?)\s*-\s*(\d+(?:,\d+)?)\s*%", raw_clean)
    if m:
        return _to_float(m.group(1)), _to_float(m.group(2)), raw_clean

    # Percentuale singola, eventualmente con < o >: "6,6%", "<1%", ">7%"
    m = re.search(r"([<>]?)\s*(\d+(?:,\d+)?)\s*%", raw_clean)
    if m:
        val = _to_float(m.group(2))
        return val, val, raw_clean

    # Range in crediti fissi (non %): "1-2cr" -> convertiamo in % implicita sul budget rif.
    m = re.search(r"(\d+(?:,\d+)?)\s*-\s*(\d+(?:,\d+)?)\s*cr", raw_clean)
    if m:
        cr_min, cr_max = _to_float(m.group(1)), _to_float(m.group(2))
        return (cr_min / BUDGET_RIFERIMENTO * 100, cr_max / BUDGET_RIFERIMENTO * 100, raw_clean)

    # Credito fisso singolo: "1cr", "max 5cr"
    m = re.search(r"(\d+(?:,\d+)?)\s*cr", raw_clean)
    if m:
        cr = _to_float(m.group(1))
        pct = cr / BUDGET_RIFERIMENTO * 100
        return pct, pct, raw_clean

    # Nessun valore numerico riconosciuto (es. "pari a Kelly", "ultimo slot")
    return None, None, raw_clean


GIUDIZIO_MAP = {
    "OK": "prendi",
    "X": "evita",
    "!": "solo_sotto",
    "?": "da_verificare",
}


# --------------------------------------------------------------------------------------
# Caricamento listone
# --------------------------------------------------------------------------------------
def load_listone() -> pd.DataFrame:
    df = pd.read_excel(LISTONE_XLSX, sheet_name="Tutti", header=1)
    df = df.rename(
        columns={
            "Id": "id",
            "R": "ruolo_classico",
            "RM": "ruoli_mantra_raw",
            "Nome": "nome",
            "Squadra": "squadra",
            "Qt.A": "quotazione_attuale",
            "Qt.A M": "quotazione_attuale_mantra",
            "FVM": "fvm",
            "FVM M": "fvm_mantra",
        }
    )
    df = df[df["nome"].notna()].copy()
    df["nome"] = df["nome"].astype(str).str.strip()
    df["squadra"] = df["squadra"].astype(str).str.strip()
    df["ruolo_classico"] = df["ruolo_classico"].astype(str).str.strip()
    df["ruoli_mantra_raw"] = df["ruoli_mantra_raw"].astype(str).str.strip()
    df["ruoli_mantra"] = df["ruoli_mantra_raw"].apply(
        lambda s: ";".join([r.strip() for r in s.split(";") if r.strip() in RUOLI_MANTRA_VALIDI])
        if s and s != "nan"
        else ""
    )
    # I portieri (Por) non hanno ruoli_mantra validi nella lista sopra: li teniamo comunque
    # nel dataset (servono per la vista generale) ma senza ruoli multi-filtro.
    df["is_portiere"] = df["ruolo_classico"] == "P"
    df["nome_norm"] = df["nome"].apply(normalize_name)
    df["id"] = df["id"].astype(str)
    return df[
        ["id", "nome", "nome_norm", "squadra", "ruolo_classico", "ruoli_mantra", "is_portiere",
         "quotazione_attuale", "fvm"]
    ]


# --------------------------------------------------------------------------------------
# Caricamento guida (cheat sheet alfabetico)
# --------------------------------------------------------------------------------------
def load_advice():
    rows = []
    with open(CHEAT_SHEET, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split("|")]
            while len(parts) < 7:
                parts.append("")
            name_raw, squadra, ruolo_cl, rm_raw, pct_raw, giudizio_code, motivazione = parts[:7]

            for single_name in split_multi_player_name(name_raw):
                corretto = "(corr.)" in single_name
                pct_min, pct_max, pct_display = parse_pct_max(pct_raw)
                rows.append(
                    {
                        "advice_nome_raw": single_name,
                        "advice_nome_norm": normalize_name(single_name),
                        "advice_squadra": squadra,
                        "advice_ruolo_classico": ruolo_cl,
                        "advice_ruoli_mantra_raw": rm_raw,
                        "pct_min": pct_min,
                        "pct_max": pct_max,
                        "pct_display": pct_display,
                        "giudizio": GIUDIZIO_MAP.get(giudizio_code.strip(), "da_verificare"),
                        "motivazione": motivazione,
                        "corretto": corretto,
                        "rm_non_determinato": rm_raw.strip() == "?",
                    }
                )
    return rows


def load_ceduti_names() -> set:
    """Carica i nomi normalizzati dal foglio 'Ceduti' del listone: giocatori
    ufficialmente ceduti/non più in Serie A 2026/27, usati per distinguere un
    consiglio 'nome scritto male' da un consiglio 'giocatore non più disponibile'."""
    try:
        df = pd.read_excel(LISTONE_XLSX, sheet_name="Ceduti", header=1)
    except Exception:
        return set()
    if "Nome" not in df.columns:
        return set()
    return {normalize_name(str(n)) for n in df["Nome"].dropna()}


def load_flag_list(path: Path):
    """Carica trappole_assolute.txt / occasioni_regali.txt: nome | nota."""
    flags = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split("|")]
            name = parts[0]
            nota = parts[1] if len(parts) > 1 else ""
            flags[normalize_name(name)] = nota
    return flags


# --------------------------------------------------------------------------------------
# Match guida -> listone (tollerante)
# --------------------------------------------------------------------------------------
def match_advice_to_listone(advice_rows, listone_df: pd.DataFrame):
    import difflib

    name_to_indices = {}
    for idx, row in listone_df.iterrows():
        name_to_indices.setdefault(row["nome_norm"], []).append(idx)

    all_norm_names = list(name_to_indices.keys())

    matched = {}   # id_listone -> advice dict
    unmatched = []  # advice non trovate nel listone

    for adv in advice_rows:
        norm = adv["advice_nome_norm"]
        candidates = name_to_indices.get(norm, [])

        if not candidates:
            # match parziale/fuzzy tollerante a piccoli errori di battitura
            close = difflib.get_close_matches(norm, all_norm_names, n=3, cutoff=0.86)
            if close:
                candidates = name_to_indices[close[0]]

        if not candidates:
            unmatched.append(adv)
            continue

        # Se più di un candidato (stesso nome, squadre diverse), prova a disambiguare per squadra
        if len(candidates) > 1 and adv["advice_squadra"]:
            squadra_norm = normalize_name(adv["advice_squadra"])
            filtered = [i for i in candidates if normalize_name(listone_df.loc[i, "squadra"]) == squadra_norm]
            if filtered:
                candidates = filtered

        chosen_idx = candidates[0]
        chosen_id = listone_df.loc[chosen_idx, "id"]
        matched[chosen_id] = adv

    return matched, unmatched


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
def main():
    print("1) Carico il listone ufficiale...")
    listone = load_listone()
    print(f"   -> {len(listone)} giocatori nel listone.")

    print("2) Carico la guida (cheat sheet alfabetico)...")
    advice_rows = load_advice()
    print(f"   -> {len(advice_rows)} voci di consiglio (dopo split multi-giocatore).")

    print("3) Carico trappole assolute, occasioni/regali e lista ceduti...")
    trappole = load_flag_list(TRAPPOLE)
    occasioni = load_flag_list(OCCASIONI)
    ceduti_norm = load_ceduti_names()

    print("4) Eseguo il match nome-per-nome tra guida e listone...")
    matched, unmatched = match_advice_to_listone(advice_rows, listone)
    print(f"   -> {len(matched)} match trovati, {len(unmatched)} voci NON trovate nel listone.")

    records = []
    for _, p in listone.iterrows():
        adv = matched.get(p["id"])
        norm = p["nome_norm"]

        if adv:
            giudizio = adv["giudizio"]
            pct_min, pct_max = adv["pct_min"], adv["pct_max"]
            pct_display = adv["pct_display"]
            motivazione = adv["motivazione"]
            corretto = adv["corretto"]

            # Trasparenza: se la guida indicava una squadra diversa da quella reale nel
            # listone (es. giocatore ceduto/scambiato dopo la stesura della guida), segnalalo.
            adv_squadra_norm = normalize_name(adv["advice_squadra"])
            if adv_squadra_norm and adv_squadra_norm != normalize_name(p["squadra"]) and adv["advice_squadra"] not in ("Da verificare", ""):
                motivazione = (
                    f"{motivazione} (nota: la guida lo indicava a {adv['advice_squadra']}, "
                    f"nel listone risulta a {p['squadra']})"
                ).strip()
        else:
            giudizio = "nessun_consiglio"
            pct_min = pct_max = None
            pct_display = ""
            motivazione = "Nessun consiglio — valutazione libera"
            corretto = False

        is_trappola = norm in trappole
        is_occasione = norm in occasioni

        records.append(
            {
                "id": p["id"],
                "nome": p["nome"],
                "squadra": p["squadra"],
                "ruolo_classico": p["ruolo_classico"],
                "ruoli_mantra": p["ruoli_mantra"],
                "is_portiere": p["is_portiere"],
                "giudizio": giudizio,
                "pct_min": pct_min,
                "pct_max": pct_max,
                "pct_display": pct_display,
                "motivazione": motivazione,
                "corretto": corretto,
                "trappola_assoluta": is_trappola,
                "trappola_nota": trappole.get(norm, ""),
                "occasione_regalo": is_occasione,
                "occasione_nota": occasioni.get(norm, ""),
                "quotazione_attuale": p["quotazione_attuale"],
                "fvm": p["fvm"],
                "non_in_listone": False,
            }
        )

    # Voci della guida MAI trovate nel listone: le teniamo comunque visibili (richiesta esplicita)
    for adv in unmatched:
        # controlliamo se il nome (o una delle ipotesi separate da "/") compare tra i Ceduti:
        # in tal caso il messaggio è molto più utile di un generico "non trovato"
        name_parts = re.split(r"\s*/\s*", adv["advice_nome_raw"])
        is_ceduto = any(normalize_name(p) in ceduti_norm for p in name_parts)
        if is_ceduto:
            nota_extra = " — CEDUTO: risulta tra i giocatori ceduti/non più in Serie A 2026/27, non disponibile in asta."
        else:
            nota_extra = " — NON TROVATO NEL LISTONE, verifica tu (nome incerto o refuso)."

        records.append(
            {
                "id": f"NA-{normalize_name(adv['advice_nome_raw']).replace(' ', '-')}",
                "nome": adv["advice_nome_raw"],
                "squadra": adv["advice_squadra"] or "Da verificare",
                "ruolo_classico": adv["advice_ruolo_classico"],
                "ruoli_mantra": "",
                "is_portiere": adv["advice_ruolo_classico"] == "P",
                "giudizio": "ceduto" if is_ceduto else "da_verificare",
                "pct_min": adv["pct_min"],
                "pct_max": adv["pct_max"],
                "pct_display": adv["pct_display"],
                "motivazione": (adv["motivazione"] + nota_extra).strip(" —"),
                "corretto": adv["corretto"],
                "trappola_assoluta": False,
                "trappola_nota": "",
                "occasione_regalo": False,
                "occasione_nota": "",
                "quotazione_attuale": None,
                "fvm": None,
                "non_in_listone": True,
            }
        )

    out_df = pd.DataFrame.from_records(records)
    out_df = out_df.sort_values(["squadra", "nome"]).reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT, index=False, quoting=csv.QUOTE_MINIMAL)
    print(f"5) Dataset salvato in {OUT} ({len(out_df)} righe totali).")

    if unmatched:
        print("\n--- Voci della guida NON trovate nel listone (verificale a mano) ---")
        for adv in unmatched:
            print(f"   - {adv['advice_nome_raw']!r} (squadra guida: {adv['advice_squadra'] or '?'})")

    with_advice = out_df[out_df["giudizio"] != "nessun_consiglio"]
    print(f"\nRiepilogo: {len(with_advice)} giocatori con consiglio esplicito su {len(out_df)} totali.")


if __name__ == "__main__":
    sys.exit(main())
