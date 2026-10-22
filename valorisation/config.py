"""Paramètres par défaut du moteur de valorisation.

Toutes les hypothèses chiffrées sont regroupées ici pour rester visibles et modifiables.
Chaque valeur peut aussi être surchargée à l'appel (voir `api.evaluer_ticker`).
"""

import os
from pathlib import Path

RACINE_PROJET = Path(__file__).resolve().parent.parent

# Dossier de cache (fichiers Damodaran, taux sans risque). Jamais versionné.
DOSSIER_CACHE = Path(os.environ.get("VALORISATION_CACHE", RACINE_PROJET / "cache"))

# --- Données Damodaran -------------------------------------------------------
URL_DAMODARAN_DATASETS = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/"
URL_DAMODARAN_NOTATIONS = "https://pages.stern.nyu.edu/~adamodar/pc/ratings.xls"
# Les jeux par industrie sont mis à jour chaque janvier, les primes pays chaque trimestre :
# un mois de cache suffit, et un cache périmé sert de secours si le site ne répond pas.
DUREE_CACHE_DAMODARAN_JOURS = 30

# --- Taux sans risque ----------------------------------------------------------
DUREE_CACHE_TAUX_HEURES = 24
# Valeurs de secours (taux d'État à 10 ans, en décimal) si aucune source en ligne ne répond,
# et pour les devises sans source automatique. À mettre à jour de temps en temps.
TAUX_SANS_RISQUE_SECOURS = {
    "EUR": 0.030,
    "USD": 0.045,
    "GBP": 0.045,
    "CHF": 0.008,
    "JPY": 0.015,
    "SEK": 0.025,
    "NOK": 0.035,
    "DKK": 0.025,
    "CAD": 0.033,
    "AUD": 0.043,
}

# --- DCF -----------------------------------------------------------------------
HORIZON_DCF_ANNEES = 10          # années 1-5 : croissance forte ; 6-10 : convergence vers g terminal
CROISSANCE_TERMINALE_MAX = 0.025  # plafond de g terminal (et toujours <= taux sans risque)
CROISSANCE_MIN = -0.05
CROISSANCE_MAX = 0.20
POIDS_CROISSANCE_HISTORIQUE = 0.5  # le reste vient de la croissance fondamentale de l'industrie
# La croissance fondamentale Damodaran (réinvestissement x ROC) est bruitée d'une industrie à
# l'autre (de -200 % à +140 %) : elle est bornée avant de servir d'ancrage.
CROISSANCE_INDUSTRIE_BORNES = (0.0, 0.10)
# Rappel partiel de la marge cible vers celle de l'industrie : un avantage concurrentiel
# s'érode, mais une marge durablement supérieure (Apple, LVMH…) ne disparaît pas en cinq ans.
POIDS_MARGE_INDUSTRIE = 0.25
POIDS_SALES_TO_CAPITAL_INDUSTRIE = 0.5
ANNEE_CONVERGENCE_MARGE = 5        # année où la marge opérationnelle atteint sa cible
VENTES_SUR_CAPITAL_BORNES = (0.3, 10.0)
# Rentabilité du capital en régime permanent : meilleur ROIC (entreprise ou industrie), au moins égal au WACC
# (aucune création de valeur) et au plus WACC + cet écart (avantage concurrentiel durable borné).
ECART_ROIC_TERMINAL_MAX = 0.05
SENSIBILITE_WACC = (-0.01, -0.005, 0.0, 0.005, 0.01)
SENSIBILITE_G = (-0.005, -0.0025, 0.0, 0.0025, 0.005)

# --- WACC ----------------------------------------------------------------------
# Damodaran distingue les grandes entreprises (capitalisation > 5 Md$) des plus petites
# pour la grille de notation synthétique.
SEUIL_GRANDE_ENTREPRISE_USD = 5e9
BETA_MIN, BETA_MAX = 0.4, 3.0

# --- Synthèse ------------------------------------------------------------------
# Écart entre valeur centrale et cours au-delà duquel le titre est jugé sous/surévalué.
SEUIL_VERDICT = 0.15
