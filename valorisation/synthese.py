"""Triangulation des méthodes et verdict (sous-évalué, correctement valorisé, surévalué)."""

import math
from dataclasses import dataclass, field
from datetime import date

from . import config

SOUS_EVALUE = "Sous-évalué"
CORRECT = "Correctement valorisé"
SUREVALUE = "Surévalué"
NON_CONCLUANT = "Non concluant"


def verdict(ecart, seuil=config.SEUIL_VERDICT):
    """`ecart` = valeur centrale / cours - 1."""
    if ecart is None or math.isnan(ecart):
        return NON_CONCLUANT
    if ecart >= seuil:
        return SOUS_EVALUE
    if ecart <= -seuil:
        return SUREVALUE
    return CORRECT


def ponderer(resultats, poids):
    """Combine les méthodes valides ; le poids d'une méthode inapplicable est redistribué.

    Renvoie (valeur centrale, bas, haut, poids effectifs).
    """
    valides = {r.methode: r for r in resultats if r.valide and poids.get(r.methode)}
    total = sum(poids[m] for m in valides)
    if not valides or total <= 0:
        return math.nan, math.nan, math.nan, {}
    effectifs = {m: poids[m] / total for m in valides}
    centrale = sum(effectifs[m] * valides[m].valeur_par_action for m in valides)
    bas = sum(effectifs[m] * min(valides[m].bas, valides[m].valeur_par_action) for m in valides)
    haut = sum(effectifs[m] * max(valides[m].haut, valides[m].valeur_par_action) for m in valides)
    return centrale, bas, haut, effectifs


@dataclass
class ResultatValorisation:
    ticker: str
    nom: str
    devise: str
    cours: float
    profil_entreprise: object
    industrie_yahoo: str
    industrie_damodaran: str
    correspondance_trouvee: bool
    region: str
    plan: object
    industrie: object
    wacc: object
    methodes: list
    valeur_centrale: float
    bas: float
    haut: float
    poids_effectifs: dict
    date_donnees_damodaran: date = None
    date_primes_pays: date = None
    date_valorisation: date = field(default_factory=date.today)
    seuil_verdict: float = config.SEUIL_VERDICT
    alertes: list = field(default_factory=list)

    @property
    def ecart(self):
        if math.isnan(self.valeur_centrale) or not self.cours:
            return math.nan
        return self.valeur_centrale / self.cours - 1

    @property
    def verdict(self):
        return verdict(self.ecart, self.seuil_verdict)

    def methode(self, nom):
        return next((r for r in self.methodes if r.methode == nom), None)

    def resume(self):
        """Dictionnaire à plat, sérialisable en JSON : c'est l'interface prévue pour le dashboard."""
        def nombre(x):
            return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 4)
        return {
            "ticker": self.ticker, "nom": self.nom, "devise": self.devise, "cours": nombre(self.cours),
            "valeur_centrale": nombre(self.valeur_centrale), "bas": nombre(self.bas), "haut": nombre(self.haut),
            "ecart": nombre(self.ecart), "verdict": self.verdict,
            "profil": self.plan.profil, "industrie_damodaran": self.industrie_damodaran, "region": self.region,
            "wacc": nombre(self.wacc.wacc) if self.wacc else None,
            "methodes": {r.methode: {"valeur": nombre(r.valeur_par_action), "bas": nombre(r.bas),
                                     "haut": nombre(r.haut), "poids": nombre(self.poids_effectifs.get(r.methode, 0.0))}
                         for r in self.methodes},
            "date_valorisation": self.date_valorisation.isoformat(),
            "date_donnees_damodaran": self.date_donnees_damodaran.isoformat() if self.date_donnees_damodaran else None,
            "alertes": list(self.alertes),
        }
