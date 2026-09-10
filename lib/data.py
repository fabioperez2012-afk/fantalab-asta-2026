"""Caricamento del dataset giocatori (generato da scripts/build_dataset.py)."""

from pathlib import Path

import pandas as pd
import streamlit as st

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "players.csv"


@st.cache_data(show_spinner=False)
def load_players() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    # pandas legge le colonne booleane come bool solo se non ci sono NaN; normalizziamo
    for col in ["is_portiere", "corretto", "trappola_assoluta", "occasione_regalo", "non_in_listone"]:
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)
    for col in ["ruoli_mantra", "motivazione", "pct_display", "trappola_nota", "occasione_nota", "squadra"]:
        if col in df.columns:
            df[col] = df[col].fillna("")
    df["giudizio"] = df["giudizio"].fillna("nessun_consiglio")
    return df
