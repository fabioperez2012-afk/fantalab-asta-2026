"""
Gestione dello stato dell'asta in tempo reale.

Lo stato (chi ho preso, a che prezzo, chi hanno preso gli altri, il budget totale)
vive in st.session_state per restare vivo tra un refresh e l'altro della pagina,
ed è inoltre salvato su un file JSON locale (data/asta_state.json) ad ogni modifica:
se il browser si chiude per sbaglio durante l'asta, al riavvio dell'app lo stato
viene ricaricato da lì invece di ripartire da zero.

Nota: essendo un file sulla stessa istanza dell'app, questo funziona per l'uso
previsto (un fantallenatore solo, su un'unica app aperta durante l'asta). Se apri
l'app da più dispositivi contemporaneamente condividono lo stesso file di stato.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "asta_state.json"
DEFAULT_BUDGET = 600


def _load_from_disk() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_to_disk():
    payload = {
        "budget_totale": st.session_state.get("budget_totale", DEFAULT_BUDGET),
        "stato_asta": st.session_state.get("stato_asta", {}),
        "assegnazioni": st.session_state.get("assegnazioni", []),
    }
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass  # se il filesystem è read-only (alcuni host), l'app funziona comunque via session_state


def ensure_state():
    if "stato_asta" not in st.session_state:
        disk = _load_from_disk()
        st.session_state["stato_asta"] = disk.get("stato_asta", {})
        st.session_state["budget_totale"] = disk.get("budget_totale", DEFAULT_BUDGET)
        st.session_state["assegnazioni"] = disk.get("assegnazioni", [])


def budget_config():
    """Renderizza in sidebar l'input del budget totale, sempre in cima."""
    with st.sidebar:
        st.markdown("### 💰 Budget asta")
        nuovo_budget = st.number_input(
            "Crediti totali a disposizione",
            min_value=1,
            max_value=5000,
            value=int(st.session_state["budget_totale"]),
            step=10,
            help="Ricalcola automaticamente tutti i crediti max consigliati per ogni giocatore.",
        )
        if nuovo_budget != st.session_state["budget_totale"]:
            st.session_state["budget_totale"] = nuovo_budget
            _save_to_disk()


def get_stato(nome: str) -> str:
    """Ritorna 'libero' / 'preso_me' / 'preso_altri' per un giocatore."""
    entry = st.session_state["stato_asta"].get(nome)
    if not entry:
        return "libero"
    return entry.get("stato", "libero")


def get_prezzo(nome: str):
    entry = st.session_state["stato_asta"].get(nome)
    if not entry:
        return None
    return entry.get("prezzo_pagato")


def set_stato(nome: str, stato: str, prezzo_pagato=None, squadra: str = "", ruolo: str = "", ruoli_mantra: str = ""):
    """Segna un giocatore come preso da me / preso da altri / lo rimette libero."""
    if stato == "libero":
        st.session_state["stato_asta"].pop(nome, None)
    else:
        st.session_state["stato_asta"][nome] = {
            "stato": stato,
            "prezzo_pagato": prezzo_pagato,
            "squadra": squadra,
            "ruolo_classico": ruolo,
            "ruoli_mantra": ruoli_mantra,
        }
    st.session_state["assegnazioni"].append(nome)
    _save_to_disk()


def undo_last():
    """Annulla l'ultima assegnazione fatta (rimette il giocatore libero)."""
    assegnazioni = st.session_state.get("assegnazioni", [])
    if not assegnazioni:
        return None
    ultimo = assegnazioni.pop()
    st.session_state["stato_asta"].pop(ultimo, None)
    _save_to_disk()
    return ultimo


def spesa_totale() -> int:
    tot = 0
    for entry in st.session_state["stato_asta"].values():
        if entry.get("stato") == "preso_me" and entry.get("prezzo_pagato"):
            tot += int(entry["prezzo_pagato"])
    return tot


def presi_da_me_df(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for nome, entry in st.session_state["stato_asta"].items():
        if entry.get("stato") == "preso_me":
            match = df[df["nome"] == nome]
            squadra = match["squadra"].iloc[0] if not match.empty else entry.get("squadra", "")
            ruolo = match["ruolo_classico"].iloc[0] if not match.empty else entry.get("ruolo_classico", "")
            ruoli_mantra = match["ruoli_mantra"].iloc[0] if not match.empty else entry.get("ruoli_mantra", "")
            rows.append(
                {
                    "nome": nome,
                    "squadra": squadra,
                    "ruolo_classico": ruolo,
                    "ruoli_mantra": ruoli_mantra,
                    "prezzo_pagato": entry.get("prezzo_pagato") or 0,
                }
            )
    if not rows:
        return pd.DataFrame(columns=["nome", "squadra", "ruolo_classico", "ruoli_mantra", "prezzo_pagato"])
    return pd.DataFrame(rows).sort_values("nome")


def num_giocatori_presi() -> int:
    return sum(1 for e in st.session_state["stato_asta"].values() if e.get("stato") == "preso_me")
