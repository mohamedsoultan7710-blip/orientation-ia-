"""
Assistant d'orientation scolaire - Republique de Djibouti
Parcours College : apres la 9eme annee, Lycee general ou LIC.
"""

import os
import json
import tempfile

import pandas as pd
import streamlit as st

from modules.ocr_bulletin import lire_texte
from modules.extraction_bulletin import analyser, MATIERES, normaliser
from modules.verification_bulletin import verifier
from modules.recommandation import recommander, charger_metiers

st.set_page_config(page_title="Orientation Djibouti", page_icon="🎓",
                   layout="centered")

# --- Couleurs du drapeau djiboutien ---
BLEU = "#6AB2E7"
VERT = "#12AD2B"
ROUGE = "#D7141A"

DOSSIER_SORTIE = os.path.join("data", "bulletins")
AUTRE = "Autre — je precise moi-meme"
NIVEAU_ATTENDU = 9
NOMS_NIVEAUX = {6: "6eme", 7: "7eme", 8: "8eme", 9: "9eme"}

COULEURS_VOIE = {
    "lycee": ("#0f5132", "#d1e7dd"),
    "limite": ("#664d03", "#fff3cd"),
    "lic": ("#084298", "#cfe2ff"),
    "inconnue": ("#41464b", "#e2e3e5"),
}

st.markdown(f"""
<style>
.entete {{
    background: linear-gradient(120deg, {BLEU} 0%, {VERT} 100%);
    border-radius: 18px; padding: 30px 32px; margin-bottom: 22px;
    color: #ffffff; position: relative; overflow: hidden;
}}
.entete .etoile {{
    position: absolute; right: 26px; top: 22px;
    font-size: 3.2rem; color: {ROUGE}; opacity: .9;
}}
.entete h1 {{ margin: 0; font-size: 1.85rem; font-weight: 800; color: #fff; }}
.entete p {{ margin: 6px 0 0 0; opacity: .92; font-size: .95rem; }}
.entete .pays {{
    font-size: .72rem; letter-spacing: .22em; text-transform: uppercase;
    opacity: .85; margin-bottom: 8px;
}}
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
    import re
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
    for m, n in notes.items():
        if m not in MATIERES:
            lignes.append({"Matiere": m, "Note": n})

    tableau = st.data_editor(
        pd.DataFrame(lignes), num_rows="dynamic", width="stretch", key=cle,
        column_config={
            "Note": st.column_config.NumberColumn(min_value=0, max_value=20, step=0.25)
        },
    )

    resultat = {}
    for _, ligne in tableau.iterrows():
        matiere = str(ligne["Matiere"]).strip()
        if matiere and matiere != "None" and pd.notna(ligne["Note"]):
            resultat[matiere] = float(ligne["Note"])
    return resultat


def enregistrer():
    os.makedirs(DOSSIER_SORTIE, exist_ok=True)
    nom_fichier = normaliser(st.session_state.eleve["nom"]).replace(" ", "_") + ".json"
    chemin = os.path.join(DOSSIER_SORTIE, nom_fichier)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(st.session_state.eleve, f, ensure_ascii=False, indent=2)
    return chemin


# ==================== ETAPE 1 : ACCUEIL ====================

if st.session_state.etape == "accueil":
    entete("Trouve la voie qui te correspond.")

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

    st.markdown(
        '<div class="avert">Tes donnees restent sur cet appareil. '
        'Rien n\'est envoye sur Internet.</div>', unsafe_allow_html=True)


# ==================== ETAPE 2 : CHOIX DU PARCOURS ====================

elif st.session_state.etape == "parcours":
    entete(f"Bonjour {st.session_state.eleve['nom']} 👋", "Etape 1 sur 4")

    st.write("**Ou en es-tu dans ta scolarite ?**")
    st.caption("Choisis ta situation actuelle.")

    colonne1, colonne2, colonne3 = st.columns(3)

    with colonne1:
        with st.container(border=True):
            st.markdown("### 🏫")
            st.markdown("**College**")
            st.caption("9eme annee — orientation vers le Lycee ou le LIC")
            if st.button("Choisir", key="p_college", type="primary"):
                st.session_state.eleve["parcours"] = "college"
                aller("bulletin")

    with colonne2:
        with st.container(border=True):
            st.markdown("### 📗")
            st.markdown("**Seconde**")
            st.caption("Choix de la serie de Baccalaureat")
            st.button("Bientot disponible", key="p_seconde", disabled=True)

    with colonne3:
        with st.container(border=True):
            st.markdown("### 🎓")
            st.markdown("**Terminale**")
            st.caption("Choix des filieres universitaires")
            st.button("Bientot disponible", key="p_terminale", disabled=True)

    st.divider()
    if st.button("← Retour"):
        aller("accueil")


# ==================== ETAPE 3 : LE BULLETIN ====================

elif st.session_state.etape == "bulletin":
    entete("Parcours College — 9eme annee", "Etape 2 sur 4 · Tes notes")

    mode = st.radio("Comment veux-tu entrer tes notes ?",
                    ["📷 Importer une photo", "✍️ Saisir a la main"],
                    horizontal=True)

    # ---- Mode photo ----
    if mode.startswith("📷"):
        st.caption("Pose ton bulletin a plat, photographie-le bien droit, "
                   "toute la feuille dans le cadre.")

        fichiers = st.file_uploader("Photos de tes bulletins de 9eme",
                                    type=["png", "jpg", "jpeg"],
                                    accept_multiple_files=True)

        if st.button("🔍 Analyser", type="primary"):
            if not fichiers:
                st.error("Importe au moins une photo.")
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
                         "trimestre": l["donnees"]["trimestre"] or 1,
                         "niveau": detecter_niveau(l["donnees"].get("classe")),
                         "rapport": l["rapport"]}
                        for l in lus
                    ]

    # ---- Mode manuel ----
    else:
        combien = st.radio("Combien de bulletins veux-tu saisir ?", [1, 2],
                           horizontal=True)
        if st.button("✍️ Commencer la saisie", type="primary"):
            st.session_state.lus = [
                {"source": f"Trimestre {i + 1}", "notes": {},
                 "trimestre": i + 1, "niveau": NIVEAU_ATTENDU, "rapport": None}
                for i in range(combien)
            ]

    # ---- Correction et validation ----
    if st.session_state.lus:
        st.divider()
        st.write("**Verifie et complete tes notes.**")

        bulletins = []
        for i, bulletin in enumerate(st.session_state.lus):
            st.markdown(f"##### 📄 {bulletin['source']}")

            if bulletin["rapport"]:
                niveau_r = bulletin["rapport"]["niveau"]
                if niveau_r == "CONFORME":
                    st.success(f"✅ Bulletin reconnu — {bulletin['rapport']['pourcentage']}%")
                else:
                    st.warning(f"⚠️ Bulletin reconnu, a completer — "
                               f"{bulletin['rapport']['pourcentage']}%")

            colonne1, colonne2 = st.columns(2)
            trimestre = colonne1.selectbox("Trimestre", [1, 2, 3],
                                           index=bulletin["trimestre"] - 1,
                                           key=f"t_{i}")
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
            moyenne = round(sum(notes.values()) / len(notes), 2) if notes else None

            if moyenne:
                st.metric("Moyenne de ce trimestre", f"{moyenne} / 20")

            bulletins.append({"source": bulletin["source"], "trimestre": trimestre,
                              "niveau": niveau, "notes": notes, "moyenne": moyenne})
            st.divider()

        mauvais = [b for b in bulletins if b["niveau"] != NIVEAU_ATTENDU]
        sans_notes = [b for b in bulletins if not b["notes"]]

        if mauvais:
            st.error(f"❌ Nous avons besoin de tes bulletins de "
                     f"{NOMS_NIVEAUX[NIVEAU_ATTENDU]}. Corrige la classe.")
        elif sans_notes:
            st.warning("Complete les notes d'au moins une matiere par bulletin.")
        elif st.button("Continuer →", type="primary"):
            st.session_state.eleve["bulletins"] = bulletins
            st.session_state.lus = None
            aller("questionnaire")

    st.divider()
    if st.button("← Retour"):
        aller("parcours")


# ==================== ETAPE 4 : LE QUESTIONNAIRE ====================

elif st.session_state.etape == "questionnaire":
    entete("Parcours College — 9eme annee", "Etape 3 sur 4 · Toi")

    liste = list(MATIERES.keys())

    st.write("**1. Quelle matiere preferes-tu ?**")
    st.caption("Celle que tu aimes le plus, meme si tu n'y as pas la meilleure note.")
    preferee = st.selectbox("Ma matiere preferee", liste, label_visibility="collapsed")

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
                              placeholder="Exemple : pilote, cuisinier, photographe...")

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
      <div class="surtitre">La voie qui se dessine pour toi</div>
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

    if r["objectif_metier"]:
        st.subheader("🎯 Ton projet")
        st.markdown(f'<div class="carte">{r["objectif_metier"]["message"]}</div>',
                    unsafe_allow_html=True)

    st.subheader("Les deux voies")
    vers_lycee = r["situation"] in ("lycee", "limite")
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
                            f'<strong>{note}</strong></div>', unsafe_allow_html=True)
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
    st.markdown(
        '<div class="avert">Cette recommandation est une aide a la reflexion, '
        'pas une decision. L\'affectation en Seconde est prononcee par la '
        'commission du MENFOP, au classement. Parles-en avec tes professeurs '
        'et le Service d\'Orientation de ton etablissement.</div>',
        unsafe_allow_html=True)

    st.divider()
    if st.button("🔄 Recommencer"):
        st.session_state.clear()
        st.rerun()