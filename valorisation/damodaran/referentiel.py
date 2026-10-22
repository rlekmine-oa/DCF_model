"""Accès unifié aux données Damodaran : paramètres d'une industrie, primes pays, IS, notations."""

import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from . import lecture, telechargement

# Lignes agrégées en bas de chaque fichier ; la première présente sert quand une industrie
# n'est pas reconnue (le fichier « Global » n'a parfois que « Total Market »).
LIGNES_MARCHE = ("Total Market (without financials)", "Total Market", "Grand Total")

# Région du fichier des primes pays -> région des jeux par industrie.
_REGION_PAR_ZONE = {
    "Western Europe": "Europe",
    "Australia & New Zealand": "Rest",
}
_REGION_PAR_PAYS = {
    "United States": "US",
    "Canada": "Rest",
    "Japan": "Japan",
    "China": "China",
    "Hong Kong": "China",
    "India": "India",
}

# Noms de pays de Yahoo Finance -> variantes possibles dans les fichiers Damodaran
# (le fichier des taux d'IS reprend les noms officiels de l'ONU).
_ALIAS_PAYS = {
    "united states": ["United States", "United States of America"],
    "usa": ["United States", "United States of America"],
    "united kingdom": ["United Kingdom", "United Kingdom of Great Britain and Northern Ireland"],
    "south korea": ["Korea", "Republic of Korea"],
    "korea": ["Korea", "Republic of Korea"],
    "hong kong": ["Hong Kong", "China, Hong Kong Special Administrative Region"],
    "netherlands": ["Netherlands", "Netherlands (Kingdom of the)"],
    "turkey": ["Turkey", "Türkiye"],
    "czech republic": ["Czech Republic", "Czechia"],
    "russia": ["Russia", "Russian Federation"],
    "vietnam": ["Vietnam", "Viet Nam"],
    "taiwan": ["Taiwan", "Taiwan Province of China"],
}


def _normaliser(nom):
    nom = unicodedata.normalize("NFKD", str(nom)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", nom.lower()).strip()


def chercher_nom(nom, index):
    """Trouve `nom` dans `index` malgré les variantes d'écriture ; None si introuvable."""
    if not nom:
        return None
    normes = {_normaliser(i): i for i in index}
    cle = _normaliser(nom)
    if cle in normes:
        return normes[cle]
    for alias in _ALIAS_PAYS.get(cle, []):
        if _normaliser(alias) in normes:
            return normes[_normaliser(alias)]
    candidats = [i for n, i in normes.items() if n.startswith(cle + " ")]
    return candidats[0] if len(candidats) == 1 else None


@dataclass
class ParametresIndustrie:
    """Moyennes d'une industrie Damodaran dans une région (ratios en décimal)."""
    industrie: str
    region: str
    nb_entreprises: int
    beta_desendette: float          # corrigé de la trésorerie (beta « pure play »)
    beta_endette: float             # bêta moyen observé (utilisé tel quel pour les financières)
    dette_sur_capitaux_propres: float
    taux_is_effectif: float
    ev_ebitda: float                # entreprises à EBITDA positif
    ev_ebit: float
    ev_ventes: float
    per: float                      # capitalisation agrégée / résultat net des entreprises bénéficiaires
    pbv: float
    roe: float
    roic: float
    marge_operationnelle: float     # marge opérationnelle avant impôt (non retraitée)
    marge_ebitda: float
    ventes_sur_capital: float
    croissance_fondamentale: float  # croissance de l'EBIT = taux de réinvestissement x ROC
    cout_capital_usd: float
    date_mise_a_jour: date = None
    # Mêmes multiples sur l'échantillon mondial : sert de borne à la fourchette des multiples.
    multiples_monde: dict = field(default_factory=dict)


def _valeur(table, industrie, *colonnes):
    if table is None or industrie not in table.index:
        return math.nan
    for c in colonnes:
        if c in table.columns:
            v = table.at[industrie, c]
            if pd.notna(v):
                return float(v)
    return math.nan


class ReferentielDamodaran:
    """Charge à la demande les fichiers Damodaran (téléchargés puis mis en cache)."""

    def __init__(self, dossier_cache=None):
        self.dossier_cache = dossier_cache
        self._tables = {}
        self._primes = None
        self._is_pays = None
        self._notations = None

    # --- Jeux par industrie ---------------------------------------------------
    def table(self, jeu, region):
        cle = (jeu, region)
        if cle not in self._tables:
            chemin = telechargement.chemin_local(jeu, region, self.dossier_cache)
            self._tables[cle] = lecture.lire_moyennes_industrie(chemin)
        return self._tables[cle][0]

    def date_mise_a_jour(self, jeu="beta", region="Global"):
        self.table(jeu, region)
        return self._tables[(jeu, region)][1]

    def industries(self, region="Global"):
        return [i for i in self.table("beta", region).index if i not in LIGNES_MARCHE]

    def industrie_marche(self, region):
        index = self.table("beta", region).index
        return next(i for i in LIGNES_MARCHE if i in index)

    def _multiples(self, industrie, region):
        return {
            "ev_ebitda": _valeur(self.table("ev_ebitda", region), industrie,
                                 "Only positive EBITDA firms | EV/EBITDA", "EV/EBITDA"),
            "ev_ebit": _valeur(self.table("ev_ebitda", region), industrie,
                               "Only positive EBITDA firms | EV/EBIT", "EV/EBIT"),
            "ev_ventes": _valeur(self.table("ventes", region), industrie, "EV/Sales"),
            "per": _valeur(self.table("per", region), industrie,
                           "Aggregate Mkt Cap/ Trailing Net Income (only money making firms)", "Trailing PE"),
            "pbv": _valeur(self.table("pbv", region), industrie, "PBV"),
        }

    def parametres_industrie(self, industrie, region):
        beta = self.table("beta", region)
        if industrie not in beta.index:
            raise KeyError(f"Industrie Damodaran inconnue : {industrie!r}")
        multiples = self._multiples(industrie, region)
        if region == "Global":
            monde = dict(multiples)
        else:
            nom_monde = industrie if industrie in self.table("beta", "Global").index else self.industrie_marche("Global")
            monde = self._multiples(nom_monde, "Global")
        return ParametresIndustrie(
            industrie=industrie,
            region=region,
            nb_entreprises=int(_valeur(beta, industrie, "Number of firms")),
            beta_desendette=_valeur(beta, industrie, "Unlevered beta corrected for cash", "Unlevered beta"),
            beta_endette=_valeur(beta, industrie, "Beta"),
            dette_sur_capitaux_propres=_valeur(beta, industrie, "D/E Ratio"),
            taux_is_effectif=_valeur(beta, industrie, "Effective Tax rate"),
            roe=_valeur(self.table("pbv", region), industrie, "ROE"),
            roic=_valeur(self.table("pbv", region), industrie, "ROIC"),
            marge_operationnelle=_valeur(self.table("marges", region), industrie,
                                         "Pre-tax Unadjusted Operating Margin"),
            marge_ebitda=_valeur(self.table("marges", region), industrie, "EBITDA/Sales"),
            ventes_sur_capital=_valeur(self.table("capex", region), industrie, "Sales/ Invested Capital (LTM)"),
            croissance_fondamentale=_valeur(self.table("croissance", region), industrie, "Expected Growth in EBIT"),
            cout_capital_usd=_valeur(self.table("wacc", region), industrie, "Cost of Capital"),
            date_mise_a_jour=self.date_mise_a_jour("beta", region),
            multiples_monde=monde,
            **multiples,
        )

    # --- Pays -------------------------------------------------------------------
    def _charger_primes(self):
        if self._primes is None:
            self._primes = lecture.lire_primes_pays(telechargement.chemin_local("primes_pays", None, self.dossier_cache))
        return self._primes

    def prime_marche_mature(self):
        return self._charger_primes()[1]

    def date_primes_pays(self):
        return self._charger_primes()[2]

    def donnees_pays(self, pays):
        """Ligne du fichier des primes pays (prime totale, prime pays, spread de défaut, région)."""
        table = self._charger_primes()[0]
        nom = chercher_nom(pays, table.index)
        if nom is None:
            return None
        ligne = table.loc[nom]
        return {
            "pays": nom,
            "zone": ligne["region"],
            "notation": ligne["notation"],
            "spread_defaut": float(ligne["spread_defaut"]),
            "prime_pays": float(ligne["prime_pays"]),
            "prime_actions_totale": float(ligne["prime_actions_totale"]),
        }

    def region_damodaran(self, pays):
        """Région des jeux par industrie pour un pays (« emerg » par défaut, « Global » si inconnu)."""
        donnees = self.donnees_pays(pays)
        if donnees is None:
            return "Global"
        if donnees["pays"] in _REGION_PAR_PAYS:
            return _REGION_PAR_PAYS[donnees["pays"]]
        return _REGION_PAR_ZONE.get(donnees["zone"], "emerg")

    def taux_is_marginal(self, pays):
        if self._is_pays is None:
            self._is_pays = lecture.lire_is_pays(telechargement.chemin_local("is_pays", None, self.dossier_cache))[0]
        nom = chercher_nom(pays, self._is_pays.index)
        return float(self._is_pays[nom]) if nom is not None else None

    # --- Notation synthétique -------------------------------------------------------
    def notation_synthetique(self, couverture_interets, grande_entreprise=True):
        """Notation et spread de défaut d'après la couverture des intérêts (EBIT / frais financiers)."""
        if self._notations is None:
            self._notations = lecture.lire_grilles_notation(
                telechargement.chemin_local("notations", None, self.dossier_cache))
        return notation_depuis_grille(self._notations["grande" if grande_entreprise else "petite"],
                                      couverture_interets)


def notation_depuis_grille(grille, couverture):
    """Tranche dont le seuil bas est le plus élevé sans dépasser la couverture.

    Les fichiers donnent des bornes du type [0,2 ; 0,649999] puis [0,65 ; 0,799999] : seul le seuil
    bas fait foi, ce qui évite les trous entre deux tranches.
    """
    # Pas de frais financiers : couverture infinie, donc meilleure notation.
    if couverture is None or math.isnan(couverture):
        couverture = math.inf
    tranches = grille.sort_values("couverture_min")
    eligibles = tranches[tranches["couverture_min"] <= couverture]
    ligne = eligibles.iloc[-1] if not eligibles.empty else tranches.iloc[0]
    return ligne["notation"], float(ligne["spread"])
