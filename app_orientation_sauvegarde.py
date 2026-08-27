"""
Assistant d'orientation scolaire - Republique de Djibouti
Parcours College : apres la 9eme annee, Lycee general ou LIC.
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
from modules.redaction import disponible, rediger, charger_voies


st.set_page_config(page_title="Orientation Djibouti", page_icon="🎓",
                   layout="centered")

BLEU = "#6AB2E7"
VERT = "#12AD2B"
ROUGE = "#D7141A"

DOSSIER_SORTIE = os.path.join("data", "bulletins")
AUTRE = "Autre — je precise moi-meme"
NIVEAU_ATTENDU = 9
NB_BULLETINS = 2
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


def aller(etape):
    st.session_state.etape = etape
    st.rerun()


def entete(sous_titre, fil=""):
    st.markdown(f"""
    <div class="entete">
      <div class="etoile">★</div>
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
    """
    Tableau verrouille : exactement les 14 matieres officielles.
    L'eleve ne peut ni ajouter, ni supprimer, ni renommer une matiere.
    Il ne peut que saisir ou corriger les notes.
    """
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


def texte_ia(eleve, r, graine=0):
    """Demande a Ollama d'expliquer le resultat avec ses propres mots."""
    profil = eleve.get("profil", {})
    contexte = {
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
    demande = ("Explique a cet eleve la voie qui se dessine pour lui, en citant "
               "ses vraies notes. Presente cette voie avec tes propres mots a "
               "partir de la base. Relie-la a ce qu'il aime et au metier qu'il "
               "vise. Termine par deux ou trois conseils concrets, reformules, "
               "et rappelle que rien n'est encore decide.")
    return rediger(contexte, demande, charger_voies())


def enregistrer():
    os.makedirs(DOSSIER_SORTIE, exist_ok=True)
    nom_fichier = normaliser(st.session_state.eleve["nom"]).replace(" ", "_") + ".json"
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

    if st.button("Commencer →", type="primary"):
        if not prenom.strip() or not nom_famille.strip():
            st.error("Merci d'entrer ton prenom et ton nom.")
        else:
            st.session_state.eleve["nom"] = f"{prenom.strip()} {nom_famille.strip()}"
            aller("parcours")

    st.markdown('<div class="avert">Tes donnees restent sur cet appareil. '
                'Rien n\'est envoye sur Internet.</div>', unsafe_allow_html=True)


# ==================== ETAPE 2 : PARCOURS ====================

elif st.session_state.etape == "parcours":
    entete(f"Bonjour {st.session_state.eleve['nom']} 👋", "Etape 1 sur 4")

    st.write("**Ou en es-tu dans ta scolarite ?**")

    colonne1, colonne2, colonne3 = st.columns(3)

    with colonne1:
        with st.container(border=True):
            st.markdown("### 🏫")
            st.markdown("**Collège**")
            st.caption("9ème année — vers le Lycée général ou le LIC")
            if st.button("Choisir", key="p_college", type="primary"):
                st.session_state.eleve["parcours"] = "college"
                aller("bulletin")

    with colonne2:
        with st.container(border=True):
            st.markdown("### 📗")
            st.markdown("**Lycee general**")
            st.caption("Seconde ou Terminale")
            if st.button("Choisir", key="p_lycee", type="primary"):
                aller("niveau_lycee")

    with colonne3:
        with st.container(border=True):
            st.markdown("### 🎓")
            st.markdown("**LIC**")
            st.caption("Lycee Industriel et Commercial")
            st.button("En cours de developpement", key="p_lic", disabled=True)

    st.divider()
    if st.button("← Retour"):
        aller("accueil")


# ==================== ETAPE 2b : NIVEAU AU LYCEE ====================

elif st.session_state.etape == "niveau_lycee":
    entete("Lycee general", "Etape 1 sur 4 · Ton niveau")

    st.write("**Dans quelle classe es-tu ?**")

    colonne1, colonne2 = st.columns(2)

    with colonne1:
        with st.container(border=True):
            st.markdown("### 📗")
            st.markdown("**Seconde**")
            st.caption("Choix de la serie : S, ES, L, GFM, IAG ou OGRH")
            st.button("En cours de developpement", key="n_seconde", disabled=True)

    with colonne2:
        with st.container(border=True):
            st.markdown("### 🎓")
            st.markdown("**Terminale**")
            st.caption("Choix des filieres universitaires")
            st.button("En cours de developpement", key="n_terminale", disabled=True)

    st.divider()
    if st.button("← Retour"):
        aller("parcours")


# ==================== ETAPE 3 : LES BULLETINS ====================

elif st.session_state.etape == "bulletin":
    entete("Parcours College — 9eme annee", "Etape 2 sur 4 · Tes notes")

    st.info(f"**Les 2 bulletins sont obligatoires** : trimestre 1 ET trimestre 2 "
            f"de {NOMS_NIVEAUX[NIVEAU_ATTENDU]}, avec les {len(MATIERES)} notes "
            "de chacun. Sans les deux, l'analyse ne serait pas fiable.")

    mode = st.radio("Comment veux-tu entrer tes notes ?",
                    ["📷 Importer une photo", "✍️ Saisir a la main"],
                    horizontal=True)

    if mode.startswith("📷"):
        st.caption("Pose ton bulletin a plat, photographie-le bien droit, "
                   "toute la feuille dans le cadre.")

        fichiers = st.file_uploader(
            f"Tes {NB_BULLETINS} bulletins (trimestre 1 et trimestre 2)",
            type=["png", "jpg", "jpeg"], accept_multiple_files=True)

        if st.button("🔍 Analyser", type="primary"):
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
                    st.error("❌ Ce document n'est pas un bulletin scolaire : "
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
        if st.button("✍️ Commencer la saisie", type="primary"):
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
            st.markdown(f"##### 📄 {bulletin['source']}")

            if bulletin["rapport"]:
                if bulletin["rapport"]["niveau"] == "CONFORME":
                    st.success(f"✅ Bulletin reconnu — "
                               f"{bulletin['rapport']['pourcentage']}%")
                else:
                    st.warning(f"⚠️ Bulletin reconnu, a completer — "
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
                st.caption(f"⚠️ Il manque {len(manquantes)} note(s) : "
                           + ", ".join(manquantes))
            else:
                moyenne = round(sum(notes.values()) / len(notes), 2)
                st.metric("Moyenne de ce trimestre", f"{moyenne} / 20")

            moyenne = (round(sum(notes.values()) / len(notes), 2)
                       if len(notes) == len(MATIERES) else None)

            bulletins.append({"source": bulletin["source"], "trimestre": trimestre,
                              "niveau": niveau, "notes": notes, "moyenne": moyenne})
            st.divider()

        # ---- Controles avant de continuer ----
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
                st.error("❌ " + message)
        elif st.button("Continuer →", type="primary"):
            st.session_state.eleve["bulletins"] = bulletins
            st.session_state.lus = None
            aller("questionnaire")

    st.divider()
    if st.button("← Retour"):
        st.session_state.lus = None
        aller("parcours")


# ==================== ETAPE 4 : LE QUESTIONNAIRE ====================

elif st.session_state.etape == "questionnaire":
    entete("Parcours College — 9eme annee", "Etape 3 sur 4 · Toi")

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

    if colonne1.button("← Retour"):
        aller("bulletin")

    if colonne2.button("Voir ma recommandation →", type="primary"):
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


# ==================== ETAPE 5 : LE RESULTAT ====================

elif st.session_state.etape == "resultat":
    eleve = st.session_state.eleve
    entete(f"{eleve['nom']} — ta recommandation", "Etape 4 sur 4 · Resultat")

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
    colonne1.metric("Moyenne", f"{r['moyenne']} / 20" if r["moyenne"] else "—")
    if r["tendance"] is not None:
        colonne2.metric("Evolution", f"{r['tendance']:+.2f} pt",
                        delta=f"{r['tendance']:+.2f}")
    else:
        colonne2.metric("Evolution", "—")
    colonne3.metric("Bulletins", len(eleve["bulletins"]))

    st.subheader("💬 Ce que ca veut dire pour toi")

    if "ia_version" not in st.session_state:
        st.session_state.ia_version = 0

    if disponible():
        cle = f"ia_{st.session_state.ia_version}"
        if cle not in st.session_state:
            with st.spinner("L'assistant redige ton explication..."):
                st.session_state[cle] = texte_ia(eleve, r,
                                                 st.session_state.ia_version)
        if st.session_state[cle]:
            st.markdown(f'<div class="carte">{st.session_state[cle]}</div>',
                        unsafe_allow_html=True)
            if st.button("🔄 Explique-moi autrement"):
                st.session_state.ia_version += 1
                st.rerun()
        else:
            st.info("L'assistant n'a pas pu rediger. Le resume ci-dessus reste valable.")
    else:
        st.info("Assistant de redaction indisponible (Ollama eteint). "
                "Le resume ci-dessus reste valable.")

    if r["objectif_metier"]:
        st.subheader("🎯 Ton projet")
        st.markdown(f'<div class="carte">{r["objectif_metier"]["message"]}</div>',
                    unsafe_allow_html=True)

    st.subheader("Les deux voies")
    vers_lycee = r["situation"] in ("favorable", "ouvert")
    onglet1, onglet2 = st.tabs(
        ["✅ Lycee general" if vers_lycee else "Lycee general",
         "LIC" if vers_lycee else "✅ LIC (voie professionnelle)"])

    with onglet1:
        for ligne in r["description_lycee"]:
            st.write("• " + ligne)
    with onglet2:
        for ligne in r["description_lic"]:
            st.write("• " + ligne)

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

    st.subheader("📈 Le BEF compte pour 40 %")
    st.write("Ta moyenne d'admission = **60 % ta moyenne de l'annee "
             "+ 40 % ta note au BEF**. Le travail de l'annee pese le plus, "
             "mais le BEF represente 4 points sur 10 : ne relache rien.")

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
    if st.button("🔄 Recommencer"):
        st.session_state.clear()
        st.rerun()