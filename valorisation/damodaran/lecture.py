"""Lecture des fichiers Excel Damodaran en tableaux propres.

Les fonctions `normaliser_*` travaillent sur la feuille brute (DataFrame sans en-tête) pour
pouvoir être testées sans fichier ; les fonctions `lire_*` ouvrent le fichier.
"""

import numbers
import re

import pandas as pd


def _texte(valeur):
    return "" if pd.isna(valeur) else re.sub(r"\s+", " ", str(valeur)).strip()


def _date_mise_a_jour(brut, jusqua):
    for i in range(min(jusqua, len(brut))):
        if _texte(brut.iat[i, 0]).lower().startswith("date"):
            valeur = brut.iat[i, 1]
            try:
                return pd.Timestamp(valeur).date()
            except (TypeError, ValueError):
                return None
    return None


def normaliser_moyennes_industrie(brut):
    """Feuille « Industry Averages » brute -> (DataFrame indexé par industrie, date de mise à jour).

    Les noms de colonnes en double (ex. EV/EBITDA « Only positive EBITDA firms » et « All firms »)
    sont préfixés par le libellé de groupe de la ligne au-dessus de l'en-tête.
    """
    lignes_entete = [i for i in range(min(40, len(brut))) if _texte(brut.iat[i, 0]).lower() == "industry name"]
    if not lignes_entete:
        raise ValueError("Ligne d'en-tête « Industry Name » introuvable")
    h = lignes_entete[0]

    groupes = brut.iloc[h - 1].map(_texte).replace("", None).ffill() if h > 0 else pd.Series([None] * brut.shape[1])
    noms = [_texte(v) for v in brut.iloc[h]]
    vus = {n: noms.count(n) for n in noms}
    colonnes = []
    for j, nom in enumerate(noms):
        if not nom:
            nom = f"col{j}"
        elif vus[nom] > 1 and j > 0 and groupes.iat[j]:
            nom = f"{groupes.iat[j]} | {nom}"
        colonnes.append(nom)

    donnees = brut.iloc[h + 1:].copy()
    donnees.columns = colonnes
    premiere_vide = donnees.iloc[:, 0].map(_texte).eq("")
    if premiere_vide.any():
        donnees = donnees.loc[: premiere_vide.idxmax()].iloc[:-1]
    donnees.index = donnees.iloc[:, 0].map(_texte)
    donnees.index.name = "industrie"
    donnees = donnees.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")
    return donnees, _date_mise_a_jour(brut, h)


def lire_moyennes_industrie(chemin):
    brut = pd.read_excel(chemin, sheet_name="Industry Averages", header=None)
    return normaliser_moyennes_industrie(brut)


def normaliser_primes_pays(brut):
    """Feuille « ERPs by country » -> (DataFrame indexé par pays, prime marché mature, date)."""
    prime_mature = None
    h = None
    for i in range(min(30, len(brut))):
        libelle = _texte(brut.iat[i, 0]).lower()
        if "mature equity market" in libelle:
            prime_mature = float(brut.iat[i, 4])
        if libelle == "country":
            h = i
            break
    if h is None:
        raise ValueError("Ligne d'en-tête « Country » introuvable dans les primes pays")

    donnees = brut.iloc[h + 1:, :6].copy()
    donnees.columns = ["pays", "region", "notation", "spread_defaut", "prime_actions_totale", "prime_pays"]
    donnees["pays"] = donnees["pays"].map(_texte)
    vide = donnees["pays"].eq("")
    if vide.any():
        donnees = donnees.loc[: vide.idxmax()].iloc[:-1]
    for c in ("spread_defaut", "prime_actions_totale", "prime_pays"):
        donnees[c] = pd.to_numeric(donnees[c], errors="coerce")
    # Le tableau principal s'arrête à la première ligne sans prime (début du tableau annexe
    # des marchés frontières, notés par PRS et non par Moody's, dont les colonnes diffèrent).
    sans_prime = donnees["prime_actions_totale"].isna()
    if sans_prime.any():
        donnees = donnees.loc[: sans_prime.idxmax()].iloc[:-1]
    donnees = donnees.set_index("pays")
    donnees["region"] = donnees["region"].map(_texte)
    return donnees, prime_mature, _date_mise_a_jour(brut, h)


def lire_primes_pays(chemin):
    brut = pd.read_excel(chemin, sheet_name="ERPs by country", header=None)
    return normaliser_primes_pays(brut)


def normaliser_grilles_notation(brut):
    """Feuille de notation synthétique -> {"grande": DataFrame, "petite": DataFrame}.

    Chaque grille a les colonnes `couverture_min`, `couverture_max`, `notation`, `spread`.
    La première grille du fichier vise les grandes entreprises, la seconde les plus petites.
    """
    blocs, courant = [], []
    for i in range(len(brut)):
        a, b, notation, spread = brut.iat[i, 0], brut.iat[i, 1], brut.iat[i, 2], brut.iat[i, 3]
        numerique = all(isinstance(v, numbers.Real) and not pd.isna(v) for v in (a, b, spread))
        if numerique and isinstance(notation, str):
            courant.append((float(a), float(b), notation.strip(), float(spread)))
        elif courant:
            blocs.append(courant)
            courant = []
    if courant:
        blocs.append(courant)
    if len(blocs) < 2:
        raise ValueError("Grilles de notation introuvables")
    colonnes = ["couverture_min", "couverture_max", "notation", "spread"]
    return {"grande": pd.DataFrame(blocs[0], columns=colonnes),
            "petite": pd.DataFrame(blocs[1], columns=colonnes)}


def lire_grilles_notation(chemin):
    brut = pd.read_excel(chemin, sheet_name=0, header=None)
    return normaliser_grilles_notation(brut)


def normaliser_is_pays(brut):
    """Taux d'IS marginal par pays (en tenant compte de l'impôt minimum mondial s'il est donné)."""
    h = next(i for i in range(min(20, len(brut))) if _texte(brut.iat[i, 0]).lower() == "country")
    donnees = brut.iloc[h + 1:].copy()
    pays = donnees.iloc[:, 0].map(_texte)
    taux = pd.to_numeric(donnees.iloc[:, 1], errors="coerce")
    if donnees.shape[1] > 2:
        taux = pd.to_numeric(donnees.iloc[:, 2], errors="coerce").fillna(taux)
    serie = pd.Series(taux.values, index=pays.values, name="taux_is")
    serie = serie[serie.index != ""].dropna()
    return serie[~serie.index.duplicated()], _date_mise_a_jour(brut, h)


def lire_is_pays(chemin):
    brut = pd.read_excel(chemin, sheet_name=0, header=None)
    return normaliser_is_pays(brut)
