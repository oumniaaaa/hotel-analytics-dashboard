"""
insights.py
-----------
Moteur de règles métier : génère des commentaires et recommandations
déterministes à partir des KPI, sans appel à un LLM externe. Les analyses
sont donc reproductibles, rapides et cohérentes d'un rapport à l'autre.

Toute la logique de seuils vit ici : pour ajuster la sensibilité des
commentaires, il suffit de modifier les constantes ci-dessous.
"""

from utils.style import format_currency, format_pct

# --- Seuils métier (ajustables) --------------------------------------------
SEUIL_ANNULATION_ELEVE = 20.0     # % au-dessus duquel le taux d'annulation est "à risque"
SEUIL_ANNULATION_MODERE = 10.0    # % au-dessus duquel il faut "surveiller"
SEUIL_NON_REMBOURSE_PROTECTEUR = 60.0  # % d'annulations non remboursées jugé "protecteur"


def _trend_direction(series) -> str:
    """Compare la 1ère et la 2ème moitié d'une série temporelle pour dégager une tendance simple."""
    values = list(series)
    if len(values) < 2:
        return "stable"
    mid = len(values) // 2
    first_half = sum(values[:mid]) / max(mid, 1)
    second_half = sum(values[mid:]) / max(len(values) - mid, 1)
    if first_half == 0 and second_half == 0:
        return "stable"
    delta = (second_half - first_half) / (first_half if first_half else 1)
    if delta > 0.10:
        return "hausse"
    if delta < -0.10:
        return "baisse"
    return "stable"


def compute_health_score(hotel_kpis: dict, global_avg: dict) -> dict:
    """Calcule un score de santé /100 à partir de 4 composantes pondérées.

    - CA relatif au meilleur hôtel                        → 30 %
    - Maîtrise du taux d'annulation                        → 30 %
    - Maîtrise du manque à gagner potentiel (vs CA hôtel)  → 20 %
    - Volume de réservations relatif au top hôtel          → 20 %

    Note (audit) : le paramètre `ranking_row` précédemment présent dans la
    signature n'était jamais utilisé dans le calcul — il a été retiré plutôt
    que laissé comme code mort. Les comparaisons "relatif au parc" passent
    déjà entièrement par `global_avg`.
    """
    top_ca = max(global_avg["top_ca"], 1)
    top_res = max(global_avg["top_reservations"], 1)

    score_ca = min(hotel_kpis["ca"] / top_ca, 1.0) * 100
    score_annulation = max(0.0, 100 - hotel_kpis["taux_annulation"] * 2.5)

    if hotel_kpis["ca"] > 0:
        ratio_pertes = hotel_kpis["manque_a_gagner_potentiel"] / hotel_kpis["ca"] * 100
        score_pertes = max(0.0, 100 - ratio_pertes * 3)
    elif hotel_kpis["reservations"] > 0:
        # Cas dégradé explicite (audit) : CA confirmé nul (toutes les
        # réservations ont été annulées) = le pire scénario possible, PAS un
        # score parfait. La division par zéro était auparavant "évitée" en
        # renvoyant 0 au ratio, ce qui donnait à tort un score de 100.
        score_pertes = 0.0
    else:
        # Aucune réservation du tout sur la période : donnée insuffisante,
        # on neutralise cette composante plutôt que de la faire échouer.
        score_pertes = 50.0

    score_volume = min(hotel_kpis["reservations"] / top_res, 1.0) * 100

    total = 0.30 * score_ca + 0.30 * score_annulation + 0.20 * score_pertes + 0.20 * score_volume
    total = round(max(0.0, min(100.0, total)))

    if total >= 80:
        category, emoji = "Excellent", "🟢"
    elif total >= 50:
        category, emoji = "Correct", "🟡"
    else:
        category, emoji = "À surveiller", "🔴"

    return {"score": total, "category": category, "emoji": emoji}


def build_executive_summary(hotel_name: str, hotel_kpis: dict, global_avg: dict) -> str:
    ecart = hotel_kpis["taux_annulation"] - global_avg["taux_annulation"]
    comparatif = "supérieur" if ecart > 0 else "inférieur"
    return (
        f"L'hôtel {hotel_name} a généré un chiffre d'affaires confirmé de "
        f"{format_currency(hotel_kpis['ca'])} durant la période sélectionnée, pour "
        f"{hotel_kpis['reservations']:,}".replace(",", " ") + " réservations. "
        f"Son taux d'annulation est de {format_pct(hotel_kpis['taux_annulation'])}, "
        f"{comparatif} à la moyenne globale ({format_pct(global_avg['taux_annulation'])}). "
        f"Les frais d'annulation réellement encaissés s'élèvent à "
        f"{format_currency(hotel_kpis['frais_annulation_reels'])} ; le manque à gagner "
        f"potentiel associé aux annulations remboursées, en valeur nominale (non cash), "
        f"est de {format_currency(hotel_kpis['manque_a_gagner_potentiel'])}."
    )


def build_performance_analysis(revenue_evo) -> str:
    trend = _trend_direction(revenue_evo["CA"]) if not revenue_evo.empty else "stable"
    if len(revenue_evo) < 2:
        return "Historique insuffisant sur la période pour dégager une tendance de chiffre d'affaires fiable."
    if trend == "hausse":
        return (
            "Le chiffre d'affaires présente une progression sur la seconde partie de la période "
            "analysée par rapport à la première, signe d'une dynamique commerciale positive."
        )
    if trend == "baisse":
        return (
            "Le chiffre d'affaires marque un recul sur la seconde partie de la période analysée "
            "par rapport à la première. Une attention particulière sur les leviers commerciaux est recommandée."
        )
    return "Le chiffre d'affaires reste globalement stable sur l'ensemble de la période analysée."


def build_cancellation_analysis(hotel_kpis: dict, global_avg: dict, refund_split) -> str:
    parts = []
    if hotel_kpis["taux_annulation"] > SEUIL_ANNULATION_ELEVE:
        parts.append(
            f"Le taux d'annulation ({format_pct(hotel_kpis['taux_annulation'])}) dépasse le seuil "
            f"de vigilance de {SEUIL_ANNULATION_ELEVE:.0f} % et signale un risque élevé."
        )
    elif hotel_kpis["taux_annulation"] > SEUIL_ANNULATION_MODERE:
        parts.append(
            f"Le taux d'annulation ({format_pct(hotel_kpis['taux_annulation'])}) est modéré mais "
            "mérite d'être surveillé dans les mois à venir."
        )
    else:
        parts.append(
            f"Le taux d'annulation ({format_pct(hotel_kpis['taux_annulation'])}) reste maîtrisé."
        )

    if hotel_kpis["taux_annulation"] > global_avg["taux_annulation"]:
        parts.append(f"Il reste supérieur à la moyenne globale ({format_pct(global_avg['taux_annulation'])}).")
    else:
        parts.append(f"Il reste inférieur à la moyenne globale ({format_pct(global_avg['taux_annulation'])}).")

    total_cancel = refund_split["Nombre"].sum()
    if total_cancel > 0:
        non_refund_count = refund_split.loc[refund_split["Type"] == "Non remboursées", "Nombre"].sum()
        pct_non_refund = non_refund_count / total_cancel * 100
        if pct_non_refund >= SEUIL_NON_REMBOURSE_PROTECTEUR:
            parts.append(
                f"Les annulations non remboursées représentent {pct_non_refund:.0f} % des annulations, "
                "ce qui limite l'impact financier réel."
            )
        else:
            parts.append(
                f"Seules {pct_non_refund:.0f} % des annulations ne sont pas remboursées : l'impact "
                "financier des annulations reste significatif."
            )

    return " ".join(parts)


def build_manque_a_gagner_analysis(manque_evo) -> str:
    """Analyse du manque à gagner POTENTIEL (nominal, non cash — voir metrics.py)."""
    if manque_evo.empty or manque_evo["ManqueAGagner"].sum() == 0:
        return "Aucun manque à gagner potentiel lié aux annulations remboursées n'a été enregistré sur la période."
    trend = _trend_direction(manque_evo["ManqueAGagner"])
    peak_month = manque_evo.loc[manque_evo["ManqueAGagner"].idxmax(), "YearMonth"]
    if trend == "hausse":
        return (
            f"Le manque à gagner potentiel (valeur nominale, pas du cash réellement remboursé) "
            f"augmente sur la période, avec un pic observé en {peak_month}. "
            "Cela suggère une amélioration possible de la politique d'annulation durant les périodes de forte activité."
        )
    if trend == "baisse":
        return (
            f"Le manque à gagner potentiel est en recul sur la période, malgré un pic ponctuel en {peak_month}."
        )
    return f"Le manque à gagner potentiel reste stable sur la période, avec un pic ponctuel en {peak_month}."


def build_cancellation_fee_analysis(fee_evo) -> str:
    """Analyse des frais d'annulation RÉELLEMENT encaissés (cash réel)."""
    if fee_evo.empty or fee_evo["FraisEncaisses"].sum() == 0:
        return "Aucun frais d'annulation n'a été réellement encaissé sur la période."
    total = fee_evo["FraisEncaisses"].sum()
    return (
        f"Les frais d'annulation réellement encaissés (cash réel, hors valeur nominale) totalisent "
        f"{format_currency(total)} sur la période. C'est la grandeur la plus fiable pour évaluer "
        f"l'impact financier concret des annulations."
    )


def build_revenue_split_interpretation(kpis: dict) -> str:
    """Interprétation automatique de la répartition du CA total généré, pour
    la section "Analyse du chiffre d'affaires" du Dashboard Global.
    Explique explicitement la différence entre valeur annulée, montant
    remboursé et revenu conservé, conformément aux règles métier Jour J."""
    total = kpis["ca_total_genere"]
    if total <= 0:
        return "Aucune donnée suffisante pour interpréter la répartition du chiffre d'affaires sur la période sélectionnée."

    pct_confirme = kpis["ca_confirme"] / total * 100
    pct_annule = kpis["valeur_totale_annulee"] / total * 100
    pct_rembourse_sur_annule = (
        kpis["montant_rembourse"] / kpis["valeur_totale_annulee"] * 100 if kpis["valeur_totale_annulee"] > 0 else 0.0
    )
    pct_conserve_sur_annule = 100 - pct_rembourse_sur_annule if kpis["valeur_totale_annulee"] > 0 else 0.0

    parts = [
        f"Sur un chiffre d'affaires total généré de {format_currency(total)}, "
        f"{format_pct(pct_confirme)} correspond à du CA confirmé (réservations non annulées) et "
        f"{format_pct(pct_annule)} à des réservations annulées ({format_currency(kpis['valeur_totale_annulee'])})."
    ]

    parts.append(
        f"Sur cette valeur annulée, {format_pct(pct_rembourse_sur_annule)} a été réellement remboursé au client "
        f"({format_currency(kpis['montant_rembourse'])}) — typiquement les annulations survenues avant le Jour J — "
        f"tandis que {format_pct(pct_conserve_sur_annule)} ({format_currency(kpis['revenu_conserve_annulees'])}) "
        f"est resté acquis à Namlatic, notamment via le Jour J non remboursé sur les annulations tardives."
    )

    if kpis["ca_annule_sans_remboursement"] > 0:
        pct_sans_remb = kpis["ca_annule_sans_remboursement"] / kpis["valeur_totale_annulee"] * 100 if kpis["valeur_totale_annulee"] > 0 else 0
        parts.append(
            f"Parmi les annulations, {format_currency(kpis['ca_annule_sans_remboursement'])} ({format_pct(pct_sans_remb)} "
            "de la valeur annulée) n'ont donné lieu à aucun remboursement — intégralement conservées par Namlatic."
        )

    if not kpis.get("no_double_counting_ok", True):
        parts.append("⚠️ Incohérence détectée dans la reconstruction des totaux — à vérifier.")

    return " ".join(parts)


def build_recommendations(hotel_kpis: dict, global_avg: dict, manque_evo) -> list[str]:
    recos = []
    if hotel_kpis["taux_annulation"] > SEUIL_ANNULATION_MODERE:
        recos.append("Réduire les délais d'annulation gratuite pour limiter le risque d'annulation tardive.")
        recos.append("Renforcer la confirmation des réservations (rappel automatique avant la date de check-in).")
    if not manque_evo.empty and _trend_direction(manque_evo["ManqueAGagner"]) == "hausse":
        recos.append("Étudier les causes des annulations durant les périodes de forte demande.")
    if hotel_kpis["ca"] < global_avg["avg_ca"]:
        recos.append("Analyser le positionnement tarifaire et l'offre commerciale pour rapprocher le CA de la moyenne du parc hôtelier.")
    if not recos:
        recos.append("Maintenir les pratiques actuelles : les indicateurs de cet hôtel sont sains sur la période analysée.")
    return recos
