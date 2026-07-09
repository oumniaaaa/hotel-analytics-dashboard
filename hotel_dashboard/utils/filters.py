"""
filters.py
----------
Widgets de filtrage réutilisables pour la sidebar. Une seule source de
vérité pour la logique de filtrage évite toute divergence entre les 3
interfaces.

Correction (audit, point g) : les widgets utilisent maintenant EXACTEMENT
les mêmes clés `key=` sur les 3 pages (au lieu d'un préfixe par page). Dans
Streamlit, `st.session_state` est partagé pour toute la session, quelle que
soit la page affichée : en utilisant la même clé partout, un changement de
filtre sur une page est donc automatiquement répercuté si l'utilisateur
navigue vers une autre page. Avec des clés préfixées différentes par page
(l'ancien code), chaque page avait sa PROPRE instance de widget et les
changements ne se propageaient pas de façon fiable.
"""

import pandas as pd
import streamlit as st

from utils.data_loader import get_filter_options

FILTER_KEYS = ["f_years", "f_months", "f_hotels", "f_types"]


def reset_filters():
    for key in FILTER_KEYS:
        st.session_state.pop(key, None)


def render_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Affiche les filtres dans la sidebar et retourne le DataFrame filtré.

    Les widgets sont liés directement à `st.session_state` via leur `key`
    (pas de variable de "default" intermédiaire) : c'est ce qui garantit la
    synchronisation entre les 3 pages.
    """
    options = get_filter_options(df)

    st.sidebar.markdown("### 🔍 Filtres")

    years = st.sidebar.multiselect("Année", options=options["years"], key="f_years")

    month_names = options["month_names"]
    months = st.sidebar.multiselect(
        "Mois", options=options["months"], format_func=lambda m: month_names[m], key="f_months",
    )

    hotels = st.sidebar.multiselect("Hôtel", options=options["hotels"], key="f_hotels")

    types = st.sidebar.multiselect(
        "Type de réservation", options=options["booking_types"],
        format_func=lambda t: t.capitalize(), key="f_types",
    )

    if st.sidebar.button("↺ Réinitialiser les filtres", width="stretch"):
        reset_filters()
        st.rerun()

    filtered = df.copy()
    if years:
        filtered = filtered[filtered["Year"].isin(years)]
    if months:
        filtered = filtered[filtered["Month"].isin(months)]
    if hotels:
        filtered = filtered[filtered["HotelName"].isin(hotels)]
    if types:
        filtered = filtered[filtered["BookingType"].isin(types)]

    st.sidebar.markdown("---")
    st.sidebar.caption(f"📄 {len(filtered):,} réservations sélectionnées".replace(",", " "))

    # Export CSV À LA DEMANDE UNIQUEMENT (correction audit : l'ancienne version
    # appelait filtered.to_csv() à chaque rerun de la page, même sans clic).
    with st.sidebar.expander("⬇️ Exporter les données filtrées"):
        if st.button("Générer le CSV", key="gen_csv_btn", width="stretch"):
            st.session_state["_csv_export_bytes"] = filtered.to_csv(index=False).encode("utf-8")
        if "_csv_export_bytes" in st.session_state:
            st.download_button(
                "Télécharger le CSV",
                data=st.session_state["_csv_export_bytes"],
                file_name="reservations_filtrees.csv",
                mime="text/csv",
                key="dl_csv_btn",
                width="stretch",
            )

    return filtered


def active_filters_label() -> str:
    """Résumé textuel des filtres actifs, utilisé pour le fil d'Ariane en
    haut de page (audit : les filtres actifs n'étaient visibles que dans la
    sidebar, facile à oublier en scrollant) et pour le rapport PDF."""
    parts = []
    if st.session_state.get("f_years"):
        parts.append("Années : " + ", ".join(str(y) for y in st.session_state["f_years"]))
    if st.session_state.get("f_months"):
        parts.append("Mois : " + ", ".join(str(m) for m in st.session_state["f_months"]))
    if st.session_state.get("f_hotels"):
        parts.append("Hôtels : " + ", ".join(st.session_state["f_hotels"]))
    if st.session_state.get("f_types"):
        parts.append("Types : " + ", ".join(st.session_state["f_types"]))
    return " · ".join(parts) if parts else "Aucun filtre actif (toutes les données)"


def render_active_filters_banner():
    """Bandeau discret rappelant les filtres actifs, à placer sous le titre
    de chaque page."""
    st.caption(f"🔎 {active_filters_label()}")
