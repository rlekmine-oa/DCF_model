"""Ligne de commande : python -m valorisation SU.PA MC.PA AAPL [options]."""

import argparse
import json
import math
import sys
from pathlib import Path

from . import config
from .api import NonValorisable, evaluer_ticker
from .damodaran.telechargement import REGIONS
from .rapport import ecrire_rapport


def _analyser(arguments):
    parseur = argparse.ArgumentParser(
        prog="python -m valorisation",
        description="Valorise des sociétés cotées (DCF + multiples) avec les données de Damodaran.")
    parseur.add_argument("tickers", nargs="+", help="tickers Yahoo Finance (ex. SU.PA, MC.PA, AAPL)")
    parseur.add_argument("--sortie", default="rapports", help="dossier des notes HTML (défaut : rapports)")
    parseur.add_argument("--json", metavar="FICHIER", help="écrit aussi le résumé de toutes les valorisations en JSON")
    parseur.add_argument("--sans-rapport", action="store_true", help="n'écrit pas de note HTML")
    parseur.add_argument("--industrie", help="industrie Damodaran imposée (ex. \"Machinery\")")
    parseur.add_argument("--region", choices=REGIONS, help="région Damodaran imposée")
    parseur.add_argument("--seuil", type=float, default=config.SEUIL_VERDICT,
                         help=f"écart minimal pour conclure à une sous/surévaluation (défaut : {config.SEUIL_VERDICT})")
    parseur.add_argument("--croissance", type=float, help="croissance du CA imposée pour les années 1-5 (ex. 0.06)")
    parseur.add_argument("--marge-cible", type=float, help="marge opérationnelle cible imposée (ex. 0.18)")
    return parseur.parse_args(arguments)


def _format(x, motif="{:,.2f}"):
    return "n.d." if x is None or (isinstance(x, float) and math.isnan(x)) else motif.format(x)


def main(arguments=None):
    args = _analyser(arguments if arguments is not None else sys.argv[1:])
    surcharges = {}
    if args.croissance is not None:
        surcharges["croissance_initiale"] = args.croissance
    if args.marge_cible is not None:
        surcharges["marge_cible"] = args.marge_cible

    sortie = Path(args.sortie)
    if not args.sans_rapport:
        sortie.mkdir(parents=True, exist_ok=True)

    resumes, echecs = [], 0
    print(f"{'Ticker':<10} {'Cours':>10} {'Valeur':>10} {'Fourchette':>21} {'Potentiel':>10}  Verdict")
    for ticker in args.tickers:
        try:
            r = evaluer_ticker(ticker, industrie=args.industrie, region=args.region,
                               surcharges_dcf=surcharges or None, seuil_verdict=args.seuil)
        except NonValorisable as erreur:
            print(f"{ticker:<10} ignoré : {erreur}")
            continue
        except Exception as erreur:  # un titre en échec ne bloque pas les suivants
            echecs += 1
            print(f"{ticker:<10} ERREUR : {erreur}")
            continue
        fourchette = f"{_format(r.bas)} – {_format(r.haut)}"
        print(f"{ticker:<10} {_format(r.cours):>10} {_format(r.valeur_centrale):>10} {fourchette:>21} "
              f"{_format(r.ecart, '{:+.1%}'):>10}  {r.verdict}")
        resume = r.resume()
        if not args.sans_rapport:
            chemin = sortie / f"valorisation_{ticker.replace('.', '_').replace('^', '')}.html"
            ecrire_rapport(r, chemin)
            resume["rapport"] = str(chemin)
        resumes.append(resume)

    if args.json:
        Path(args.json).write_text(json.dumps(resumes, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Résumé écrit dans {args.json}")
    if not args.sans_rapport and resumes:
        print(f"Notes HTML écrites dans {sortie.resolve()}")
    return 1 if echecs else 0
