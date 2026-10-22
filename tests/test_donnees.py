"""Lecture des fichiers Damodaran, correspondances sectorielles, choix des méthodes, API."""

import math

import numpy as np
import pandas as pd
import pytest
from conftest import GRILLE_GRANDE, profil

from valorisation import NonValorisable, correspondances, evaluer_profil, synthese
from valorisation.damodaran import lecture
from valorisation.damodaran.referentiel import chercher_nom, notation_depuis_grille
from valorisation.selection import choisir_methodes

N = np.nan

# Les 94 industries Damodaran (mise à jour de janvier 2026).
INDUSTRIES_DAMODARAN = """Advertising|Aerospace/Defense|Air Transport|Apparel|Auto & Truck|Auto Parts|Bank (Money Center)|
Banks (Regional)|Beverage (Alcoholic)|Beverage (Soft)|Broadcasting|Brokerage & Investment Banking|Building Materials|
Business & Consumer Services|Cable TV|Chemical (Basic)|Chemical (Diversified)|Chemical (Specialty)|Coal & Related Energy|
Computer Services|Computers/Peripherals|Construction Supplies|Diversified|Drugs (Biotechnology)|Drugs (Pharmaceutical)|
Education|Electrical Equipment|Electronics (Consumer & Office)|Electronics (General)|Engineering/Construction|
Entertainment|Environmental & Waste Services|Farming/Agriculture|Financial Svcs. (Non-bank & Insurance)|Food Processing|
Food Wholesalers|Furn/Home Furnishings|Green & Renewable Energy|Healthcare Products|Healthcare Support Services|
Heathcare Information and Technology|Homebuilding|Hospitals/Healthcare Facilities|Hotel/Gaming|Household Products|
Information Services|Insurance (General)|Insurance (Life)|Insurance (Prop/Cas.)|Investments & Asset Management|Machinery|
Metals & Mining|Office Equipment & Services|Oil/Gas (Integrated)|Oil/Gas (Production and Exploration)|
Oil/Gas Distribution|Oilfield Svcs/Equip.|Packaging & Container|Paper/Forest Products|Power|Precious Metals|
Publishing & Newspapers|R.E.I.T.|Real Estate (Development)|Real Estate (General/Diversified)|
Real Estate (Operations & Services)|Recreation|Reinsurance|Restaurant/Dining|Retail (Automotive)|
Retail (Building Supply)|Retail (Distributors)|Retail (General)|Retail (Grocery and Food)|Retail (REITs)|
Retail (Special Lines)|Rubber& Tires|Semiconductor|Semiconductor Equip|Shipbuilding & Marine|Shoe|
Software (Entertainment)|Software (Internet)|Software (System & Application)|Steel|Telecom (Wireless)|
Telecom. Equipment|Telecom. Services|Tobacco|Transportation|Transportation (Railroads)|Trucking|Utility (General)|
Utility (Water)""".replace("\n", "").split("|")


# --- Lecture des fichiers ------------------------------------------------------------------
def test_moyennes_industrie_colonnes_en_double_et_fin_de_tableau():
    brut = pd.DataFrame([
        ["Date updated:", pd.Timestamp("2026-01-05"), N, N],
        [N, N, "Only positive EBITDA firms", "All firms"],
        ["Industry Name", "Number of firms", "EV/EBITDA", "EV/EBITDA"],
        ["Machinery ", 210, 15.0, 14.0],
        ["Steel", 40, 6.0, 7.5],
        [N, N, N, N],
        ["Note de bas de page", N, N, N],
    ])
    table, date_maj = lecture.normaliser_moyennes_industrie(brut)
    assert list(table.index) == ["Machinery", "Steel"]
    assert table.at["Machinery", "Only positive EBITDA firms | EV/EBITDA"] == 15.0
    assert table.at["Steel", "All firms | EV/EBITDA"] == 7.5
    assert str(date_maj) == "2026-01-05"


def test_primes_pays_s_arrete_avant_le_tableau_annexe():
    brut = pd.DataFrame([
        ["Enter the current risk premium for a mature equity market", N, N, N, 0.0423, N],
        ["Country", "Africa", "Moody's rating", "Spread", "Total ERP", "CRP"],
        ["France", "Western Europe", "Aa3", 0.005, 0.050, 0.0078],
        ["Germany", "Western Europe", "Aaa", 0.0, 0.0423, 0.0],
        ["Frontier Markets (no sovereign ratings)", N, N, N, N, N],
        ["Algeria", 67, 0.10, 0.058, 0.038, N],
    ])
    table, prime_mature, _ = lecture.normaliser_primes_pays(brut)
    assert prime_mature == 0.0423
    assert list(table.index) == ["France", "Germany"]


def test_grilles_de_notation():
    brut = pd.DataFrame([
        ["For large firms", N, N, N],
        [-100000, 0.199999, "D2/D", 0.19], [0.2, 100000, "Aaa/AAA", 0.004],
        [N, N, N, N],
        [-100000, 0.499999, "D2/D", 0.19], [0.5, 100000, "Aaa/AAA", 0.004],
    ], dtype=object)
    grilles = lecture.normaliser_grilles_notation(brut)
    assert len(grilles["grande"]) == 2 and grilles["petite"]["couverture_min"].iloc[1] == 0.5


@pytest.mark.parametrize("couverture, notation", [
    (-3.0, "D2/D"), (0.1999995, "D2/D"), (4.0, "A2/A"), (8.5, "Aaa/AAA"), (math.inf, "Aaa/AAA"), (None, "Aaa/AAA")])
def test_notation_synthetique(couverture, notation):
    assert notation_depuis_grille(GRILLE_GRANDE, couverture)[0] == notation


def test_noms_de_pays_variantes():
    index = ["United States of America", "United States Virgin Islands", "Republic of Korea", "France"]
    assert chercher_nom("United States", index) == "United States of America"
    assert chercher_nom("South Korea", index) == "Republic of Korea"
    assert chercher_nom("france", index) == "France"
    assert chercher_nom("Atlantide", index) is None


# --- Correspondances et choix des méthodes ---------------------------------------------------
def test_correspondances_pointent_vers_des_industries_existantes():
    cibles = set(correspondances.table_industries().values())
    assert cibles <= set(INDUSTRIES_DAMODARAN)
    for industries in correspondances.regles_methodes()["industries"].values():
        assert set(industries) <= set(INDUSTRIES_DAMODARAN)


def test_poids_des_profils_somment_a_un():
    for nom, profil_regle in correspondances.regles_methodes()["profils"].items():
        assert sum(profil_regle["methodes"].values()) == pytest.approx(1.0), nom


def test_correspondance_tolere_la_ponctuation():
    assert correspondances.industrie_damodaran("Drug Manufacturers—General") == "Drugs (Pharmaceutical)"
    assert correspondances.industrie_damodaran("Industrie inventée") is None


def test_choix_standard_puis_ebitda_negatif():
    assert choisir_methodes(profil(), "Machinery").poids == {"dcf": 0.6, "ev_ebitda": 0.4}
    plan = choisir_methodes(profil(ebit=-100.0), "Machinery")
    assert "ev_ventes" in plan.poids and "ev_ebitda" not in plan.poids and plan.marge_vers_industrie


def test_choix_banque_avec_perte():
    plan = choisir_methodes(profil(resultat_net=-10.0), "Banks (Regional)")
    # Une banque reste financière même si l'EBIT est renseigné (règle limitée aux industries mixtes).
    assert plan.profil == "financiere" and plan.poids == {"pbv": 1.0}


def test_choix_cyclique_normalise():
    plan = choisir_methodes(profil(), "Steel")
    assert plan.profil == "cyclique" and plan.normaliser


# --- API de bout en bout (sans réseau) --------------------------------------------------------
def test_evaluation_complete(referentiel):
    r = evaluer_profil(profil(), referentiel=referentiel, taux_sans_risque=(0.04, "test"))
    assert r.industrie_damodaran == "Machinery" and r.correspondance_trouvee
    assert r.bas <= r.valeur_centrale <= r.haut
    assert r.verdict in (synthese.SOUS_EVALUE, synthese.CORRECT, synthese.SUREVALUE)
    resume = r.resume()
    assert resume["methodes"]["dcf"]["poids"] == pytest.approx(0.6)


def test_industrie_inconnue_utilise_le_marche(referentiel):
    r = evaluer_profil(profil(industrie_yahoo="Industrie inventée"), referentiel=referentiel,
                       taux_sans_risque=(0.04, "test"))
    assert r.industrie_damodaran == "Total Market (without financials)" and not r.correspondance_trouvee
    assert any("non répertoriée" in a for a in r.alertes)


def test_etf_refuse(referentiel):
    with pytest.raises(NonValorisable):
        evaluer_profil(profil(type_titre="ETF"), referentiel=referentiel)


def test_rapport_html_genere(referentiel):
    from valorisation.rapport import generer_html
    html = generer_html(evaluer_profil(profil(), referentiel=referentiel, taux_sans_risque=(0.04, "test")))
    assert "Société Test" in html and "DCF inversé" in html and "<script" in html


def test_societe_financiere_a_commissions_reclassee():
    # Réseau de paiement : EBIT élevé, peu de frais financiers -> DCF + EV/EBITDA, pas de P/BV.
    reseau = profil(chiffre_affaires=1000.0, ebit=550.0, frais_financiers=20.0)
    plan = choisir_methodes(reseau, "Financial Svcs. (Non-bank & Insurance)")
    assert plan.profil == "standard" and "pbv" not in plan.poids
    # Banque : pas d'EBIT publié -> reste financière.
    preteur = profil(ebit=300.0, frais_financiers=400.0)
    assert choisir_methodes(preteur, "Financial Svcs. (Non-bank & Insurance)").profil == "financiere"
    assureur = profil(ebit=550.0, frais_financiers=20.0)
    assert choisir_methodes(assureur, "Insurance (Life)").profil == "financiere"
