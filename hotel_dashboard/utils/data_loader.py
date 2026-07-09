"""
data_loader.py
--------------
Chargement, nettoyage et mise en cache des données de réservations hôtelières.
Toute la logique de parsing/nettoyage vit ici pour éviter toute duplication
dans les pages de l'application.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "bookings_raw_merged.csv"

# Colonnes numériques qui doivent être présentes même si vides dans le CSV brut
NUMERIC_COLS = [
    "RoomCount", "GuestCount", "Days", "BookingAmount", "BookingAmount_Vat",
    "AmountPaid", "AmountToPayAtHotel", "CancelledFee", "ServiceCharge",
    "RefundAmount", "CIBBankFee", "HotelCommission", "HotelOwnerVAT",
    "NamlaticCommission", "NamlaticVat", "AgentCommission", "AgentDocumentFees",
]

STATUS_LABELS = {
    "complete": "Complète",
    "upcoming": "À venir",
    "ongoing": "En cours",
    "cancel": "Annulée",
}


@st.cache_data(show_spinner=False)
def load_bookings(path: str | Path = DATA_PATH) -> pd.DataFrame:
    """Charge le CSV fusionné et applique tout le nettoyage nécessaire.

    Le résultat est mis en cache par Streamlit : le nettoyage (parsing de
    dates, typage, colonnes dérivées) n'est exécuté qu'une seule fois par
    session tant que le fichier source ne change pas.
    """
    df = pd.read_csv(path)

    # --- Nettoyage des chaînes -------------------------------------------------
    df["HotelName"] = df["HotelName"].astype(str).str.strip()
    df["BookingStatus"] = df["BookingStatus"].astype(str).str.strip().str.lower()
    df["BookingType"] = df["BookingType"].astype(str).str.strip().str.lower()
    df["PaymentType"] = df["PaymentType"].astype(str).str.strip().str.lower()

    # --- Colonnes numériques : NaN -> 0 -----------------------------------------
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # --- Dates -------------------------------------------------------------
    # BookedOn : "11 Jun 2026 13:38:40 ( CET +01:00 )" — toutes les valeurs sont
    # exprimées en CET = UTC+1 fixe (Algérie n'applique pas l'heure d'été).
    # On retire l'étiquette de fuseau puis on convertit explicitement en UTC
    # naïf pour être dans le MÊME référentiel temporel que CancelledOn
    # ci-dessous (correction d'un bug où BookedOn restait en heure locale
    # brute pendant que CancelledOn était converti en UTC, créant un écart
    # d'environ 1h entre les deux colonnes).
    booked_clean = df["BookedOn"].astype(str).str.replace(
        r"\s*\(.*\)\s*$", "", regex=True
    )
    booked_local = pd.to_datetime(booked_clean, format="%d %b %Y %H:%M:%S", errors="coerce")
    df["BookedOn"] = booked_local - pd.Timedelta(hours=1)  # CET (UTC+1) -> UTC naïf

    df["CheckIn"] = pd.to_datetime(df["CheckIn"], format="%d/%m/%Y", errors="coerce")
    df["CheckOut"] = pd.to_datetime(df["CheckOut"], format="%d/%m/%Y", errors="coerce")

    # CancelledOn n'est renseigné que pour les réservations annulées (format ISO, UTC)
    df["CancelledOn"] = pd.to_datetime(df["CancelledOn"], errors="coerce", utc=True).dt.tz_localize(None)

    # --- Colonnes dérivées ---------------------------------------------------
    df["IsCancelled"] = df["BookingStatus"] == "cancel"
    df["IsRefunded"] = df["IsCancelled"] & (df["RefundAmount"] > 0)

    # --- Contrôle qualité : une annulation ne peut pas précéder sa réservation ---
    # On NE supprime PAS ces lignes (décision métier, pas technique) : on les
    # flague pour que l'anomalie soit visible dans l'app plutôt que silencieuse.
    df["DateAnomaly"] = (
        df["IsCancelled"] & df["CancelledOn"].notna() & df["BookedOn"].notna()
        & (df["CancelledOn"] < df["BookedOn"])
    )
    # Anomalie "sévère" : écart de plus de 2 jours, inexplicable par un simple
    # résidu d'arrondi/fuseau horaire -> mérite une investigation sur la source.
    gap = (df["BookedOn"] - df["CancelledOn"]).dt.total_seconds() / 86400
    df["DateAnomalySevere"] = df["DateAnomaly"] & (gap > 2)

    # --- HotelOwnerVAT : une TVA ne devrait jamais être négative -----------
    # On flague les lignes concernées (probable signe inversé côté export) et
    # on neutralise la valeur (0) pour éviter qu'elle ne fausse un total futur,
    # sans supprimer la réservation elle-même.
    df["NegativeVATFlag"] = df["HotelOwnerVAT"] < 0
    df.loc[df["NegativeVATFlag"], "HotelOwnerVAT"] = 0.0

    # Date de référence pour l'analyse temporelle : date de réservation (BookedOn)
    df["RefDate"] = df["BookedOn"]
    df["Year"] = df["RefDate"].dt.year
    df["Month"] = df["RefDate"].dt.month
    df["MonthLabel"] = df["RefDate"].dt.strftime("%b %Y")
    df["YearMonth"] = df["RefDate"].dt.to_period("M").astype(str)

    df["StatusLabel"] = df["BookingStatus"].map(STATUS_LABELS).fillna(df["BookingStatus"])

    # Lignes sans date exploitable : on les retire des analyses temporelles
    rows_before = len(df)
    df = df.dropna(subset=["RefDate"]).reset_index(drop=True)
    df.attrs["rows_dropped_no_date"] = rows_before - len(df)

    return df


@st.cache_data(show_spinner=False)
def data_quality_summary(df: pd.DataFrame) -> dict:
    """Résumé des anomalies détectées au chargement, pour affichage transparent
    dans l'application plutôt que de les laisser fausser silencieusement les
    analyses (cf. audit : fuseau horaire, TVA négative, dates incohérentes)."""
    return {
        "rows_dropped_no_date": df.attrs.get("rows_dropped_no_date", 0),
        "date_anomalies": int(df["DateAnomaly"].sum()),
        "date_anomalies_severe": int(df["DateAnomalySevere"].sum()),
        "negative_vat_rows": int(df["NegativeVATFlag"].sum()),
    }


@st.cache_data(show_spinner=False)
def get_filter_options(df: pd.DataFrame) -> dict:
    """Retourne les options disponibles pour les filtres de la sidebar."""
    years = sorted(df["Year"].dropna().unique().astype(int), reverse=True)
    hotels = sorted(df["HotelName"].dropna().unique())
    booking_types = sorted(df["BookingType"].dropna().unique())
    months = list(range(1, 13))
    month_names = {
        1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
        7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre",
    }
    return {
        "years": years,
        "hotels": hotels,
        "booking_types": booking_types,
        "months": months,
        "month_names": month_names,
    }
