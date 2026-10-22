# Note méthodologique

Cette note justifie chaque choix du moteur. Tous les paramètres chiffrés sont dans
[`valorisation/config.py`](../valorisation/config.py), et les règles sectorielles dans
[`valorisation/correspondances/`](../valorisation/correspondances).

## 1. Identification de l'entreprise

| Étape | Source | Détail |
|---|---|---|
| Comptes | Yahoo Finance | Année de base : **12 mois glissants** quand ils existent (sinon dernier exercice) ; historique annuel (4-5 ans) pour les tendances ; bilan le plus récent (semestriel ou trimestriel). |
| Devise | Yahoo Finance | Les montants sont exprimés dans la devise de cotation. Des comptes publiés dans une autre devise sont convertis au dernier cours de change. Les cotations en centièmes (pence, `GBp`) sont ramenées à l'unité. |
| Industrie | `industries.yaml` | 145 industries Yahoo (classification Morningstar), chacune associée à l'une des 94 industries Damodaran. Une industrie inconnue reçoit les moyennes du marché, avec une alerte. |
| Région | Fichier des primes pays | Europe de l'Ouest → fichiers « Europe » ; États-Unis → « US » ; Japon, Chine, Inde → leur fichier ; Canada, Australie, Nouvelle-Zélande → « Rest » ; autres pays → « emerg ». |

Les ETF, fonds, indices et titres sans comptes publiés (ETC) sont écartés (`NonValorisable`).

## 2. Choix de la méthode

| Profil | Industries Damodaran | Méthodes (poids) | Raison |
|---|---|---|---|
| Standard | toutes les autres | DCF 60 % + EV/EBITDA 40 % | Flux prévisibles : valeur intrinsèque, confrontée au prix de marché d'actifs comparables. |
| Cyclique | Mines, acier, pétrole, chimie de base, automobile, transport aérien, construction… | DCF 50 % + EV/EBITDA 50 %, **sur des marges normalisées** | Une année isolée reflète la position dans le cycle : la marge de départ du DCF et l'EBITDA du multiple sont des moyennes historiques. |
| Financière | Banques, assurances, gestion d'actifs, courtage | P/BV 50 % + P/E 50 % | La dette est une matière première et non un financement : EV, EBITDA et FCFF n'ont pas de sens. |
| Actifs | Foncières (REIT), promotion, immobilier diversifié | P/BV 50 % + EV/EBITDA 50 % | En IFRS, les immeubles de placement sont à la juste valeur : le P/BV approche l'ANR. |

Ajustements automatiques :

- **EBITDA négatif** : EV/EBITDA est remplacé par EV/Ventes, et la marge du DCF converge entièrement vers celle de l'industrie.
- **Résultat net négatif** (profil financier) : le P/E est écarté au profit du P/BV.
- **Société financière à commissions** (réseau de paiement, gestionnaire d'actifs) : dans les industries Damodaran qui mélangent prêteurs et sociétés à commissions, une entreprise qui publie un EBIT positif avec des frais financiers inférieurs à 10 % du CA est valorisée comme une entreprise standard. Sans cela, Mastercard serait valorisée au P/BV, alors que ses fonds propres sont quasi nuls après des années de rachats d'actions.
- Une méthode inapplicable (agrégat négatif, donnée manquante) est retirée, et son poids est **redistribué** aux autres.

## 3. Coût du capital (approche « bottom-up »)

```
bêta réendetté      = bêta désendetté de l'industrie × (1 + (1 − t) × D/E)
coût des fonds prop. = rf + bêta × (prime marché mature + prime pays)
coût de la dette     = rf + spread de la notation synthétique + spread de défaut du pays
WACC                 = E/(D+E) × ke + D/(D+E) × kd × (1 − t)
```

- **Bêta** : le bêta désendetté de l'industrie, corrigé de la trésorerie (Damodaran, régressions sur 2 et 5 ans), est plus stable que le bêta de régression de l'entreprise seule. Il est réendetté au D/E de marché de l'entreprise, dette locative comprise.
- **Taux sans risque** : courbe AAA de la zone euro à 10 ans (API de la BCE) pour l'euro ; Trésor américain à 10 ans pour le dollar ; valeurs de secours paramétrables pour les autres devises.
- **Prime de risque** : prime implicite d'un marché mature (S&P 500), plus la prime du pays d'immatriculation (notation Moody's × volatilité relative actions/obligations).
- **Coût de la dette** : notation synthétique tirée de la couverture des intérêts (EBIT / frais financiers), avec une grille différente pour les entreprises de plus ou moins de 5 Md$ de capitalisation.
- **Taux d'IS** : taux marginal du pays (impôt minimum mondial de 15 % pris en compte).

## 4. DCF (FCFF)

Projection sur 10 ans :

| Élément | Règle |
|---|---|
| Croissance du CA, années 1-5 | Moyenne de la croissance historique du CA et de la **croissance fondamentale de l'EBIT de l'industrie** (taux de réinvestissement × ROC), cette dernière bornée à [0 % ; 10 %] car elle va de −200 % à +140 % selon les industries. Le résultat est borné à [−5 % ; 20 %]. |
| Croissance, années 6-10 | Décroissance linéaire vers la croissance terminale. |
| Croissance terminale | min(taux sans risque, 2,5 %) : aucune entreprise ne croît durablement plus vite que l'économie. |
| Marge opérationnelle | Convergence linéaire, atteinte en année 5, vers une cible = 75 % de la marge historique moyenne + 25 % de la marge de l'industrie. Un avantage concurrentiel s'érode, mais pas en cinq ans. |
| Impôt | Taux effectif convergeant vers le taux marginal sur les années 6-10. |
| Réinvestissement | ΔCA / (ventes / capital investi), le ratio moyen de l'entreprise et de l'industrie. |
| Valeur terminale | FCFF(N+1) = NOPAT(N+1) × (1 − g / ROIC terminal), actualisé au WACC. Le ROIC terminal est le meilleur des ROIC de l'entreprise et de l'industrie, borné entre le WACC (aucune création de valeur) et WACC + 5 points. |

Passage à la valeur par action : valeur d'entreprise + trésorerie + participations non consolidées
− dette financière (locations comprises) − intérêts minoritaires, divisé par le nombre d'actions.

Sorties complémentaires :

- **Fourchette** : WACC ± 0,5 point et croissance terminale ∓ 0,25 point.
- **Matrice de sensibilité** : WACC ± 1 point × croissance terminale ± 0,5 point.
- **DCF inversé** : la croissance du CA sur les années 1 à 5 que le cours actuel intègre, à marges inchangées (résolution par dichotomie).

Le moteur est vérifié contre des formules fermées. Sans croissance, la valeur doit égaler la rente perpétuelle NOPAT / WACC. À croissance constante, avec un ROIC cohérent avec le ratio ventes/capital, elle doit égaler la formule de Gordon FCFF₁ / (WACC − g). Ces deux cas sont couverts par les tests.

## 5. Multiples

Les multiples sont ceux de l'industrie Damodaran, **agrégés** : somme des valeurs d'entreprise divisée par la
somme des EBITDA de toutes les entreprises du secteur. Cette méthode est moins sensible aux valeurs
extrêmes qu'une moyenne de ratios.

| Multiple | Variante Damodaran retenue |
|---|---|
| EV/EBITDA | Entreprises à EBITDA positif |
| EV/Ventes | Toutes les entreprises |
| P/E | Capitalisation / résultat net des entreprises bénéficiaires (12 mois glissants) |
| P/BV | Toutes les entreprises |

La valeur centrale utilise le multiple de la région, et la fourchette va du multiple régional au multiple mondial.
Le multiple auquel le marché valorise aujourd'hui l'entreprise est affiché pour comparaison.

## 6. Synthèse et verdict

Valeur centrale = moyenne pondérée des méthodes applicables ; même pondération pour les bornes.

| Écart (valeur centrale / cours − 1) | Verdict |
|---|---|
| ≥ +15 % | Sous-évalué |
| entre −15 % et +15 % | Correctement valorisé |
| ≤ −15 % | Surévalué |
| aucune méthode applicable | Non concluant |

## 7. Limites connues

- **Moyennes sectorielles** : un multiple d'industrie ne capte pas un risque propre à l'entreprise (disruption,
  litige, gouvernance). Dans ce cas, le DCF inversé est plus parlant que le verdict : il montre l'hypothèse
  implicite du marché.
- **Décalage temporel** : les multiples Damodaran sont mis à jour en janvier. Si le marché a beaucoup bougé
  depuis, la comparaison est décalée d'autant.
- **Prime pays** : elle est celle du pays d'immatriculation. Une pondération par zone de chiffre d'affaires,
  plus juste pour les multinationales, est prévue.
- **Pondération du WACC** : elle utilise les valeurs de marché actuelles. Pour une entreprise dont le cours a
  chuté, le poids de la dette augmente et le WACC baisse.
- **Doubles cotations** (Rio Tinto plc / Ltd) : Yahoo ne compte que les actions d'une des deux entités, il faut
  corriger `nb_actions` via `corrections_profil`.
- **Financières** : dans cette phase, P/BV et P/E sectoriels uniquement. Le P/BV justifié par le ROE
  ((ROE − g) / (ke − g)) et le modèle de rentabilité excédentaire sont prévus en phase 2.
- **Foncières et holdings** : le P/BV n'est qu'une approximation de l'ANR. Un ANR actif par actif (somme des
  parties et décote de holding) est prévu en phase 2.
