"""
metrics.py
----------
Tous les calculs métier (KPI, agrégations) centralisés ici. Les 3
interfaces appellent ces mêmes fonctions : aucune duplication de logique
de calcul entre les pages.

⚠️ RÈGLES MÉTIER OFFICIELLES (communiquées par Namlatic, remplacent les
anciennes hypothèses de l'audit précédent) :
1. Annulation AVANT le Jour J (jour d'arrivée) : remboursement à 100 % si le
   client avait payé → Namlatic ne conserve aucun revenu (hors frais
   d'annulation éventuels). `RefundAmount` == `BookingAmount` dans ce cas.
2. Annulation LE Jour J : remboursement partiel (uniquement les jours de
   séjour restants) → le montant du Jour J reste acquis à Namlatic.
   `RefundAmount` < `BookingAmount` dans ce cas (vérifié sur les données :
   295 réservations annulées avec un remboursement strictement partiel,
   cohérent avec cette règle).

Conséquence directe pour le code : `RefundAmount` est désormais la
RÉFÉRENCE OFFICIELLE pour tout calcul de remboursement réellement effectué
(remplace l'ancienne prudence "nominal, pas cash" — la règle métier
ci-dessus confirme sa fiabilité, y compris pour les réservations payées à
l'hôtel : le remboursement peut concerner un acompte, une garantie, ou être
calculé par le système indépendamment du canal de paiement).
Note factuelle conservée : `AmountPaid` ne reflète que les paiements
réalisés en ligne via la plateforme (peu utilisé sur ce parc, dominé par le
paiement à l'hôtel) — ce n'est PAS la même chose que "le client a payé" au
sens large, donc `AmountPaid` n'est plus utilisé comme référence de calcul.

Conventions retenues (6 KPI financiers de la section "Analyse du chiffre
d'affaires", tous vérifiés pour exclure tout double comptage — voir
`compute_global_kpis` et son garde-fou `no_double_counting_ok`) :

1. CA total généré              = Σ BookingAmount (TOUTES réservations)
2. CA confirmé                  = Σ BookingAmount (réservations NON annulées)
3. Valeur totale des réservations annulées = Σ BookingAmount (réservations annulées)
4. Montant réellement remboursé = Σ RefundAmount (réservations annulées)
5. Revenu conservé sur annulées = Σ (BookingAmount − RefundAmount) (réservations annulées)
                                 = Valeur totale annulée − Montant remboursé
                                 → le "Jour J" retenu par Namlatic malgré l'annulation.
6. CA annulé sans remboursement = Σ BookingAmount où RefundAmount == 0
                                 (sous-ensemble de "Revenu conservé" : annulations
                                 où AUCUN remboursement n'a eu lieu, par opposition
                                 aux annulations Jour J où un remboursement partiel
                                 a quand même eu lieu).

Identités de cohérence (aucun double comptage) :
  (1) = (2) + (3)                    [partition annulé / non annulé]
  (3) = (4) + (5)                    [partition remboursé / conservé, par construction]
  (6) ≤ (5)                          [sous-ensemble, PAS une somme supplémentaire]
"""

import pandas as pd


def compute_global_kpis(df: pd.DataFrame) -> dict:
    non_cancelled = df[~df["IsCancelled"]]
    complete = df[df["BookingStatus"] == "complete"]
    pipeline = df[df["BookingStatus"].isin(["upcoming", "ongoing"])]
    cancelled = df[df["IsCancelled"]]
    non_refunded = cancelled[cancelled["RefundAmount"] == 0]
    refunded = cancelled[cancelled["RefundAmount"] > 0]

    total_bookings = len(df)
    cancelled_count = len(cancelled)

    ca_total_genere = df["BookingAmount"].sum()
    ca_confirme = non_cancelled["BookingAmount"].sum()
    valeur_totale_annulee = cancelled["BookingAmount"].sum()
    montant_rembourse = cancelled["RefundAmount"].sum()
    revenu_conserve_annulees = valeur_totale_annulee - montant_rembourse
    ca_annule_sans_remboursement = non_refunded["BookingAmount"].sum()

    kpis = {
        # --- Les 6 KPI de la section "Analyse du chiffre d'affaires" ---------
        "ca_total_genere": ca_total_genere,
        "ca_confirme": ca_confirme,
        "valeur_totale_annulee": valeur_totale_annulee,
        "montant_rembourse": montant_rembourse,
        "revenu_conserve_annulees": revenu_conserve_annulees,
        "ca_annule_sans_remboursement": ca_annule_sans_remboursement,
        # --- Compléments (répartition, KPI déjà existants, inchangés) --------
        "ca_realise": complete["BookingAmount"].sum(),
        "ca_pipeline": pipeline["BookingAmount"].sum(),
        "valeur_cancel_refunded": refunded["BookingAmount"].sum(),
        "valeur_cancel_non_refunded": ca_annule_sans_remboursement,
        "cancel_refunded_count": len(refunded),
        "cancel_non_refunded_count": len(non_refunded),
        "frais_annulation_reels": cancelled["CancelledFee"].sum(),
        "taux_annulation": (cancelled_count / total_bookings * 100) if total_bookings else 0.0,
        "total_bookings": total_bookings,
        "cancelled_count": cancelled_count,
    }

    # --- Garde-fous anti double comptage (vérifiés à chaque calcul) ---------
    check_1 = abs((ca_confirme + valeur_totale_annulee) - ca_total_genere) < 0.01
    check_2 = abs((montant_rembourse + revenu_conserve_annulees) - valeur_totale_annulee) < 0.01
    kpis["no_double_counting_ok"] = check_1 and check_2

    return kpis


def revenue_evolution(df: pd.DataFrame) -> pd.DataFrame:
    """CA confirmé mensuel (réservations non annulées) pour le graphique d'évolution."""
    base = df[~df["IsCancelled"]]
    out = (
        base.groupby("YearMonth", as_index=False)
        .agg(CA=("BookingAmount", "sum"), Reservations=("BookingNo", "count"))
        .sort_values("YearMonth")
    )
    return out


def revenue_breakdown(kpis: dict) -> pd.DataFrame:
    """Répartition du CA TOTAL GÉNÉRÉ en 3 blocs mutuellement exclusifs,
    conformes aux règles métier Jour J :
      - CA confirmé                 (réservations non annulées)
      - Montant remboursé           (argent rendu sur annulations)
      - Revenu conservé (annulées)  (le "Jour J" gardé par Namlatic)

    Ces 3 blocs somment EXACTEMENT à "CA total généré" (voir
    compute_global_kpis -> no_double_counting_ok) : remplace l'ancienne
    répartition à 4 catégories en valeur nominale, devenue incohérente avec
    les nouvelles règles métier (remboursement partiel Jour J).
    """
    return pd.DataFrame(
        {
            "Catégorie": ["CA confirmé", "Montant remboursé (annulées)", "Revenu conservé (annulées)"],
            "Montant": [kpis["ca_confirme"], kpis["montant_rembourse"], kpis["revenu_conserve_annulees"]],
        }
    )


def cancellation_rate_evolution(df: pd.DataFrame) -> pd.DataFrame:
    out = (
        df.groupby("YearMonth")
        .agg(Total=("BookingNo", "count"), Annulees=("IsCancelled", "sum"))
        .reset_index()
        .sort_values("YearMonth")
    )
    out["TauxAnnulation"] = (out["Annulees"] / out["Total"] * 100).fillna(0)
    return out


def cancellation_fee_evolution(df: pd.DataFrame) -> pd.DataFrame:
    """Frais d'annulation RÉELLEMENT encaissés (CancelledFee), par mois.
    C'est la grandeur fiable à utiliser pour parler d'impact financier des
    annulations — contrairement à RefundAmount qui est nominal (voir en-tête
    du module)."""
    cancelled = df[df["IsCancelled"]]
    out = (
        cancelled.groupby("YearMonth", as_index=False)
        .agg(FraisEncaisses=("CancelledFee", "sum"))
        .sort_values("YearMonth")
    )
    return out


def manque_a_gagner_evolution(df: pd.DataFrame) -> pd.DataFrame:
    """Évolution du manque à gagner POTENTIEL (nominal, RefundAmount) —
    à afficher toujours avec la mention explicite "valeur nominale, pas du
    cash réel"."""
    cancelled = df[df["IsCancelled"] & df["IsRefunded"]]
    out = (
        cancelled.groupby("YearMonth", as_index=False)
        .agg(ManqueAGagner=("RefundAmount", "sum"))
        .sort_values("YearMonth")
    )
    return out


def previous_period_df(df_all: pd.DataFrame, filtered: pd.DataFrame, hotels=None, types=None) -> pd.DataFrame:
    """Retourne le sous-ensemble correspondant à la période immédiatement
    précédente, de même durée que `filtered`, avec les mêmes filtres
    hôtel/type — utilisé pour calculer les deltas de tendance sur les KPI.
    """
    if filtered.empty:
        return filtered
    start = filtered["RefDate"].min()
    end = filtered["RefDate"].max()
    duration = end - start
    prev_end = start - pd.Timedelta(seconds=1)
    prev_start = prev_end - duration
    subset = df_all[(df_all["RefDate"] >= prev_start) & (df_all["RefDate"] <= prev_end)]
    if hotels:
        subset = subset[subset["HotelName"].isin(hotels)]
    if types:
        subset = subset[subset["BookingType"].isin(types)]
    return subset


def payment_type_cancellation(df: pd.DataFrame) -> pd.DataFrame:
    """Taux d'annulation par mode de paiement. Signal fort identifié en audit :
    les réservations sans engagement financier amont (paiement à l'hôtel)
    annulent nettement plus que celles payées en ligne — levier actionnable
    concret (ex. exiger un acompte pour ces modes de paiement)."""
    PAYMENT_LABELS = {
        "pah": "Paiement à l'hôtel",
        "wt": "Virement (wt)",
        "card": "Carte bancaire",
        "wallet": "Wallet",
        "satim_cib": "SATIM / CIB",
    }
    out = (
        df.groupby("PaymentType")
        .agg(Total=("BookingNo", "count"), Annulees=("IsCancelled", "sum"))
        .reset_index()
    )
    out["TauxAnnulation"] = (out["Annulees"] / out["Total"] * 100).fillna(0)
    out["Libelle"] = out["PaymentType"].map(PAYMENT_LABELS).fillna(out["PaymentType"])
    return out.sort_values("TauxAnnulation", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------
# Interface 2 : analyse par hôtel
# --------------------------------------------------------------------------

def hotel_kpis(df_hotel: pd.DataFrame) -> dict:
    cancelled = df_hotel[df_hotel["IsCancelled"]]
    refunded = cancelled[cancelled["IsRefunded"]]
    total = len(df_hotel)
    return {
        "reservations": total,
        "ca": df_hotel[~df_hotel["IsCancelled"]]["BookingAmount"].sum(),
        "taux_annulation": (len(cancelled) / total * 100) if total else 0.0,
        "frais_annulation_reels": cancelled["CancelledFee"].sum(),
        "manque_a_gagner_potentiel": refunded["RefundAmount"].sum(),
        # Ancien alias conservé pour compatibilité interne (score de santé, etc.)
        "revenus_perdus": refunded["RefundAmount"].sum(),
    }


def hotel_monthly_bookings(df_hotel: pd.DataFrame) -> pd.DataFrame:
    return (
        df_hotel.groupby("YearMonth", as_index=False)
        .agg(Reservations=("BookingNo", "count"))
        .sort_values("YearMonth")
    )


def hotel_monthly_revenue(df_hotel: pd.DataFrame) -> pd.DataFrame:
    base = df_hotel[~df_hotel["IsCancelled"]]
    return (
        base.groupby("YearMonth", as_index=False)
        .agg(CA=("BookingAmount", "sum"))
        .sort_values("YearMonth")
    )


def hotel_cancel_refund_split(df_hotel: pd.DataFrame) -> pd.DataFrame:
    cancelled = df_hotel[df_hotel["IsCancelled"]]
    refunded_count = int(cancelled["IsRefunded"].sum())
    non_refunded_count = int((~cancelled["IsRefunded"]).sum())
    return pd.DataFrame(
        {
            "Type": ["Remboursées", "Non remboursées"],
            "Nombre": [refunded_count, non_refunded_count],
        }
    )


def hotel_monthly_cancellation_fee(df_hotel: pd.DataFrame) -> pd.DataFrame:
    """Frais d'annulation réellement encaissés (cash réel) pour un hôtel."""
    cancelled = df_hotel[df_hotel["IsCancelled"]]
    return (
        cancelled.groupby("YearMonth", as_index=False)
        .agg(FraisEncaisses=("CancelledFee", "sum"))
        .sort_values("YearMonth")
    )


def hotel_cancel_reason_split(df_hotel: pd.DataFrame, top_n: int = 6) -> pd.DataFrame:
    cancelled = df_hotel[df_hotel["IsCancelled"]].copy()
    cancelled["CancelledReason"] = cancelled["CancelledReason"].fillna("Non précisé").replace("", "Non précisé")
    counts = cancelled["CancelledReason"].value_counts().head(top_n).reset_index()
    counts.columns = ["Motif", "Nombre"]
    return counts


# --------------------------------------------------------------------------
# Interface 3 : classement des hôtels
# --------------------------------------------------------------------------

def global_benchmark(df: pd.DataFrame) -> dict:
    """Indicateurs de référence utilisés pour comparer un hôtel au reste du parc
    (rapport PDF, score de santé)."""
    ranking = hotel_ranking_table(df)
    global_kpis = compute_global_kpis(df)
    return {
        "avg_ca": ranking["Chiffre d'affaires (DZD)"].mean() if not ranking.empty else 0.0,
        "avg_reservations": ranking["Réservations"].mean() if not ranking.empty else 0.0,
        "taux_annulation": global_kpis["taux_annulation"],
        "top_ca": ranking["Chiffre d'affaires (DZD)"].max() if not ranking.empty else 0.0,
        "top_reservations": ranking["Réservations"].max() if not ranking.empty else 0.0,
    }


def hotel_ranking_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for hotel, g in df.groupby("HotelName"):
        cancelled = g[g["IsCancelled"]]
        refunded = cancelled[cancelled["IsRefunded"]]
        total = len(g)
        rows.append(
            {
                "Hôtel": hotel,
                "Réservations": total,
                "Chiffre d'affaires (DZD)": g[~g["IsCancelled"]]["BookingAmount"].sum(),
                "Annulations": len(cancelled),
                "Taux d'annulation (%)": round((len(cancelled) / total * 100) if total else 0.0, 1),
                "Frais d'annulation encaissés (DZD)": cancelled["CancelledFee"].sum(),
                "Manque à gagner potentiel (DZD)": refunded["RefundAmount"].sum(),
            }
        )
    out = pd.DataFrame(rows)
    return out.sort_values("Chiffre d'affaires (DZD)", ascending=False).reset_index(drop=True)
