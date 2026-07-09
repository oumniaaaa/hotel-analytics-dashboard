"""
Interface 2 : Analyse détaillée par hôtel.
"""

import streamlit as st

from utils.data_loader import load_bookings
from utils.filters import active_filters_label, render_active_filters_banner, render_sidebar_filters
from utils.metrics import (
    hotel_cancel_reason_split,
    hotel_cancel_refund_split,
    hotel_kpis,
    hotel_monthly_bookings,
    hotel_monthly_cancellation_fee,
    hotel_monthly_revenue,
    hotel_ranking_table,
    previous_period_df,
)
from utils.charts import (
    hotel_cancel_reason_chart,
    hotel_cancel_split_chart,
    hotel_cancellation_fee_chart,
    hotel_monthly_bookings_chart,
    hotel_monthly_revenue_chart,
)
from utils.report import generate_hotel_report_pdf
from utils.style import COLORS, delta_info, format_currency, format_pct, inject_css, kpi_card


def _period_label(df_scope) -> str:
    if df_scope.empty:
        return "Aucune donnée"
    start = df_scope["RefDate"].min().strftime("%d/%m/%Y")
    end = df_scope["RefDate"].max().strftime("%d/%m/%Y")
    return f"du {start} au {end}"


st.set_page_config(
    page_title="Analyse par hôtel | Réservations Hôtelières",
  
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

st.title("Analyse détaillée par hôtel")

with st.spinner("Chargement des données..."):
    df = load_bookings()

filtered = render_sidebar_filters(df)
render_active_filters_banner()

if filtered.empty:
    st.warning("⚠️ Aucune donnée ne correspond aux filtres sélectionnés. Ajustez vos critères dans la barre latérale.")
    st.stop()

# Sélecteur trié par CA décroissant (correction audit 3 : liste alphabétique
# peu exploitable sur un grand parc hôtelier).
ranking = hotel_ranking_table(filtered)
hotel_list = ranking["Hôtel"].tolist()

if not hotel_list:
    st.info("Aucun hôtel disponible avec les filtres actuels.")
    st.stop()

selected_hotel = st.selectbox("Sélectionnez un hôtel (triés par CA confirmé décroissant)", hotel_list)
df_hotel = filtered[filtered["HotelName"] == selected_hotel]

if df_hotel.empty:
    st.warning("Aucune réservation pour cet hôtel avec les filtres actuels.")
    st.stop()

st.caption(f"📍 {df_hotel['HotelAddress'].iloc[0]}")

# --- Rapport PDF généré UNIQUEMENT à la demande (correction audit critique :
# l'ancienne version le régénérait à chaque interaction de la page, même sans
# clic sur le bouton, ce qui coûtait 2 secondes de matplotlib+reportlab à
# chaque changement de filtre). ---------------------------------------------
col_title, col_btn = st.columns([4, 1.4])
with col_btn:
    if st.button(" Générer le rapport PDF", width="stretch"):
        with st.spinner("Génération du PDF..."):
            st.session_state["_pdf_bytes"] = generate_hotel_report_pdf(
                df_hotel=df_hotel,
                df_all=filtered,
                hotel_name=selected_hotel,
                period_label=_period_label(df_hotel),
                filters_label=active_filters_label(),
            )
            st.session_state["_pdf_hotel"] = selected_hotel

    if st.session_state.get("_pdf_hotel") == selected_hotel and "_pdf_bytes" in st.session_state:
        st.download_button(
            "⬇️ Télécharger le PDF",
            data=st.session_state["_pdf_bytes"],
            file_name=f"rapport_{selected_hotel.replace(' ', '_')}.pdf",
            mime="application/pdf",
            width="stretch",
        )

kpis = hotel_kpis(df_hotel)

# --- Delta vs période précédente --------------------------------------------
prev_df_all = previous_period_df(df, filtered, hotels=[selected_hotel], types=st.session_state.get("f_types"))
prev_kpis = hotel_kpis(prev_df_all) if not prev_df_all.empty else None


def _delta(key, higher_is_better=True):
    if prev_kpis is None:
        return "", "flat"
    return delta_info(kpis[key], prev_kpis[key], higher_is_better=higher_is_better)


c1, c2, c3, c4 = st.columns(4)
with c1:
    d, cls = _delta("ca")
    kpi_card("Chiffre d'affaires confirmé", format_currency(kpis["ca"]), delta=d, delta_sign=cls)
with c2:
    kpi_card("Nombre de réservations", f"{kpis['reservations']:,}".replace(",", " "))
with c3:
    d, cls = _delta("taux_annulation", higher_is_better=False)
    accent = COLORS["red"] if kpis["taux_annulation"] > 20 else (COLORS["orange"] if kpis["taux_annulation"] > 10 else COLORS["green"])
    kpi_card("Taux d'annulation", format_pct(kpis["taux_annulation"]), delta=d, delta_sign=cls, accent_color=accent)
with c4:
    d, cls = _delta("frais_annulation_reels")
    kpi_card("Frais d'annulation encaissés (cash réel)", format_currency(kpis["frais_annulation_reels"]), delta=d, delta_sign=cls)

st.caption(
    f"ℹ️ Manque à gagner potentiel (valeur nominale, non cash) : {format_currency(kpis['manque_a_gagner_potentiel'])}"
)

st.write("")
st.divider()

row1_col1, row1_col2 = st.columns(2)
with row1_col1:
    st.plotly_chart(hotel_monthly_bookings_chart(hotel_monthly_bookings(df_hotel)), width="stretch")
with row1_col2:
    st.plotly_chart(hotel_monthly_revenue_chart(hotel_monthly_revenue(df_hotel)), width="stretch")

row2_col1, row2_col2 = st.columns(2)
with row2_col1:
    split = hotel_cancel_refund_split(df_hotel)
    if split["Nombre"].sum() > 0:
        st.plotly_chart(hotel_cancel_split_chart(split), width="stretch")
    else:
        st.info("Aucune annulation enregistrée pour cet hôtel sur la période sélectionnée.")
with row2_col2:
    st.plotly_chart(hotel_cancellation_fee_chart(hotel_monthly_cancellation_fee(df_hotel)), width="stretch")

reasons = hotel_cancel_reason_split(df_hotel)
if not reasons.empty:
    st.plotly_chart(hotel_cancel_reason_chart(reasons), width="stretch")
