# 📊 Dashboard Réservations Hôtelières

Outil d'aide à la décision pour piloter l'activité de réservation et
d'annulation, construit avec **Streamlit + Plotly + Pandas**.

## Structure du projet

```
hotel_dashboard/
├── app.py                          # Interface 1 : Dashboard Global (page d'accueil)
├── pages/
│   ├── 1_🏨_Analyse_par_hôtel.py   # Interface 2 : analyse individuelle par hôtel (+ export PDF)
│   └── 2_🏆_Classement.py          # Interface 3 : classement / comparaison des hôtels
├── utils/
│   ├── data_loader.py               # Chargement + nettoyage des données (mis en cache)
│   ├── filters.py                   # Filtres sidebar réutilisables (année, mois, hôtel, type)
│   ├── metrics.py                   # Tous les calculs de KPI et agrégations métier
│   ├── charts.py                    # Construction des graphiques Plotly (palette cohérente)
│   ├── style.py                     # Design system : couleurs, CSS, cartes KPI
│   ├── insights.py                  # Moteur de règles métier : analyses rédigées + score de santé (sans IA externe)
│   └── report.py                    # Génération du rapport PDF (reportlab + matplotlib)
├── data/
│   └── bookings_raw_merged.csv      # Données fusionnées (réservations + annulations)
├── .streamlit/config.toml           # Thème Streamlit (couleurs, police)
└── requirements.txt
```

## Installation

```bash
cd hotel_dashboard
python -m venv venv
source venv/bin/activate      # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement

```bash
streamlit run app.py
```

L'application s'ouvre sur `http://localhost:8501`. La navigation entre les
3 interfaces se fait via le menu dans la barre latérale (généré
automatiquement par Streamlit à partir du dossier `pages/`).

## Données

Le fichier `data/bookings_raw_merged.csv` fusionne :
- `BookingReport.csv` (réservations complètes / à venir / en cours)
- `BookingReport__2_.csv` (réservations annulées, avec remboursements, frais,
  motifs)

Les doublons (153 réservations apparaissant dans les deux fichiers) ont été
dédoublonnés en conservant la version "annulée", plus à jour.

**Pour rafraîchir les données** : remplacez ce fichier par un nouvel export
au même format (32 colonnes identiques), ou adaptez le chemin dans
`utils/data_loader.py::DATA_PATH`. Le cache Streamlit (`st.cache_data`) se
réinvalide automatiquement si le contenu du fichier change.

## 💹 Règles métier officielles — Analyse du chiffre d'affaires

Suite à un audit initial, puis à la clarification des règles métier
officielles par Namlatic, la section "Analyse du chiffre d'affaires" du
Dashboard Global applique désormais la logique suivante :

1. **Annulation avant le Jour J** (jour d'arrivée) : remboursement à 100 %
   si le client avait payé → Namlatic ne conserve aucun revenu (hors frais
   d'annulation éventuels).
2. **Annulation le Jour J** : remboursement partiel (jours de séjour
   restants uniquement) → le montant du Jour J reste acquis à Namlatic.

**`RefundAmount` est donc la référence officielle pour tout remboursement
réellement effectué** (et non plus traité comme une simple valeur
théorique). `CancelledFee` reste suivi séparément (frais d'annulation
distincts du remboursement lui-même).

D'autres corrections issues de l'audit initial restent en place : fuseau
horaire harmonisé entre `BookedOn`/`CancelledOn`, division par zéro
corrigée dans le score de santé, synchronisation des filtres entre pages,
génération du PDF à la demande uniquement, TVA négative neutralisée, taux
d'annulation par mode de paiement. Voir les commentaires en tête de
`utils/metrics.py` et `utils/insights.py` pour le détail de chaque règle.

## Conventions de calcul — les 6 KPI de la section "Analyse du chiffre d'affaires"

| # | Indicateur | Définition |
|---|---|---|
| 1 | CA total généré | Σ `BookingAmount` — **toutes** les réservations (confirmées, complétées, annulées) |
| 2 | CA confirmé | Σ `BookingAmount` des réservations **non annulées** |
| 3 | Valeur totale des réservations annulées | Σ `BookingAmount` des réservations **annulées** |
| 4 | Montant réellement remboursé | Σ `RefundAmount` des réservations annulées |
| 5 | Revenu conservé sur annulées | Σ (`BookingAmount` − `RefundAmount`) des réservations annulées — le "Jour J" gardé par Namlatic |
| 6 | CA annulé sans remboursement | Σ `BookingAmount` des annulations où `RefundAmount == 0` |

**Identités de cohérence (vérifiées automatiquement à chaque calcul, aucun double comptage)** :
```
(1) = (2) + (3)      CA total généré = CA confirmé + Valeur annulée
(3) = (4) + (5)      Valeur annulée  = Montant remboursé + Revenu conservé
(6) ⊆ (5)             CA sans remboursement est un SOUS-ENSEMBLE du revenu conservé,
                       pas une catégorie supplémentaire à additionner
```
Le flag `kpis["no_double_counting_ok"]` est recalculé à chaque chargement et
affiché comme alerte dans l'interface s'il devient `False` (ex. après
modification du code ou changement de source de données).

Autres indicateurs (inchangés) :

| Indicateur | Définition |
|---|---|
| CA réalisé | Σ `BookingAmount` où `BookingStatus == complete` |
| CA en cours de réalisation | Σ `BookingAmount` où statut = upcoming/ongoing |
| Frais d'annulation encaissés | Σ `CancelledFee` sur les réservations annulées (cash réel, distinct du remboursement) |
| Taux d'annulation | Annulations / Total réservations |

Ces règles sont centralisées dans `utils/metrics.py` (fonction
`compute_global_kpis`) — modifiez-les à un seul endroit si votre définition
métier évolue.

## Palette de couleurs

- 🔵 Bleu (`#2563EB`) — indicateurs principaux
- 🟢 Vert (`#16A34A`) — revenus positifs
- 🟠 Orange (`#F59E0B`) — remboursements
- 🔴 Rouge (`#DC2626`) — pertes uniquement

## Rapport PDF (Interface 2)

Depuis **Analyse par hôtel**, une fois un hôtel sélectionné, le bouton
**📄 Télécharger le rapport PDF** génère un rapport prêt à envoyer à l'hôtel
ou à une direction :

- Page de garde (hôtel, date, période, filtres, auteur)
- Résumé exécutif + **score de santé /100** (🟢 Excellent / 🟡 Correct / 🔴 À surveiller)
- Tableau des KPI (CA, réservations, annulations, taux, revenus perdus, remboursées/non remboursées)
- Graphiques : évolution CA, réservations, annulations, pertes financières
- Comparaison du CA de l'hôtel vs moyenne du parc vs meilleur hôtel
- **Analyse automatique** (performance, annulations, revenus perdus) et **recommandations**,
  générées par un moteur de règles métier déterministe (`utils/insights.py`) — **aucun appel à un LLM externe**,
  donc résultat reproductible, rapide et sans dépendance.
- Pied de page traçable (date, version, filtres utilisés)

Pour ajuster les seuils des règles métier (taux d'annulation "à risque", etc.) ou la formule
du score de santé, modifiez uniquement `utils/insights.py`.

## Notes

- Le taux d'annulation global observé sur les données actuelles est
  d'environ **29 %** — vérifiez que cela correspond à votre réalité métier
  avant présentation.
- Toute nouvelle page ou graphique doit réutiliser les fonctions de
  `metrics.py` et `charts.py` pour rester cohérent avec le reste de
  l'application.
