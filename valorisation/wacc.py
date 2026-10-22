"""Coût moyen pondéré du capital, construit « bottom-up » à la manière de Damodaran.

  coût des fonds propres = taux sans risque + bêta réendetté x (prime marché mature + prime pays)
  bêta réendetté         = bêta désendetté de l'industrie x (1 + (1 - t) x D/E de l'entreprise)
  coût de la dette       = taux sans risque + spread de la notation synthétique + spread du pays
  WACC                   = E/(D+E) x coût des fonds propres + D/(D+E) x coût de la dette x (1 - t)

D et E sont en valeur de marché (dette financière y compris locations, capitalisation boursière).
Pour une institution financière, la dette fait partie de l'activité : le bêta endetté moyen de
l'industrie est utilisé tel quel (pas de désendettement / réendettement), et seul le coût des fonds
propres sert à la valorisation.
"""

import math
from dataclasses import dataclass, field

from . import config, marche
from .formats import nombre, pct

TAUX_IS_DEFAUT = 0.25


@dataclass
class DetailWacc:
    taux_sans_risque: float
    source_taux: str
    beta_desendette: float
    dette_sur_fonds_propres: float
    taux_is_marginal: float
    beta_reendette: float
    financiere: bool
    prime_marche_mature: float
    prime_pays: float
    cout_fonds_propres: float
    couverture_interets: float
    notation_synthetique: str
    spread_entreprise: float
    spread_pays: float
    cout_dette_avant_impot: float
    poids_fonds_propres: float
    wacc: float
    alertes: list = field(default_factory=list)

    @property
    def prime_actions(self):
        return self.prime_marche_mature + self.prime_pays

    @property
    def cout_dette_apres_impot(self):
        return self.cout_dette_avant_impot * (1 - self.taux_is_marginal)

    @property
    def poids_dette(self):
        return 1 - self.poids_fonds_propres


def _capitalisation_usd(profil):
    try:
        return profil.capitalisation * marche.taux_change(profil.devise, "USD")
    except Exception:
        return profil.capitalisation


def calculer_wacc(profil, industrie, referentiel, taux_sans_risque=None, financiere=False):
    """`industrie` : ParametresIndustrie Damodaran ; `taux_sans_risque` : (taux, source) imposé ;
    `financiere` : banque ou assurance (bêta endetté de l'industrie, sans réendettement)."""
    alertes = []
    rf, source = taux_sans_risque or marche.taux_sans_risque(profil.devise)

    t = referentiel.taux_is_marginal(profil.pays)
    if t is None:
        t = industrie.taux_is_effectif if not math.isnan(industrie.taux_is_effectif) else TAUX_IS_DEFAUT
        alertes.append(f"Taux d'IS marginal de « {profil.pays} » introuvable : {pct(t)} retenu.")

    d_e = profil.dette_financiere / profil.capitalisation if profil.capitalisation > 0 else 0.0
    if financiere and not math.isnan(industrie.beta_endette):
        beta_l = industrie.beta_endette
    else:
        beta_l = industrie.beta_desendette * (1 + (1 - t) * d_e)
    beta_borne = min(max(beta_l, config.BETA_MIN), config.BETA_MAX)
    if beta_borne != beta_l:
        alertes.append(f"Bêta réendetté de {nombre(beta_l, 2)} ramené à {nombre(beta_borne, 2)}.")

    pays = referentiel.donnees_pays(profil.pays)
    prime_mature = referentiel.prime_marche_mature()
    if pays is None:
        alertes.append(f"Pays « {profil.pays} » absent des primes Damodaran : aucune prime pays appliquée.")
        prime_pays, spread_pays = 0.0, 0.0
    else:
        prime_pays, spread_pays = pays["prime_pays"], pays["spread_defaut"]
    ke = rf + beta_borne * (prime_mature + prime_pays)

    if profil.frais_financiers and not math.isnan(profil.frais_financiers) and profil.frais_financiers > 0:
        couverture = profil.ebit / profil.frais_financiers if not math.isnan(profil.ebit) else math.nan
    else:
        couverture = math.inf
    grande = _capitalisation_usd(profil) >= config.SEUIL_GRANDE_ENTREPRISE_USD
    notation, spread = referentiel.notation_synthetique(couverture, grande_entreprise=grande)
    kd = rf + spread + spread_pays

    e = profil.capitalisation
    d = profil.dette_financiere
    poids_e = e / (e + d) if e + d > 0 else 1.0
    wacc = poids_e * ke + (1 - poids_e) * kd * (1 - t)

    return DetailWacc(
        taux_sans_risque=rf, source_taux=source,
        beta_desendette=industrie.beta_desendette, dette_sur_fonds_propres=d_e, taux_is_marginal=t,
        beta_reendette=beta_borne, financiere=financiere, prime_marche_mature=prime_mature, prime_pays=prime_pays,
        cout_fonds_propres=ke, couverture_interets=couverture, notation_synthetique=notation,
        spread_entreprise=spread, spread_pays=spread_pays, cout_dette_avant_impot=kd,
        poids_fonds_propres=poids_e, wacc=wacc, alertes=alertes,
    )
