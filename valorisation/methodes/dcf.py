"""DCF des flux de trésorerie disponibles pour l'entreprise (FCFF), structure Damodaran.

Projection sur `HORIZON_DCF_ANNEES` ans :
- chiffre d'affaires : croissance g0 les 5 premières années, puis décroissance linéaire vers g terminal ;
- marge opérationnelle : convergence linéaire de la marge actuelle vers la marge cible ;
- impôt : du taux effectif vers le taux marginal sur la seconde moitié de l'horizon ;
- réinvestissement = hausse du CA / ratio ventes sur capital investi ;
- FCFF = EBIT x (1 - t) - réinvestissement.
Valeur terminale (Gordon) : FCFF_{N+1} = NOPAT_{N+1} x (1 - g / ROIC terminal), actualisé au WACC.
"""

import math
from dataclasses import asdict, dataclass

import pandas as pd

from .. import config
from ..formats import nombre as _nb
from ..formats import pct as _pct
from . import ResultatMethode, pont_valeur_entreprise


@dataclass
class HypothesesDCF:
    croissance_initiale: float
    croissance_terminale: float
    marge_initiale: float
    marge_cible: float
    ventes_sur_capital: float
    taux_is_initial: float
    taux_is_terminal: float
    roic_terminal: float
    wacc: float
    chiffre_affaires_base: float
    horizon: int = config.HORIZON_DCF_ANNEES
    annee_convergence_marge: int = config.ANNEE_CONVERGENCE_MARGE


def _moyenne_ponderee(valeur_entreprise, valeur_industrie, poids_industrie):
    a, b = valeur_entreprise, valeur_industrie
    if a is None or math.isnan(a):
        return b
    if b is None or math.isnan(b):
        return a
    return (1 - poids_industrie) * a + poids_industrie * b


def construire_hypotheses(profil, industrie, wacc, normaliser=False, marge_vers_industrie=False, surcharges=None):
    """Hypothèses par défaut, tirées de l'historique de l'entreprise et des moyennes Damodaran.

    Renvoie (HypothesesDCF, justifications) ; `justifications` décrit l'origine de chaque hypothèse.
    """
    justif = {}
    surcharges = dict(surcharges or {})

    g_hist = profil.croissance_historique()
    g_ind = industrie.croissance_fondamentale
    if g_ind is not None and not math.isnan(g_ind):
        g_ind = min(max(g_ind, config.CROISSANCE_INDUSTRIE_BORNES[0]), config.CROISSANCE_INDUSTRIE_BORNES[1])
    g0 = _moyenne_ponderee(g_hist, g_ind, 1 - config.POIDS_CROISSANCE_HISTORIQUE)
    g_terminal = min(wacc.taux_sans_risque, config.CROISSANCE_TERMINALE_MAX)
    if g0 is None or math.isnan(g0):
        g0 = g_terminal
    g0 = min(max(g0, config.CROISSANCE_MIN), config.CROISSANCE_MAX)
    justif["croissance_initiale"] = (
        f"Moyenne de la croissance historique du CA ({_pct(g_hist)}) et de la croissance fondamentale "
        f"de l'EBIT de l'industrie ({_pct(g_ind)}, réinvestissement x ROC, bornée à "
        f"[{_pct(config.CROISSANCE_INDUSTRIE_BORNES[0], 0)} ; {_pct(config.CROISSANCE_INDUSTRIE_BORNES[1], 0)}]), le tout "
        f"borné à [{_pct(config.CROISSANCE_MIN, 0)} ; {_pct(config.CROISSANCE_MAX, 0)}].")
    justif["croissance_terminale"] = (
        f"Plafonnée au taux sans risque ({_pct(wacc.taux_sans_risque)}) et à "
        f"{_pct(config.CROISSANCE_TERMINALE_MAX)} : aucune entreprise ne croît durablement plus vite que l'économie.")

    marge_actuelle = profil.marge_moyenne("ebit") if normaliser else profil.marge_ebit
    marge_historique = profil.marge_moyenne("ebit")
    m_ind = industrie.marge_operationnelle
    if marge_actuelle is None or math.isnan(marge_actuelle):
        marge_actuelle = m_ind
    if marge_vers_industrie or math.isnan(marge_historique) or marge_historique <= 0:
        marge_cible = m_ind
        justif["marge_cible"] = f"Marge opérationnelle de l'industrie ({_pct(m_ind)}), faute de marge historique positive."
    else:
        marge_cible = _moyenne_ponderee(marge_historique, m_ind, config.POIDS_MARGE_INDUSTRIE)
        justif["marge_cible"] = (f"Marge historique moyenne ({_pct(marge_historique)}) rapprochée à "
                                 f"{_pct(config.POIDS_MARGE_INDUSTRIE, 0)} de celle de l'industrie ({_pct(m_ind)}), "
                                 f"atteinte en année {config.ANNEE_CONVERGENCE_MARGE}.")
    justif["marge_initiale"] = ("Marge opérationnelle moyenne de l'historique (normalisation du cycle)."
                                if normaliser else f"Marge opérationnelle de la base ({profil.base_comptes}).")

    s2c_entreprise = math.nan
    if profil.capital_investi and not math.isnan(profil.capital_investi) and profil.capital_investi > 0:
        s2c_entreprise = profil.chiffre_affaires / profil.capital_investi
    s2c = _moyenne_ponderee(s2c_entreprise, industrie.ventes_sur_capital, config.POIDS_SALES_TO_CAPITAL_INDUSTRIE)
    if s2c is None or math.isnan(s2c):
        s2c = 1.5
    s2c = min(max(s2c, config.VENTES_SUR_CAPITAL_BORNES[0]), config.VENTES_SUR_CAPITAL_BORNES[1])
    justif["ventes_sur_capital"] = (f"Moyenne du ratio de l'entreprise ({_nb(s2c_entreprise, 2)}) et de "
                                    f"l'industrie ({_nb(industrie.ventes_sur_capital, 2)}) : chaque unité de CA "
                                    f"supplémentaire exige {_nb(1 / s2c, 2)} unité de capital investi.")

    t0 = profil.taux_is_effectif
    if math.isnan(t0):
        t0 = industrie.taux_is_effectif if not math.isnan(industrie.taux_is_effectif) else wacc.taux_is_marginal
    justif["taux_is"] = (f"Taux effectif ({_pct(t0)}) convergeant vers le taux marginal du pays "
                         f"({_pct(wacc.taux_is_marginal)}).")

    roic_entreprise = math.nan
    if not math.isnan(profil.capital_investi) and profil.capital_investi > 0 and not math.isnan(profil.ebit):
        roic_entreprise = profil.ebit * (1 - t0) / profil.capital_investi
    candidats = [x for x in (roic_entreprise, industrie.roic) if x is not None and not math.isnan(x)]
    roic_ref = max(candidats) if candidats else wacc.wacc
    roic_t = max(wacc.wacc, min(roic_ref, wacc.wacc + config.ECART_ROIC_TERMINAL_MAX))
    justif["roic_terminal"] = (f"Meilleur des ROIC de l'entreprise ({_pct(roic_entreprise)}) et de l'industrie "
                               f"({_pct(industrie.roic)}), borné entre le WACC et WACC + "
                               f"{_pct(config.ECART_ROIC_TERMINAL_MAX, 0)} : fixe le réinvestissement en régime permanent.")

    hypotheses = HypothesesDCF(
        croissance_initiale=g0, croissance_terminale=g_terminal, marge_initiale=marge_actuelle,
        marge_cible=marge_cible, ventes_sur_capital=s2c, taux_is_initial=t0,
        taux_is_terminal=wacc.taux_is_marginal, roic_terminal=roic_t, wacc=wacc.wacc,
        chiffre_affaires_base=profil.chiffre_affaires,
    )
    for cle, valeur in surcharges.items():
        if not hasattr(hypotheses, cle):
            raise KeyError(f"Hypothèse DCF inconnue : {cle}")
        setattr(hypotheses, cle, valeur)
        justif[cle] = f"Valeur imposée par l'utilisateur ({valeur})."
    return hypotheses, justif


def projeter(h):
    """Tableau des flux projetés et valeur d'entreprise. Renvoie (DataFrame, dict des agrégats)."""
    if h.wacc <= h.croissance_terminale:
        raise ValueError("Le WACC doit dépasser la croissance terminale")
    n, palier = h.horizon, min(5, h.horizon)
    lignes = []
    ca_prec = h.chiffre_affaires_base
    for t in range(1, n + 1):
        if t <= palier:
            g = h.croissance_initiale
        else:
            g = h.croissance_initiale - (h.croissance_initiale - h.croissance_terminale) * (t - palier) / (n - palier)
        ca = ca_prec * (1 + g)
        marge = h.marge_initiale + (h.marge_cible - h.marge_initiale) * min(t / h.annee_convergence_marge, 1.0)
        impot = h.taux_is_initial + (h.taux_is_terminal - h.taux_is_initial) * max(0, t - palier) / max(1, n - palier)
        ebit = ca * marge
        nopat = ebit * (1 - impot) if ebit > 0 else ebit
        reinvestissement = (ca - ca_prec) / h.ventes_sur_capital
        fcff = nopat - reinvestissement
        actualisation = 1 / (1 + h.wacc) ** t
        lignes.append({"annee": t, "croissance": g, "chiffre_affaires": ca, "marge": marge, "ebit": ebit,
                       "taux_is": impot, "nopat": nopat, "reinvestissement": reinvestissement, "fcff": fcff,
                       "facteur_actualisation": actualisation, "fcff_actualise": fcff * actualisation})
        ca_prec = ca

    tableau = pd.DataFrame(lignes).set_index("annee")
    ca_terminal = ca_prec * (1 + h.croissance_terminale)
    nopat_terminal = ca_terminal * h.marge_cible * (1 - h.taux_is_terminal)
    taux_reinvestissement = h.croissance_terminale / h.roic_terminal if h.roic_terminal > 0 else 0.0
    fcff_terminal = nopat_terminal * (1 - taux_reinvestissement)
    valeur_terminale = fcff_terminal / (h.wacc - h.croissance_terminale)
    va_terminale = valeur_terminale / (1 + h.wacc) ** n
    va_flux = tableau["fcff_actualise"].sum()
    return tableau, {
        "va_flux": va_flux, "valeur_terminale": valeur_terminale, "va_valeur_terminale": va_terminale,
        "valeur_entreprise": va_flux + va_terminale, "taux_reinvestissement_terminal": taux_reinvestissement,
        "part_valeur_terminale": va_terminale / (va_flux + va_terminale) if va_flux + va_terminale else math.nan,
    }


def valeur_par_action(h, profil):
    _, agregats = projeter(h)
    return pont_valeur_entreprise(agregats["valeur_entreprise"], profil) / profil.nb_actions


def _variante(h, **modifs):
    d = asdict(h)
    d.update(modifs)
    return HypothesesDCF(**d)


def sensibilite(h, profil):
    """Valeur par action selon WACC (lignes) et croissance terminale (colonnes)."""
    grille = {}
    for dw in config.SENSIBILITE_WACC:
        ligne = {}
        for dg in config.SENSIBILITE_G:
            variante = _variante(h, wacc=h.wacc + dw, croissance_terminale=h.croissance_terminale + dg)
            try:
                ligne[variante.croissance_terminale] = valeur_par_action(variante, profil)
            except ValueError:
                ligne[variante.croissance_terminale] = math.nan
        grille[h.wacc + dw] = ligne
    return pd.DataFrame(grille).T


def dcf_inverse(h, profil, cours, bornes=(-0.15, 0.50)):
    """Croissance initiale du CA (années 1-5) que le cours actuel intègre, à marges inchangées."""
    def ecart(g):
        return valeur_par_action(_variante(h, croissance_initiale=g), profil) - cours
    bas, haut = bornes
    try:
        if ecart(bas) > 0 or ecart(haut) < 0:
            return None
    except ValueError:
        return None
    for _ in range(60):
        milieu = (bas + haut) / 2
        if ecart(milieu) > 0:
            haut = milieu
        else:
            bas = milieu
    return (bas + haut) / 2


def valoriser(profil, industrie, wacc, normaliser=False, marge_vers_industrie=False, surcharges=None):
    alertes = []
    if math.isnan(profil.chiffre_affaires) or profil.chiffre_affaires <= 0:
        return ResultatMethode("dcf", "DCF (FCFF)", math.nan, math.nan, math.nan,
                               alertes=["Chiffre d'affaires indisponible : DCF impossible."])
    h, justifications = construire_hypotheses(profil, industrie, wacc, normaliser, marge_vers_industrie, surcharges)
    tableau, agregats = projeter(h)
    valeur_fp = pont_valeur_entreprise(agregats["valeur_entreprise"], profil)
    vpa = valeur_fp / profil.nb_actions
    grille = sensibilite(h, profil)

    # Fourchette : WACC +/- 0,5 point et g terminal -/+ 0,25 point (cases intérieures de la grille).
    pessimiste = _variante(h, wacc=h.wacc + 0.005, croissance_terminale=h.croissance_terminale - 0.0025)
    optimiste = _variante(h, wacc=h.wacc - 0.005, croissance_terminale=h.croissance_terminale + 0.0025)
    bas, haut = valeur_par_action(pessimiste, profil), valeur_par_action(optimiste, profil)

    if agregats["part_valeur_terminale"] > 0.85:
        alertes.append(f"La valeur terminale pèse {_pct(agregats['part_valeur_terminale'], 0)} de la valeur : "
                       "résultat très sensible aux hypothèses de long terme.")
    if vpa <= 0:
        alertes.append("Valeur des fonds propres négative : la dette excède la valeur des actifs d'exploitation.")

    return ResultatMethode(
        "dcf", "DCF (FCFF)", vpa, bas, haut,
        detail={
            "hypotheses": h, "justifications": justifications, "projections": tableau,
            "valeur_fonds_propres": valeur_fp, "sensibilite": grille,
            "croissance_implicite": dcf_inverse(h, profil, profil.cours), **agregats,
        },
        alertes=alertes,
    )
