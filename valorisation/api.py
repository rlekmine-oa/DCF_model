"""Point d'entrée du moteur : `evaluer_ticker` (société cotée) et `evaluer_profil` (profil fourni).

Exemple :
    from valorisation import evaluer_ticker
    r = evaluer_ticker("SU.PA")
    print(r.verdict, r.valeur_centrale, r.ecart)
"""

from . import correspondances, synthese
from .damodaran.referentiel import ReferentielDamodaran
from .entreprise import TYPES_NON_VALORISABLES, NonValorisable, charger_depuis_yfinance
from .methodes import dcf, multiples
from .selection import choisir_methodes
from .wacc import calculer_wacc

_REFERENTIEL = None


def referentiel_par_defaut():
    global _REFERENTIEL
    if _REFERENTIEL is None:
        _REFERENTIEL = ReferentielDamodaran()
    return _REFERENTIEL


def evaluer_ticker(ticker, corrections_profil=None, **options):
    """Valorise une société cotée à partir de son ticker Yahoo Finance (ex. « SU.PA », « AAPL »).

    `corrections_profil` remplace des champs du profil chargé, par exemple
    {"nb_actions": 1.62e9} pour une société à double cotation (Rio Tinto plc + Ltd).
    Les autres options sont celles d'`evaluer_profil`.
    """
    profil = charger_depuis_yfinance(ticker)
    for champ, valeur in (corrections_profil or {}).items():
        if not hasattr(profil, champ):
            raise KeyError(f"Champ de profil inconnu : {champ}")
        setattr(profil, champ, valeur)
        profil.alertes.append(f"{champ} corrigé manuellement : {valeur}.")
    return evaluer_profil(profil, **options)


def evaluer_profil(profil, referentiel=None, industrie=None, region=None, taux_sans_risque=None,
                   surcharges_dcf=None, poids=None, seuil_verdict=None):
    """Valorise un `ProfilEntreprise`.

    Options :
      industrie        industrie Damodaran imposée (sinon déduite de l'industrie Yahoo) ;
      region           région Damodaran imposée (US, Europe, Japan, Rest, emerg, China, India, Global) ;
      taux_sans_risque (taux, source) imposé ;
      surcharges_dcf   dict d'hypothèses DCF imposées (ex. {"croissance_initiale": 0.05}) ;
      poids            pondération imposée des méthodes (ex. {"dcf": 1.0}) ;
      seuil_verdict    écart minimal pour conclure à une sous/surévaluation (0,15 par défaut).
    """
    if (profil.type_titre or "EQUITY").upper() in TYPES_NON_VALORISABLES:
        raise NonValorisable(f"{profil.ticker} est un {profil.type_titre} : seules les actions sont valorisées.")
    ref = referentiel or referentiel_par_defaut()
    alertes = list(profil.alertes)

    region = region or ref.region_damodaran(profil.pays)
    if industrie:
        nom_industrie, trouvee = industrie, True
    else:
        nom_industrie = correspondances.industrie_damodaran(profil.industrie_yahoo)
        trouvee = nom_industrie is not None
        if not trouvee:
            nom_industrie = ref.industrie_marche(region)
            alertes.append(f"Industrie Yahoo « {profil.industrie_yahoo} » non répertoriée : "
                           f"moyennes du marché utilisées ({nom_industrie}).")
    if nom_industrie not in ref.table("beta", region).index:
        alertes.append(f"« {nom_industrie} » absente des données {region} : données mondiales utilisées.")
        region = "Global"
    parametres = ref.parametres_industrie(nom_industrie, region)

    plan = choisir_methodes(profil, nom_industrie, poids)
    alertes.extend(plan.ajustements)

    detail_wacc = calculer_wacc(profil, parametres, ref, taux_sans_risque, financiere=plan.profil == "financiere")
    alertes.extend(detail_wacc.alertes)

    resultats = []
    for methode in plan.poids:
        if methode == "dcf":
            resultat = dcf.valoriser(profil, parametres, detail_wacc, plan.normaliser,
                                     plan.marge_vers_industrie, surcharges_dcf)
        else:
            resultat = multiples.valoriser(profil, parametres, methode, plan.normaliser)
        resultats.append(resultat)
        alertes.extend(resultat.alertes)

    centrale, bas, haut, effectifs = synthese.ponderer(resultats, plan.poids)
    if not effectifs:
        alertes.append("Aucune méthode applicable : valorisation non concluante.")

    return synthese.ResultatValorisation(
        ticker=profil.ticker, nom=profil.nom, devise=profil.devise, cours=profil.cours,
        profil_entreprise=profil, industrie_yahoo=profil.industrie_yahoo, industrie_damodaran=nom_industrie,
        correspondance_trouvee=trouvee, region=region, plan=plan, industrie=parametres, wacc=detail_wacc,
        methodes=resultats, valeur_centrale=centrale, bas=bas, haut=haut, poids_effectifs=effectifs,
        date_donnees_damodaran=parametres.date_mise_a_jour, date_primes_pays=ref.date_primes_pays(),
        seuil_verdict=seuil_verdict if seuil_verdict is not None else synthese.config.SEUIL_VERDICT,
        alertes=list(dict.fromkeys(alertes)),
    )
