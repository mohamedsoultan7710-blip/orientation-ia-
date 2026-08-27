"""
Assistant d'orientation scolaire - Republique de Djibouti
Parcours College : apres la 9eme annee, Lycee general ou LIC.
Parcours Seconde : recommandation de serie (Lycee general).
"""
import os
import re
import json
import tempfile
import pandas as pd
import streamlit as st

from modules.ocr_bulletin import lire_texte
from modules.extraction_bulletin import analyser, MATIERES, normaliser
from modules.verification_bulletin import verifier
from modules.recommandation import recommander, charger_metiers
from modules.redaction import (disponible, rediger, charger_voies, brouillon)
from modules.recommandation_seconde import (
    recommander as recommander_seconde,
    MATIERES_SECONDE, NOMS_SERIES, SPECIALITES_SG,
)
from modules.redaction_seconde import (
    rediger as rediger_seconde,
    brouillon as brouillon_seconde,
)
from modules.recommandation_terminale import (
    recommander_terminale, charger_filieres as charger_filieres_terminale,
)
from modules.redaction_terminale import (
    rediger as rediger_terminale,
    brouillon as brouillon_terminale,
)
from modules.formation_professionnelle import (
    charger_formation_pro, filieres_par_domaine,
)
from modules.bourses_privees import charger_bourses_privees

st.set_page_config(page_title="Orientation Djibouti", page_icon="X",
                   layout="centered")

BLEU = "#6AB2E7"
VERT = "#12AD2B"
ROUGE = "#D7141A"
DOSSIER_SORTIE = os.path.join("data", "bulletins")
AUTRE = "Autre - je precise moi-meme"
NIVEAU_ATTENDU = 9
NB_BULLETINS = 2
NB_BULLETINS_SECONDE = 2
NB_CARNETS_TERMINALE = 3
TRIMESTRES_ATTENDUS = [1, 2]
NOMS_NIVEAUX = {6: "6eme", 7: "7eme", 8: "8eme", 9: "9eme"}
COULEURS_VOIE = {
    "favorable": ("#0f5132", "#d1e7dd"),
    "ouvert": ("#664d03", "#fff3cd"),
    "remontee": ("#084298", "#cfe2ff"),
    "alerte": ("#842029", "#f8d7da"),
    "inconnue": ("#41464b", "#e2e3e5"),
}

st.markdown(f"""
<style>
.entete {{
    background: linear-gradient(120deg, {BLEU} 0%, {VERT} 100%);
    border-radius: 18px; padding: 30px 32px; margin-bottom: 22px;
    color: #ffffff; position: relative; overflow: hidden;
}}
.entete .etoile {{ position: absolute; right: 26px; top: 22px;
                   font-size: 3.2rem; color: {ROUGE}; opacity: .9; }}
.entete h1 {{ margin: 0; font-size: 1.85rem; font-weight: 800; color: #fff; }}
.entete p {{ margin: 6px 0 0 0; opacity: .92; font-size: .95rem; }}
.entete .pays {{ font-size: .72rem; letter-spacing: .22em;
                 text-transform: uppercase; opacity: .85; margin-bottom: 8px; }}
.bandeau {{ border-radius: 16px; padding: 24px 28px; margin: 8px 0 18px 0; }}
.bandeau .surtitre {{ font-size: .72rem; letter-spacing: .14em;
                      text-transform: uppercase; opacity: .7; }}
.bandeau .titre {{ font-size: 1.8rem; font-weight: 700; margin: 6px 0 0 0; }}
.carte {{ border-radius: 12px; padding: 16px 20px; margin-bottom: 12px;
          background: rgba(128,128,128,.09); }}
.carte .etiquette {{ font-size: .72rem; letter-spacing: .1em;
                     text-transform: uppercase; opacity: .65; }}
.ligne-note {{ display: flex; justify-content: space-between; padding: 7px 0;
               border-bottom: 1px solid rgba(128,128,128,.18); }}
.ligne-note:last-child {{ border-bottom: none; }}
.avert {{ font-size: .84rem; opacity: .75; border-left: 3px solid {ROUGE};
          padding: 10px 14px; }}
.etape-fil {{ font-size: .78rem; letter-spacing: .08em; opacity: .6;
              text-transform: uppercase; margin-bottom: 4px; }}
</style>
""", unsafe_allow_html=True)

# ==================== ETAT ====================
if "etape" not in st.session_state:
    st.session_state.etape = "accueil"
if "eleve" not in st.session_state:
    st.session_state.eleve = {"nom": "", "parcours": None,
                              "bulletins": [], "profil": {}}
if "lus" not in st.session_state:
    st.session_state.lus = None
if "lus_seconde" not in st.session_state:
    st.session_state.lus_seconde = None
if "lus_terminale" not in st.session_state:
    st.session_state.lus_terminale = None


def aller(etape):
    st.session_state.etape = etape
    st.rerun()


def entete(sous_titre, fil=""):
    st.markdown(f"""
    <div class="entete">
      <div class="etoile">*</div>
      <div class="pays">Republique de Djibouti</div>
      <h1>Assistant d'orientation scolaire</h1>
      <p>{sous_titre}</p>
    </div>
    """, unsafe_allow_html=True)
    if fil:
        st.markdown(f'<div class="etape-fil">{fil}</div>', unsafe_allow_html=True)


# ==================== OUTILS ====================

def detecter_niveau(texte_classe):
    if not texte_classe:
        return None
    t = normaliser(texte_classe)
    for niveau in (9, 8, 7, 6):
        if re.search(rf"\b{niveau}\s*(eme|em|e)?\b", t):
            return niveau
    return None


def traiter_fichier(fichier):
    suffixe = os.path.splitext(fichier.name)[1] or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffixe) as tmp:
        tmp.write(fichier.getbuffer())
        chemin = tmp.name
    try:
        texte = lire_texte(chemin)
        donnees = analyser(texte)
        rapport = verifier(texte, donnees)
    finally:
        os.remove(chemin)
    return donnees, rapport


def tableau_notes(notes, cle):
    lignes = [{"Matiere": m, "Note": notes.get(m)} for m in MATIERES]
    tableau = st.data_editor(
        pd.DataFrame(lignes), num_rows="fixed", width="stretch",
        key=cle, hide_index=True,
        column_config={
            "Matiere": st.column_config.TextColumn(disabled=True),
            "Note": st.column_config.NumberColumn(min_value=0, max_value=20, step=0.25),
        },
    )
    resultat = {}
    for _, ligne in tableau.iterrows():
        matiere = str(ligne["Matiere"]).strip()
        if matiere in MATIERES and pd.notna(ligne["Note"]):
            resultat[matiere] = float(ligne["Note"])
    return resultat


def tableau_notes_seconde(notes, cle, matieres_liste):
    """Meme principe que tableau_notes(), mais pour la liste de matieres de
    la Seconde (10 ou 11 matieres selon la langue rare choisie)."""
    lignes = [{"Matiere": m, "Note": notes.get(m)} for m in matieres_liste]
    tableau = st.data_editor(
        pd.DataFrame(lignes), num_rows="fixed", width="stretch",
        key=cle, hide_index=True,
        column_config={
            "Matiere": st.column_config.TextColumn(disabled=True),
            "Note": st.column_config.NumberColumn(min_value=0, max_value=20, step=0.25),
        },
    )
    resultat = {}
    for _, ligne in tableau.iterrows():
        matiere = str(ligne["Matiere"]).strip()
        if matiere in matieres_liste and pd.notna(ligne["Note"]):
            resultat[matiere] = float(ligne["Note"])
    return resultat


def tableau_notes_terminale(notes, cle, matieres_liste):
    """Meme principe que tableau_notes(), pour le releve officiel du bac de
    Terminale (matieres qui dependent de la serie de l'eleve : S, ES, L ou SG)."""
    lignes = [{"Matiere": m, "Note": notes.get(m)} for m in matieres_liste]
    tableau = st.data_editor(
        pd.DataFrame(lignes), num_rows="fixed", width="stretch",
        key=cle, hide_index=True,
        column_config={
            "Matiere": st.column_config.TextColumn(disabled=True),
            "Note": st.column_config.NumberColumn(min_value=0, max_value=20, step=0.25),
        },
    )
    resultat = {}
    for _, ligne in tableau.iterrows():
        matiere = str(ligne["Matiere"]).strip()
        if matiere in matieres_liste and pd.notna(ligne["Note"]):
            resultat[matiere] = float(ligne["Note"])
    return resultat


def contexte_ia(eleve, r):
    profil = eleve.get("profil", {})
    return {
        "prenom": eleve.get("nom", "").split()[0],
        "moyenne_generale": r["moyenne"],
        "moyennes_par_trimestre": r["moyennes_trimestres"],
        "evolution_entre_trimestres": r["tendance"],
        "voie_qui_se_dessine": r["voie"],
        "situation": r["situation"],
        "points_forts": r["points_forts"],
        "matieres_a_renforcer": r["a_renforcer"],
        "metier_vise": (r["objectif_metier"]["metier"]
                        if r["objectif_metier"] else None),
        "matiere_preferee": profil.get("matiere_preferee"),
        "matieres_alaise": profil.get("matieres_alaise", []),
    }


def texte_ia(eleve, r, graine=0):
    return rediger(contexte_ia(eleve, r), None, charger_voies())


def contexte_ia_seconde(eleve, r):
    profil = eleve.get("profil", {})
    manques_top = []
    if r["classement"]:
        ligne_top = next((l for l in r["classement"]
                          if l["serie"] == r["serie_recommandee"]), None)
        if ligne_top:
            manques_top = ligne_top["manques"]
    return {
        "prenom": eleve.get("nom", "").split()[0],
        "moyenne_generale": r["moyenne"],
        "moyennes_par_trimestre": r["moyennes_trimestres"],
        "situation": r["situation"],
        "points_forts": r["points_forts"],
        "a_renforcer": r["a_renforcer"],
        "serie_recommandee": r["serie_recommandee"],
        "nom_serie": (NOMS_SERIES.get(r["serie_recommandee"], "")
                     if r["serie_recommandee"] else ""),
        "series_validees": r["series_validees"],
        "manques_serie_top": manques_top,
        "langue_rare": r["langue_rare"],
        "metier_vise": (profil.get("ambition_libre")
                        if profil.get("ambition") == AUTRE
                        and profil.get("ambition_libre")
                        else profil.get("ambition")),
    }


def texte_ia_seconde(eleve, r, graine=0):
    return rediger_seconde(contexte_ia_seconde(eleve, r), None, charger_voies())


def enregistrer():
    os.makedirs(DOSSIER_SORTIE, exist_ok=True)
    parcours = st.session_state.eleve.get("parcours") or "general"
    base = normaliser(st.session_state.eleve["nom"]).replace(" ", "_")
    nom_fichier = f"{base}_{parcours}.json"
    chemin = os.path.join(DOSSIER_SORTIE, nom_fichier)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(st.session_state.eleve, f, ensure_ascii=False, indent=2)
    return chemin


# ==================== ETAPE 1 : ACCUEIL ====================
if st.session_state.etape == "accueil":
    entete("Trouve la voie qui te correspond, etape par etape")
    st.write("Pour commencer, dis-nous qui tu es.")
    colonne1, colonne2 = st.columns(2)
    prenom = colonne1.text_input("Prenom", placeholder="Zeinab")
    nom_famille = colonne2.text_input("Nom", placeholder="Ali")
    if st.button("Commencer ->", type="primary"):
        if not prenom.strip() or not nom_famille.strip():
            st.error("Merci d'entrer ton prenom et ton nom.")
        else:
            st.session_state.eleve["nom"] = f"{prenom.strip()} {nom_famille.strip()}"
            aller("parcours")
    st.markdown('<div class="avert">Tes donnees restent sur cet appareil. '
                'Rien n\'est envoye sur Internet.</div>', unsafe_allow_html=True)

# ==================== ETAPE 2 : PARCOURS ====================
elif st.session_state.etape == "parcours":
    entete(f"Bonjour {st.session_state.eleve['nom']}", "Etape 1 sur 4")
    st.write("**Ou en es-tu dans ta scolarite ?**")
    colonne1, colonne2, colonne3 = st.columns(3)
    with colonne1:
        with st.container(border=True):
            st.markdown("**College**")
            st.caption("9eme annee - vers le Lycee general ou le LIC")
            if st.button("Choisir", key="p_college", type="primary"):
                st.session_state.eleve["parcours"] = "college"
                aller("bulletin")
    with colonne2:
        with st.container(border=True):
            st.markdown("**Lycee general**")
            st.caption("Seconde ou Terminale")
            if st.button("Choisir", key="p_lycee", type="primary"):
                aller("niveau_lycee")
    with colonne3:
        with st.container(border=True):
            st.markdown("**LIC**")
            st.caption("Lycee Industriel et Commercial - et tout le reseau technique")
            if st.button("Choisir", key="p_lic", type="primary"):
                aller("formation_pro")
    st.divider()
    if st.button("<- Retour"):
        aller("accueil")

# ==================== ETAPE 2b : NIVEAU AU LYCEE ====================
elif st.session_state.etape == "niveau_lycee":
    entete("Lycee general", "Etape 1 sur 4 - Ton niveau")
    st.write("**Dans quelle classe es-tu ?**")
    colonne1, colonne2 = st.columns(2)
    with colonne1:
        with st.container(border=True):
            st.markdown("**Seconde**")
            st.caption("Choix de la serie : S, ES, L, GFM, IAG ou OGRH")
            if st.button("Choisir", key="n_seconde", type="primary"):
                st.session_state.eleve["parcours"] = "seconde"
                aller("bulletin_seconde")
    with colonne2:
        with st.container(border=True):
            st.markdown("**Terminale**")
            st.caption("Choix des filieres universitaires")
            if st.button("Choisir", key="n_terminale", type="primary"):
                st.session_state.eleve["parcours"] = "terminale"
                aller("bulletin_terminale")
    st.divider()
    if st.button("<- Retour"):
        aller("parcours")

# ==================== ETAPE 3 : LES BULLETINS (COLLEGE) ====================
elif st.session_state.etape == "bulletin":
    entete("Parcours College - 9eme annee", "Etape 2 sur 4 - Tes notes")
    st.info(f"**Les 2 bulletins sont obligatoires** : trimestre 1 ET trimestre 2 "
            f"de {NOMS_NIVEAUX[NIVEAU_ATTENDU]}, avec les {len(MATIERES)} notes "
            "de chacun. Sans les deux, l'analyse ne serait pas fiable.")
    mode = st.radio("Comment veux-tu entrer tes notes ?",
                    ["Importer une photo", "Saisir a la main"],
                    horizontal=True)
    if mode.startswith("Importer"):
        st.caption("Pose ton bulletin a plat, photographie-le bien droit, "
                   "toute la feuille dans le cadre.")
        fichiers = st.file_uploader(
            f"Tes {NB_BULLETINS} bulletins (trimestre 1 et trimestre 2)",
            type=["png", "jpg", "jpeg"], accept_multiple_files=True)
        if st.button("Analyser", type="primary"):
            if not fichiers:
                st.error("Importe tes 2 bulletins.")
            elif len(fichiers) != NB_BULLETINS:
                st.error(f"Il faut exactement {NB_BULLETINS} bulletins : "
                         f"le trimestre 1 et le trimestre 2. "
                         f"Tu en as importe {len(fichiers)}.")
            else:
                lus = []
                for fichier in fichiers:
                    with st.spinner(f"Lecture de {fichier.name}..."):
                        donnees, rapport = traiter_fichier(fichier)
                    lus.append({"source": fichier.name, "donnees": donnees,
                                "rapport": rapport})
                rejets = [l["source"] for l in lus
                          if l["rapport"]["niveau"] == "NON RECONNU"]
                if rejets:
                    st.error("Ce document n'est pas un bulletin scolaire : "
                             + ", ".join(rejets))
                else:
                    st.session_state.lus = [
                        {"source": l["source"],
                         "notes": l["donnees"]["notes"],
                         "trimestre": (l["donnees"]["trimestre"]
                                       if l["donnees"]["trimestre"] in TRIMESTRES_ATTENDUS
                                       else i + 1),
                         "niveau": detecter_niveau(l["donnees"].get("classe")),
                         "rapport": l["rapport"]}
                        for i, l in enumerate(lus)
                    ]
    else:
        st.caption(f"Tu vas saisir tes {NB_BULLETINS} bulletins, l'un apres l'autre.")
        if st.button("Commencer la saisie", type="primary"):
            st.session_state.lus = [
                {"source": f"Trimestre {i + 1}", "notes": {},
                 "trimestre": i + 1, "niveau": NIVEAU_ATTENDU, "rapport": None}
                for i in range(NB_BULLETINS)
            ]
    if st.session_state.lus:
        st.divider()
        st.write(f"**Verifie et complete tes {len(MATIERES)} notes, "
                 "pour chacun des 2 bulletins.**")
        bulletins = []
        for i, bulletin in enumerate(st.session_state.lus):
            st.markdown(f"##### {bulletin['source']}")
            if bulletin["rapport"]:
                if bulletin["rapport"]["niveau"] == "CONFORME":
                    st.success(f"Bulletin reconnu - "
                               f"{bulletin['rapport']['pourcentage']}%")
                else:
                    st.warning(f"Bulletin reconnu, a completer - "
                               f"{bulletin['rapport']['pourcentage']}%")
            colonne1, colonne2 = st.columns(2)
            depart = (bulletin["trimestre"]
                      if bulletin["trimestre"] in TRIMESTRES_ATTENDUS else 1)
            trimestre = colonne1.selectbox("Trimestre", TRIMESTRES_ATTENDUS,
                                           index=depart - 1, key=f"t_{i}")
            if bulletin["niveau"] is None:
                niveau = colonne2.selectbox("Confirme ta classe", [6, 7, 8, 9],
                                            index=3,
                                            format_func=lambda n: NOMS_NIVEAUX[n],
                                            key=f"n_{i}")
            else:
                niveau = bulletin["niveau"]
                colonne2.text_input("Classe", value=NOMS_NIVEAUX[niveau],
                                    disabled=True, key=f"c_{i}")
            notes = tableau_notes(bulletin["notes"], f"tab_{i}")
            manquantes = [m for m in MATIERES if m not in notes]
            if manquantes:
                st.caption(f"Il manque {len(manquantes)} note(s) : "
                           + ", ".join(manquantes))
            else:
                moyenne = round(sum(notes.values()) / len(notes), 2)
                st.metric("Moyenne de ce trimestre", f"{moyenne} / 20")
            moyenne = (round(sum(notes.values()) / len(notes), 2)
                       if len(notes) == len(MATIERES) else None)
            bulletins.append({"source": bulletin["source"], "trimestre": trimestre,
                              "niveau": niveau, "notes": notes, "moyenne": moyenne})
            st.divider()
        erreurs = []
        mauvais = [b for b in bulletins if b["niveau"] != NIVEAU_ATTENDU]
        if mauvais:
            erreurs.append(f"Nous avons besoin de tes bulletins de "
                           f"{NOMS_NIVEAUX[NIVEAU_ATTENDU]}. Corrige la classe.")
        incomplets = [b for b in bulletins if len(b["notes"]) < len(MATIERES)]
        if incomplets:
            erreurs.append(f"Chaque bulletin doit contenir les {len(MATIERES)} "
                           "notes. Complete les cases vides.")
        if sorted(b["trimestre"] for b in bulletins) != TRIMESTRES_ATTENDUS:
            erreurs.append("Il faut un bulletin du trimestre 1 ET un du "
                           "trimestre 2. Corrige le trimestre.")
        if erreurs:
            for message in erreurs:
                st.error(message)
        elif st.button("Continuer ->", type="primary"):
            st.session_state.eleve["bulletins"] = bulletins
            st.session_state.lus = None
            aller("questionnaire")
    st.divider()
    if st.button("<- Retour"):
        st.session_state.lus = None
        aller("parcours")

# ==================== ETAPE 4 : LE QUESTIONNAIRE (COLLEGE) ====================
elif st.session_state.etape == "questionnaire":
    entete("Parcours College - 9eme annee", "Etape 3 sur 4 - Toi")
    liste = list(MATIERES.keys())
    st.write("**1. Quelle matiere preferes-tu ?**")
    st.caption("Celle que tu aimes le plus, meme si tu n'y as pas la meilleure note.")
    preferee = st.selectbox("Ma matiere preferee", liste,
                            label_visibility="collapsed")
    st.write("**2. Dans quelles matieres te sens-tu a l'aise ?**")
    st.caption("Celles ou tu comprends facilement, sans forcer.")
    alaise = st.multiselect("Je suis a l'aise en...", liste,
                            label_visibility="collapsed")
    st.write("**3. Quel metier aimerais-tu faire plus tard ?**")
    st.caption("Rien n'est definitif. Choisis ce qui t'attire le plus.")
    metiers = charger_metiers()
    noms = [m["nom"] for m in metiers] + [AUTRE]
    ambition = st.selectbox("Mon ambition", noms, label_visibility="collapsed")
    libre = ""
    if ambition == AUTRE:
        libre = st.text_input("Precise le metier",
                              placeholder="Exemple : pilote, cuisinier...")
    st.divider()
    colonne1, colonne2 = st.columns([1, 2])
    if colonne1.button("<- Retour"):
        aller("bulletin")
    if colonne2.button("Voir ma recommandation ->", type="primary"):
        if not alaise:
            st.error("Choisis au moins une matiere ou tu te sens a l'aise.")
        elif ambition == AUTRE and not libre.strip():
            st.error("Precise le metier qui t'interesse.")
        else:
            st.session_state.eleve["profil"] = {
                "matiere_preferee": preferee,
                "matieres_alaise": alaise,
                "ambition": ambition,
                "ambition_libre": libre.strip(),
            }
            enregistrer()
            aller("resultat")

# ==================== ETAPE 5 : LE RESULTAT (COLLEGE) ====================
elif st.session_state.etape == "resultat":
    eleve = st.session_state.eleve
    entete(f"{eleve['nom']} - ta recommandation", "Etape 4 sur 4 - Resultat")
    r = recommander(eleve)
    texte, fond = COULEURS_VOIE.get(r["situation"], COULEURS_VOIE["inconnue"])
    st.markdown(f"""
    <div class="bandeau" style="background:{fond}; color:{texte};">
      <div class="surtitre">CE QU'ON TE RECOMMANDE</div>
      <div class="titre">{r['voie'] or 'Donnees insuffisantes'}</div>
    </div>
    """, unsafe_allow_html=True)
    st.write(r["message"])
    colonne1, colonne2, colonne3 = st.columns(3)
    colonne1.metric("Moyenne", f"{r['moyenne']} / 20" if r["moyenne"] else "-")
    if r["tendance"] is not None:
        colonne2.metric("Evolution", f"{r['tendance']:+.2f} pt",
                        delta=f"{r['tendance']:+.2f}")
    else:
        colonne2.metric("Evolution", "-")
    colonne3.metric("Bulletins", len(eleve["bulletins"]))
    st.subheader("Ce que ca veut dire pour toi")
    if "ia_version" not in st.session_state:
        st.session_state.ia_version = 0
    cle = f"ia_{st.session_state.ia_version}"
    if cle not in st.session_state:
        if st.session_state.ia_version == 0:
            st.session_state[cle] = brouillon(contexte_ia(eleve, r),
                                              charger_voies())
        else:
            with st.spinner("L'assistant reformule... jusqu'a 2 minutes la premiere fois"):
                st.session_state[cle] = texte_ia(eleve, r,
                                                 st.session_state.ia_version)
    if st.session_state[cle]:
        contenu = st.session_state[cle].replace("\n\n", "<br><br>")
        st.markdown(f'<div class="carte">{contenu}</div>',
                    unsafe_allow_html=True)
    else:
        st.info("L'assistant n'a pas pu rediger. Le resume ci-dessus reste valable.")
    if disponible():
        if st.button("Explique-moi autrement"):
            st.session_state.ia_version += 1
            st.rerun()
    else:
        st.caption("Reformulation par IA indisponible (Ollama eteint).")
    if r["objectif_metier"]:
        st.subheader("Ton objectif")
        st.markdown(f'<div class="carte">{r["objectif_metier"]["message"]}</div>',
                    unsafe_allow_html=True)
    st.subheader("Les deux voies")
    vers_lycee = r["situation"] in ("favorable", "ouvert")
    onglet1, onglet2 = st.tabs(
        ["Lycee general (recommande)" if vers_lycee else "Lycee general",
         "LIC" if vers_lycee else "LIC (recommande)"])
    with onglet1:
        for ligne in r["description_lycee"]:
            st.write("- " + ligne)
    with onglet2:
        for ligne in r["description_lic"]:
            st.write("- " + ligne)
    st.subheader("Ton profil de notes")
    gauche, droite = st.columns(2)
    with gauche:
        st.markdown('<div class="carte"><div class="etiquette">Points forts</div>',
                    unsafe_allow_html=True)
        for matiere, note in r["points_forts"]:
            st.markdown(f'<div class="ligne-note"><span>{matiere}</span>'
                        f'<strong>{note}</strong></div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with droite:
        st.markdown('<div class="carte"><div class="etiquette">A renforcer</div>',
                    unsafe_allow_html=True)
        if r["a_renforcer"]:
            for matiere, note in r["a_renforcer"]:
                st.markdown(f'<div class="ligne-note"><span>{matiere}</span>'
                            f'<strong>{note}</strong></div>',
                            unsafe_allow_html=True)
        else:
            st.write("Aucune matiere sous 12. Continue comme ca.")
        st.markdown("</div>", unsafe_allow_html=True)
    # --- Alerte BEF : les 4 epreuves testees ---
    try:
        import unicodedata as _ud

        def _cle_bef(nom):
            n = _ud.normalize("NFD", str(nom)).encode("ascii", "ignore").decode().lower()
            if n.startswith("franc"):
                return "Francais"
            if n.startswith("math"):
                return "Mathematiques"
            if n.startswith("phys"):
                return "Physique-Chimie"
            if n.startswith("svt") or n.startswith("sciences de la vie"):
                return "SVT"
            return None

        _bulls = eleve.get("bulletins") or []
        _notes = {}
        for _b in _bulls:
            for _m, _n in (_b.get("notes") or {}).items():
                _c = _cle_bef(_m)
                if _c is not None:
                    try:
                        _notes.setdefault(_c, []).append(float(_n))
                    except (TypeError, ValueError):
                        pass
        _bef = {k: round(sum(v) / len(v), 2) for k, v in _notes.items() if v}
        _moys = [float(_b["moyenne"]) for _b in _bulls if _b.get("moyenne") is not None]
        _moy = sum(_moys) / len(_moys) if _moys else None
        _faibles = sorted([(k, v) for k, v in _bef.items() if v < 12], key=lambda t: t[1])

        if len(_bef) == 4 and _faibles and _moy is not None:
            st.markdown("---")
            st.error(
                "**Attention : le BEF ne teste que ces 4 matieres sur tes "
                + str(len(_bulls) and 14 or 14)
                + ".** Tes meilleures notes ne sont pas dedans."
            )
            st.markdown("#### Les 4 seules matieres qui comptent au BEF")
            _c = st.columns(4)
            for _i, _nom in enumerate(["Francais", "Mathematiques", "Physique-Chimie", "SVT"]):
                _v = _bef.get(_nom)
                _cf = {"Francais": "2", "Mathematiques": "2",
                       "Physique-Chimie": "1", "SVT": "0,5"}[_nom]
                _c[_i].metric(f"{_nom} (coef {_cf})", f"{_v:.1f}",
                              "sous le seuil" if _v < 12 else "correct",
                              delta_color="inverse" if _v < 12 else "off")

            _COEF_BEF = {"Francais": 2.0, "Mathematiques": 2.0,
                         "Physique-Chimie": 1.0, "SVT": 0.5}
            _TOT_BEF = sum(_COEF_BEF.values())
            _bef_now = sum(_bef[_k] * _COEF_BEF[_k] for _k in _COEF_BEF) / _TOT_BEF
            _adm_now = 0.6 * _moy + 0.4 * _bef_now
            _cible = {k: (12.0 if v < 12 else v) for k, v in _bef.items()}
            _bef_cible = sum(_cible[_k] * _COEF_BEF[_k] for _k in _COEF_BEF) / _TOT_BEF
            _adm_cible = 0.6 * _moy + 0.4 * _bef_cible

            _liste = ", ".join(f"**{_k}** ({_v:.1f})" for _k, _v in _faibles)
            st.markdown(
                "Aujourd'hui tu es en difficulte en " + _liste + ". "
                "Ces notes comptent double a l'examen, et l'examen pese 40 % "
                "de ton admission. Si elles ne montent pas d'ici la fin de "
                "l'annee, ta moyenne d'admission descendra, meme si le reste "
                "de ton bulletin est excellent."
            )

            if _moy - _adm_now >= 0.5:
                st.warning(
                    "**Ta moyenne de bulletin est de "
                    + f"{_moy:.2f}"
                    + ", mais ta moyenne d'admission estimee est de "
                    + f"{_adm_now:.2f}"
                    + ".** L'ecart vient de la : tes meilleures notes ne sont "
                    "pas testees au BEF. C'est sur ces 4 matieres que se joue "
                    "ton passage en Seconde."
                )

            st.markdown("#### Ce que tu gagnes si tu montes ces matieres a 12")
            _g1, _g2, _g3 = st.columns(3)
            _g1.metric("Si rien ne change", f"{_adm_now:.2f}")
            _g2.metric("Si tu atteins 12 partout", f"{_adm_cible:.2f}")
            _g3.metric("Tu gagnes", f"+{_adm_cible - _adm_now:.2f} pt")
            st.caption(
                "Simulation basee sur tes notes actuelles, en supposant que tu "
                "obtiennes au BEF les memes resultats que dans ton bulletin. "
                "Ce n'est pas une prediction de ta note reelle a l'examen."
            )
            st.info(
                "**Par quoi commencer :** prends la matiere la plus basse en "
                "premier, c'est elle qui te fait gagner le plus vite. Demande a "
                "ton professeur les annales du BEF des annees passees, et "
                "travaille un peu chaque jour plutot que beaucoup la veille."
            )
            st.markdown("---")
    except Exception:
        pass

    st.subheader("Le BEF compte pour 40 %")
    st.write("Ta moyenne d'admission = **60 % ta moyenne de l'annee "
             "+ 40 % ta note au BEF**. Le BEF porte sur 3 epreuves : "
             "Francais (coef 2), Mathematiques (coef 2) et Sciences, "
             "elle-meme divisee en Physique-Chimie (coef 1) et SVT (coef 0,5). "
             "Total des coefficients : 5,5.")
    if r["tableau_bef"]:
        tableau = pd.DataFrame(r["tableau_bef"])
        tableau.columns = ["Note au BEF", "Ta moyenne d'admission"]
        st.bar_chart(tableau.set_index("Note au BEF"), height=250)
        st.caption("Chaque point gagne au BEF fait monter ton admission de "
                   "0,4 point. Il n'y a pas de note magique : plus tu montes, "
                   "plus tu remontes dans le classement.")
    st.divider()
    st.markdown('<div class="avert">Cette recommandation est une aide a la '
                'reflexion, pas une decision. L\'affectation en Seconde est '
                'prononcee par la commission du MENFOP, au classement. '
                'Parles-en avec tes professeurs et le Service d\'Orientation '
                'de ton etablissement.</div>', unsafe_allow_html=True)
    st.divider()
    if st.button("Recommencer"):
        st.session_state.clear()
        st.rerun()

# ==================== ETAPE S1 : LES BULLETINS (SECONDE) ====================
elif st.session_state.etape == "bulletin_seconde":
    entete("Seconde - Lycee general", "Etape 2 sur 4 - Tes notes")
    st.write("**Etudies-tu le Chinois ou le Turc cette annee ?**")
    st.caption("Cette langue ne compte pas dans le choix de ta serie : "
               "c'est juste pour t'encourager a continuer si tu la suis.")
    choix_langue = st.radio(
        "Langue rare", ["Aucune", "Chinois", "Turc"],
        horizontal=True, label_visibility="collapsed", key="langue_rare_choice")
    matieres_seconde_liste = list(MATIERES_SECONDE)
    if choix_langue != "Aucune":
        matieres_seconde_liste = matieres_seconde_liste + [choix_langue]
    st.divider()
    complement = (f" (+ {choix_langue}, a titre indicatif)."
                  if choix_langue != "Aucune" else ".")
    st.info(f"**Les 2 bulletins sont obligatoires** : trimestre 1 ET "
            f"trimestre 2, avec les {len(MATIERES_SECONDE)} notes de chacun"
            + complement)
    if st.session_state.lus_seconde is None:
        if st.button("Commencer la saisie", type="primary", key="debut_saisie_seconde"):
            st.session_state.lus_seconde = [
                {"source": f"Trimestre {i + 1}", "trimestre": i + 1, "notes": {}}
                for i in range(NB_BULLETINS_SECONDE)
            ]
            st.rerun()
    if st.session_state.lus_seconde:
        bulletins = []
        for i, bulletin in enumerate(st.session_state.lus_seconde):
            st.markdown(f"##### {bulletin['source']}")
            notes = tableau_notes_seconde(bulletin["notes"], f"tab_sec_{i}",
                                          matieres_seconde_liste)
            manquantes = [m for m in matieres_seconde_liste if m not in notes]
            if manquantes:
                st.caption(f"Il manque {len(manquantes)} note(s) : "
                           + ", ".join(manquantes))
            else:
                notes_base = {m: n for m, n in notes.items() if m in MATIERES_SECONDE}
                moyenne = round(sum(notes_base.values()) / len(notes_base), 2)
                st.metric("Moyenne de ce trimestre", f"{moyenne} / 20")
            bulletins.append({"source": bulletin["source"],
                              "trimestre": bulletin["trimestre"], "notes": notes})
            st.divider()
        incomplets = [b for b in bulletins if len(
            [m for m in matieres_seconde_liste if m in b["notes"]]
        ) < len(matieres_seconde_liste)]
        if incomplets:
            st.error("Complete les notes manquantes avant de continuer.")
        elif st.button("Continuer ->", type="primary", key="continuer_seconde"):
            st.session_state.eleve["bulletins"] = bulletins
            st.session_state.eleve["langue_rare"] = (
                choix_langue if choix_langue != "Aucune" else None)
            st.session_state.lus_seconde = None
            aller("questionnaire_seconde")
    st.divider()
    if st.button("<- Retour", key="retour_bulletin_seconde"):
        st.session_state.lus_seconde = None
        aller("niveau_lycee")

# ==================== ETAPE S2 : LE QUESTIONNAIRE (SECONDE) ====================
elif st.session_state.etape == "questionnaire_seconde":
    entete("Seconde - Lycee general", "Etape 3 sur 4 - Toi")
    st.caption("Tes reponses ici ne changent rien au calcul de ta serie : "
               "la recommandation reste basee a 100% sur tes notes, comme "
               "au college. Elles servent seulement a personnaliser ce "
               "qu'on te dit ensuite.")
    liste = list(MATIERES_SECONDE)
    st.write("**1. Quelle matiere preferes-tu ?**")
    st.caption("Celle que tu aimes le plus, meme si tu n'y as pas la meilleure note.")
    preferee = st.selectbox("Ma matiere preferee", liste,
                            label_visibility="collapsed", key="preferee_seconde")
    st.write("**2. Dans quelles matieres te sens-tu a l'aise ?**")
    st.caption("Celles ou tu comprends facilement, sans forcer.")
    alaise = st.multiselect("Je suis a l'aise en...", liste,
                            label_visibility="collapsed", key="alaise_seconde")
    st.write("**3. Quel metier aimerais-tu faire plus tard ?**")
    st.caption("Rien n'est definitif. Choisis ce qui t'attire le plus.")
    metiers = charger_metiers()
    noms = [m["nom"] for m in metiers] + [AUTRE]
    ambition = st.selectbox("Mon ambition", noms, label_visibility="collapsed",
                            key="ambition_seconde")
    libre = ""
    if ambition == AUTRE:
        libre = st.text_input("Precise le metier",
                              placeholder="Exemple : pilote, cuisinier...",
                              key="ambition_libre_seconde")
    st.divider()
    colonne1, colonne2 = st.columns([1, 2])
    if colonne1.button("<- Retour", key="retour_questionnaire_seconde"):
        aller("bulletin_seconde")
    if colonne2.button("Voir ma recommandation ->", type="primary", key="voir_reco_seconde"):
        if not alaise:
            st.error("Choisis au moins une matiere ou tu te sens a l'aise.")
        elif ambition == AUTRE and not libre.strip():
            st.error("Precise le metier qui t'interesse.")
        else:
            st.session_state.eleve["profil"] = {
                "matiere_preferee": preferee,
                "matieres_alaise": alaise,
                "ambition": ambition,
                "ambition_libre": libre.strip(),
            }
            enregistrer()
            aller("resultat_seconde")

# ==================== ETAPE S3 : LE RESULTAT (SECONDE) ====================
elif st.session_state.etape == "resultat_seconde":
    eleve = st.session_state.eleve
    entete(f"{eleve['nom']} - ta recommandation de serie", "Etape 4 sur 4 - Resultat")
    r = recommander_seconde(eleve)
    texte, fond = COULEURS_VOIE.get(r["situation"], COULEURS_VOIE["inconnue"])
    if r["situation"] in ("alerte", "remontee"):
        surtitre = "AVANT DE PARLER DE SERIE"
        titre_bandeau = "Consolider d'abord tes bases"
    elif r["situation"] == "favorable":
        surtitre = "CE QU'ON TE RECOMMANDE"
        titre_bandeau = (f"Serie {r['serie_recommandee']} - "
                         f"{NOMS_SERIES.get(r['serie_recommandee'], '')}")
    elif r["situation"] == "ouvert":
        surtitre = "LA SERIE QUI SE DESSINE, POUR L'INSTANT"
        titre_bandeau = (f"Serie {r['serie_recommandee']} - "
                         f"{NOMS_SERIES.get(r['serie_recommandee'], '')}"
                         if r["serie_recommandee"] else "Donnees insuffisantes")
    else:
        surtitre = "EN ATTENTE DE NOTES"
        titre_bandeau = "Donnees insuffisantes"
    st.markdown(f"""
    <div class="bandeau" style="background:{fond}; color:{texte};">
      <div class="surtitre">{surtitre}</div>
      <div class="titre">{titre_bandeau}</div>
    </div>
    """, unsafe_allow_html=True)
    st.write(r["message"])
    colonne1, colonne2, colonne3 = st.columns(3)
    colonne1.metric("Moyenne generale", f"{r['moyenne']} / 20" if r["moyenne"] else "-")
    if r["tendance"] is not None:
        colonne2.metric("Evolution", f"{r['tendance']:+.2f} pt",
                        delta=f"{r['tendance']:+.2f}")
    else:
        colonne2.metric("Evolution", "-")
    colonne3.metric("Bulletins", len(eleve["bulletins"]))
    st.subheader("Ce que ca veut dire pour toi")
    if "ia_version_seconde" not in st.session_state:
        st.session_state.ia_version_seconde = 0
    cle_ia = f"ia_seconde_{st.session_state.ia_version_seconde}"
    if cle_ia not in st.session_state:
        if st.session_state.ia_version_seconde == 0:
            st.session_state[cle_ia] = brouillon_seconde(
                contexte_ia_seconde(eleve, r), charger_voies())
        else:
            with st.spinner("L'assistant reformule... jusqu'a 2 minutes la premiere fois"):
                st.session_state[cle_ia] = texte_ia_seconde(
                    eleve, r, st.session_state.ia_version_seconde)
    if st.session_state[cle_ia]:
        contenu_ia = st.session_state[cle_ia].replace("\n\n", "<br><br>")
        st.markdown(f'<div class="carte">{contenu_ia}</div>',
                    unsafe_allow_html=True)
    else:
        st.info("L'assistant n'a pas pu rediger. Le resume ci-dessus reste valable.")
    if disponible():
        if st.button("Explique-moi autrement", key="reformuler_seconde"):
            st.session_state.ia_version_seconde += 1
            st.rerun()
    else:
        st.caption("Reformulation par IA indisponible (Ollama eteint).")
    if r["situation"] in ("alerte", "remontee"):
        st.markdown(
            '<div class="avert">Tant que le trimestre n\'est pas valide '
            '(moyenne generale sous 10/20), aucune serie n\'est recommandee. '
            'Ce n\'est pas une sanction : c\'est pour eviter un faux espoir '
            'sur une serie que tu ne pourrais pas suivre. Si le niveau ne '
            'remonte pas, le redoublement devient un risque reel - '
            'parles-en cette semaine a ton professeur principal et a tes '
            'parents.</div>', unsafe_allow_html=True)
    else:
        st.subheader("Classement des 4 series")
        st.caption("Coche = tu valides les conditions de cette serie. Les "
                   "autres restent visibles pour que tu voies ou tu en es, "
                   "mais elles ne sont pas encore confirmees.")
        for ligne in r["classement"]:
            valide = ligne["valide"]
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{'[OK] ' if valide else ''}{ligne['serie']} - "
                           f"{ligne['nom_complet']}**")
                c2.metric("Score", ligne["score"] if ligne["score"] is not None else "-")
                if not valide and ligne["manques"]:
                    st.caption("Pour valider cette serie, il manque : "
                              + "; ".join(ligne["manques"]))
        if r["specialites_sg"]:
            st.subheader("Sciences de Gestion : quelle specialite ?")
            st.caption("Le choix entre IAG, OGRH et GFM se precise vraiment "
                       "en Premiere, mais voici ce que tes notes actuelles "
                       "indiquent (l'IG est une matiere de la SG, elle ne "
                       "compte pas dans le choix entre les 4 series ci-dessus).")
            detail = r["specialites_sg"]["detail"]
            for nom_spe, (valide_spe, manques_spe) in detail.items():
                with st.container(border=True):
                    st.markdown(f"**{'[OK] ' if valide_spe else ''}{nom_spe} - "
                               f"{SPECIALITES_SG[nom_spe]}**")
                    if not valide_spe and manques_spe:
                        st.caption("Il manque : " + "; ".join(manques_spe))
            if r["note_ig"] is not None:
                st.caption(f"Ta note d'IG actuelle : {r['note_ig']}/20 (indicative).")
    if r["langue_rare"]:
        st.info(f"Tu suis aussi le {r['langue_rare']} : ce n'est pas compte "
                "dans le choix de serie, mais continue - c'est un vrai "
                "atout a garder.")
    profil = eleve.get("profil", {})
    if profil.get("ambition"):
        metier_txt = (profil["ambition_libre"] if profil["ambition"] == AUTRE
                     and profil.get("ambition_libre") else profil["ambition"])
        st.subheader("Ton objectif")
        st.markdown(
            f'<div class="carte">Tu vises {metier_txt}. Garde cet objectif '
            'en tete pour choisir, si plusieurs series te sont ouvertes : '
            'le calcul ci-dessus ne regarde que tes notes, a toi de voir '
            'ensuite laquelle sert le mieux ce metier.</div>',
            unsafe_allow_html=True)
    st.subheader("Ton profil de notes")
    gauche, droite = st.columns(2)
    with gauche:
        st.markdown('<div class="carte"><div class="etiquette">Points forts</div>',
                    unsafe_allow_html=True)
        if r["points_forts"]:
            for matiere, note in r["points_forts"]:
                st.markdown(f'<div class="ligne-note"><span>{matiere}</span>'
                            f'<strong>{note}</strong></div>', unsafe_allow_html=True)
        else:
            st.write("Aucune matiere n'atteint encore 12/20. La priorite "
                     "est de faire remonter ces notes avant de parler de "
                     "points forts.")
        st.markdown("</div>", unsafe_allow_html=True)
    with droite:
        st.markdown('<div class="carte"><div class="etiquette">A renforcer</div>',
                    unsafe_allow_html=True)
        if r["a_renforcer"]:
            for matiere, note in r["a_renforcer"]:
                st.markdown(f'<div class="ligne-note"><span>{matiere}</span>'
                            f'<strong>{note}</strong></div>', unsafe_allow_html=True)
        else:
            st.write("Aucune matiere sous 12. Continue comme ca.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.divider()
    st.markdown(
        '<div class="avert">Cette recommandation est une aide a la '
        'reflexion, pas une decision. Le passage en serie est prononce par '
        'le conseil de classe. Parles-en avec tes professeurs et le '
        'Service d\'Orientation de ton etablissement.</div>',
        unsafe_allow_html=True)
    st.divider()
    if st.button("Recommencer", key="recommencer_seconde"):
        st.session_state.clear()
        st.rerun()

# ==================== ETAPE T1 : LES BULLETINS ET LE BAC (TERMINALE) ====================
elif st.session_state.etape == "bulletin_terminale":
    entete("Terminale - apres le bac", "Etape 2 sur 4 - Tes bulletins et ton bac")
    st.write("**Quelle etait ta serie ?**")
    serie = st.radio(
        "Serie", ["S", "ES", "L", "SG"], horizontal=True,
        format_func=lambda s: f"{s} - {NOMS_SERIES.get(s, s)}",
        label_visibility="collapsed", key="serie_terminale")
    donnees_t = charger_filieres_terminale()
    matieres_serie = donnees_t["matieres_par_serie"].get(serie, [])

    st.write("**As-tu suivi le Chinois ou le Turc pendant le lycee ?**")
    st.caption("Cette langue ne compte pas dans ton classement : c'est "
               "juste pour te feliciter si tu l'as continuee.")
    choix_langue_t = st.radio(
        "Langue rare", ["Aucune", "Chinois", "Turc"],
        horizontal=True, label_visibility="collapsed", key="langue_rare_terminale")

    st.divider()
    st.write(f"**Saisis tes {NB_CARNETS_TERMINALE} bulletins de l'annee de "
             f"Terminale** (trimestre 1, 2 et 3), comme au College.")
    st.caption("Ces notes ne changent pas ton classement (il reste base a "
               "100% sur ton releve du bac ci-dessous) : elles servent juste "
               "a montrer ton chemin sur l'annee.")
    if st.session_state.lus_terminale is None:
        st.session_state.lus_terminale = [
            {"trimestre": i + 1, "notes": {}} for i in range(NB_CARNETS_TERMINALE)
        ]
    carnets = []
    for i, carnet in enumerate(st.session_state.lus_terminale):
        st.markdown(f"##### Trimestre {carnet['trimestre']}")
        notes_carnet = tableau_notes_terminale(
            carnet["notes"], f"tab_carnet_t_{i}", matieres_serie)
        if matieres_serie and len(notes_carnet) == len(matieres_serie):
            moyenne_carnet = round(sum(notes_carnet.values()) / len(notes_carnet), 2)
            st.metric(f"Moyenne trimestre {carnet['trimestre']}", f"{moyenne_carnet} / 20")
        carnets.append(notes_carnet)
        st.divider()

    st.write(f"**Saisis tes notes officielles du bac** "
             f"({len(matieres_serie)} matieres pour la serie {serie}).")
    st.caption("Ce sont les notes du releve officiel du bac, pas celles "
               "d'un bulletin de classe.")
    notes = tableau_notes_terminale(
        st.session_state.eleve.get("releve_bac", {}),
        "tab_releve_bac", matieres_serie)
    manquantes = [m for m in matieres_serie if m not in notes]
    mention_calculee = None
    bac_obtenu = True
    if manquantes:
        st.caption(f"Il manque {len(manquantes)} note(s) : "
                   + ", ".join(manquantes))
    else:
        moyenne = round(sum(notes.values()) / len(notes), 2)
        st.metric("Moyenne generale du releve", f"{moyenne} / 20")
        if moyenne >= 16:
            mention_calculee = "Tres Bien"
        elif moyenne >= 14:
            mention_calculee = "Bien"
        elif moyenne >= 12:
            mention_calculee = "Assez Bien"
        elif moyenne >= 10:
            mention_calculee = "Passable"
        else:
            bac_obtenu = False
        if not bac_obtenu:
            st.error("Avec cette moyenne (en dessous de 10), le bac n'est "
                     "pas obtenu : l'annee est a redoubler. Cet outil est "
                     "fait pour les eleves qui ont deja leur bac.")
        elif mention_calculee == "Passable":
            st.success("Mention calculee : Passable (pas de mention specifique).")
        else:
            st.success(f"Mention calculee : {mention_calculee}")
    st.divider()
    colonne1, colonne2 = st.columns([1, 2])
    if colonne1.button("<- Retour", key="retour_bulletin_terminale"):
        st.session_state.lus_terminale = None
        aller("niveau_lycee")
    if colonne2.button("Continuer ->", type="primary", key="continuer_terminale"):
        if manquantes:
            st.error("Complete toutes tes notes du releve du bac avant de continuer.")
        elif not bac_obtenu:
            st.error("Tu ne peux pas continuer : la moyenne du releve est inferieure a 10.")
        else:
            st.session_state.eleve["serie"] = serie
            st.session_state.eleve["releve_bac"] = notes
            st.session_state.eleve["carnets"] = carnets
            st.session_state.eleve["mention"] = (
                None if mention_calculee == "Passable" else mention_calculee)
            st.session_state.eleve["langue_rare"] = (
                None if choix_langue_t == "Aucune" else choix_langue_t)
            aller("questionnaire_terminale")

# ==================== ETAPE T2 : LE QUESTIONNAIRE (TERMINALE) ====================
elif st.session_state.etape == "questionnaire_terminale":
    entete("Terminale - apres le bac", "Etape 3 sur 4 - Toi")
    st.caption("Tes reponses ici ne changent rien au calcul de ton classement : "
               "il reste base a 100% sur ton releve du bac. Elles servent "
               "seulement a departager les filieres tres proches chez toi, "
               "et a personnaliser ce qu'on te dit ensuite.")
    serie_t = st.session_state.eleve.get("serie")
    donnees_t = charger_filieres_terminale()
    liste_t = donnees_t["matieres_par_serie"].get(serie_t, [])
    st.write("**1. Quelles matieres preferes-tu ?**")
    st.caption("Celles que tu aimes le plus, meme si tu n'y as pas la meilleure note.")
    preferees = st.multiselect("Mes matieres preferees", liste_t,
                               label_visibility="collapsed", key="preferees_terminale")
    st.write("**2. Dans quelles matieres te sens-tu a l'aise ?**")
    st.caption("Celles ou tu comprends facilement, sans forcer.")
    alaise_t = st.multiselect("Je suis a l'aise en...", liste_t,
                              label_visibility="collapsed", key="alaise_terminale")
    st.write("**3. Quel metier aimerais-tu faire plus tard ?**")
    st.caption("Facultatif. Ca nous aide seulement a departager des "
               "filieres tres proches chez toi.")
    metier_t = st.text_input(
        "Mon ambition", placeholder="Exemple : ingenieur, medecin...",
        key="metier_terminale")
    st.divider()
    colonne1, colonne2 = st.columns([1, 2])
    if colonne1.button("<- Retour", key="retour_questionnaire_terminale"):
        aller("bulletin_terminale")
    if colonne2.button("Voir ma recommandation ->", type="primary", key="voir_reco_terminale"):
        st.session_state.eleve["profil"] = {
            "matieres_preferees": preferees,
            "matieres_a_l_aise": alaise_t,
            "domaines_preferes": [],
            "metier_vise": metier_t.strip(),
        }
        enregistrer()
        aller("resultat_terminale")

# ==================== ETAPE T3 : LE RESULTAT (TERMINALE) ====================
elif st.session_state.etape == "resultat_terminale":
    eleve = st.session_state.eleve
    entete(f"{eleve['nom']} - ton classement des 18 filieres", "Etape 4 sur 4 - Resultat")
    r = recommander_terminale(eleve)
    donnees_t = charger_filieres_terminale()
    premier = r["classement"][0]
    fond_ok, texte_ok = COULEURS_VOIE["favorable"][1], COULEURS_VOIE["favorable"][0]
    st.markdown(f"""
    <div class="bandeau" style="background:{fond_ok}; color:{texte_ok};">
      <div class="surtitre">TA FILIERE LA MIEUX CLASSEE</div>
      <div class="titre">{premier['nom']}</div>
    </div>
    """, unsafe_allow_html=True)
    colonne1, colonne2, colonne3 = st.columns(3)
    colonne1.metric("Serie", eleve.get("serie") or "-")
    colonne2.metric("Mention", eleve.get("mention") or "Sans mention")
    colonne3.metric("Filieres calculables", 18 - len(r["non_calculables"]))
    if eleve.get("langue_rare"):
        st.info(f"Tu as aussi suivi le {eleve['langue_rare']} au lycee : ce "
                "n'est pas compte dans ton classement, mais c'est un vrai "
                "atout a garder.")
    st.subheader("Ce que ca veut dire pour toi")
    if "ia_version_terminale" not in st.session_state:
        st.session_state.ia_version_terminale = 0
    cle_ia_t = f"ia_terminale_{st.session_state.ia_version_terminale}"
    if cle_ia_t not in st.session_state:
        if st.session_state.ia_version_terminale == 0:
            st.session_state[cle_ia_t] = brouillon_terminale(
                r, eleve, donnees_t.get("familles"))
        else:
            with st.spinner("L'assistant reformule... jusqu'a 2 minutes la premiere fois"):
                st.session_state[cle_ia_t] = rediger_terminale(
                    r, eleve, donnees_t.get("familles"))
    if st.session_state[cle_ia_t]:
        contenu_t = st.session_state[cle_ia_t].replace("\n\n", "<br><br>")
        st.markdown(f'<div class="carte">{contenu_t}</div>',
                    unsafe_allow_html=True)
    else:
        st.info("L'assistant n'a pas pu rediger. Le classement ci-dessous reste valable.")
    if disponible():
        if st.button("Explique-moi autrement", key="reformuler_terminale"):
            st.session_state.ia_version_terminale += 1
            st.rerun()
    else:
        st.caption("Reformulation par IA indisponible (Ollama eteint).")
    st.subheader("Ton classement des 18 filieres")
    st.caption("Classe du rang 1 au rang 18, en tenant compte de tes notes "
               "puis de tes preferences en cas de quasi-egalite. Seules les "
               "filieres ouvertes a ta serie sont classees.")
    classables = [l for l in r["classement"] if l["calculable"]]
    lignes_tableau = [
        {"Rang": i + 1, "Filiere": l["nom"]}
        for i, l in enumerate(classables)
    ]
    st.dataframe(pd.DataFrame(lignes_tableau), hide_index=True, width="stretch")
    st.subheader("Les 4 filieres sur concours")
    st.caption("Admission par epreuve ecrite, independante de ce classement. "
               "Ouvertes a toutes les series.")
    for c in r["concours"]:
        corr = c["correspondance"]
        with st.container(border=True):
            st.markdown(f"**{c['nom']}**")
            st.caption(corr["message"])
    st.divider()
    st.subheader("Autres portes apres le bac")
    st.caption("En plus du classement ci-dessus : des bourses a l'etranger "
               "et une universite privee a Djibouti. Rien n'est garanti, "
               "mais tenter sa chance ne coute rien.")
    donnees_bourses = charger_bourses_privees()
    for b in donnees_bourses["bourses"]:
        with st.container(border=True):
            st.markdown(f"**{b['nom']}** - {b['pour_qui']}")
            st.write(b["description"])
            st.caption(b["procedure"])
            if b.get("lien"):
                st.markdown(f"[Site officiel]({b['lien']})")
    for u in donnees_bourses["universites_privees"]:
        with st.container(border=True):
            st.markdown(f"**{u['nom']}** - {u['type']}")
            st.write(f"{u['diplomes']} - cours en {u['langues']}")
            st.caption(f"{u['adresse']} - Tel : "
                       + " / ".join(u["telephones"]))
    st.divider()
    st.markdown(
        '<div class="avert">Ce classement est une aide a la reflexion, pas '
        'une decision. L\'affectation definitive est prononcee par '
        'l\'universite de Djibouti, au classement et selon les places '
        'disponibles. Parles-en avec le Service d\'Orientation.</div>',
        unsafe_allow_html=True)
    st.divider()
    if st.button("Recommencer", key="recommencer_terminale"):
        st.session_state.clear()
        st.rerun()

# ==================== LIC / FORMATION PROFESSIONNELLE (information seule) ====================
elif st.session_state.etape == "formation_pro":
    entete("Formation professionnelle", "LIC et reseau technique national - information, pas un classement")
    st.write(
        "Contrairement au College, a la Seconde et a la Terminale, cette "
        "page ne calcule aucun classement : les metiers manuels et "
        "techniques dependent trop de ton lieu de vie et de tes gouts "
        "personnels pour etre notes comme les filieres universitaires. "
        "C'est juste une information claire et a jour sur ce qui existe "
        "reellement, partout dans le pays."
    )
    donnees_pro = charger_formation_pro()

    with st.expander("Comprendre les niveaux de diplome (CFP, CAP, BAC PRO, BTS)"):
        for niveau in donnees_pro["niveaux_diplomes"]:
            st.markdown(f"**{niveau['code']}** - {niveau['nom']}")
            st.caption(f"{niveau['description_simple']} (apres : {niveau['apres']})")

    st.divider()
    st.write("**Dans quelle region habites-tu ?**")
    noms_regions = [r["nom"] for r in donnees_pro["regions"]]
    region_choisie = st.radio(
        "Region", noms_regions, horizontal=True,
        label_visibility="collapsed", key="region_formation_pro")
    region = next(r for r in donnees_pro["regions"] if r["nom"] == region_choisie)

    for etablissement in region["etablissements"]:
        st.subheader(etablissement["nom"])
        st.caption(etablissement["type"])
        if etablissement.get("note"):
            st.info(etablissement["note"])
        groupes = filieres_par_domaine(etablissement)
        for domaine, filieres in groupes.items():
            st.markdown(f'<div class="carte"><div class="etiquette">{domaine}</div>',
                        unsafe_allow_html=True)
            for f in filieres:
                st.markdown(f'<div class="ligne-note"><span>{f["nom"]}</span>'
                            f'<strong>{f["niveau"]}</strong></div>',
                            unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        st.divider()

    st.markdown(
        '<div class="avert">Cette liste vient de la carte scolaire '
        'officielle du MENFOP (2026-2027). Les places disponibles changent '
        'chaque annee : renseigne-toi directement aupres de l\'etablissement '
        'ou du MENFOP pour les conditions d\'entree.</div>',
        unsafe_allow_html=True)
    st.divider()
    if st.button("<- Retour", key="retour_formation_pro"):
        aller("parcours")