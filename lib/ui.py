"""Componenti UI riutilizzabili: CSS, header sticky, filtri, card giocatore."""

import unicodedata

import pandas as pd
import streamlit as st

from lib.state import get_stato, get_prezzo, set_stato, spesa_totale, num_giocatori_presi

RUOLI_MANTRA_ORDINE = ["Dc", "Dd", "Ds", "B", "E", "M", "C", "T", "W", "A", "Pc"]

GIUDIZIO_LABELS = {
    "prendi": ("PRENDI", "#15803d", "#dcfce7", "#bbf7d0"),
    "evita": ("EVITA / TRAPPOLA", "#b91c1c", "#fee2e2", "#fecaca"),
    "solo_sotto": ("SOLO SOTTO SOGLIA", "#c2410c", "#ffedd5", "#fed7aa"),
    "da_verificare": ("DA VERIFICARE", "#6d28d9", "#ede9fe", "#ddd6fe"),
    "ceduto": ("CEDUTO / NON DISPONIBILE", "#4b5563", "#f3f4f6", "#e5e7eb"),
    "nessun_consiglio": ("NESSUN CONSIGLIO — valutazione libera", "#4b5563", "#f3f4f6", "#e5e7eb"),
}

STATO_LABELS = {
    "libero": ("Libero", "#6b7280"),
    "preso_me": ("✅ Preso da te", "#15803d"),
    "preso_altri": ("🚫 Preso da altri", "#b91c1c"),
}


def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def normalize_search(s: str) -> str:
    return _strip_accents(str(s)).lower().strip()


# ---------------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------------
def inject_css():
    st.markdown(
        """
        <style>
        /* Header sticky: barra di ricerca + contatore budget sempre visibili */
        .st-key-sticky_header {
            position: sticky;
            top: 0;
            z-index: 999;
            background: var(--background-color, #ffffff);
            padding-top: 0.6rem;
            padding-bottom: 0.6rem;
            border-bottom: 1px solid rgba(49, 51, 63, 0.1);
            margin-bottom: 0.6rem;
        }
        [data-testid="stAppViewContainer"] .block-container {
            padding-top: 1rem;
            max-width: 1100px;
        }
        .player-card {
            border: 1px solid rgba(49, 51, 63, 0.15);
            border-radius: 12px;
            padding: 14px 16px;
            margin-bottom: 10px;
            background: var(--background-color, #ffffff);
        }
        .player-card.compact {
            padding: 10px 14px;
        }
        .badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.02em;
        }
        .player-name {
            font-size: 1.05rem;
            font-weight: 700;
        }
        .player-meta {
            color: #6b7280;
            font-size: 0.85rem;
        }
        .credit-pill {
            display: inline-block;
            padding: 2px 10px;
            border-radius: 8px;
            background: #f3f4f6;
            font-weight: 600;
            font-size: 0.85rem;
        }
        @media (max-width: 640px) {
            .player-card { padding: 12px; }
            .player-name { font-size: 1rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------------
# Header sticky
# ---------------------------------------------------------------------------------
def render_header() -> str:
    with st.container(key="sticky_header"):
        search = st.text_input(
            "🔍 Cerca giocatore",
            key="search_box",
            placeholder="Scrivi un nome (es. 'Kalulu', 'Thuram', 'Calhanoglu')...",
            label_visibility="collapsed",
        )
        budget = st.session_state["budget_totale"]
        spesi = spesa_totale()
        rimanenti = budget - spesi
        presi = num_giocatori_presi()
        c1, c2, c3 = st.columns(3)
        c1.metric("Budget totale", budget)
        c2.metric("Spesi / Rimanenti", f"{spesi} / {rimanenti}")
        c3.metric("Giocatori presi", presi)
    return search


# ---------------------------------------------------------------------------------
# Filtri sidebar
# ---------------------------------------------------------------------------------
def render_sidebar_filters(df: pd.DataFrame) -> dict:
    st.markdown("### 🎛️ Filtri")

    ruoli_options = [r for r in RUOLI_MANTRA_ORDINE]
    ruoli_sel = st.multiselect("Ruolo Mantra", ruoli_options, default=[])

    squadre_options = sorted(df["squadra"].unique().tolist())
    squadre_sel = st.multiselect("Squadra", squadre_options, default=[])

    giudizio_options = ["prendi", "evita", "solo_sotto", "da_verificare", "ceduto", "nessun_consiglio"]
    giudizio_labels = {k: GIUDIZIO_LABELS[k][0] for k in giudizio_options}
    giudizio_sel = st.multiselect(
        "Giudizio",
        giudizio_options,
        default=[],
        format_func=lambda k: giudizio_labels[k],
    )

    budget = st.session_state["budget_totale"]
    max_possibile = max(int(budget * 0.5), 10)
    crediti_range = st.slider(
        "Crediti max consigliati (fascia)",
        min_value=0,
        max_value=max_possibile,
        value=(0, max_possibile),
        help="Filtra per il valore massimo consigliato in crediti, ricalcolato sul budget corrente.",
    )

    st.divider()
    nascondi_presi = st.toggle("Nascondi già presi", value=False)
    solo_con_consiglio = st.toggle("Mostra solo con consiglio", value=False)

    return {
        "ruoli": ruoli_sel,
        "squadre": squadre_sel,
        "giudizi": giudizio_sel,
        "crediti_range": crediti_range,
        "nascondi_presi": nascondi_presi,
        "solo_con_consiglio": solo_con_consiglio,
    }


def _crediti_max_for_row(row, budget: int):
    """Ricalcola il tetto in crediti a partire dalla percentuale memorizzata, sul budget corrente."""
    pct_max = row.get("pct_max")
    if pd.isna(pct_max):
        return None
    return round(pct_max / 100 * budget)


def _crediti_min_for_row(row, budget: int):
    pct_min = row.get("pct_min")
    if pd.isna(pct_min):
        return None
    return round(pct_min / 100 * budget)


def apply_filters(df: pd.DataFrame, filters: dict, search_query: str) -> pd.DataFrame:
    budget = st.session_state["budget_totale"]
    out = df.copy()

    if search_query:
        q = normalize_search(search_query)
        out = out[out["nome"].apply(lambda n: q in normalize_search(n))]

    if filters["ruoli"]:
        wanted = set(filters["ruoli"])
        out = out[
            out["ruoli_mantra"].apply(
                lambda s: bool(wanted.intersection(set(s.split(";")))) if s else False
            )
        ]

    if filters["squadre"]:
        out = out[out["squadra"].isin(filters["squadre"])]

    if filters["giudizi"]:
        out = out[out["giudizio"].isin(filters["giudizi"])]

    lo, hi = filters["crediti_range"]
    crediti_max_series = out.apply(lambda r: _crediti_max_for_row(r, budget), axis=1)
    # i giocatori senza valore numerico (es. "pari a Kelly") non vengono esclusi dal filtro fascia,
    # a meno che la fascia sia stata ristretta esplicitamente: li teniamo visibili di default
    default_range = (0, max(int(budget * 0.5), 10))
    if (lo, hi) != default_range:
        mask_range = crediti_max_series.apply(lambda v: (v is not None) and (lo <= v <= hi))
        out = out[mask_range]

    if filters["nascondi_presi"]:
        out = out[out["nome"].apply(lambda n: get_stato(n) == "libero")]

    if filters["solo_con_consiglio"]:
        out = out[out["giudizio"] != "nessun_consiglio"]

    return out


# ---------------------------------------------------------------------------------
# Card giocatore
# ---------------------------------------------------------------------------------
def render_player_card(row: pd.Series, compact: bool = False, key_prefix: str = "default"):
    budget = st.session_state["budget_totale"]
    nome = row["nome"]
    stato = get_stato(nome)

    giudizio = row.get("giudizio", "nessun_consiglio")
    label, color, bg, border = GIUDIZIO_LABELS.get(giudizio, GIUDIZIO_LABELS["nessun_consiglio"])

    cr_min = _crediti_min_for_row(row, budget)
    cr_max = _crediti_max_for_row(row, budget)
    if cr_min is not None and cr_max is not None:
        if cr_min == cr_max:
            crediti_txt = f"{cr_max} cr"
        else:
            crediti_txt = f"{cr_min}–{cr_max} cr"
    else:
        pct_display = row.get("pct_display", "")
        crediti_txt = pct_display if pct_display and pct_display != "—" else "n.d."

    ruoli = row.get("ruoli_mantra", "")
    ruoli_txt = ruoli.replace(";", " · ") if ruoli else row.get("ruolo_classico", "")

    stato_label, stato_color = STATO_LABELS.get(stato, STATO_LABELS["libero"])

    card_class = "player-card compact" if compact else "player-card"
    with st.container():
        st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)

        top_cols = st.columns([5, 2, 2]) if not compact else st.columns([6, 2])
        with top_cols[0]:
            extra_badges = ""
            if row.get("trappola_assoluta"):
                extra_badges += ' <span class="badge" style="background:#fee2e2;color:#b91c1c;">TRAPPOLA ASSOLUTA</span>'
            if row.get("occasione_regalo"):
                extra_badges += ' <span class="badge" style="background:#dcfce7;color:#15803d;">OCCASIONE</span>'
            if row.get("corretto"):
                extra_badges += ' <span class="badge" style="background:#e0e7ff;color:#3730a3;">nome/ruolo corretto</span>'
            st.markdown(
                f"""
                <div class="player-name">{nome} <span class="player-meta">· {row.get('squadra','')}</span></div>
                <div class="player-meta">{row.get('ruolo_classico','')} · Mantra: {ruoli_txt}</div>
                <span class="badge" style="background:{bg};color:{color};border:1px solid {border};">{label}</span>
                {extra_badges}
                """,
                unsafe_allow_html=True,
            )
        with top_cols[1]:
            st.markdown(
                f'<div style="text-align:right;"><span class="credit-pill">💰 {crediti_txt}</span></div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="text-align:right;color:{stato_color};font-weight:600;font-size:0.85rem;margin-top:4px;">{stato_label}</div>',
                unsafe_allow_html=True,
            )
        if not compact:
            with top_cols[2]:
                pass

        motivazione = row.get("motivazione", "")
        if motivazione:
            with st.expander("Perché? (motivazione)", expanded=False):
                st.write(motivazione)
                if row.get("trappola_nota"):
                    st.caption(f"Trappola assoluta: {row['trappola_nota']}")
                if row.get("occasione_nota"):
                    st.caption(f"Occasione: {row['occasione_nota']}")

        if stato == "libero":
            btn_cols = st.columns([1, 1, 1.4])
            if btn_cols[0].button("✅ Preso da me", key=f"{key_prefix}_me_{nome}", width='stretch'):
                st.session_state[f"show_price_{nome}"] = True
            if btn_cols[1].button("🚫 Preso da altri", key=f"{key_prefix}_altri_{nome}", width='stretch'):
                set_stato(
                    nome, "preso_altri",
                    squadra=row.get("squadra", ""),
                    ruolo=row.get("ruolo_classico", ""),
                    ruoli_mantra=row.get("ruoli_mantra", ""),
                )
                st.rerun()

            if st.session_state.get(f"show_price_{nome}"):
                with btn_cols[2]:
                    prezzo = st.number_input(
                        "Prezzo pagato",
                        min_value=1,
                        max_value=int(budget),
                        value=max(cr_max or 1, 1),
                        key=f"{key_prefix}_prezzo_{nome}",
                        label_visibility="collapsed",
                    )
                    if st.button("Conferma", key=f"{key_prefix}_conferma_{nome}", width='stretch'):
                        set_stato(
                            nome, "preso_me", prezzo_pagato=int(prezzo),
                            squadra=row.get("squadra", ""),
                            ruolo=row.get("ruolo_classico", ""),
                            ruoli_mantra=row.get("ruoli_mantra", ""),
                        )
                        st.session_state[f"show_price_{nome}"] = False
                        st.rerun()
        else:
            prezzo_attuale = get_prezzo(nome)
            info = f"Prezzo pagato: {prezzo_attuale} cr" if prezzo_attuale else ""
            btn_cols = st.columns([2, 1])
            btn_cols[0].caption(info)
            if btn_cols[1].button("↩️ Rimetti libero", key=f"{key_prefix}_undo_{nome}", width='stretch'):
                set_stato(nome, "libero")
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
