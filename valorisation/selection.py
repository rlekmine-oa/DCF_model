"""Choix des méthodes de valorisation selon le profil sectoriel et la situation de l'entreprise."""

import math
from dataclasses import dataclass, field

from . import correspondances
from .formats import pct


@dataclass
class PlanValorisation:
    profil: str
    libelle: str
    justification: str
    poids: dict                      # méthode -> poids (somme = 1)
    normaliser: bool = False         # cycle : marges et EBITDA moyens de l'historique
    marge_vers_industrie: bool = False
    ajustements: list = field(default_factory=list)


# Frais financiers / CA en dessous duquel une société « financière » n'a pas un bilan de prêteur.
SEUIL_FRAIS_FINANCIERS_PRETEUR = 0.10
# Seules ces industries mélangent prêteurs et sociétés à commissions (réseaux de paiement,
# gestionnaires d'actifs). Banques et assureurs restent valorisés sur leurs fonds propres même
# s'ils publient un EBIT : leur bilan est leur outil de production.
INDUSTRIES_FINANCIERES_MIXTES = {"Financial Svcs. (Non-bank & Insurance)", "Investments & Asset Management"}


def activite_a_commissions(profil_entreprise):
    """Vrai pour une société financière dont le modèle repose sur des commissions (réseau de paiement,
    gestionnaire d'actifs, plateforme) : elle publie un EBIT positif et ses frais financiers sont faibles.
    Une banque ne publie pas d'EBIT et ses frais financiers représentent une part majeure de ses revenus."""
    ebit, ca = profil_entreprise.ebit, profil_entreprise.chiffre_affaires
    if math.isnan(ebit) or ebit <= 0 or math.isnan(ca) or ca <= 0:
        return False
    frais = profil_entreprise.frais_financiers
    return math.isnan(frais) or frais / ca < SEUIL_FRAIS_FINANCIERS_PRETEUR


def _plan(nom_profil):
    regle = correspondances.regles_methodes()["profils"][nom_profil]
    return PlanValorisation(
        profil=nom_profil, libelle=regle["libelle"], justification=" ".join(regle["justification"].split()),
        poids=dict(regle["methodes"]), normaliser=bool(regle.get("normaliser", False)),
    )


def choisir_methodes(profil_entreprise, industrie_damodaran, poids_imposes=None):
    nom_profil = correspondances.profil_sectoriel(industrie_damodaran)
    reclasse = industrie_damodaran in INDUSTRIES_FINANCIERES_MIXTES and activite_a_commissions(profil_entreprise)
    plan = _plan("standard" if reclasse else nom_profil)
    if reclasse:
        plan.ajustements.append("Société financière à commissions (EBIT publié, frais financiers inférieurs à "
                                f"{pct(SEUIL_FRAIS_FINANCIERS_PRETEUR, 0)} du CA) : valorisée comme une entreprise "
                                "standard, le P/BV n'ayant pas de sens sans bilan de prêteur.")
    nom_profil, poids = plan.profil, plan.poids

    ebitda = profil_entreprise.ebitda
    if plan.normaliser:
        marge = profil_entreprise.marge_moyenne("ebitda")
        if not math.isnan(marge):
            ebitda = marge * profil_entreprise.chiffre_affaires
    if "ev_ebitda" in poids and nom_profil != "actifs" and (math.isnan(ebitda) or ebitda <= 0):
        poids["ev_ventes"] = poids.pop("ev_ebitda")
        plan.marge_vers_industrie = True
        plan.ajustements.append("EBITDA négatif : EV/EBITDA remplacé par EV/Ventes, et la marge du DCF "
                                "converge vers celle de l'industrie.")

    rn = profil_entreprise.resultat_net
    if "per" in poids and (math.isnan(rn) or rn <= 0) and "pbv" in poids:
        poids["pbv"] += poids.pop("per")
        plan.ajustements.append("Résultat net négatif : le P/E est écarté au profit du P/BV.")

    if poids_imposes:
        plan.poids = {m: float(p) for m, p in poids_imposes.items() if p}
        plan.ajustements.append("Pondération des méthodes imposée par l'utilisateur.")
    total = sum(plan.poids.values())
    plan.poids = {m: p / total for m, p in plan.poids.items()}
    return plan
