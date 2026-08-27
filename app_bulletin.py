"""
Interface d'import de bulletin - parcours College (BEF).
Deux modes au choix : import d'une photo (OCR) ou saisie manuelle.
"""

import os
import re
import json
import tempfile

import pandas as pd
import streamlit as st

from modules.ocr_bulletin import lire_texte
from modules.extraction_bulletin import analyser, MATIERES, normaliser
from modules.verification_bulletin import verifier, comparer_nom

st.set_page_config(page_title="Import du bulletin", page_icon="🎓")

SYMBOLES = {"ok": "✅", "attention": "⚠️", "erreur": "❌"}
DOSSIER_SORTIE = os.path.join("data", "bulletins")
NIVEAU_ATTENDU = 9
SEUIL_MEME_PERSONNE = 75
MIN_MATIERES = 0
NOMS_NIVEAUX = {6: "6eme", 7: "7eme", 8: "8eme", 9: "9eme"}


# ==================== OUTILS ====================

def detecter_niveau(classe_texte):
    """Retourne 6, 7, 8, 9 -- ou None si la classe est illisible."""
    if not classe_texte:
        return None
    t = normaliser(classe_texte)
    for niveau in (9, 8, 7, 6):
        if re.search(rf"\b{niveau}\s*(eme|em|e)?\b", t):
            return niveau
    return None


def traiter_fichier(fichier):
    """Enregistre l'image temporairement, puis OCR + extraction + verification."""
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


def est_un_bulletin(donnees, rapport):
    """Un document est accepte comme bulletin s'il a assez de matieres et de marqueurs."""
    assez_de_matieres = len(donnees.get("notes", {})) >= MIN_MATIERES
    pas_rejete = rapport["niveau"] != "NON RECONNU"
    return assez_de_matieres and pas_rejete


def afficher_rapport(rapport):
    """Affiche le niveau de confiance et le detail des controles."""
    texte = f"{rapport['niveau']} — {rapport['pourcentage']}% de coherence"
    if rapport["niveau"] == "CONFORME":
        st.success("✅ " + texte)
    elif rapport["niveau"] != "NON RECONNU":
        st.warning("⚠️ " + texte)
    else:
        st.error("❌ " + texte)

    with st.expander("Voir le detail des controles"):
        for etat, titre, detail in rapport["controles"]:
            st.write(f"{SYMBOLES[etat]} **{titre}** — {detail}")


def tableau_notes(notes, cle):
    """Affiche un tableau corrigeable et retourne les notes validees."""
    lignes = [{"Matiere": m, "Note": notes.get(m)} for m in MATIERES]
    for m, n in notes.items():
        if m not in MATIERES:
            lignes.append({"Matiere": m, "Note": n})

    tableau = st.data_editor(
        pd.DataFrame(lignes),
        num_rows="dynamic",
        width="stretch",
        key=cle,
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


def reinitialiser():
    st.session_state.pop("bulletins", None)


# ==================== PAGE ====================

st.title("🎓 Import du bulletin")
st.caption("Parcours College — orientation apres la 9eme")

nom_saisi = st.text_input("Nom et prenom de l'eleve", placeholder="Ahmed Mohamed Hassan")

mode = st.radio(
    "Comment veux-tu entrer tes notes ?",
    ["📷 Importer une photo", "✍️ Saisir a la main"],
    horizontal=True,
    on_change=reinitialiser,
)


# ---------- MODE PHOTO ----------

if mode.startswith("📷"):
    st.info(
        "Importe tes bulletins du **1er et du 2e trimestre de 9eme**. "
        "L'ordinateur lit les notes automatiquement, puis tu pourras les corriger."
    )

    fichiers = st.file_uploader(
        "Photos des bulletins",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )

    if st.button("🔍 Analyser les bulletins", type="primary"):
        if not nom_saisi.strip():
            st.error("Merci d'entrer le nom de l'eleve avant de continuer.")
        elif not fichiers:
            st.error("Merci d'importer au moins une photo.")
        else:
            lus = []
            for fichier in fichiers:
                with st.spinner(f"Lecture de {fichier.name}..."):
                    donnees, rapport = traiter_fichier(fichier)
                lus.append({"fichier": fichier.name, "donnees": donnees, "rapport": rapport})

            rejets = []

            # --- Regle 1 : est-ce bien un bulletin ? ---
            for lu in lus:
                if not est_un_bulletin(lu["donnees"], lu["rapport"]):
                    rejets.append(
                        f"**{lu['fichier']}** : ce document n'est pas un bulletin scolaire. "
                        "Verifie que tu as bien envoye la photo de ton bulletin."
                    )

            # --- Regle 2 : est-ce bien la 9eme ? ---
            if not rejets:
                for lu in lus:
                    niveau = detecter_niveau(lu["donnees"].get("classe"))
                    lu["niveau"] = niveau
                    if niveau is not None and niveau != NIVEAU_ATTENDU:
                        rejets.append(
                            f"**{lu['fichier']}** : ce bulletin est celui de la "
                            f"{NOMS_NIVEAUX[niveau]}. Nous avons besoin de tes bulletins "
                            f"de {NOMS_NIVEAUX[NIVEAU_ATTENDU]}."
                        )

            # --- Regle 3 : est-ce la meme personne ? ---
            if not rejets and len(lus) >= 2:
                noms = [lu["donnees"].get("nom") for lu in lus]
                for i in range(1, len(noms)):
                    ressemblance = comparer_nom(noms[0], noms[i])
                    if ressemblance is not None and ressemblance < SEUIL_MEME_PERSONNE:
                        rejets.append(
                            f"Ces bulletins ne sont pas au meme nom : "
                            f"« {noms[0]} » et « {noms[i]} ». "
                            "Tous les bulletins doivent appartenir au meme eleve."
                        )

            if rejets:
                st.error("❌ Import refuse")
                for message in rejets:
                    st.markdown("- " + message)
                st.session_state.pop("bulletins", None)
            else:
                st.session_state["bulletins"] = [
                    {
                        "source": lu["fichier"],
                        "notes": lu["donnees"]["notes"],
                        "trimestre": lu["donnees"]["trimestre"] or 1,
                        "classe": lu["donnees"].get("classe") or "",
                        "niveau": lu.get("niveau"),
                        "rapport": lu["rapport"],
                    }
                    for lu in lus
                ]
                st.session_state["nom"] = nom_saisi


# ---------- MODE MANUEL ----------

else:
    st.info("Saisis toi-meme tes notes. Laisse vide une matiere que tu n'as pas.")

    combien = st.radio("Combien de bulletins veux-tu saisir ?", [1, 2], horizontal=True)

    if st.button("✍️ Commencer la saisie", type="primary"):
        if not nom_saisi.strip():
            st.error("Merci d'entrer le nom de l'eleve avant de continuer.")
        else:
            st.session_state["bulletins"] = [
                {
                    "source": f"Saisie manuelle {i + 1}",
                    "notes": {},
                    "trimestre": i + 1,
                    "classe": "9eme",
                    "niveau": NIVEAU_ATTENDU,
                    "rapport": None,
                }
                for i in range(combien)
            ]
            st.session_state["nom"] = nom_saisi


# ==================== SAISIE ET CORRECTION ====================

if "bulletins" in st.session_state:
    st.divider()
    st.subheader("Verifie et complete")

    bulletins_finaux = []

    for i, bulletin in enumerate(st.session_state["bulletins"]):
        st.markdown(f"### 📄 {bulletin['source']}")

        if bulletin["rapport"] is not None:
            afficher_rapport(bulletin["rapport"])

        colonne1, colonne2 = st.columns(2)

        with colonne1:
            trimestre = st.selectbox(
                "Trimestre",
                [1, 2, 3],
                index=bulletin["trimestre"] - 1,
                key=f"trim_{i}",
            )

        with colonne2:
            if bulletin["niveau"] is None:
                st.warning("Classe illisible sur la photo.")
                niveau = st.selectbox(
                    "Confirme ta classe",
                    [6, 7, 8, 9],
                    index=3,
                    format_func=lambda n: NOMS_NIVEAUX[n],
                    key=f"niv_{i}",
                )
            else:
                niveau = bulletin["niveau"]
                st.text_input("Classe", value=NOMS_NIVEAUX[niveau],
                              disabled=True, key=f"cls_{i}")

        notes = tableau_notes(bulletin["notes"], f"table_{i}")

        if notes:
            moyenne = round(sum(notes.values()) / len(notes), 2)
            st.metric("Moyenne du trimestre", f"{moyenne} / 20")
        else:
            moyenne = None
            st.warning("Aucune note saisie pour ce bulletin.")

        bulletins_finaux.append({
            "source": bulletin["source"],
            "trimestre": trimestre,
            "niveau": niveau,
            "notes": notes,
            "moyenne": moyenne,
            "niveau_confiance": bulletin["rapport"]["niveau"] if bulletin["rapport"] else "SAISIE MANUELLE",
        })

        st.divider()

    # --- Controle final sur la classe confirmee ---
    mauvais_niveau = [b for b in bulletins_finaux if b["niveau"] != NIVEAU_ATTENDU]

    if mauvais_niveau:
        st.error(
            f"❌ Un bulletin n'est pas celui de la {NOMS_NIVEAUX[NIVEAU_ATTENDU]}. "
            "Corrige la classe ou importe le bon bulletin."
        )
    elif st.button("💾 Valider et enregistrer", type="primary"):
        os.makedirs(DOSSIER_SORTIE, exist_ok=True)
        nom_fichier = normaliser(st.session_state["nom"]).replace(" ", "_") + ".json"
        chemin = os.path.join(DOSSIER_SORTIE, nom_fichier)

        contenu = {
            "nom": st.session_state["nom"],
            "parcours": "college",
            "bulletins": bulletins_finaux,
        }

        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(contenu, f, ensure_ascii=False, indent=2)

        st.success(f"Enregistre dans : {chemin}")
        st.json(contenu)