"""Valorisation par multiples sectoriels Damodaran.

Le multiple central est celui de l'industrie dans la région de l'entreprise ; la fourchette va du
multiple régional au multiple mondial de la même industrie. Les multiples de valeur d'entreprise
(EV/EBITDA, EV/Ventes) passent par le pont EV -> fonds propres ; P/E et P/BV donnent directement
la valeur des fonds propres.
"""

import math

from . import ResultatMethode, pont_valeur_entreprise

# méthode -> (libellé, multiple de valeur d'entreprise ?, nom de l'agrégat)
METHODES = {
    "ev_ebitda": ("EV/EBITDA sectoriel", True, "EBITDA"),
    "ev_ventes": ("EV/Ventes sectoriel", True, "chiffre d'affaires"),
    "per": ("P/E sectoriel", False, "résultat net"),
    "pbv": ("P/BV sectoriel", False, "capitaux propres"),
}


def agregat(profil, methode, normaliser=False):
    if methode == "ev_ebitda":
        if normaliser:
            marge = profil.marge_moyenne("ebitda")
            if not math.isnan(marge):
                return profil.chiffre_affaires * marge
        return profil.ebitda
    if methode == "ev_ventes":
        return profil.chiffre_affaires
    if methode == "per":
        return profil.resultat_net
    if methode == "pbv":
        return profil.capitaux_propres
    raise KeyError(methode)


def _par_action(multiple, base, est_ev, profil):
    valeur = multiple * base
    if est_ev:
        valeur = pont_valeur_entreprise(valeur, profil)
    return valeur / profil.nb_actions


def valoriser(profil, industrie, methode, normaliser=False):
    libelle, est_ev, nom_agregat = METHODES[methode]
    base = agregat(profil, methode, normaliser)
    m_region = getattr(industrie, methode)
    m_monde = industrie.multiples_monde.get(methode, math.nan)
    alertes = []

    if base is None or math.isnan(base) or base <= 0:
        return ResultatMethode(methode, libelle, math.nan, math.nan, math.nan,
                               alertes=[f"{nom_agregat.capitalize()} négatif ou indisponible : {libelle} non applicable."])
    if math.isnan(m_region):
        if math.isnan(m_monde):
            return ResultatMethode(methode, libelle, math.nan, math.nan, math.nan,
                                   alertes=[f"Multiple {libelle} absent des données Damodaran."])
        m_region = m_monde
        alertes.append(f"Multiple régional absent : multiple mondial utilisé pour {libelle}.")
    if math.isnan(m_monde):
        m_monde = m_region

    central = _par_action(m_region, base, est_ev, profil)
    extremes = sorted([_par_action(m_region, base, est_ev, profil), _par_action(m_monde, base, est_ev, profil)])
    if normaliser and methode == "ev_ebitda":
        alertes.append("EBITDA normalisé : marge d'EBITDA moyenne de l'historique appliquée au CA actuel.")

    return ResultatMethode(
        methode, libelle, central, extremes[0], extremes[1],
        detail={
            "agregat": nom_agregat, "base": base, "normalise": normaliser and methode == "ev_ebitda",
            "multiple_region": m_region, "multiple_monde": m_monde, "region": industrie.region,
            "multiple_actuel": _multiple_actuel(profil, methode, base, est_ev),
        },
        alertes=alertes,
    )


def _multiple_actuel(profil, methode, base, est_ev):
    """Multiple auquel le marché valorise aujourd'hui l'entreprise, pour comparaison."""
    numerateur = profil.valeur_entreprise_marche if est_ev else profil.capitalisation
    return numerateur / base if base else math.nan
