"""Résolution d'une saisie libre (« SU.PA », « Crédit Agricole », « airbus ») en ticker Yahoo."""

import re
import unicodedata

_SEPARATEURS = re.compile(r"[,;\n]+")

# Marchés de gré à gré américains (ADR non cotés) : jamais retenus par la recherche.
_PLACES_HORS_COTE = {"PNK", "OQB", "OQX", "OID", "OBB", "OEM", "OGM"}
# Places secondaires où se négocient des titres étrangers : écartées quand on cherche la place d'origine.
_PLACES_SECONDAIRES = {"FRA", "STU", "HAN", "HAM", "MUN", "DUS", "BER", "VIE", "DXE", "IOB", "MEX", "NEO", "SAO"}


def decouper_saisie(texte):
    """« SU.PA, MC.PA AAPL ; Schneider Electric » -> ["SU.PA", "MC.PA", "AAPL", "Schneider Electric"].

    Les virgules, points-virgules et retours à la ligne séparent toujours ; les espaces ne séparent
    que des éléments qui ressemblent tous à des tickers (pour garder « Schneider Electric » entier).
    """
    elements = []
    for morceau in _SEPARATEURS.split(texte or ""):
        morceau = morceau.strip()
        if not morceau:
            continue
        mots = morceau.split()
        if len(mots) > 1 and all(ressemble_a_un_ticker(m) for m in mots):
            elements.extend(mots)
        else:
            elements.append(" ".join(mots))
    return list(dict.fromkeys(elements))


def ressemble_a_un_ticker(texte):
    """Un seul mot, avec un suffixe de place (.PA, ^…) ou entièrement en majuscules (AAPL, MSFT)."""
    texte = texte.strip()
    if not texte or " " in texte:
        return False
    return any(c in texte for c in ".^=") or (texte.isupper() and len(texte) <= 6)


def sans_accents(texte):
    """La recherche Yahoo ne renvoie rien pour « Crédit Agricole » mais trouve « Credit Agricole »."""
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()


def candidats(resultats):
    """Actions retenues parmi les résultats de recherche Yahoo, dans l'ordre de pertinence."""
    retenus = []
    for r in resultats:
        if (r.get("quoteType") or "").upper() != "EQUITY" or not r.get("symbol"):
            continue
        nom = f"{r.get('shortname') or ''} {r.get('longname') or ''}"
        if r.get("exchange") in _PLACES_HORS_COTE or re.search(r"\bCDR\b", nom):
            continue
        retenus.append(r)
    return retenus


def choisir_cotation(retenus, devises):
    """Préfère la cotation d'origine : si la première action est cotée dans une autre devise que celle
    de ses comptes (ADR américain d'une société européenne, par exemple), retient la première autre
    cotation dans la devise des comptes. `devises(symbole)` -> (devise de cotation, devise des comptes)."""
    premier = retenus[0]
    cotation, comptes = devises(premier["symbol"])
    if not comptes or cotation == comptes:
        return premier
    for r in retenus[1:]:
        if r.get("exchange") in _PLACES_SECONDAIRES:
            continue
        if devises(r["symbol"])[0] == comptes:
            return r
    return premier


def _devises_yahoo(symbole):
    import yfinance as yf

    from .marche import normaliser_devise
    try:
        info = yf.Ticker(symbole).info or {}
    except Exception:
        return None, None
    cotation = normaliser_devise(info.get("currency"))[0] if info.get("currency") else None
    comptes = normaliser_devise(info.get("financialCurrency"))[0] if info.get("financialCurrency") else None
    return cotation, comptes


def chercher_action(texte):
    """(ticker, nom) de l'action la plus pertinente pour une saisie libre, via la recherche Yahoo."""
    import yfinance as yf
    requetes = list(dict.fromkeys([sans_accents(texte).strip(), texte.strip()]))
    for requete in requetes:
        retenus = candidats(yf.Search(requete, max_results=10).quotes)
        if retenus:
            choix = choisir_cotation(retenus, _devises_yahoo)
            return choix["symbol"], choix.get("longname") or choix.get("shortname") or choix["symbol"]
    raise ValueError(f"Aucune action trouvée pour « {texte} »")
