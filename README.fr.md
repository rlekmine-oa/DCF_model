# Moteur de valorisation d'entreprise

**Valorisation intrinsèque de sociétés cotées, adaptée au secteur. Le moteur identifie l'activité, choisit
la méthode qui lui correspond (DCF + EV/EBITDA, multiples, P/BV pour les banques, approximation de l'ANR pour
les foncières) et cale chaque hypothèse sur les données sectorielles d'Aswath Damodaran (NYU Stern). Il
indique ensuite si le cours se situe au-dessus ou en dessous d'une fourchette de valeur défendable.**

Le package Python est autonome et s'appelle en une fonction. Il peut ainsi s'intégrer à un dashboard de
portefeuille pour signaler les positions sur- ou sous-évaluées.

🇬🇧 [English version](README.md) · 📐 [Note méthodologique](docs/methodologie.md)

---

## Fonctionnement

```
ticker ──► profil ──► industrie et région Damodaran ──► choix des méthodes ──► WACC ──► DCF / multiples ──► fourchette + verdict
          (Yahoo, 12 mois glissants)  (145 Yahoo → 94 Damodaran)  (règles sectorielles)  (bottom-up)              + note HTML d'une page
```

| Étape | Contenu |
|---|---|
| **Identification** | Compte de résultat sur 12 mois glissants, dernier bilan, 4 à 5 ans d'historique, conversion de devise (cotations en pence comprises). |
| **Correspondance sectorielle** | Chaque industrie Yahoo/Morningstar est associée à l'une des 94 industries Damodaran ; chaque pays à une région Damodaran. |
| **Choix de la méthode** | *Standard* : DCF 60 % + EV/EBITDA 40 %. *Cyclique* : idem sur **marges normalisées**. *Financière* : P/BV + P/E. *Foncière* : P/BV (approximation de l'ANR) + EV/EBITDA. Bascules automatiques : EBITDA négatif → EV/Ventes ; société financière à commissions (réseau de paiement, gestion d'actifs) → standard. |
| **Coût du capital** | Bêta désendetté de l'industrie réendetté au D/E de marché, prime marché mature + prime pays, **notation synthétique** d'après la couverture des intérêts, taux d'IS marginal du pays. |
| **DCF (FCFF)** | 10 ans : croissance décroissante vers le taux terminal, marge convergeant vers une cible, réinvestissement piloté par le ratio ventes/capital investi, valeur terminale avec réinvestissement = g / ROIC. |
| **Multiples** | EV/EBITDA, EV/Ventes, P/E, P/BV agrégés de l'industrie ; multiple régional en valeur centrale, multiple mondial comme autre borne. |
| **Sorties** | Fourchette pondérée, verdict (seuil ±15 %), **DCF inversé** (croissance intégrée dans le cours), matrice de sensibilité WACC × g, graphique en *football field*, alertes de qualité des données. |

## Démarrage rapide

```bash
pip install -r requirements.txt

python -m valorisation SU.PA MC.PA BNP.PA AAPL          # une note HTML par société dans rapports/
python -m valorisation SU.PA --croissance 0.06          # croissance des années 1-5 imposée
python -m valorisation RIO.L --json resume.json         # résumé exploitable par programme
python -m pytest                                        # tests hors ligne
```

```python
from valorisation import evaluer_ticker

r = evaluer_ticker("SU.PA")
print(r.verdict, r.valeur_centrale, r.bas, r.haut, r.ecart)
```

Les ETF, fonds et titres sans comptes publiés lèvent `NonValorisable`, qu'une boucle sur un portefeuille peut
simplement ignorer.

## Feuille de route

- **Phase 2** : P/BV justifié et modèle de rentabilité excédentaire pour les banques ; ANR détaillé pour
  holdings et foncières (somme des parties, décote de holding) ; saisie de sociétés non cotées depuis un modèle
  Excel (usage PE) ; export Excel du modèle ; prime pays pondérée par zone de chiffre d'affaires.
- **Phase 3** : intégration au [dashboard de portefeuille](https://github.com/rlekmine-oa/Financial-Dashboard)
  (valeur intrinsèque par position) ; module LBO simplifié (TRI, multiple).

---

*Projet personnel. Données : Aswath Damodaran (NYU Stern), Yahoo Finance, BCE. Ceci n'est pas un conseil en investissement.*
Auteur : Rayan LEKMINE · Licence : [MIT](LICENSE)
