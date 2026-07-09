"""
charts.py
---------
Constructeurs de graphiques Plotly. Chaque fonction reçoit un DataFrame
déjà agrégé (voir metrics.py) et retourne une figure prête à afficher.
Palette et template centralisés dans style.py pour garder une cohérence
visuelle totale entre les 3 interfaces.
"""

import plotly.express as px
import plotly.graph_objects as go

from utils.style import COLORS, PLOTLY_TEMPLATE

BASE_LAYOUT = dict(
    template=PLOTLY_TEMPLATE,
    font=dict(family="Inter, -apple-system, sans-serif", size=14, color=COLORS["text"]),
    margin=dict(l=10, r=10, t=50, b=10),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)


def _apply_base(fig, title: str):
    fig.update_layout(title=dict(text=title, font=dict(size=17, weight="bold")), **BASE_LAYOUT)
    return fig


def revenue_evolution_chart(df):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["YearMonth"], y=df["CA"], mode="lines+markers",
            line=dict(color=COLORS["blue"], width=3),
            marker=dict(size=6),
            fill="tozeroy", fillcolor="rgba(37, 99, 235, 0.08)",
            name="Chiffre d'affaires",
        )
    )
    fig.update_yaxes(title="CA (DZD)")
    fig.update_xaxes(title="Mois")
    return _apply_base(fig, "Évolution du chiffre d'affaires")


def _apply_pie_base(fig, title: str):
    """Layout dédié aux graphiques en anneau : les catégories et pourcentages
    sont déjà affichés à côté de l'anneau (textinfo), donc la légende du haut
    est désactivée pour éviter tout chevauchement avec le titre."""
    layout = dict(BASE_LAYOUT)
    layout["margin"] = dict(l=10, r=10, t=60, b=10)
    layout["showlegend"] = False
    fig.update_layout(title=dict(text=title, font=dict(size=17, weight="bold")), **layout)
    return fig


def revenue_breakdown_chart(df):
    """Répartition du CA total généré : CA confirmé / Montant remboursé /
    Revenu conservé sur annulées. Les 3 tranches somment à 100% du CA total
    généré (partition exacte, conforme aux règles métier Jour J — voir
    metrics.revenue_breakdown)."""
    colors = [COLORS["green"], COLORS["orange"], COLORS["blue"]]
    fig = go.Figure(
        go.Pie(
            labels=df["Catégorie"], values=df["Montant"], hole=0.55,
            marker=dict(colors=colors, line=dict(color="white", width=2)),
            textinfo="label+percent",
            textposition="outside",
            texttemplate="<b>%{label}</b><br>%{percent}",
            insidetextorientation="horizontal",
        )
    )
    return _apply_pie_base(fig, "Répartition du chiffre d'affaires total généré")


def cancellation_rate_chart(df):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["YearMonth"], y=df["TauxAnnulation"], mode="lines+markers",
            line=dict(color=COLORS["red"], width=3),
            marker=dict(size=6),
            name="Taux d'annulation",
        )
    )
    fig.update_yaxes(title="Taux d'annulation (%)")
    fig.update_xaxes(title="Mois")
    return _apply_base(fig, "Évolution du taux d'annulation")


def cancellation_fee_chart(df):
    """Frais d'annulation RÉELLEMENT encaissés (cash réel) — la grandeur fiable
    à utiliser pour parler d'impact financier des annulations (voir audit :
    RefundAmount est nominal, CancelledFee est le seul flux de cash avéré)."""
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["YearMonth"], y=df["FraisEncaisses"],
            marker_color=COLORS["orange"],
            name="Frais d'annulation encaissés",
        )
    )
    fig.update_yaxes(title="Frais encaissés (DZD)")
    fig.update_xaxes(title="Mois")
    return _apply_base(fig, "Frais d'annulation réellement encaissés (cash réel)")


def manque_a_gagner_chart(df):
    """Manque à gagner POTENTIEL (valeur nominale, PAS du cash réel) — à
    afficher seulement en complément du graphique cash réel ci-dessus, jamais
    seul, pour ne pas laisser croire à une perte de trésorerie réelle."""
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["YearMonth"], y=df["ManqueAGagner"],
            marker_color=COLORS["grey"],
            name="Manque à gagner potentiel",
        )
    )
    fig.update_yaxes(title="Manque à gagner potentiel (DZD, nominal)")
    fig.update_xaxes(title="Mois")
    return _apply_base(fig, "Manque à gagner potentiel (valeur nominale, non cash)")


def payment_type_cancel_chart(df):
    """Taux d'annulation par mode de paiement — signal fort identifié en
    audit : les modes sans engagement financier amont annulent nettement plus."""
    top = df.iloc[::-1]
    fig = go.Figure(
        go.Bar(
            x=top["TauxAnnulation"], y=top["Libelle"], orientation="h",
            marker_color=COLORS["blue"],
            text=[f"{v:.1f}%" for v in top["TauxAnnulation"]],
            textposition="outside",
        )
    )
    fig.update_xaxes(title="Taux d'annulation (%)")
    return _apply_base(fig, "Taux d'annulation par mode de paiement")


# --------------------------------------------------------------------------
# Interface 2
# --------------------------------------------------------------------------

def hotel_monthly_bookings_chart(df):
    fig = go.Figure(
        go.Bar(x=df["YearMonth"], y=df["Reservations"], marker_color=COLORS["blue"])
    )
    fig.update_yaxes(title="Nombre de réservations")
    fig.update_xaxes(title="Mois")
    return _apply_base(fig, "Réservations par mois")


def hotel_monthly_revenue_chart(df):
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["YearMonth"], y=df["CA"], mode="lines+markers",
            line=dict(color=COLORS["green"], width=3),
            fill="tozeroy", fillcolor="rgba(22, 163, 74, 0.08)",
        )
    )
    fig.update_yaxes(title="CA (DZD)")
    fig.update_xaxes(title="Mois")
    return _apply_base(fig, "Évolution du chiffre d'affaires mensuel")


def hotel_cancel_split_chart(df):
    colors = [COLORS["orange"], COLORS["grey"]]
    fig = go.Figure(
        go.Pie(
            labels=df["Type"], values=df["Nombre"], hole=0.55,
            marker=dict(colors=colors, line=dict(color="white", width=2)),
            textinfo="label+percent",
            textposition="outside",
            texttemplate="<b>%{label}</b><br>%{percent}",
        )
    )
    return _apply_pie_base(fig, "Annulations : remboursées vs non remboursées")


def hotel_cancellation_fee_chart(df):
    """Frais d'annulation réellement encaissés (cash réel) pour un hôtel."""
    fig = go.Figure(go.Bar(x=df["YearMonth"], y=df["FraisEncaisses"], marker_color=COLORS["orange"]))
    fig.update_yaxes(title="Frais encaissés (DZD)")
    fig.update_xaxes(title="Mois")
    return _apply_base(fig, "Frais d'annulation réellement encaissés (cash réel)")


def hotel_cancel_reason_chart(df):
    fig = go.Figure(
        go.Bar(
            x=df["Nombre"], y=df["Motif"], orientation="h",
            marker_color=COLORS["blue"],
        )
    )
    fig.update_layout(yaxis=dict(autorange="reversed"))
    fig.update_xaxes(title="Nombre d'annulations")
    return _apply_base(fig, "Répartition des motifs d'annulation")


# --------------------------------------------------------------------------
# Interface 3
# --------------------------------------------------------------------------

def top_hotels_revenue_chart(df, n: int = 10):
    top = df.nlargest(n, "Chiffre d'affaires (DZD)").iloc[::-1]
    fig = go.Figure(
        go.Bar(
            x=top["Chiffre d'affaires (DZD)"], y=top["Hôtel"], orientation="h",
            marker_color=COLORS["blue"],
        )
    )
    fig.update_xaxes(title="CA (DZD)")
    return _apply_base(fig, f"Top {n} hôtels par chiffre d'affaires")


def top_hotels_bookings_chart(df, n: int = 10):
    top = df.nlargest(n, "Réservations").iloc[::-1]
    fig = go.Figure(
        go.Bar(
            x=top["Réservations"], y=top["Hôtel"], orientation="h",
            marker_color=COLORS["green"],
        )
    )
    fig.update_xaxes(title="Nombre de réservations")
    return _apply_base(fig, f"Top {n} hôtels par nombre de réservations")


def top_hotels_cancel_rate_chart(df, n: int = 10, min_bookings: int = 5):
    subset = df[df["Réservations"] >= min_bookings]
    top = subset.nlargest(n, "Taux d'annulation (%)").iloc[::-1]
    fig = go.Figure(
        go.Bar(
            x=top["Taux d'annulation (%)"], y=top["Hôtel"], orientation="h",
            marker_color=COLORS["red"],
        )
    )
    fig.update_xaxes(title="Taux d'annulation (%)")
    return _apply_base(fig, f"Top {n} hôtels par taux d'annulation (min. {min_bookings} résa.)")
