"""
Fantalab Asta 2026/27 — webapp Streamlit per seguire l'asta Mantra in tempo reale.
Entry point. Vedi README.md per come lanciarla in locale o aggiornare i dati.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from lib.data import load_players
from lib.state import (
    ensure_state,
    budget_config,
    get_stato,
    set_stato,
    undo_last,
    spesa_totale,
    presi_da_me_df,
)
from lib.ui import (
    inject_css,
    render_header,
    render_player_card,
    render_sidebar_filters,
    apply_filters,
    GIUDIZIO_LABELS,
)

st.set_page_config(
    page_title="Fantalab Asta 2026/27",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()
ensure_state()

df = load_players()

# ---------------------------------------------------------------------------------
# Sidebar: budget + filtri
# ---------------------------------------------------------------------------------
budget_config()

with st.sidebar:
    st.divider()
    filters = render_sidebar_filters(df)

# ---------------------------------------------------------------------------------
# Header sticky: ricerca + contatore budget
# ---------------------------------------------------------------------------------
search_query = render_header()

# ---------------------------------------------------------------------------------
# Tabs principali
# ---------------------------------------------------------------------------------
tab_ricerca, tab_ruolo, tab_evidenza, tab_rosa = st.tabs(
    ["🔍 Cerca & filtra", "📋 Per ruolo", "⭐ In evidenza", "🎒 La mia rosa"]
)

with tab_ricerca:
    filtered = apply_filters(df, filters, search_query)
    st.caption(f"{len(filtered)} giocatori trovati su {len(df)} nel listone.")
    if filtered.empty:
        st.info("Nessun giocatore corrisponde ai filtri. Prova ad allargare la ricerca.")
    else:
        # su schermi piccoli le card sono più leggibili di una tabella stretta:
        # qui usiamo sempre le card, ordinate per rilevanza (prendi > solo_sotto > ... )
        order = {"prendi": 0, "solo_sotto": 1, "da_verificare": 2, "ceduto": 2, "nessun_consiglio": 3, "evita": 4}
        filtered = filtered.assign(_order=filtered["giudizio"].map(order).fillna(3))
        filtered = filtered.sort_values(["_order", "nome"])
        for _, row in filtered.iterrows():
            render_player_card(row, key_prefix="search")

with tab_ruolo:
    st.caption("Giocatori raggruppati per ruolo Mantra: chi ha più ruoli compare in ogni sezione pertinente.")
    ruoli_ordine = ["Dc", "Dd", "Ds", "B", "E", "M", "C", "T", "W", "A", "Pc"]
    nascondi_presi = filters["nascondi_presi"]
    for ruolo in ruoli_ordine:
        mask = df["ruoli_mantra"].fillna("").apply(lambda s: ruolo in s.split(";") if s else False)
        sub = df[mask].copy()
        if nascondi_presi:
            sub = sub[sub["nome"].apply(lambda n: get_stato(n) == "libero")]
        if sub.empty:
            continue
        order = {"prendi": 0, "solo_sotto": 1, "da_verificare": 2, "ceduto": 2, "nessun_consiglio": 3, "evita": 4}
        sub = sub.assign(_order=sub["giudizio"].map(order).fillna(3)).sort_values(["_order", "nome"])
        with st.expander(f"**{ruolo}** — {len(sub)} giocatori", expanded=False):
            for _, row in sub.iterrows():
                render_player_card(row, compact=True, key_prefix=f"ruolo_{ruolo}")

with tab_evidenza:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🚫 Trappole assolute")
        st.caption("Non pagarli oltre la soglia indicata.")
        trappole = df[df["trappola_assoluta"] == True].sort_values("nome")
        for _, row in trappole.iterrows():
            render_player_card(row, compact=True, key_prefix="trappole")
    with col2:
        st.markdown("### 🎁 Occasioni / regali")
        st.caption("Non farteli scappare a questi prezzi.")
        occasioni = df[df["occasione_regalo"] == True].sort_values("nome")
        for _, row in occasioni.iterrows():
            render_player_card(row, compact=True, key_prefix="occasioni")

with tab_rosa:
    st.markdown("### La tua rosa")
    rosa = presi_da_me_df(df)
    if rosa.empty:
        st.info("Non hai ancora preso nessun giocatore. Segnali con 'Preso da me' nelle altre tab.")
    else:
        budget = st.session_state["budget_totale"]
        spesi = spesa_totale()
        st.metric("Crediti spesi", f"{spesi} / {budget}")
        display_cols = rosa[["nome", "squadra", "ruolo_classico", "ruoli_mantra", "prezzo_pagato"]].rename(
            columns={
                "nome": "Nome",
                "squadra": "Squadra",
                "ruolo_classico": "Ruolo",
                "ruoli_mantra": "Ruoli Mantra",
                "prezzo_pagato": "Prezzo pagato",
            }
        )
        st.dataframe(display_cols, width='stretch', hide_index=True)

        csv = display_cols.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Esporta rosa (CSV)",
            data=csv,
            file_name="la_mia_rosa_fantalab_2026_27.csv",
            mime="text/csv",
            width='stretch',
        )

        st.divider()
        st.markdown("#### Composizione per ruolo classico")
        by_role = rosa.groupby("ruolo_classico").agg(
            giocatori=("nome", "count"), crediti=("prezzo_pagato", "sum")
        )
        st.dataframe(by_role, width='stretch')

    if st.session_state.get("assegnazioni"):
        st.divider()
        if st.button("↩️ Annulla ultima assegnazione", width='stretch'):
            undone = undo_last()
            if undone:
                st.success(f"Annullata l'assegnazione di {undone}.")
                st.rerun()
