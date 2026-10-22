# Company Valuation Engine

**Sector-aware intrinsic valuation of listed companies: the engine identifies the business, picks the
valuation method that fits its sector (DCF + EV/EBITDA, multiples, P/BV for banks, NAV proxy for real
estate), calibrates every assumption on Aswath Damodaran's industry datasets (NYU Stern) and tells whether
the share price is above or below a defensible value range.**

Built as a stand-alone Python package with a one-function API, so it can be plugged into a portfolio
dashboard to flag over- and under-valued holdings.

🇫🇷 [Version française](README.fr.md) · 📐 [Methodology note (FR)](docs/methodologie.md) · The interface is in French.

---

## What it does

```
ticker ──► company profile ──► Damodaran industry + region ──► method selection ──► WACC ──► DCF / multiples ──► value range + verdict
          (Yahoo Finance, TTM)  (145 Yahoo → 94 Damodaran)      (sector rules)      (bottom-up)                     + one-page HTML note
```

| Step | What happens | Techniques |
|---|---|---|
| **Identification** | Trailing-twelve-month P&L, latest balance sheet, 4–5 years of history; FX conversion when accounts and quote differ (incl. pence quotes) | Yahoo Finance, ECB and US Treasury rates |
| **Industry mapping** | Every Yahoo/Morningstar industry mapped to one of Damodaran's 94 industries; country → Damodaran region (Europe, US, Japan, emerging…) | YAML tables, validated by tests |
| **Method selection** | *Standard* → DCF 60 % + EV/EBITDA 40 %; *cyclical* → same on **normalised margins**; *financial* → P/BV + P/E; *real estate* → P/BV (NAV proxy) + EV/EBITDA. Automatic switches: negative EBITDA → EV/Sales; fee-based financials (payment networks, asset managers) → standard | Rule engine in YAML |
| **Cost of capital** | Industry unlevered beta (cash-corrected) relevered at the company's market D/E; mature-market ERP + country risk premium; **synthetic rating** from interest coverage → cost of debt; marginal tax rate by country | Damodaran `beta`, `ctryprem`, `ratings`, `countrytaxrates` |
| **DCF (FCFF)** | 10-year projection: growth fades to terminal, margin converges to a target, reinvestment driven by sales-to-capital, terminal value with reinvestment = g / ROIC | Damodaran `margin`, `capex`, `fundgrEB`, `pbv` |
| **Multiples** | Aggregate industry EV/EBITDA, EV/Sales, P/E, P/BV; regional multiple as central case, global multiple as the other bound | Damodaran `vebitda`, `ps`, `pe`, `pbv` |
| **Output** | Weighted value range, verdict (±15 % band), **reverse DCF** (growth priced in by the market), WACC × g sensitivity grid, football-field chart, data-quality warnings | Plotly, self-contained HTML |

## Design choices worth noting

- **Every assumption is traceable.** Each DCF input comes with a sentence stating its origin (company history,
  Damodaran industry average, or user override), and that sentence is printed in the report.
- **Reverse DCF next to the verdict.** A sector multiple cannot see company-specific risk (disruption,
  litigation). The implied growth rate shows what the market is betting on, which often says more than the
  verdict itself.
- **Noisy inputs are bounded, not trusted blindly.** Damodaran's fundamental growth ranges from −200 % to
  +140 % across industries: it is clipped before use. Terminal ROIC is bounded between WACC (no value
  creation) and WACC + 5 points.
- **Right tool for the balance sheet.** Banks are not valued on EV/EBITDA; but a payment network classified
  as "Credit Services" (Mastercard) is not valued on P/BV either: fee-based financials are detected and
  re-routed.
- **Checked against closed-form results.** With zero growth the DCF must equal the NOPAT perpetuity; with
  constant growth and a consistent ROIC it must equal Gordon's formula. Both are unit-tested (44 offline
  tests on synthetic data, no network).
- **Data is downloaded, never committed.** Damodaran files are fetched on demand, cached for 30 days, and a
  stale cache is used if the site is down.

## Quick start

```bash
pip install -r requirements.txt

python -m valorisation SU.PA MC.PA BNP.PA AAPL          # one HTML note per company in rapports/
python -m valorisation SU.PA --croissance 0.06          # override years 1-5 revenue growth
python -m valorisation RIO.L --json resume.json         # machine-readable summary
python -m pytest                                        # offline tests
```

```
Ticker          Cours     Valeur            Fourchette  Potentiel  Verdict
SU.PA          240.25     153.57       146.62 – 174.85     -36.1%  Surévalué
...
```

### API (dashboard integration)

```python
from valorisation import evaluer_ticker, NonValorisable

r = evaluer_ticker("SU.PA")
r.valeur_centrale, r.bas, r.haut      # value per share and range, quote currency
r.ecart, r.verdict                    # upside/downside vs price, "Sous-évalué" / "Correctement valorisé" / "Surévalué"
r.resume()                            # flat JSON-serialisable dict

from valorisation.rapport import ecrire_rapport
ecrire_rapport(r, "note.html")
```

ETFs, funds and instruments without published accounts raise `NonValorisable`, so a portfolio loop can skip
them.

## Architecture

| Module | Role |
|---|---|
| `damodaran/` | Download and cache (`telechargement`), generic Excel parser (`lecture`), unified access to industry parameters, country premiums, tax rates and rating grids (`referentiel`) |
| `correspondances/` | `industries.yaml` (Yahoo → Damodaran), `methodes.yaml` (sector profiles and weights) |
| `entreprise.py` | `ProfilEntreprise`: P&L, balance sheet, history, Yahoo loader |
| `marche.py` | Risk-free rates (ECB, US Treasury) and FX |
| `wacc.py` | Bottom-up cost of capital |
| `methodes/` | `dcf.py` (projection, sensitivity, reverse DCF), `multiples.py`, equity bridge |
| `selection.py` · `synthese.py` | Method selection, weighting, verdict |
| `rapport.py` · `cli.py` · `api.py` | One-page HTML note, command line, public API |

## Roadmap

- **Phase 2**: justified P/BV ((ROE − g)/(COE − g)) and excess-return model for banks; detailed NAV for
  holdings and real estate (sum of the parts, holding discount); private companies entered from an Excel
  template (PE use case); Excel export of the model; country risk premium weighted by revenue geography.
- **Phase 3**: integration in the [portfolio dashboard](https://github.com/rlekmine-oa/Financial-Dashboard)
  (intrinsic value column per holding); quick LBO module (IRR, MOIC).

## Limitations

See the [methodology note](docs/methodologie.md#7-limites-connues). In short: industry averages miss
company-specific risk, Damodaran multiples are refreshed each January, the country premium is that of the
country of incorporation, and Yahoo Finance data is free but unofficial.

---

*Personal project. Data: Aswath Damodaran (NYU Stern), Yahoo Finance, ECB. Nothing here is investment advice.*
Author: Rayan LEKMINE · License: [MIT](LICENSE)
