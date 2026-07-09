"""
style.py
--------
Design system centralisé : palette de couleurs, CSS injecté, et composant
de carte KPI réutilisé dans les 3 interfaces. Toute modification visuelle
(couleur, arrondi, ombre) se fait à un seul endroit.
"""

import streamlit as st

# --- Palette --------------------------------------------------------------
COLORS = {
    "blue": "#2563EB",       # indicateurs principaux
    "blue_light": "#93C5FD",
    "green": "#16A34A",      # revenus positifs
    "green_light": "#86EFAC",
    "orange": "#F59E0B",     # remboursements
    "orange_light": "#FCD34D",
    "red": "#DC2626",        # pertes uniquement
    "red_light": "#FCA5A5",
    "grey": "#64748B",       # neutre / secondaire
    "grey_light": "#E2E8F0",
    "bg": "#F8FAFC",
    "card_bg": "#FFFFFF",
    "text": "#0F172A",
    "text_secondary": "#64748B",
}

PLOTLY_TEMPLATE = "plotly_white"


def inject_css():
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: {COLORS['bg']};
        }}
        #MainMenu, footer {{visibility: hidden;}}

        h1, h2, h3 {{
            color: {COLORS['text']};
            font-weight: 700;
        }}

        /* --- Carte KPI --- */
        .kpi-card {{
            background: {COLORS['card_bg']};
            border-radius: 16px;
            padding: 20px 22px;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.08);
            border: 1px solid {COLORS['grey_light']};
            height: 100%;
        }}
        .kpi-card.accent {{
            border-left: 4px solid var(--accent-color, {COLORS['blue']});
        }}
        .kpi-label {{
            font-size: 0.82rem;
            color: {COLORS['text_secondary']};
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            margin-bottom: 6px;
        }}
        .kpi-value {{
            font-size: 1.75rem;
            font-weight: 700;
            color: {COLORS['text']};
            line-height: 1.2;
        }}
        .kpi-delta {{
            font-size: 0.85rem;
            font-weight: 600;
            margin-top: 4px;
        }}
        .kpi-delta.up {{ color: {COLORS['green']}; }}
        .kpi-delta.down {{ color: {COLORS['red']}; }}
        .kpi-delta.flat {{ color: {COLORS['grey']}; }}

        section[data-testid="stSidebar"] {{
            background-color: {COLORS['card_bg']};
            border-right: 1px solid {COLORS['grey_light']};
        }}

        div[data-testid="stMetric"] {{
            background: {COLORS['card_bg']};
            border-radius: 16px;
            padding: 16px 20px;
            border: 1px solid {COLORS['grey_light']};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, delta: str | None = None, delta_sign: str = "flat", icon: str = "", accent_color: str | None = None):
    """Affiche une carte KPI stylée (icône discrète + valeur + tendance optionnelle).

    accent_color : si fourni, ajoute une bordure gauche colorée pour faire
    ressortir visuellement les indicateurs d'alerte (ex. taux d'annulation)
    plutôt que de les traiter comme n'importe quel autre chiffre (retour d'audit).
    """
    delta_html = f'<div class="kpi-delta {delta_sign}">{delta}</div>' if delta else ""
    card_class = "kpi-card accent" if accent_color else "kpi-card"
    style_attr = f'style="--accent-color: {accent_color};"' if accent_color else ""
    st.markdown(
        f"""
        <div class="{card_class}" {style_attr}>
            <div class="kpi-label">{icon} {label}</div>
            <div class="kpi-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def delta_info(current: float, previous: float, higher_is_better: bool = True) -> tuple[str, str]:
    """Calcule le libellé et la classe CSS d'un delta de tendance (vs période
    précédente de même durée). Renvoie ("", "flat") si pas de référence fiable."""
    if previous is None or previous == 0:
        return "", "flat"
    pct = (current - previous) / abs(previous) * 100
    arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "▬")
    if abs(pct) < 0.5:
        sign_class = "flat"
    elif (pct > 0) == higher_is_better:
        sign_class = "up"
    else:
        sign_class = "down"
    label = f"{arrow} {abs(pct):.1f}% vs période précédente"
    return label, sign_class


def format_currency(value: float) -> str:
    """Formate un montant en DZD, lisible même sur grand écran de projection."""
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:,.2f} M DZD".replace(",", " ")
    return f"{value:,.0f} DZD".replace(",", " ")


def format_pct(value: float) -> str:
    return f"{value:.1f} %"
