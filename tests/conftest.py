"""Jeux de données synthétiques : les tests tournent sans réseau."""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valorisation.damodaran.referentiel import ParametresIndustrie, notation_depuis_grille  # noqa: E402
from valorisation.entreprise import ProfilEntreprise  # noqa: E402

GRILLE_GRANDE = pd.DataFrame(
    [(-1e5, 0.199999, "D2/D", 0.19), (0.2, 1.249999, "Caa/CCC", 0.0885), (1.25, 2.999999, "B1/B+", 0.0275),
     (3.0, 5.499999, "A2/A", 0.0078), (5.5, 8.499999, "Aa2/AA", 0.0055), (8.5, 1e5, "Aaa/AAA", 0.004)],
    columns=["couverture_min", "couverture_max", "notation", "spread"])


def parametres(**modifs):
    valeurs = dict(
        industrie="Machinery", region="Europe", nb_entreprises=200, beta_desendette=1.0, beta_endette=1.1,
        dette_sur_capitaux_propres=0.2, taux_is_effectif=0.2, ev_ebitda=10.0, ev_ebit=14.0, ev_ventes=1.5,
        per=15.0, pbv=2.0, roe=0.12, roic=0.12, marge_operationnelle=0.10, marge_ebitda=0.15,
        ventes_sur_capital=2.0, croissance_fondamentale=0.04, cout_capital_usd=0.08,
        date_mise_a_jour=date(2026, 1, 5),
        multiples_monde={"ev_ebitda": 12.0, "ev_ebit": 16.0, "ev_ventes": 1.8, "per": 17.0, "pbv": 2.5},
    )
    valeurs.update(modifs)
    return ParametresIndustrie(**valeurs)


class ReferentielFactice:
    """Remplace ReferentielDamodaran : mêmes méthodes, valeurs fixes."""

    def __init__(self, industries=None):
        self.industries_connues = industries or {"Machinery": parametres(),
                                                 "Banks (Regional)": parametres(industrie="Banks (Regional)")}

    def table(self, jeu, region):
        return pd.DataFrame(index=list(self.industries_connues) + ["Total Market (without financials)"])

    def industrie_marche(self, region):
        return "Total Market (without financials)"

    def parametres_industrie(self, industrie, region):
        return self.industries_connues.get(industrie, parametres(industrie=industrie, region=region))

    def region_damodaran(self, pays):
        return "Europe"

    def donnees_pays(self, pays):
        if pays != "France":
            return None
        return {"pays": "France", "zone": "Western Europe", "notation": "Aa3", "spread_defaut": 0.005,
                "prime_pays": 0.008, "prime_actions_totale": 0.050}

    def prime_marche_mature(self):
        return 0.042

    def date_primes_pays(self):
        return date(2026, 1, 1)

    def taux_is_marginal(self, pays):
        return 0.25 if pays == "France" else None

    def notation_synthetique(self, couverture, grande_entreprise=True):
        return notation_depuis_grille(GRILLE_GRANDE, couverture)


def profil(**modifs):
    historique = pd.DataFrame({
        "chiffre_affaires": [800.0, 880.0, 950.0, 1000.0],
        "ebit": [96.0, 106.0, 114.0, 120.0],
        "amortissements": [40.0, 44.0, 47.0, 50.0],
        "resultat_net": [60.0, 66.0, 72.0, 76.0],
    }, index=[2022, 2023, 2024, 2025])
    historique["ebitda"] = historique["ebit"] + historique["amortissements"]
    valeurs = dict(
        ticker="TEST", nom="Société Test", pays="France", devise="USD", cours=20.0, nb_actions=100.0,
        secteur="Industrials", industrie_yahoo="Specialty Industrial Machinery",
        chiffre_affaires=1000.0, ebit=120.0, amortissements=50.0, resultat_net=76.0,
        resultat_avant_impot=100.0, impot=24.0, frais_financiers=10.0,
        dette_financiere=400.0, tresorerie=100.0, capitaux_propres=900.0, interets_minoritaires=0.0,
        participations=0.0, historique=historique, base_comptes="exercice clos le 2025-12-31",
    )
    valeurs.update(modifs)
    return ProfilEntreprise(**valeurs)


@pytest.fixture
def referentiel():
    return ReferentielFactice()
