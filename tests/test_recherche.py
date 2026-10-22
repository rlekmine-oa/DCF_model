"""Saisie libre de l'interface : découpage, accents, choix de la cotation d'origine (sans réseau)."""

from valorisation.recherche import candidats, choisir_cotation, decouper_saisie, ressemble_a_un_ticker, sans_accents


def test_decoupage_garde_les_noms_composes():
    assert decouper_saisie("SU.PA, MC.PA AAPL ; Schneider Electric\nairbus, SU.PA") == \
        ["SU.PA", "MC.PA", "AAPL", "Schneider Electric", "airbus"]
    assert decouper_saisie("  ,, ") == []


def test_reconnaissance_des_tickers():
    assert ressemble_a_un_ticker("SU.PA") and ressemble_a_un_ticker("AAPL") and ressemble_a_un_ticker("^FCHI")
    assert not ressemble_a_un_ticker("airbus") and not ressemble_a_un_ticker("Credit Agricole")


def test_accents_retires_pour_la_recherche():
    assert sans_accents("Crédit Agricole") == "Credit Agricole"
    assert sans_accents("Hermès") == "Hermes"


def test_candidats_ecartent_etf_hors_cote_et_cdr():
    resultats = [
        {"symbol": "XAAPL=F", "quoteType": "FUTURE", "exchange": "CME"},
        {"symbol": "SBGSY", "quoteType": "EQUITY", "exchange": "PNK"},
        {"symbol": "AAPL.TO", "quoteType": "EQUITY", "exchange": "TOR", "shortname": "APPLE CDR (CAD HEDGED)"},
        {"symbol": "ESE.PA", "quoteType": "ETF", "exchange": "PAR"},
        {"symbol": "AAPL", "quoteType": "EQUITY", "exchange": "NMS"},
    ]
    assert [r["symbol"] for r in candidats(resultats)] == ["AAPL"]


def test_cotation_d_origine_preferee_a_l_adr():
    retenus = [{"symbol": "SNY", "exchange": "NMS"}, {"symbol": "SNW.F", "exchange": "FRA"},
               {"symbol": "SAN.PA", "exchange": "PAR"}]
    devises = {"SNY": ("USD", "EUR"), "SNW.F": ("EUR", "EUR"), "SAN.PA": ("EUR", "EUR")}
    assert choisir_cotation(retenus, devises.get)["symbol"] == "SAN.PA"   # place secondaire (FRA) sautée
    # Société américaine : la première cotation est déjà dans la devise des comptes.
    assert choisir_cotation([{"symbol": "AAPL", "exchange": "NMS"}], lambda s: ("USD", "USD"))["symbol"] == "AAPL"
