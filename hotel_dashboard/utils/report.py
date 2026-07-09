"""
report.py
---------
Génération du rapport PDF pour un hôtel donné (Interface 2). Réutilise les
fonctions de metrics.py (calculs) et insights.py (analyse rédigée par
règles métier, sans IA externe). Les graphiques sont rendus avec
matplotlib (rendu statique, fidèle à la palette de l'application) puis
intégrés au PDF via reportlab.
"""

import io
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from utils.insights import (
    build_cancellation_analysis,
    build_cancellation_fee_analysis,
    build_executive_summary,
    build_manque_a_gagner_analysis,
    build_performance_analysis,
    build_recommendations,
    compute_health_score,
)
from utils.metrics import (
    global_benchmark,
    hotel_cancel_refund_split,
    hotel_kpis,
    hotel_monthly_bookings,
    hotel_monthly_cancellation_fee,
    hotel_monthly_revenue,
)
from utils.style import COLORS, format_currency, format_pct

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm

# --- Palette matplotlib (hex -> RGB matplotlib-friendly) --------------------
MPL_BLUE = COLORS["blue"]
MPL_GREEN = COLORS["green"]
MPL_ORANGE = COLORS["orange"]
MPL_RED = COLORS["red"]
MPL_GREY = COLORS["grey"]

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "axes.edgecolor": "#E2E8F0",
        "axes.labelcolor": "#334155",
        "text.color": "#0F172A",
        "xtick.color": "#64748B",
        "ytick.color": "#64748B",
        "axes.grid": True,
        "grid.color": "#F1F5F9",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)


def _fig_to_image(fig, width_mm=170):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=170, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=width_mm * mm, height=width_mm * mm * 0.42)


def _line_chart(df, x_col, y_col, title, color, ylabel):
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.plot(df[x_col], df[y_col], color=color, linewidth=2.4, marker="o", markersize=4)
    ax.fill_between(df[x_col], df[y_col], color=color, alpha=0.08)
    ax.set_title(title, fontsize=12, fontweight="bold", loc="left", color="#0F172A")
    ax.set_ylabel(ylabel, fontsize=9)
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " ")))
    fig.tight_layout()
    return fig


def _bar_chart(df, x_col, y_col, title, color, ylabel):
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.bar(df[x_col], df[y_col], color=color, width=0.6)
    ax.set_title(title, fontsize=12, fontweight="bold", loc="left", color="#0F172A")
    ax.set_ylabel(ylabel, fontsize=9)
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " ")))
    fig.tight_layout()
    return fig


def _comparison_chart(hotel_name, hotel_ca, avg_ca, top_ca):
    fig, ax = plt.subplots(figsize=(7, 2.6))
    labels = [hotel_name[:22], "Moyenne du parc", "Meilleur hôtel"]
    values = [hotel_ca, avg_ca, top_ca]
    colors_ = [MPL_BLUE, MPL_GREY, MPL_GREEN]
    bars = ax.barh(labels, values, color=colors_, height=0.5)
    ax.invert_yaxis()
    ax.set_title("Chiffre d'affaires confirmé : positionnement de l'hôtel", fontsize=12, fontweight="bold", loc="left")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", " ")))
    for bar, val in zip(bars, values):
        ax.text(val, bar.get_y() + bar.get_height() / 2, f"  {format_currency(val)}",
                va="center", fontsize=8, color="#0F172A")
    ax.tick_params(labelsize=9)
    fig.tight_layout()
    return fig


def _cover_page(story, styles, hotel_name, period_label, filters_label):
    title_style = ParagraphStyle(
        "CoverTitle", parent=styles["Title"], fontSize=26, textColor=colors.HexColor(COLORS["text"]),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "CoverSubtitle", parent=styles["Normal"], fontSize=14, textColor=colors.HexColor(COLORS["blue"]),
        spaceAfter=30,
    )
    meta_style = ParagraphStyle(
        "CoverMeta", parent=styles["Normal"], fontSize=10.5, textColor=colors.HexColor(COLORS["text_secondary"]),
        spaceAfter=4, leading=16,
    )

    # Logo / wordmark simplifié (pas de fichier image fourni)
    logo_style = ParagraphStyle(
        "Logo", parent=styles["Normal"], fontSize=20, textColor=colors.HexColor(COLORS["blue"]),
        fontName="Helvetica-Bold",
    )
    story.append(Spacer(1, 30))
    story.append(Paragraph("NAMLATIC", logo_style))
    story.append(Spacer(1, 60))
    story.append(Paragraph("Rapport de performance hôtelière", title_style))
    story.append(Paragraph(hotel_name, subtitle_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"<b>Date de génération :</b> {datetime.now().strftime('%d/%m/%Y à %H:%M')}", meta_style))
    story.append(Paragraph(f"<b>Période analysée :</b> {period_label}", meta_style))
    story.append(Paragraph(f"<b>Filtres appliqués :</b> {filters_label}", meta_style))
    story.append(Paragraph("<b>Auteur :</b> Namlatic — Dashboard Réservations Hôtelières", meta_style))
    story.append(PageBreak())


def _kpi_table(kpis: dict, refund_split) -> Table:
    refunded = int(refund_split.loc[refund_split["Type"] == "Remboursées", "Nombre"].sum()) if not refund_split.empty else 0
    non_refunded = int(refund_split.loc[refund_split["Type"] == "Non remboursées", "Nombre"].sum()) if not refund_split.empty else 0

    data = [
        ["Indicateur", "Valeur"],
        ["Chiffre d'affaires confirmé", format_currency(kpis["ca"])],
        ["Nombre de réservations", f"{kpis['reservations']:,}".replace(",", " ")],
        ["Nombre d'annulations", f"{refunded + non_refunded:,}".replace(",", " ")],
        ["Taux d'annulation", format_pct(kpis["taux_annulation"])],
        ["Frais d'annulation encaissés (cash réel)", format_currency(kpis["frais_annulation_reels"])],
        ["Manque à gagner potentiel (valeur nominale, non cash)", format_currency(kpis["manque_a_gagner_potentiel"])],
        ["Réservations remboursées", f"{refunded:,}".replace(",", " ")],
        ["Réservations non remboursées", f"{non_refunded:,}".replace(",", " ")],
    ]
    table = Table(data, colWidths=[110 * mm, 60 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(COLORS["blue"])),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(COLORS["grey_light"])),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return table


def generate_hotel_report_pdf(df_hotel, df_all, hotel_name: str, period_label: str, filters_label: str) -> bytes:
    """Construit le rapport PDF complet pour un hôtel et retourne les octets du fichier."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN,
        title=f"Rapport - {hotel_name}",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], textColor=colors.HexColor(COLORS["text"]), fontSize=16, spaceAfter=10)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=colors.HexColor(COLORS["blue"]), fontSize=13, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10.5, leading=15.5, textColor=colors.HexColor(COLORS["text"]))
    exec_box = ParagraphStyle("ExecBox", parent=body, backColor=colors.HexColor("#EFF6FF"), borderPadding=10, leading=16)

    story = []

    # --- 1. Page de garde ---------------------------------------------------
    _cover_page(story, styles, hotel_name, period_label, filters_label)

    # --- Calculs sous-jacents ------------------------------------------------
    kpis = hotel_kpis(df_hotel)
    benchmark = global_benchmark(df_all)
    refund_split = hotel_cancel_refund_split(df_hotel)
    revenue_evo = hotel_monthly_revenue(df_hotel)
    bookings_evo = hotel_monthly_bookings(df_hotel)
    fee_evo = hotel_monthly_cancellation_fee(df_hotel)

    health = compute_health_score(kpis, benchmark)

    # --- 2. Résumé exécutif --------------------------------------------------
    story.append(Paragraph("Résumé exécutif", h1))
    summary_text = build_executive_summary(hotel_name, kpis, benchmark)
    story.append(Paragraph(summary_text, exec_box))
    story.append(Spacer(1, 10))

    # Score de santé
    score_style = ParagraphStyle(
        "Score", parent=styles["Normal"], fontSize=22, fontName="Helvetica-Bold",
        textColor=colors.HexColor(COLORS["text"]),
    )
    story.append(Paragraph(
        f"{health['emoji']} Score de santé global : <font color='{COLORS['blue']}'>{health['score']}/100</font> "
        f"— {health['category']}", score_style
    ))
    story.append(Spacer(1, 16))

    # --- 3. KPI ---------------------------------------------------------------
    story.append(Paragraph("Indicateurs clés", h1))
    story.append(_kpi_table(kpis, refund_split))
    story.append(PageBreak())

    # --- 4. Graphiques ----------------------------------------------------
    story.append(Paragraph("Évolution de l'activité", h1))
    if not revenue_evo.empty:
        story.append(_fig_to_image(_line_chart(revenue_evo, "YearMonth", "CA", "Évolution du chiffre d'affaires", MPL_GREEN, "CA (DZD)")))
        story.append(Spacer(1, 8))
    if not bookings_evo.empty:
        story.append(_fig_to_image(_bar_chart(bookings_evo, "YearMonth", "Reservations", "Évolution des réservations", MPL_BLUE, "Réservations")))
        story.append(Spacer(1, 8))
    story.append(PageBreak())

    if not fee_evo.empty:
        cancel_evo = bookings_evo.merge(
            df_hotel[df_hotel["IsCancelled"]].groupby("YearMonth").size().rename("Annulations").reset_index(),
            on="YearMonth", how="left",
        ).fillna(0)
        story.append(_fig_to_image(_bar_chart(cancel_evo, "YearMonth", "Annulations", "Évolution des annulations", MPL_ORANGE, "Annulations")))
        story.append(Spacer(1, 8))
        story.append(_fig_to_image(_bar_chart(fee_evo, "YearMonth", "FraisEncaisses", "Frais d'annulation réellement encaissés (cash réel)", MPL_BLUE, "Frais encaissés (DZD)")))
        story.append(Spacer(1, 8))

    # --- Comparaison avec les autres hôtels --------------------------------
    story.append(Paragraph("Comparaison avec les autres hôtels", h1))
    story.append(_fig_to_image(_comparison_chart(hotel_name, kpis["ca"], benchmark["avg_ca"], benchmark["top_ca"])))
    story.append(PageBreak())

    # --- 5. Analyse automatique ---------------------------------------------
    story.append(Paragraph("Analyse automatique", h1))

    story.append(Paragraph("Performance commerciale", h2))
    story.append(Paragraph(build_performance_analysis(revenue_evo), body))

    story.append(Paragraph("Annulations", h2))
    story.append(Paragraph(build_cancellation_analysis(kpis, benchmark, refund_split), body))

    story.append(Paragraph("Frais d'annulation encaissés (cash réel)", h2))
    story.append(Paragraph(build_cancellation_fee_analysis(fee_evo), body))

    story.append(Paragraph("Manque à gagner potentiel (valeur nominale)", h2))
    manque_evo_real = df_hotel[df_hotel["IsCancelled"] & df_hotel["IsRefunded"]].groupby("YearMonth", as_index=False).agg(ManqueAGagner=("RefundAmount", "sum")).sort_values("YearMonth")
    story.append(Paragraph(build_manque_a_gagner_analysis(manque_evo_real), body))

    # --- 6. Recommandations ---------------------------------------------------
    story.append(Paragraph("Recommandations", h1))
    recos = build_recommendations(kpis, benchmark, manque_evo_real)
    for reco in recos:
        story.append(Paragraph(f"✅ {reco}", body))
        story.append(Spacer(1, 4))

    # --- Pied de page traçabilité --------------------------------------------
    story.append(Spacer(1, 24))
    footer_style = ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor(COLORS["text_secondary"]))
    story.append(Paragraph("Analyse générée automatiquement — règles métier déterministes (sans IA externe)", footer_style))
    story.append(Paragraph(f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}", footer_style))
    story.append(Paragraph("Version : 1.0", footer_style))
    story.append(Paragraph(f"Filtres utilisés : {filters_label}", footer_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
