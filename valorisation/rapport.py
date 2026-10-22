"""Note de valorisation d'une page (HTML autonome, graphiques Plotly), au style du dashboard."""

import math
from html import escape

import plotly.graph_objects as go

from . import synthese
from .formats import millions, multiple, nombre, pct
from .formats import vide as _vide

INK, PANEL, LINE = "#0E1A2B", "#15243B", "#2B3D59"
IVORY, SLATE, GOLD, SAGE, BRICK = "#EFE9DB", "#8B96A8", "#C9A15E", "#7BAE95", "#B15B45"
FONT_SANS, FONT_MONO = "IBM Plex Sans, sans-serif", "IBM Plex Mono, monospace"
CONFIG_GRAPHIQUE = {"displayModeBar": False, "responsive": True}
COULEUR_VERDICT = {synthese.SOUS_EVALUE: SAGE, synthese.CORRECT: GOLD,
                   synthese.SUREVALUE: BRICK, synthese.NON_CONCLUANT: SLATE}
# --- Blocs ----------------------------------------------------------------------------
def _section(titre, contenu, note=""):
    note_html = f'<p class="note">{note}</p>' if note else ""
    return (f'<section class="section"><div class="section-head"><span class="eyebrow">{escape(titre)}</span>'
            f'<span class="rule"></span></div>{note_html}{contenu}</section>')


def _tableau(entetes, lignes, classes=None):
    tete = "".join(f"<th>{escape(h)}</th>" for h in entetes)
    corps = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in ligne) + "</tr>" for ligne in lignes)
    return f'<div class="table-wrap"><table class="{classes or ""}"><thead><tr>{tete}</tr></thead><tbody>{corps}</tbody></table></div>'


def _graphique_fourchettes(r):
    lignes = [(m.libelle + f" ({r.poids_effectifs[m.methode]:.0%})", m)
              for m in r.methodes if m.valide and m.methode in r.poids_effectifs]
    noms = [n for n, _ in lignes] + ["Synthèse pondérée"]
    bas = [min(m.bas, m.valeur_par_action) for _, m in lignes] + [r.bas]
    haut = [max(m.haut, m.valeur_par_action) for _, m in lignes] + [r.haut]
    centre = [m.valeur_par_action for _, m in lignes] + [r.valeur_centrale]
    couleurs = [SLATE] * len(lignes) + [GOLD]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=noms, x=[h - b for b, h in zip(bas, haut)], base=bas, orientation="h",
        marker=dict(color=couleurs, opacity=0.55, line=dict(width=0)), width=0.5,
        customdata=list(zip(bas, haut)), name="Fourchette",
        hovertemplate="%{y}<br>%{customdata[0]:,.2f} – %{customdata[1]:,.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(
        y=noms, x=centre, mode="markers", name="Valeur centrale",
        marker=dict(symbol="line-ns", size=22, line=dict(width=3, color=IVORY)),
        hovertemplate="%{y}<br>Valeur centrale : %{x:,.2f}<extra></extra>"))
    fig.add_vline(x=r.cours, line=dict(color=BRICK, width=2, dash="dash"))
    fig.add_annotation(x=r.cours, y=1.02, yref="paper", text=f"Cours {nombre(r.cours, 2)}", showarrow=False,
                       font=dict(family=FONT_MONO, color=BRICK, size=11), yanchor="bottom")
    fig.update_layout(
        height=110 + 52 * len(noms), showlegend=False, bargap=0.4,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_SANS, color=SLATE, size=12), margin=dict(l=10, r=20, t=36, b=36),
        xaxis=dict(gridcolor=LINE, zeroline=False, tickfont=dict(family=FONT_MONO, size=11),
                   title=dict(text=f"Valeur par action ({r.devise})", font=dict(size=11))),
        yaxis=dict(autorange="reversed", tickfont=dict(color=IVORY, size=12)),
        hoverlabel=dict(bgcolor=PANEL, bordercolor=LINE, font=dict(family=FONT_MONO, color=IVORY)),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, config=CONFIG_GRAPHIQUE)


def _bloc_methode(r):
    plan = r.plan
    lignes = [[escape(m.libelle), pct(plan.poids.get(m.methode, 0.0), 0),
               pct(r.poids_effectifs.get(m.methode, 0.0), 0),
               nombre(m.valeur_par_action, 2) if m.valide else "non applicable"] for m in r.methodes]
    ajustements = "".join(f"<li>{escape(a)}</li>" for a in plan.ajustements)
    correspondance = (f"Industrie Yahoo « {escape(str(r.industrie_yahoo))} » → industrie Damodaran "
                      f"« {escape(r.industrie_damodaran)} », région {escape(r.region)} "
                      f"({r.industrie.nb_entreprises} entreprises).")
    contenu = (f'<div class="card"><div class="card-title">{escape(plan.libelle)}</div>'
               f'<p>{escape(plan.justification)}</p><p class="muted">{correspondance}</p>'
               f'{"<ul>" + ajustements + "</ul>" if ajustements else ""}</div>'
               + _tableau(["Méthode", "Poids prévu", "Poids retenu", f"Valeur / action ({r.devise})"], lignes))
    return _section("Choix de la méthode", contenu)


def _bloc_dcf(r):
    m = r.methode("dcf")
    if m is None or not m.valide:
        return ""
    d, h, j = m.detail, m.detail["hypotheses"], m.detail["justifications"]
    hypotheses = [
        ["Croissance du CA (années 1-5)", pct(h.croissance_initiale), escape(j["croissance_initiale"])],
        ["Croissance terminale", pct(h.croissance_terminale), escape(j["croissance_terminale"])],
        ["Marge opérationnelle de départ", pct(h.marge_initiale), escape(j["marge_initiale"])],
        ["Marge opérationnelle cible", pct(h.marge_cible), escape(j["marge_cible"])],
        ["Ventes / capital investi", nombre(h.ventes_sur_capital, 2), escape(j["ventes_sur_capital"])],
        ["Taux d'impôt", f"{pct(h.taux_is_initial)} → {pct(h.taux_is_terminal)}", escape(j["taux_is"])],
        ["ROIC terminal", pct(h.roic_terminal), escape(j["roic_terminal"])],
        ["WACC", pct(h.wacc, 2), "Voir la construction du coût du capital ci-dessous."],
    ]
    p = d["projections"]
    entetes = ["En millions " + r.devise] + [f"A{a}" for a in p.index] + ["Terminal"]
    lignes = [
        ["Croissance du CA"] + [pct(x) for x in p["croissance"]] + [pct(h.croissance_terminale)],
        ["Chiffre d'affaires"] + [millions(x) for x in p["chiffre_affaires"]] + [""],
        ["Marge opérationnelle"] + [pct(x) for x in p["marge"]] + [pct(h.marge_cible)],
        ["EBIT"] + [millions(x) for x in p["ebit"]] + [""],
        ["Taux d'impôt"] + [pct(x) for x in p["taux_is"]] + [pct(h.taux_is_terminal)],
        ["EBIT après impôt"] + [millions(x) for x in p["nopat"]] + [""],
        ["− Réinvestissement"] + [millions(x) for x in p["reinvestissement"]]
        + [pct(d["taux_reinvestissement_terminal"]) + " du NOPAT"],
        ["FCFF"] + [millions(x) for x in p["fcff"]] + [millions(d["valeur_terminale"])],
        ["FCFF actualisé"] + [millions(x) for x in p["fcff_actualise"]] + [millions(d["va_valeur_terminale"])],
    ]
    profil = r.profil_entreprise
    pont = [
        ["Valeur actuelle des flux (années 1-10)", millions(d["va_flux"])],
        ["+ Valeur actuelle de la valeur terminale", millions(d["va_valeur_terminale"])
         + f' <span class="muted">({pct(d["part_valeur_terminale"], 0)} du total)</span>'],
        ["= Valeur d'entreprise", millions(d["valeur_entreprise"])],
        ["+ Trésorerie et placements", millions(profil.tresorerie)],
        ["+ Participations non consolidées", millions(profil.participations)],
        ["− Dette financière (y compris locations)", millions(profil.dette_financiere)],
        ["− Intérêts minoritaires", millions(profil.interets_minoritaires)],
        ["= Valeur des fonds propres", millions(d["valeur_fonds_propres"])],
        [f"÷ Nombre d'actions (millions)", nombre(profil.nb_actions / 1e6, 1)],
        [f"= Valeur par action ({r.devise})", f"<strong>{nombre(m.valeur_par_action, 2)}</strong>"],
    ]
    g_implicite = d.get("croissance_implicite")
    if g_implicite is None:
        lecture = "Le cours actuel ne peut pas être justifié dans la plage de croissance testée (−15 % à +50 %)."
    else:
        lecture = (f"À marges inchangées, le cours de {nombre(r.cours, 2)} {r.devise} suppose une croissance du "
                   f"chiffre d'affaires de <strong>{pct(g_implicite)}</strong> par an pendant 5 ans, contre "
                   f"{pct(h.croissance_initiale)} retenus.")
    contenu = (_tableau(["Hypothèse", "Valeur", "Origine"], hypotheses, "hypotheses")
               + '<div class="sub">Flux projetés</div>' + _tableau(entetes, lignes, "projections")
               + '<div class="grid2"><div><div class="sub">De la valeur d\'entreprise à la valeur par action</div>'
               + _tableau(["", ""], pont, "pont") + '</div><div><div class="sub">DCF inversé</div>'
               + f'<div class="card"><p>{lecture}</p></div>'
               + '<div class="sub">Sensibilité de la valeur par action</div>' + _sensibilite(r, d["sensibilite"])
               + "</div></div>")
    return _section("DCF — flux de trésorerie disponibles", contenu)


def _sensibilite(r, grille):
    entetes = ["WACC \\ g"] + [pct(g, 2) for g in grille.columns]
    lignes = []
    for wacc, ligne in grille.iterrows():
        cellules = [f"<strong>{pct(wacc, 2)}</strong>"]
        for v in ligne:
            ecart = v / r.cours - 1 if not _vide(v) else math.nan
            classe = {synthese.SOUS_EVALUE: "pos", synthese.SUREVALUE: "neg"}.get(
                synthese.verdict(ecart, r.seuil_verdict), "")
            cellules.append(f'<span class="{classe}">{nombre(v, 2)}</span>')
        lignes.append(cellules)
    return _tableau(entetes, lignes, "sensibilite")


def _bloc_wacc(r):
    w = r.wacc
    if w.financiere:
        lignes_beta = [["Bêta de l'industrie", nombre(w.beta_reendette, 2),
                        "Damodaran, bêta endetté moyen (non retraité : la dette fait partie de l'activité)"]]
    else:
        lignes_beta = [
            ["Bêta désendetté de l'industrie", nombre(w.beta_desendette, 2), "Damodaran, corrigé de la trésorerie"],
            ["Dette / capitalisation", pct(w.dette_sur_fonds_propres), "Valeurs de marché"],
            ["Bêta réendetté", nombre(w.beta_reendette, 2), "βu × (1 + (1 − t) × D/E)"],
        ]
    fonds_propres = [
        ["Taux sans risque", pct(w.taux_sans_risque, 2), escape(w.source_taux)],
        *lignes_beta,
        ["Prime de risque marché mature", pct(w.prime_marche_mature, 2), "Damodaran, prime implicite du S&P 500"],
        ["Prime de risque pays", pct(w.prime_pays, 2), f"Damodaran, pays : {escape(str(r.profil_entreprise.pays))}"],
        ["<strong>Coût des fonds propres</strong>", f"<strong>{pct(w.cout_fonds_propres, 2)}</strong>",
         "rf + β × (prime mature + prime pays)"],
    ]
    if "dcf" not in r.plan.poids:
        note = ("Pour une institution financière, la dette fait partie de l'activité : seul le coût des fonds "
                "propres est pertinent (il sert de référence au ROE).")
        return _section("Coût des fonds propres", _tableau(["Composante", "Valeur", "Source"], fonds_propres, "wacc"), note)
    couverture = "∞" if w.couverture_interets == math.inf else nombre(w.couverture_interets, 1) + "x"
    dette = [
        ["Couverture des intérêts (EBIT / frais financiers)", couverture, "Base : " + escape(r.profil_entreprise.base_comptes)],
        ["Notation synthétique", escape(w.notation_synthetique), "Grille Damodaran"],
        ["Spread de l'entreprise + spread pays", f"{pct(w.spread_entreprise, 2)} + {pct(w.spread_pays, 2)}", ""],
        ["Coût de la dette avant impôt", pct(w.cout_dette_avant_impot, 2), "rf + spreads"],
        ["Taux d'IS marginal", pct(w.taux_is_marginal, 1), "Damodaran, taux par pays"],
        ["Poids fonds propres / dette", f"{pct(w.poids_fonds_propres, 0)} / {pct(w.poids_dette, 0)}", "Valeurs de marché"],
        ["<strong>WACC</strong>", f"<strong>{pct(w.wacc, 2)}</strong>", ""],
    ]
    return _section("Coût du capital", '<div class="grid2"><div>'
                    + _tableau(["Fonds propres", "Valeur", "Source"], fonds_propres, "wacc") + "</div><div>"
                    + _tableau(["Dette et WACC", "Valeur", "Source"], dette, "wacc") + "</div></div>")


def _bloc_multiples(r):
    lignes = []
    for m in r.methodes:
        if m.methode == "dcf":
            continue
        d = m.detail
        if not d:
            lignes.append([escape(m.libelle), "", "", "", "", escape("; ".join(m.alertes))])
            continue
        base = millions(d["base"]) + (" (normalisé)" if d.get("normalise") else "")
        lignes.append([escape(m.libelle), base, multiple(d["multiple_region"]), multiple(d["multiple_monde"]),
                       multiple(d["multiple_actuel"]),
                       f"{nombre(m.valeur_par_action, 2)} <span class=\"muted\">({nombre(m.bas, 2)} – {nombre(m.haut, 2)})</span>"])
    if not lignes:
        return ""
    entetes = ["Multiple", f"Agrégat (M {r.devise})", f"Industrie {r.region}", "Industrie monde",
               "Entreprise aujourd'hui", f"Valeur / action ({r.devise})"]
    note = ("Multiples agrégés de l'industrie Damodaran (capitalisations et agrégats sommés sur toutes les "
            "entreprises du secteur). Valeur centrale : multiple régional ; fourchette : multiples régional et mondial.")
    return _section("Multiples sectoriels", _tableau(entetes, lignes), note)


def _bloc_alertes(r):
    if not r.alertes:
        return ""
    items = "".join(f"<li>{escape(a)}</li>" for a in r.alertes)
    return _section("Points d'attention", f'<div class="card"><ul>{items}</ul></div>')


def _bloc_sources(r):
    profil = r.profil_entreprise
    items = [
        f"Comptes : Yahoo Finance, {escape(profil.base_comptes)} (historique : {len(profil.historique)} exercices).",
        f"Données sectorielles : Aswath Damodaran, NYU Stern, mise à jour du "
        f"{r.date_donnees_damodaran.strftime('%d/%m/%Y') if r.date_donnees_damodaran else 'n.d.'} ; primes pays du "
        f"{r.date_primes_pays.strftime('%d/%m/%Y') if r.date_primes_pays else 'n.d.'}.",
        f"Taux sans risque : {escape(r.wacc.source_taux)}.",
        f"Verdict : écart entre valeur centrale et cours supérieur à ±{pct(r.seuil_verdict, 0)}.",
        "Outil d'analyse à visée pédagogique : ceci n'est pas un conseil en investissement.",
    ]
    return _section("Sources et conventions", "<ul class=\"sources\">" + "".join(f"<li>{i}</li>" for i in items) + "</ul>")


def generer_html(r):
    couleur = COULEUR_VERDICT.get(r.verdict, SLATE)
    profil = r.profil_entreprise
    entete = (
        f'<header class="masthead"><div><div class="eyebrow">Note de valorisation</div>'
        f'<h1>{escape(r.nom)}</h1><div class="muted mono">{escape(r.ticker)} · {escape(str(profil.secteur))} · '
        f'{escape(str(r.industrie_yahoo))} · {escape(str(profil.pays))}</div></div>'
        f'<div class="right mono">Valorisation du {r.date_valorisation.strftime("%d/%m/%Y")}<br>'
        f'Capitalisation {nombre(profil.capitalisation / 1e9, 1)} Md {r.devise}</div></header>')
    heros = (
        f'<div class="hero"><div class="hero-item"><div class="hero-label">Valeur centrale</div>'
        f'<div class="hero-number">{nombre(r.valeur_centrale, 2)}<span class="unit"> {r.devise}</span></div>'
        f'<div class="muted mono">Fourchette {nombre(r.bas, 2)} – {nombre(r.haut, 2)}</div></div>'
        f'<div class="hero-item"><div class="hero-label">Cours</div>'
        f'<div class="hero-number small">{nombre(r.cours, 2)}<span class="unit"> {r.devise}</span></div>'
        f'<div class="muted mono">Potentiel {pct(r.ecart, 1, signe=True)}</div></div>'
        f'<div class="hero-item"><div class="hero-label">Verdict</div>'
        f'<div class="badge" style="color:{couleur};border-color:{couleur}">{escape(r.verdict)}</div></div></div>')
    corps = (entete + heros
             + _section("Synthèse des méthodes", _graphique_fourchettes(r) if r.poids_effectifs else "")
             + _bloc_methode(r) + _bloc_dcf(r) + _bloc_wacc(r) + _bloc_multiples(r)
             + _bloc_alertes(r) + _bloc_sources(r))
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Valorisation — {escape(r.nom)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>{CSS}</style></head>
<body><main class="sheet">{corps}</main></body></html>"""


def ecrire_rapport(r, chemin):
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(generer_html(r))
    return chemin


CSS = f"""
:root{{--ink:{INK};--panel:{PANEL};--line:{LINE};--ivory:{IVORY};--slate:{SLATE};--gold:{GOLD};--sage:{SAGE};--brick:{BRICK};}}
*{{box-sizing:border-box;}} html,body{{margin:0;padding:0;}}
body{{background:radial-gradient(1200px 500px at 15% -10%, rgba(201,161,94,.06), transparent), var(--ink);
  color:var(--ivory); font-family:'IBM Plex Sans',sans-serif; -webkit-font-smoothing:antialiased; padding:40px 16px 80px;}}
.sheet{{max-width:1200px; margin:0 auto;}}
.mono{{font-family:'IBM Plex Mono',monospace;}} .muted{{color:var(--slate);}}
.eyebrow{{font-family:'IBM Plex Mono',monospace; font-size:13px; font-weight:600; letter-spacing:.12em; text-transform:uppercase; color:var(--gold);}}
.masthead{{display:flex; justify-content:space-between; align-items:flex-end; gap:16px; flex-wrap:wrap;
  border-bottom:1px solid var(--line); padding-bottom:18px; margin-bottom:24px;}}
.masthead h1{{font-family:'Fraunces',serif; font-weight:500; font-size:26px; margin:6px 0;}}
.masthead .muted{{font-size:12px;}} .masthead .right{{text-align:right; color:var(--slate); font-size:12px;}}
.hero{{display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; margin-bottom:28px;}}
.hero-item{{background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:18px 20px;}}
.hero-label{{font-family:'Fraunces',serif; color:var(--slate); font-size:15px; margin-bottom:8px;}}
.hero-number{{font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:clamp(28px,5vw,40px); line-height:1.1;}}
.hero-number.small{{font-size:clamp(24px,4vw,32px);}} .unit{{font-size:14px; color:var(--slate); font-weight:400;}}
.hero-item .muted{{font-size:12px; margin-top:6px;}}
.badge{{display:inline-block; font-family:'IBM Plex Mono',monospace; font-size:18px; font-weight:600; padding:8px 14px;
  border:1px solid; border-radius:24px; margin-top:4px;}}
.section{{margin:34px 0;}} .section-head{{display:flex; align-items:center; gap:14px; margin-bottom:14px;}}
.rule{{flex:1; height:1px; background:var(--line);}}
.note{{color:var(--slate); font-size:13px; margin:0 0 12px;}}
.sub{{font-family:'IBM Plex Mono',monospace; font-size:12px; letter-spacing:.06em; text-transform:uppercase; color:var(--slate); margin:20px 0 8px;}}
.card{{background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:14px 18px; margin-bottom:12px; font-size:14px; line-height:1.55;}}
.card p{{margin:6px 0;}} .card ul{{margin:6px 0; padding-left:20px;}} .card-title{{font-family:'Fraunces',serif; font-size:17px; color:var(--gold);}}
.grid2{{display:grid; grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); gap:20px;}}
.table-wrap{{overflow-x:auto; border:1px solid var(--line); border-radius:10px;}}
table{{width:100%; border-collapse:collapse; font-size:13px;}}
th{{text-align:left; font-family:'IBM Plex Mono',monospace; font-weight:500; font-size:11px; letter-spacing:.04em;
  text-transform:uppercase; color:var(--slate); background:var(--panel); padding:9px 12px; border-bottom:1px solid var(--line); white-space:nowrap;}}
td{{padding:8px 12px; border-bottom:1px solid rgba(43,61,89,.6); vertical-align:top;}}
tr:last-child td{{border-bottom:none;}}
td:not(:first-child){{font-family:'IBM Plex Mono',monospace; white-space:nowrap;}}
table.hypotheses td:last-child, table.wacc td:last-child{{font-family:'IBM Plex Sans',sans-serif; white-space:normal; color:var(--slate);}}
table.projections td:first-child{{white-space:nowrap;}} table.projections td:not(:first-child){{text-align:right;}}
table.pont td:last-child, table.sensibilite td:not(:first-child){{text-align:right;}}
.pos{{color:var(--sage);}} .neg{{color:var(--brick);}}
ul.sources{{color:var(--slate); font-size:13px; line-height:1.7; padding-left:20px;}}
@media (max-width:600px){{ .masthead .right{{text-align:left;}} .grid2{{grid-template-columns:1fr;}} }}
"""
