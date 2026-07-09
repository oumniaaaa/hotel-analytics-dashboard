"""
app.py — Interface 1 : Dashboard Global
Vision globale de l'activité (CA, annulations) avec filtres interactifs.

💡 Section "Analyse du chiffre d'affaires" alignée sur les règles métier
officielles (Jour J) communiquées par Namlatic — voir l'en-tête de
utils/metrics.py::compute_global_kpis pour le détail des 6 KPI et la
vérification anti double-comptage. `RefundAmount` est la référence
officielle des remboursements réellement effectués. Le taux d'annulation,
indicateur d'alerte le plus fiable, reste mis en avant visuellement
(bordure d'accent).
"""

import streamlit as st

from utils.data_loader import data_quality_summary, load_bookings
from utils.filters import render_active_filters_banner, render_sidebar_filters
from utils.metrics import (
    cancellation_fee_evolution,
    cancellation_rate_evolution,
    compute_global_kpis,
    payment_type_cancellation,
    previous_period_df,
    revenue_breakdown,
    revenue_evolution,
)
from utils.charts import (
    cancellation_fee_chart,
    cancellation_rate_chart,
    payment_type_cancel_chart,
    revenue_breakdown_chart,
    revenue_evolution_chart,
)
from utils.insights import build_revenue_split_interpretation
from utils.style import delta_info, format_currency, format_pct, inject_css, kpi_card, COLORS

st.set_page_config(
    page_title="Dashboard Global | Réservations Hôtelières",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()


st.title("Dashboard Global")
st.caption("Vision d'ensemble de l'activité de réservation et d'annulation")

with st.spinner("Chargement des données..."):
    df = load_bookings()

filtered = render_sidebar_filters(df)
render_active_filters_banner()

if filtered.empty:
    st.warning(" Aucune donnée ne correspond aux filtres sélectionnés. Ajustez vos critères dans la barre latérale.")
    st.stop()

kpis = compute_global_kpis(filtered)

# --- Delta vs période précédente (même durée, mêmes filtres hôtel/type) -----
prev_df = previous_period_df(
    df, filtered,
    hotels=st.session_state.get("f_hotels"),
    types=st.session_state.get("f_types"),
)
prev_kpis = compute_global_kpis(prev_df) if not prev_df.empty else None


def _delta(key, higher_is_better=True):
    if prev_kpis is None:
        return "", "flat"
    return delta_info(kpis[key], prev_kpis[key], higher_is_better=higher_is_better)


# --- Section : Analyse du chiffre d'affaires --------------------------------
st.subheader(" Analyse du chiffre d'affaires")


def _pct_of_total(amount: float) -> str:
    total = kpis["ca_total_genere"]
    return f"{(amount / total * 100):.1f}% du CA total généré" if total else ""


# Ligne 1 : vue d'ensemble du volume d'activité (KPI déjà existants, inchangés)
c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi_card("CA total généré", format_currency(kpis["ca_total_genere"]))
with c2:
    d, cls = _delta("ca_confirme")
    kpi_card("CA confirmé (hors annulations)", format_currency(kpis["ca_confirme"]), delta=d, delta_sign=cls)
with c3:
    d, cls = _delta("ca_realise")
    kpi_card("CA réalisé (séjours complétés)", format_currency(kpis["ca_realise"]), delta=d, delta_sign=cls)
with c4:
    d, cls = _delta("ca_pipeline")
    kpi_card("CA en cours de réalisation", format_currency(kpis["ca_pipeline"]), delta=d, delta_sign=cls)

st.write("")

# Ligne 2 : décomposition des annulations, conforme aux règles métier Jour J
c5, c6, c7, c8 = st.columns(4)
with c5:
    d, cls = _delta("taux_annulation", higher_is_better=False)
    # Indicateur d'alerte : mis en avant visuellement (bordure d'accent), pas
    # traité comme un chiffre neutre parmi d'autres (retour d'audit 3.1).
    accent = COLORS["red"] if kpis["taux_annulation"] > 20 else (COLORS["orange"] if kpis["taux_annulation"] > 10 else COLORS["green"])
    kpi_card("Taux d'annulation", format_pct(kpis["taux_annulation"]), delta=d, delta_sign=cls,  accent_color=accent)
with c6:
    kpi_card(
        "Valeur totale des réservations annulées",
        format_currency(kpis["valeur_totale_annulee"]),
        delta=_pct_of_total(kpis["valeur_totale_annulee"]), delta_sign="flat"
    )
with c7:
    kpi_card(
        "Montant réellement remboursé",
        format_currency(kpis["montant_rembourse"]),
        delta=_pct_of_total(kpis["montant_rembourse"]), delta_sign="flat"
    )
with c8:
    kpi_card(
        "Revenu conservé sur annulées",
        format_currency(kpis["revenu_conserve_annulees"]),
        delta=_pct_of_total(kpis["revenu_conserve_annulees"]), delta_sign="flat"
    )

st.write("")

# Ligne 3 : compléments (sous-ensemble non remboursé + cash réel encaissé sur frais)
c9, c10 = st.columns(2)
with c9:
    kpi_card(
        "CA annulé sans remboursement",
        format_currency(kpis["ca_annule_sans_remboursement"]),
        delta=_pct_of_total(kpis["ca_annule_sans_remboursement"]), delta_sign="flat"
    )
with c10:
    d, cls = _delta("frais_annulation_reels")
    kpi_card("Frais d'annulation encaissés (cash réel)", format_currency(kpis["frais_annulation_reels"]), delta=d, delta_sign=cls)

if not kpis["no_double_counting_ok"]:
    st.error(" Incohérence détectée dans la reconstruction des totaux du CA — vérifier `compute_global_kpis`.")

st.write("")
st.divider()

# --- Graphiques --------------------------------------------------------------
row1_col1, row1_col2 = st.columns(2)
with row1_col1:
    st.plotly_chart(revenue_evolution_chart(revenue_evolution(filtered)), width="stretch")
with row1_col2:
    st.plotly_chart(revenue_breakdown_chart(revenue_breakdown(kpis)), width="stretch")

st.info(f"📌 **Interprétation automatique** — {build_revenue_split_interpretation(kpis)}")

row2_col1, row2_col2 = st.columns(2)
with row2_col1:
    st.plotly_chart(cancellation_rate_chart(cancellation_rate_evolution(filtered)), width="stretch")
with row2_col2:
    st.plotly_chart(cancellation_fee_chart(cancellation_fee_evolution(filtered)), width="stretch")

st.plotly_chart(payment_type_cancel_chart(payment_type_cancellation(filtered)), width="stretch")
st.caption("Les réservations sans engagement financier amont (paiement à l'hôtel, virement) annulent nettement plus que celles payées en ligne — un levier actionnable concret.")

# --- Qualité des données -----------------------------------------------------
dq = data_quality_summary(df)
with st.expander("Qualité des données"):
    st.markdown(
        f"""
        - **{dq['rows_dropped_no_date']}** réservations exclues des analyses temporelles (date de réservation illisible)
        - **{dq['date_anomalies']}** réservations où la date d'annulation précède la date de réservation
          (dont **{dq['date_anomalies_severe']}** avec un écart de plus de 2 jours, à investiguer sur la source des données)
        - **{dq['negative_vat_rows']}** réservations avec une TVA hôtelier négative (neutralisées à 0)
        """
    )

st.caption(" Utilisez la page **Analyse par hôtel** pour un focus individuel, ou **Classement** pour comparer les hôtels entre eux.")
