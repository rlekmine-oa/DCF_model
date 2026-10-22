"""Données de marché : taux sans risque par devise et taux de change.

- EUR : taux à 10 ans de la courbe AAA de la zone euro (API de la BCE) ;
- USD : rendement du Trésor américain à 10 ans (^TNX sur Yahoo Finance) ;
- autres devises : valeurs de secours de `config.TAUX_SANS_RISQUE_SECOURS`.
Les taux sont mis en cache `DUREE_CACHE_TAUX_HEURES` heures.
"""

import csv
import io
import json
import time
import urllib.request
from pathlib import Path

from . import config

URL_BCE_10A = ("https://data-api.ecb.europa.eu/service/data/YC/"
               "B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y?lastNObservations=1&format=csvdata")

# Devises cotées en centièmes sur Yahoo (pence, cents sud-africains, agorot).
SOUS_UNITES = {"GBp": ("GBP", 100), "GBX": ("GBP", 100), "ZAc": ("ZAR", 100), "ILA": ("ILS", 100)}


def normaliser_devise(devise):
    """('GBp') -> ('GBP', 100) : devise principale et diviseur à appliquer aux prix."""
    if devise in SOUS_UNITES:
        return SOUS_UNITES[devise]
    return (devise or "EUR").upper(), 1


def _chemin_cache():
    return Path(config.DOSSIER_CACHE) / "taux_sans_risque.json"


def _lire_cache():
    try:
        return json.loads(_chemin_cache().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _ecrire_cache(cache):
    chemin = _chemin_cache()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _taux_bce():
    with urllib.request.urlopen(URL_BCE_10A, timeout=30) as reponse:
        lignes = list(csv.DictReader(io.StringIO(reponse.read().decode("utf-8"))))
    return float(lignes[-1]["OBS_VALUE"]) / 100, f"BCE, courbe AAA zone euro 10 ans ({lignes[-1]['TIME_PERIOD']})"


def _taux_tresor_us():
    import yfinance as yf
    historique = yf.Ticker("^TNX").history(period="10d")["Close"].dropna()
    return float(historique.iloc[-1]) / 100, f"Trésor US 10 ans ({historique.index[-1].date()})"


_SOURCES = {"EUR": _taux_bce, "USD": _taux_tresor_us}


def taux_sans_risque(devise):
    """(taux, source) pour une devise. Ne lève jamais : retombe sur la valeur de secours."""
    devise = normaliser_devise(devise)[0]
    cache = _lire_cache()
    entree = cache.get(devise)
    if entree and time.time() - entree["horodatage"] < config.DUREE_CACHE_TAUX_HEURES * 3600:
        return entree["taux"], entree["source"]

    if devise in _SOURCES:
        try:
            taux, source = _SOURCES[devise]()
            cache[devise] = {"taux": taux, "source": source, "horodatage": time.time()}
            _ecrire_cache(cache)
            return taux, source
        except Exception as erreur:
            if entree:
                return entree["taux"], entree["source"] + " (cache périmé)"
            print(f"[Marché] Taux sans risque {devise} indisponible ({erreur}) : valeur de secours.")

    secours = config.TAUX_SANS_RISQUE_SECOURS.get(devise, config.TAUX_SANS_RISQUE_SECOURS["USD"])
    return secours, f"valeur de secours ({devise}, config.py)"


def taux_change(de, vers):
    """Nombre d'unités de `vers` pour une unité de `de` (dernier cours Yahoo)."""
    de, vers = normaliser_devise(de)[0], normaliser_devise(vers)[0]
    if de == vers:
        return 1.0
    import yfinance as yf
    historique = yf.Ticker(f"{de}{vers}=X").history(period="10d")["Close"].dropna()
    if historique.empty:
        raise RuntimeError(f"Taux de change {de}/{vers} indisponible")
    return float(historique.iloc[-1])
