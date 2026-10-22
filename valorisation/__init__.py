"""Moteur de valorisation d'entreprise adossé aux données d'Aswath Damodaran (NYU Stern)."""

from .api import NonValorisable, evaluer_profil, evaluer_ticker

__all__ = ["evaluer_ticker", "evaluer_profil", "NonValorisable"]
__version__ = "0.1.0"
