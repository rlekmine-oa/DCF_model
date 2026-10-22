"""Tables de correspondance (YAML) : industries Yahoo -> Damodaran, profils sectoriels -> méthodes."""

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import yaml

DOSSIER = Path(__file__).resolve().parent


def _cle(texte):
    texte = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", texte.lower())


@lru_cache(maxsize=None)
def table_industries():
    with open(DOSSIER / "industries.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=None)
def regles_methodes():
    with open(DOSSIER / "methodes.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def industrie_damodaran(industrie_yahoo):
    """Industrie Damodaran correspondant à une industrie Yahoo, ou None si elle n'est pas répertoriée."""
    if not industrie_yahoo:
        return None
    index = {_cle(k): v for k, v in table_industries().items()}
    return index.get(_cle(industrie_yahoo))


def profil_sectoriel(industrie):
    """Nom du profil (standard, cyclique, financiere, actifs) d'une industrie Damodaran."""
    for profil, industries in regles_methodes()["industries"].items():
        if industrie in industries:
            return profil
    return "standard"
