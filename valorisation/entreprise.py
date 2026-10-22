"""Profil financier d'une entreprise : identification, compte de résultat, bilan, historique.

Tous les montants sont exprimés dans la devise de cotation (les comptes publiés dans une autre
devise sont convertis au dernier cours de change). Un profil peut être construit à la main
(société non cotée, cas d'école) ou chargé depuis Yahoo Finance avec `charger_depuis_yfinance`.
"""

import math
from dataclasses import dataclass, field

import pandas as pd

from . import marche
from .formats import nombre

NAN = math.nan

# Types de titres Yahoo qui ne se valorisent pas comme une entreprise.
TYPES_NON_VALORISABLES = {"ETF", "MUTUALFUND", "INDEX", "CURRENCY", "CRYPTOCURRENCY", "FUTURE", "OPTION"}


class NonValorisable(ValueError):
    """Titre hors du champ de l'outil (ETF, fonds, indice…)."""


def _ok(x):
    return x is not None and not (isinstance(x, float) and math.isnan(x))


@dataclass
class ProfilEntreprise:
    ticker: str
    nom: str
    pays: str
    devise: str
    cours: float
    nb_actions: float
    secteur: str = None
    industrie_yahoo: str = None
    type_titre: str = "EQUITY"
    # Compte de résultat de l'année de base (12 mois glissants quand ils sont disponibles)
    chiffre_affaires: float = NAN
    ebit: float = NAN
    amortissements: float = NAN
    resultat_net: float = NAN
    resultat_avant_impot: float = NAN
    impot: float = NAN
    frais_financiers: float = NAN
    # Bilan le plus récent
    dette_financiere: float = 0.0      # y compris dettes locatives (IFRS 16)
    tresorerie: float = 0.0
    capitaux_propres: float = NAN
    interets_minoritaires: float = 0.0
    participations: float = 0.0        # sociétés mises en équivalence et titres non consolidés
    # Historique annuel (index : année, croissant) : chiffre_affaires, ebit, ebitda, resultat_net
    historique: pd.DataFrame = field(default_factory=pd.DataFrame)
    devise_comptes: str = None
    base_comptes: str = ""
    beta_yahoo: float = NAN
    alertes: list = field(default_factory=list)

    # --- Agrégats ----------------------------------------------------------------
    @property
    def ebitda(self):
        if _ok(self.ebit) and _ok(self.amortissements):
            return self.ebit + self.amortissements
        return NAN

    @property
    def capitalisation(self):
        return self.cours * self.nb_actions

    @property
    def dette_nette(self):
        return self.dette_financiere - self.tresorerie

    @property
    def valeur_entreprise_marche(self):
        return self.capitalisation + self.dette_nette + self.interets_minoritaires - self.participations

    @property
    def capital_investi(self):
        """Capitaux propres comptables + dette financière - trésorerie (définition Damodaran)."""
        if not _ok(self.capitaux_propres):
            return NAN
        return self.capitaux_propres + self.interets_minoritaires + self.dette_financiere - self.tresorerie

    @property
    def marge_ebit(self):
        if _ok(self.ebit) and _ok(self.chiffre_affaires) and self.chiffre_affaires > 0:
            return self.ebit / self.chiffre_affaires
        return NAN

    @property
    def taux_is_effectif(self):
        if _ok(self.impot) and _ok(self.resultat_avant_impot) and self.resultat_avant_impot > 0:
            return min(max(self.impot / self.resultat_avant_impot, 0.0), 0.5)
        return NAN

    @property
    def bpa(self):
        return self.resultat_net / self.nb_actions if _ok(self.resultat_net) else NAN

    @property
    def actif_net_par_action(self):
        return self.capitaux_propres / self.nb_actions if _ok(self.capitaux_propres) else NAN

    # --- Tendances historiques -----------------------------------------------------
    def croissance_historique(self):
        """Taux de croissance annuel moyen du chiffre d'affaires sur l'historique disponible."""
        ca = self.historique.get("chiffre_affaires", pd.Series(dtype=float)).dropna()
        ca = ca[ca > 0]
        if len(ca) < 2:
            return NAN
        annees = len(ca) - 1
        return (ca.iloc[-1] / ca.iloc[0]) ** (1 / annees) - 1

    def marge_moyenne(self, colonne):
        """Marge moyenne (colonne / CA) sur l'historique, pondérée par le CA."""
        h = self.historique
        if colonne not in h or "chiffre_affaires" not in h:
            return NAN
        valide = h[["chiffre_affaires", colonne]].dropna()
        valide = valide[valide["chiffre_affaires"] > 0]
        if valide.empty:
            return NAN
        return valide[colonne].sum() / valide["chiffre_affaires"].sum()


# --- Chargement depuis Yahoo Finance --------------------------------------------------
def _ligne(table, noms, colonne=0):
    if table is None or table.empty:
        return NAN
    for nom in noms:
        if nom in table.index:
            serie = table.loc[nom]
            if isinstance(serie, pd.DataFrame):
                serie = serie.iloc[0]
            if colonne < len(serie) and pd.notna(serie.iloc[colonne]):
                return float(serie.iloc[colonne])
    return NAN


_CHAMPS_RESULTAT = {
    "chiffre_affaires": ["Total Revenue", "Operating Revenue"],
    "ebit": ["Operating Income", "EBIT", "Total Operating Income As Reported"],
    "amortissements": ["Reconciled Depreciation", "Depreciation And Amortization In Income Statement",
                       "Depreciation And Amortization"],
    "resultat_net": ["Net Income Common Stockholders", "Net Income"],
    "resultat_avant_impot": ["Pretax Income"],
    "impot": ["Tax Provision"],
    "frais_financiers": ["Interest Expense", "Interest Expense Non Operating"],
}


def _tableau(fonction):
    try:
        resultat = fonction()
        return resultat if isinstance(resultat, pd.DataFrame) else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def charger_depuis_yfinance(ticker):
    """Construit le profil d'une société cotée à partir de Yahoo Finance."""
    import yfinance as yf

    titre = yf.Ticker(ticker)
    info = titre.info or {}
    alertes = []
    type_titre = (info.get("quoteType") or "EQUITY").upper()
    if type_titre in TYPES_NON_VALORISABLES:
        raise NonValorisable(f"{ticker} est un {type_titre} : seules les actions sont valorisées.")

    devise, diviseur = marche.normaliser_devise(info.get("currency"))
    cours = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
    if not cours:
        raise ValueError(f"{ticker} : cours introuvable sur Yahoo Finance")
    cours = float(cours) / diviseur

    devise_comptes = marche.normaliser_devise(info.get("financialCurrency") or devise)[0]
    change = 1.0
    if devise_comptes != devise:
        change = marche.taux_change(devise_comptes, devise)
        alertes.append(f"Comptes publiés en {devise_comptes}, convertis en {devise} au cours de {nombre(change, 4)}.")

    annuel = _tableau(lambda: titre.income_stmt)
    glissant = _tableau(lambda: titre.ttm_income_stmt)
    flux = _tableau(lambda: titre.cashflow)
    # Bilan semestriel ou trimestriel le plus récent, sinon bilan annuel.
    bilan = _tableau(lambda: titre.quarterly_balance_sheet)
    if math.isnan(_ligne(bilan, ["Stockholders Equity", "Total Debt"])):
        bilan = _tableau(lambda: titre.balance_sheet)

    if annuel.empty and glissant.empty:
        raise NonValorisable(f"{ticker} : aucun compte publié sur Yahoo Finance (ETC, fonds ou titre non couvert).")

    base_glissante = not glissant.empty and not math.isnan(_ligne(glissant, _CHAMPS_RESULTAT["chiffre_affaires"]))
    source = glissant if base_glissante else annuel
    if base_glissante:
        base_comptes = f"12 mois glissants au {pd.Timestamp(glissant.columns[0]).date()}"
    else:
        base_comptes = f"exercice clos le {pd.Timestamp(annuel.columns[0]).date()}"

    resultat = {}
    for champ, noms in _CHAMPS_RESULTAT.items():
        valeur = _ligne(source, noms)
        if math.isnan(valeur) and base_glissante:
            valeur = _ligne(annuel, noms)  # poste absent des 12 mois glissants : dernier exercice
        if math.isnan(valeur) and champ == "amortissements":
            valeur = _ligne(flux, ["Depreciation And Amortization", "Depreciation"])
        resultat[champ] = valeur * change if not math.isnan(valeur) else NAN
    if not math.isnan(resultat["frais_financiers"]):
        resultat["frais_financiers"] = abs(resultat["frais_financiers"])

    historique = []
    for j, colonne in enumerate(annuel.columns):
        ligne = {
            "annee": pd.Timestamp(colonne).year,
            "chiffre_affaires": _ligne(annuel, _CHAMPS_RESULTAT["chiffre_affaires"], j),
            "ebit": _ligne(annuel, _CHAMPS_RESULTAT["ebit"], j),
            "amortissements": _ligne(annuel, _CHAMPS_RESULTAT["amortissements"], j),
            "resultat_net": _ligne(annuel, _CHAMPS_RESULTAT["resultat_net"], j),
        }
        if not math.isnan(ligne["chiffre_affaires"]):
            historique.append(ligne)
    historique = pd.DataFrame(historique)
    if not historique.empty:
        historique = historique.set_index("annee").sort_index() * change
        historique["ebitda"] = historique["ebit"] + historique["amortissements"]

    dette = _ligne(bilan, ["Total Debt"])
    if math.isnan(dette):
        dette = 0.0
        alertes.append("Dette financière introuvable : supposée nulle.")
    tresorerie = _ligne(bilan, ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"])
    nb_actions = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding") \
        or _ligne(bilan, ["Ordinary Shares Number", "Share Issued"])
    if not nb_actions:
        raise ValueError(f"{ticker} : nombre d'actions introuvable")

    def _bilan(noms, defaut=0.0):
        v = _ligne(bilan, noms)
        return defaut if math.isnan(v) else v * change

    if len(historique) < 3:
        alertes.append(f"Historique court ({len(historique)} exercice(s)) : tendances peu fiables.")

    return ProfilEntreprise(
        ticker=ticker,
        nom=info.get("longName") or info.get("shortName") or ticker,
        pays=info.get("country"),
        devise=devise,
        cours=cours,
        nb_actions=float(nb_actions),
        secteur=info.get("sector"),
        industrie_yahoo=info.get("industry"),
        type_titre=info.get("quoteType", "EQUITY"),
        dette_financiere=dette * change,
        tresorerie=0.0 if math.isnan(tresorerie) else tresorerie * change,
        capitaux_propres=_bilan(["Stockholders Equity", "Common Stock Equity"], NAN),
        interets_minoritaires=_bilan(["Minority Interest"]),
        participations=_bilan(["Long Term Equity Investment", "Investmentsin Associatesat Cost"]),
        historique=historique,
        devise_comptes=devise_comptes,
        base_comptes=base_comptes,
        beta_yahoo=info.get("beta") or NAN,
        alertes=alertes,
        **resultat,
    )
