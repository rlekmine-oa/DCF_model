"""Formatage des nombres à la française (virgule décimale, espace fine pour les milliers)."""

import math

ESPACE_FINE = "\u202f"


def vide(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def nombre(x, decimales=0):
    if vide(x):
        return "n.d."
    texte = f"{x:,.{decimales}f}".replace(",", ESPACE_FINE).replace(".", ",")
    return texte.replace("-", "−")


def pct(x, decimales=1, signe=False):
    if vide(x):
        return "n.d."
    texte = f"{x * 100:{'+' if signe else ''}.{decimales}f}".replace(".", ",").replace("-", "−")
    return texte + ESPACE_FINE + "%"


def millions(x):
    return "n.d." if vide(x) else nombre(x / 1e6)


def multiple(x):
    return "n.d." if vide(x) else nombre(x, 1) + "x"
