"""Téléchargement et mise en cache des fichiers de la base Damodaran.

Les fichiers ne sont jamais versionnés : ils sont téléchargés à la demande depuis
pages.stern.nyu.edu, conservés `DUREE_CACHE_DAMODARAN_JOURS` jours, et le cache périmé
sert de secours si le site ne répond pas.
"""

import time
import urllib.request
from pathlib import Path

from .. import config

# Région Damodaran -> suffixe des fichiers. Les fichiers US n'ont pas de suffixe et
# certains portent un nom différent (betas.xls, pedata.xls…).
REGIONS = ("US", "Europe", "Japan", "Rest", "emerg", "China", "India", "Global")

# Jeu de données -> (nom du fichier US, modèle de nom pour les autres régions)
JEUX_PAR_INDUSTRIE = {
    "beta": ("betas.xls", "beta{r}.xls"),
    "ev_ebitda": ("vebitda.xls", "vebitda{r}.xls"),
    "per": ("pedata.xls", "pe{r}.xls"),
    "pbv": ("pbvdata.xls", "pbv{r}.xls"),
    "ventes": ("psdata.xls", "ps{r}.xls"),
    "marges": ("margin.xls", "margin{r}.xls"),
    "capex": ("capex.xls", "capex{r}.xls"),
    "wacc": ("wacc.xls", "wacc{r}.xls"),
    "croissance": ("fundgrEB.xls", "fundgrEB{r}.xls"),
}

FICHIERS_UNIQUES = {
    "primes_pays": config.URL_DAMODARAN_DATASETS + "ctryprem.xlsx",
    "is_pays": config.URL_DAMODARAN_DATASETS + "countrytaxrates.xls",
    "notations": config.URL_DAMODARAN_NOTATIONS,
}

# Signatures binaires : .xls (OLE2) et .xlsx (zip). Évite de mettre en cache une page
# d'erreur HTML renvoyée avec un code 200.
_SIGNATURES = (b"\xd0\xcf\x11\xe0", b"PK\x03\x04")


def nom_fichier(jeu, region):
    if region not in REGIONS:
        raise ValueError(f"Région Damodaran inconnue : {region!r} (attendu : {', '.join(REGIONS)})")
    nom_us, modele = JEUX_PAR_INDUSTRIE[jeu]
    return nom_us if region == "US" else modele.format(r=region)


def url_jeu(jeu, region=None):
    if jeu in FICHIERS_UNIQUES:
        return FICHIERS_UNIQUES[jeu]
    return config.URL_DAMODARAN_DATASETS + nom_fichier(jeu, region)


def _telecharger(url, destination):
    requete = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (valorisation-entreprise)"})
    with urllib.request.urlopen(requete, timeout=60) as reponse:
        contenu = reponse.read()
    if not contenu.startswith(_SIGNATURES):
        raise ValueError(f"Réponse inattendue pour {url} (pas un fichier Excel)")
    temporaire = destination.with_suffix(destination.suffix + ".tmp")
    temporaire.write_bytes(contenu)
    temporaire.replace(destination)


def chemin_local(jeu, region=None, dossier=None, forcer=False):
    """Renvoie le chemin du fichier en cache, en le (re)téléchargeant si nécessaire."""
    dossier = Path(dossier or config.DOSSIER_CACHE) / "damodaran"
    dossier.mkdir(parents=True, exist_ok=True)
    url = url_jeu(jeu, region)
    destination = dossier / url.rsplit("/", 1)[-1]

    age_max = config.DUREE_CACHE_DAMODARAN_JOURS * 86400
    frais = destination.exists() and (time.time() - destination.stat().st_mtime) < age_max
    if frais and not forcer:
        return destination
    try:
        _telecharger(url, destination)
    except Exception as erreur:
        if destination.exists():
            print(f"[Damodaran] Échec du téléchargement de {url} ({erreur}) : cache périmé utilisé.")
            return destination
        raise RuntimeError(f"Impossible de télécharger {url} et aucun cache local : {erreur}") from erreur
    return destination
