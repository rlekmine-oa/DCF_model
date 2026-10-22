"""Méthodes de valorisation et éléments communs."""

from dataclasses import dataclass, field


def pont_valeur_entreprise(valeur_entreprise, profil):
    """Valeur d'entreprise -> valeur des fonds propres (passage « EV to equity »).

    + trésorerie et placements, + participations non consolidées (à leur valeur comptable),
    - dette financière (y compris locations), - intérêts minoritaires (à leur valeur comptable).
    """
    return (valeur_entreprise + profil.tresorerie + profil.participations
            - profil.dette_financiere - profil.interets_minoritaires)


@dataclass
class ResultatMethode:
    """Résultat commun à toutes les méthodes, en valeur par action (devise de cotation)."""
    methode: str
    libelle: str
    valeur_par_action: float
    bas: float
    haut: float
    detail: dict = field(default_factory=dict)
    alertes: list = field(default_factory=list)

    @property
    def valide(self):
        v = self.valeur_par_action
        return v is not None and v == v and v > 0
