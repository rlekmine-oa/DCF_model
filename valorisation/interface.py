"""Interface graphique (Tkinter) : saisir un ou plusieurs tickers ou noms de sociétés, valoriser,
consulter les résultats et ouvrir les notes HTML. Lancement : `python -m valorisation.interface`
ou `Valorisation.exe`.
"""

import os
import queue
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import ttk

from . import config, synthese
from .formats import nombre, pct
from .recherche import chercher_action, decouper_saisie, ressemble_a_un_ticker

ENCRE, PANNEAU, PANNEAU_2, LIGNE = "#0E1A2B", "#15243B", "#1C2E48", "#2B3D59"
IVOIRE, ARDOISE, OR, SAUGE, BRIQUE = "#EFE9DB", "#8B96A8", "#C9A15E", "#7BAE95", "#B15B45"
COULEURS_VERDICT = {synthese.SOUS_EVALUE: SAUGE, synthese.CORRECT: OR, synthese.SUREVALUE: BRIQUE,
                    synthese.NON_CONCLUANT: ARDOISE, "Ignoré": ARDOISE, "Erreur": BRIQUE}
POLICE = "Segoe UI"
POLICE_MONO = "Consolas"

COLONNES = [("ticker", "Ticker", 90, "w"), ("societe", "Société", 230, "w"), ("cours", "Cours", 90, "e"),
            ("valeur", "Valeur", 90, "e"), ("fourchette", "Fourchette", 150, "e"),
            ("potentiel", "Potentiel", 85, "e"), ("verdict", "Verdict", 170, "w")]


def _rediriger_sorties():
    """En .exe fenêtré, stdout/stderr n'existent pas : les messages vont dans un journal."""
    if sys.stdout is None or sys.stderr is None:
        config.DOSSIER_CACHE.mkdir(parents=True, exist_ok=True)
        journal = open(config.DOSSIER_CACHE / "journal.txt", "a", encoding="utf-8")
        sys.stdout = sys.stdout or journal
        sys.stderr = sys.stderr or journal


def _activer_haute_resolution():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


class Application:
    def __init__(self, racine):
        self.racine = racine
        self.file = queue.Queue()
        self.resultats = {}          # identifiant de ligne -> (ResultatValorisation, chemin de la note)
        self.saisies = {}            # identifiant de ligne -> texte saisi par l'utilisateur
        self.en_cours = False
        self.dossier_notes = Path(config.DOSSIER_RAPPORTS_DEFAUT)

        racine.title("Valorisation d'entreprise")
        icone = Path(__file__).resolve().parent / "ressources" / "valorisation.ico"
        if icone.exists() and sys.platform == "win32":
            racine.iconbitmap(default=str(icone))
        racine.geometry("1060x720")
        racine.minsize(820, 560)
        racine.configure(bg=ENCRE)
        self._styles()
        self._construire()
        racine.after(100, self._lire_file)

    # --- Mise en forme ------------------------------------------------------------------
    def _styles(self):
        s = ttk.Style(self.racine)
        s.theme_use("clam")
        s.configure(".", background=ENCRE, foreground=IVOIRE, font=(POLICE, 10), bordercolor=LIGNE)
        s.configure("TFrame", background=ENCRE)
        s.configure("Panneau.TFrame", background=PANNEAU)
        s.configure("TLabel", background=ENCRE, foreground=IVOIRE)
        s.configure("Titre.TLabel", font=("Georgia", 18), foreground=IVOIRE)
        s.configure("Surtitre.TLabel", font=(POLICE_MONO, 9, "bold"), foreground=OR)
        s.configure("Discret.TLabel", foreground=ARDOISE)
        s.configure("Panneau.TLabel", background=PANNEAU, foreground=ARDOISE)
        s.configure("TEntry", fieldbackground=PANNEAU_2, foreground=IVOIRE, insertcolor=IVOIRE,
                    bordercolor=LIGNE, lightcolor=LIGNE, darkcolor=LIGNE, padding=6)
        s.configure("TSpinbox", fieldbackground=PANNEAU_2, foreground=IVOIRE, arrowcolor=IVOIRE,
                    background=PANNEAU, bordercolor=LIGNE, insertcolor=IVOIRE)
        s.configure("TCheckbutton", background=ENCRE, foreground=IVOIRE, indicatorbackground=PANNEAU_2)
        s.map("TCheckbutton", background=[("active", ENCRE)])
        s.configure("Principal.TButton", background=OR, foreground=ENCRE, font=(POLICE, 10, "bold"),
                    padding=(16, 6), borderwidth=0)
        s.map("Principal.TButton", background=[("disabled", LIGNE), ("active", "#E3C384")],
              foreground=[("disabled", ARDOISE)])
        s.configure("TButton", background=PANNEAU_2, foreground=IVOIRE, padding=(10, 5), borderwidth=0)
        s.map("TButton", background=[("active", LIGNE), ("disabled", PANNEAU)], foreground=[("disabled", ARDOISE)])
        s.configure("Treeview", background=PANNEAU, fieldbackground=PANNEAU, foreground=IVOIRE,
                    rowheight=28, borderwidth=0, font=(POLICE, 10))
        s.configure("Treeview.Heading", background=PANNEAU_2, foreground=ARDOISE, relief="flat",
                    font=(POLICE_MONO, 9, "bold"), padding=(6, 5))
        s.map("Treeview", background=[("selected", LIGNE)], foreground=[("selected", IVOIRE)])
        s.map("Treeview.Heading", background=[("active", LIGNE)])
        s.configure("Horizontal.TProgressbar", background=OR, troughcolor=PANNEAU, bordercolor=LIGNE,
                    lightcolor=OR, darkcolor=OR)
        s.configure("Vertical.TScrollbar", background=PANNEAU_2, troughcolor=PANNEAU, arrowcolor=ARDOISE,
                    bordercolor=PANNEAU)

    def _construire(self):
        cadre = ttk.Frame(self.racine, padding=(20, 16, 20, 12))
        cadre.pack(fill="both", expand=True)

        ttk.Label(cadre, text="VALORISATION D'ENTREPRISE", style="Surtitre.TLabel").pack(anchor="w")
        ttk.Label(cadre, text="DCF et multiples calibrés sur les données Damodaran",
                  style="Titre.TLabel").pack(anchor="w", pady=(2, 12))

        # Saisie
        ttk.Label(cadre, text="Tickers Yahoo ou noms de sociétés, séparés par des virgules "
                              "(ex. SU.PA, MC.PA, AAPL, Airbus)", style="Discret.TLabel").pack(anchor="w")
        ligne = ttk.Frame(cadre)
        ligne.pack(fill="x", pady=(4, 8))
        self.saisie = ttk.Entry(ligne, font=(POLICE, 12))
        self.saisie.pack(side="left", fill="x", expand=True)
        self.saisie.bind("<Return>", lambda _: self.lancer())
        self.saisie.focus_set()
        self.bouton = ttk.Button(ligne, text="Valoriser", style="Principal.TButton", command=self.lancer)
        self.bouton.pack(side="left", padx=(10, 0))

        options = ttk.Frame(cadre)
        options.pack(fill="x", pady=(0, 10))
        ttk.Label(options, text="Seuil du verdict ± ").pack(side="left")
        self.seuil = tk.StringVar(value=str(round(config.SEUIL_VERDICT * 100)))
        ttk.Spinbox(options, from_=5, to=50, increment=5, width=4, textvariable=self.seuil).pack(side="left")
        ttk.Label(options, text=" %").pack(side="left")
        self.ouvrir_auto = tk.BooleanVar(value=True)
        ttk.Checkbutton(options, text="Ouvrir les notes à la fin du calcul",
                        variable=self.ouvrir_auto).pack(side="left", padx=(24, 0))

        # Résultats
        tableau = ttk.Frame(cadre)
        tableau.pack(fill="both", expand=True)
        self.arbre = ttk.Treeview(tableau, columns=[c[0] for c in COLONNES], show="headings",
                                  selectmode="browse", height=8)
        for cle, titre, largeur, ancre in COLONNES:
            self.arbre.heading(cle, text=titre.upper(), anchor=ancre)
            self.arbre.column(cle, width=largeur, anchor=ancre, stretch=cle == "societe")
        for verdict, couleur in COULEURS_VERDICT.items():
            self.arbre.tag_configure(verdict, foreground=couleur)
        defilement = ttk.Scrollbar(tableau, orient="vertical", command=self.arbre.yview)
        self.arbre.configure(yscrollcommand=defilement.set)
        self.arbre.pack(side="left", fill="both", expand=True)
        defilement.pack(side="left", fill="y")
        self.arbre.bind("<<TreeviewSelect>>", lambda _: self._afficher_detail())
        self.arbre.bind("<Double-1>", lambda _: self.ouvrir_note())

        # Détail de la ligne sélectionnée
        self.detail = tk.Text(cadre, height=9, bg=PANNEAU, fg=IVOIRE, relief="flat", wrap="word",
                              font=(POLICE, 10), padx=12, pady=10, highlightthickness=1,
                              highlightbackground=LIGNE, insertbackground=IVOIRE)
        self.detail.tag_configure("titre", foreground=OR, font=(POLICE, 11, "bold"))
        self.detail.tag_configure("discret", foreground=ARDOISE)
        self.detail.tag_configure("alerte", foreground="#E3C384")
        self.detail.pack(fill="x", pady=(10, 8))
        self._ecrire_detail([("Double-cliquez sur une ligne pour ouvrir sa note de valorisation.", "discret")])

        # Barre du bas
        bas = ttk.Frame(cadre)
        bas.pack(fill="x")
        self.bouton_note = ttk.Button(bas, text="Ouvrir la note", command=self.ouvrir_note, state="disabled")
        self.bouton_note.pack(side="left")
        ttk.Button(bas, text="Dossier des notes", command=self.ouvrir_dossier).pack(side="left", padx=6)
        ttk.Button(bas, text="Effacer", command=self.effacer).pack(side="left")
        self.statut = ttk.Label(bas, text="Prêt.", style="Discret.TLabel")
        self.statut.pack(side="right")
        self.progression = ttk.Progressbar(bas, length=160, mode="determinate")
        self.progression.pack(side="right", padx=10)

    # --- Actions -------------------------------------------------------------------------
    def lancer(self):
        if self.en_cours:
            return
        elements = decouper_saisie(self.saisie.get())
        if not elements:
            self.statut.configure(text="Saisissez au moins un ticker ou un nom de société.")
            return
        try:
            seuil = float(self.seuil.get().replace(",", ".")) / 100
        except ValueError:
            seuil = config.SEUIL_VERDICT
        self.en_cours = True
        self.bouton.configure(state="disabled")
        self.progression.configure(maximum=len(elements), value=0)
        threading.Thread(target=self._travailler, args=(elements, seuil, self.ouvrir_auto.get()),
                         daemon=True).start()

    def _travailler(self, elements, seuil, ouvrir):
        """Fil de calcul : n'accède jamais aux widgets, communique par la file."""
        from .api import evaluer_ticker
        from .entreprise import NonValorisable
        from .rapport import ecrire_rapport

        self.dossier_notes.mkdir(parents=True, exist_ok=True)
        notes = []
        for i, saisie in enumerate(elements, 1):
            self.file.put(("statut", f"Valorisation de {saisie} ({i}/{len(elements)})…"))
            try:
                if ressemble_a_un_ticker(saisie):
                    try:
                        resultat = evaluer_ticker(saisie.upper(), seuil_verdict=seuil)
                    except NonValorisable:
                        raise
                    except Exception:
                        # Ticker inexistant : on tente une recherche par nom.
                        ticker, _ = chercher_action(saisie)
                        resultat = evaluer_ticker(ticker, seuil_verdict=seuil)
                else:
                    ticker, _ = chercher_action(saisie)
                    resultat = evaluer_ticker(ticker, seuil_verdict=seuil)
                nom_fichier = f"valorisation_{resultat.ticker.replace('.', '_').replace('^', '')}.html"
                chemin = ecrire_rapport(resultat, self.dossier_notes / nom_fichier)
                notes.append(chemin)
                self.file.put(("resultat", saisie, resultat, chemin))
            except NonValorisable as erreur:
                self.file.put(("ignore", saisie, str(erreur)))
            except Exception as erreur:
                traceback.print_exc()
                self.file.put(("erreur", saisie, str(erreur) or erreur.__class__.__name__))
            self.file.put(("progression", i))
        self.file.put(("fin", notes if ouvrir else []))

    def _lire_file(self):
        try:
            while True:
                message = self.file.get_nowait()
                getattr(self, "_recevoir_" + message[0])(*message[1:])
        except queue.Empty:
            pass
        self.racine.after(100, self._lire_file)

    def _recevoir_statut(self, texte):
        self.statut.configure(text=texte)

    def _recevoir_progression(self, valeur):
        self.progression.configure(value=valeur)

    def _recevoir_resultat(self, saisie, r, chemin):
        fourchette = f"{nombre(r.bas, 2)} – {nombre(r.haut, 2)}"
        valeurs = (r.ticker, r.nom, f"{nombre(r.cours, 2)} {r.devise}", nombre(r.valeur_centrale, 2),
                   fourchette, pct(r.ecart, 1, signe=True), r.verdict)
        iid = self.arbre.insert("", "end", values=valeurs, tags=(r.verdict,))
        self.resultats[iid] = (r, chemin)
        self.saisies[iid] = saisie
        self.arbre.selection_set(iid)
        self.arbre.see(iid)

    def _recevoir_ignore(self, saisie, message):
        iid = self.arbre.insert("", "end", values=(saisie, message, "", "", "", "", "Ignoré"), tags=("Ignoré",))
        self.resultats[iid] = (None, message)

    def _recevoir_erreur(self, saisie, message):
        iid = self.arbre.insert("", "end", values=(saisie, message, "", "", "", "", "Erreur"), tags=("Erreur",))
        self.resultats[iid] = (None, message)

    def _recevoir_fin(self, notes):
        self.en_cours = False
        self.bouton.configure(state="normal")
        n = sum(1 for r, _ in self.resultats.values() if r is not None)
        self.statut.configure(text=f"Terminé : {n} note{'s' if n > 1 else ''} au total dans « Dossier des notes ».")
        for chemin in notes:
            webbrowser.open(Path(chemin).resolve().as_uri())

    def _selection(self):
        selection = self.arbre.selection()
        return self.resultats.get(selection[0]) if selection else None

    def _afficher_detail(self):
        element = self._selection()
        if element is None:
            return
        r, info = element
        self.bouton_note.configure(state="normal" if r is not None else "disabled")
        if r is None:
            self._ecrire_detail([(info, "alerte")])
            return
        saisie = self.saisies.get(self.arbre.selection()[0], "")
        trouve = f"   trouvé pour « {saisie} »" if saisie and saisie.upper() != r.ticker else ""
        morceaux = [(f"{r.nom} ({r.ticker})", "titre"), (trouve + "\n", "discret"),
                    (f"{r.plan.libelle} · industrie Damodaran « {r.industrie_damodaran} », région {r.region}\n",
                     "discret")]
        for m in r.methodes:
            poids = r.poids_effectifs.get(m.methode, 0.0)
            valeur = f"{nombre(m.valeur_par_action, 2)} {r.devise}" if m.valide else "non applicable"
            morceaux.append((f"  {m.libelle} : {valeur}  (poids {pct(poids, 0)})\n", None))
        if r.wacc is not None:
            morceaux.append((f"  Coût des fonds propres {pct(r.wacc.cout_fonds_propres, 2)}"
                             + (f" · WACC {pct(r.wacc.wacc, 2)}" if "dcf" in r.plan.poids else "") + "\n", None))
        dcf = r.methode("dcf")
        if dcf is not None and dcf.valide:
            g = dcf.detail.get("croissance_implicite")
            if g is not None:
                morceaux.append((f"  DCF inversé : le cours suppose {pct(g)} de croissance annuelle du CA "
                                 f"sur 5 ans (hypothèse retenue {pct(dcf.detail['hypotheses'].croissance_initiale)}).\n",
                                 None))
        for alerte in r.alertes:
            morceaux.append((f"  ⚠ {alerte}\n", "alerte"))
        self._ecrire_detail(morceaux)

    def _ecrire_detail(self, morceaux):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        for texte, style in morceaux:
            self.detail.insert("end", texte, style or ())
        self.detail.configure(state="disabled")

    def ouvrir_note(self):
        element = self._selection()
        if element and element[0] is not None:
            webbrowser.open(Path(element[1]).resolve().as_uri())

    def ouvrir_dossier(self):
        self.dossier_notes.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(self.dossier_notes)
        else:
            webbrowser.open(self.dossier_notes.resolve().as_uri())

    def effacer(self):
        if self.en_cours:
            return
        self.arbre.delete(*self.arbre.get_children())
        self.resultats.clear()
        self.saisies.clear()
        self.bouton_note.configure(state="disabled")
        self.progression.configure(value=0)
        self._ecrire_detail([("Double-cliquez sur une ligne pour ouvrir sa note de valorisation.", "discret")])
        self.statut.configure(text="Prêt.")


def main():
    _rediriger_sorties()
    _activer_haute_resolution()
    racine = tk.Tk()
    Application(racine)
    racine.mainloop()


if __name__ == "__main__":
    main()
