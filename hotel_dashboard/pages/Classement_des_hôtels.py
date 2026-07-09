"""
Interface 3 : Classement et comparaison des hôtels.
"""

import streamlit as st

from utils.data_loader import load_bookings
from utils.filters import render_active_filters_banner, render_sidebar_filters
from utils.metrics import hotel_ranking_table
from utils.charts import (
    top_hotels_bookings_chart,
    top_hotels_cancel_rate_chart,
    top_hotels_revenue_chart,
)
from utils.style import inject_css

st.set_page_config(
    page_title="Classement des hôtels | Réservations Hôtelières",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()

st.title("Classement des hôtels")
st.caption("Comparer les performances des hôtels sur la période sélectionnée")

with st.spinner("Chargement des données..."):
    df = load_bookings()

filtered = render_sidebar_filters(df)
render_active_filters_banner()

if filtered.empty:
    st.warning("⚠️ Aucune donnée ne correspond aux filtres sélectionnés. Ajustez vos critères dans la barre latérale.")
    st.stop()

ranking = hotel_ranking_table(filtered)

top_n = st.slider("Nombre d'hôtels affichés dans les classements", min_value=5, max_value=25, value=10)

row1_col1, row1_col2 = st.columns(2)
with row1_col1:
    st.plotly_chart(top_hotels_revenue_chart(ranking, n=top_n), width="stretch")
with row1_col2:
    st.plotly_chart(top_hotels_bookings_chart(ranking, n=top_n), width="stretch")

st.plotly_chart(top_hotels_cancel_rate_chart(ranking, n=top_n), width="stretch")

st.divider()
st.subheader("Tableau récapitulatif")
st.caption(
    "Cliquez sur l'en-tête d'une colonne pour trier le tableau. "
    "« Frais d'annulation encaissés » = cash réel ; « Manque à gagner potentiel » = valeur nominale, non cash (voir audit)."
)

st.dataframe(
    ranking,
    width="stretch",
    hide_index=True,
    column_config={
        "Chiffre d'affaires (DZD)": st.column_config.NumberColumn(format="%.0f DZD"),
        "Frais d'annulation encaissés (DZD)": st.column_config.NumberColumn(format="%.0f DZD"),
        "Manque à gagner potentiel (DZD)": st.column_config.NumberColumn(format="%.0f DZD"),
        "Taux d'annulation (%)": st.column_config.NumberColumn(format="%.1f %%"),
    },
)
