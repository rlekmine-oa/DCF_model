"""Calculs financiers : WACC, DCF (contre des formules fermées), multiples, synthèse."""

import math

import pytest
from conftest import parametres, profil

from valorisation import synthese
from valorisation.methodes import ResultatMethode, dcf, multiples, pont_valeur_entreprise
from valorisation.methodes.dcf import HypothesesDCF
from valorisation.wacc import calculer_wacc

RF = (0.04, "test")


def hypotheses(**modifs):
    valeurs = dict(croissance_initiale=0.03, croissance_terminale=0.03, marge_initiale=0.12, marge_cible=0.12,
                   ventes_sur_capital=2.0, taux_is_initial=0.25, taux_is_terminal=0.25,
                   roic_terminal=0.2, wacc=0.09, chiffre_affaires_base=1000.0)
    valeurs.update(modifs)
    return HypothesesDCF(**valeurs)


# --- WACC ------------------------------------------------------------------------------
def test_wacc_construit_pas_a_pas(referentiel):
    w = calculer_wacc(profil(), parametres(), referentiel, RF)
    # D/E = 400 / 2000 ; bêta = 1 x (1 + 0,75 x 0,2) ; prime = 4,2 % + 0,8 %
    assert w.dette_sur_fonds_propres == pytest.approx(0.2)
    assert w.beta_reendette == pytest.approx(1.15)
    assert w.cout_fonds_propres == pytest.approx(0.04 + 1.15 * 0.05)
    # couverture 120 / 10 = 12 -> AAA (0,4 %) ; + spread pays 0,5 %
    assert w.notation_synthetique == "Aaa/AAA"
    assert w.cout_dette_avant_impot == pytest.approx(0.049)
    attendu = (2000 / 2400) * (0.04 + 1.15 * 0.05) + (400 / 2400) * 0.049 * 0.75
    assert w.wacc == pytest.approx(attendu)


def test_wacc_sans_dette_ni_frais_financiers(referentiel):
    w = calculer_wacc(profil(dette_financiere=0.0, frais_financiers=0.0), parametres(), referentiel, RF)
    assert w.poids_fonds_propres == 1.0
    assert w.beta_reendette == pytest.approx(1.0)
    assert w.wacc == pytest.approx(w.cout_fonds_propres)
    assert w.notation_synthetique == "Aaa/AAA"


def test_wacc_financiere_sans_reendettement(referentiel):
    # Banque : D/E énorme, mais le bêta endetté de l'industrie est utilisé tel quel.
    w = calculer_wacc(profil(dette_financiere=10000.0), parametres(beta_endette=0.9), referentiel, RF,
                      financiere=True)
    assert w.beta_reendette == pytest.approx(0.9)
    assert w.cout_fonds_propres == pytest.approx(0.04 + 0.9 * 0.05)


def test_wacc_pays_inconnu_signale(referentiel):
    w = calculer_wacc(profil(pays="Atlantide"), parametres(taux_is_effectif=0.2), referentiel, RF)
    assert w.prime_pays == 0.0 and w.taux_is_marginal == 0.2
    assert len(w.alertes) == 2


# --- DCF -------------------------------------------------------------------------------
def test_dcf_sans_croissance_egal_rente_perpetuelle():
    h = hypotheses(croissance_initiale=0.0, croissance_terminale=0.0)
    _, agregats = dcf.projeter(h)
    assert agregats["valeur_entreprise"] == pytest.approx(1000 * 0.12 * 0.75 / 0.09)


def test_dcf_croissance_constante_egal_gordon():
    # Avec ROIC = (1+g) x ventes/capital x marge x (1-t), le réinvestissement des années explicites
    # et celui de la valeur terminale coïncident : la valeur doit être exactement FCFF_1 / (WACC - g).
    g, s2c, m, t = 0.03, 2.0, 0.12, 0.25
    h = hypotheses(roic_terminal=(1 + g) * s2c * m * (1 - t))
    _, agregats = dcf.projeter(h)
    fcff_1 = 1000 * (1 + g) * m * (1 - t) - 1000 * g / s2c
    assert agregats["valeur_entreprise"] == pytest.approx(fcff_1 / (0.09 - g))


def test_dcf_trajectoires_de_croissance_et_de_marge():
    h = hypotheses(croissance_initiale=0.10, croissance_terminale=0.02, marge_initiale=0.05, marge_cible=0.15)
    tableau, _ = dcf.projeter(h)
    assert list(tableau["croissance"].iloc[:5]) == pytest.approx([0.10] * 5)
    assert tableau["croissance"].iloc[-1] == pytest.approx(0.02)
    assert tableau["marge"].iloc[4] == pytest.approx(0.15)   # cible atteinte en année 5
    assert tableau["marge"].iloc[0] == pytest.approx(0.07)


def test_dcf_refuse_wacc_inferieur_a_g():
    with pytest.raises(ValueError):
        dcf.projeter(hypotheses(wacc=0.02))


def test_dcf_inverse_retrouve_la_croissance():
    p = profil()
    cible = dcf.valeur_par_action(hypotheses(croissance_initiale=0.07), p)
    assert dcf.dcf_inverse(hypotheses(), p, cible) == pytest.approx(0.07, abs=1e-6)


def test_dcf_complet_et_fourchette(referentiel):
    p = profil()
    w = calculer_wacc(p, parametres(), referentiel, RF)
    r = dcf.valoriser(p, parametres(), w)
    assert r.valide and r.bas < r.valeur_par_action < r.haut
    assert r.detail["sensibilite"].shape == (5, 5)
    # Valeur par action = (valeur d'entreprise + trésorerie - dette) / actions
    attendu = (r.detail["valeur_entreprise"] + 100 - 400) / 100
    assert r.valeur_par_action == pytest.approx(attendu)


def test_dcf_surcharges_et_cle_inconnue(referentiel):
    p = profil()
    w = calculer_wacc(p, parametres(), referentiel, RF)
    h, justif = dcf.construire_hypotheses(p, parametres(), w, surcharges={"croissance_initiale": 0.08})
    assert h.croissance_initiale == 0.08 and "imposée" in justif["croissance_initiale"]
    with pytest.raises(KeyError):
        dcf.construire_hypotheses(p, parametres(), w, surcharges={"inconnue": 1})


def test_croissance_industrie_aberrante_bornee(referentiel):
    p = profil()
    w = calculer_wacc(p, parametres(), referentiel, RF)
    h, _ = dcf.construire_hypotheses(p, parametres(croissance_fondamentale=-2.0), w)
    # historique : (1000/800)^(1/3) - 1 = 7,7 % ; industrie bornée à 0 % -> moyenne 3,9 %
    assert h.croissance_initiale == pytest.approx(((1000 / 800) ** (1 / 3) - 1) / 2)


# --- Multiples et pont -------------------------------------------------------------------
def test_pont_valeur_entreprise():
    p = profil(participations=50.0, interets_minoritaires=30.0)
    assert pont_valeur_entreprise(1000.0, p) == pytest.approx(1000 + 100 + 50 - 400 - 30)


def test_multiples_central_et_fourchette():
    p = profil()
    ev = multiples.valoriser(p, parametres(), "ev_ebitda")
    assert ev.valeur_par_action == pytest.approx((170 * 10 + 100 - 400) / 100)
    assert ev.haut == pytest.approx((170 * 12 + 100 - 400) / 100)
    assert multiples.valoriser(p, parametres(), "per").valeur_par_action == pytest.approx(76 * 15 / 100)
    assert multiples.valoriser(p, parametres(), "pbv").valeur_par_action == pytest.approx(900 * 2 / 100)


def test_multiple_inapplicable_si_agregat_negatif():
    r = multiples.valoriser(profil(resultat_net=-5.0), parametres(), "per")
    assert not r.valide and r.alertes


def test_ebitda_normalise_sur_historique():
    p = profil()
    r = multiples.valoriser(p, parametres(), "ev_ebitda", normaliser=True)
    marge_moyenne = (136 + 150 + 161 + 170) / (800 + 880 + 950 + 1000)
    assert r.detail["base"] == pytest.approx(1000 * marge_moyenne)


# --- Synthèse ----------------------------------------------------------------------------
def test_ponderation_redistribue_les_methodes_inapplicables():
    resultats = [ResultatMethode("dcf", "DCF", 10.0, 8.0, 12.0),
                 ResultatMethode("ev_ebitda", "EV", math.nan, math.nan, math.nan)]
    centrale, bas, haut, poids = synthese.ponderer(resultats, {"dcf": 0.6, "ev_ebitda": 0.4})
    assert poids == {"dcf": 1.0}
    assert (centrale, bas, haut) == (10.0, 8.0, 12.0)


def test_ponderation_moyenne():
    resultats = [ResultatMethode("dcf", "DCF", 10.0, 9.0, 11.0), ResultatMethode("per", "PE", 20.0, 18.0, 24.0)]
    centrale, bas, haut, _ = synthese.ponderer(resultats, {"dcf": 0.5, "per": 0.5})
    assert (centrale, bas, haut) == pytest.approx((15.0, 13.5, 17.5))


@pytest.mark.parametrize("ecart, attendu", [
    (0.30, synthese.SOUS_EVALUE), (0.15, synthese.SOUS_EVALUE), (0.10, synthese.CORRECT),
    (-0.10, synthese.CORRECT), (-0.15, synthese.SUREVALUE), (math.nan, synthese.NON_CONCLUANT)])
def test_verdict(ecart, attendu):
    assert synthese.verdict(ecart, 0.15) == attendu
