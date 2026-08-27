"""
Questionnaire d'orientation - parcours College (apres la 9eme).
Complete le fichier de l'eleve avec son profil personnel.
"""

import os
import glob
import json

import streamlit as st

from modules.extraction_bulletin import MATIERES

st.set_page_config(page_title="Questionnaire d'orientation", page_icon="🧭")

DOSSIER_BULLETINS = os.path.join("data", "bulletins")
FICHIER_METIERS = os.path.join("data", "metiers.json")
AUTRE = "Autre — je precise moi-meme"


def charger_metiers():
    with open(FICHIER_METIERS, encoding="utf-8") as f:
        return json.load(f)["metiers"]


def lister_fichiers_eleves():
    return sorted(glob.glob(os.path.join(DOSSIER_BULLETINS, "*.json")))


def charger_eleve(chemin):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def enregistrer_eleve(chemin, contenu):
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(contenu, f, ensure_ascii=False, indent=2)


def moyenne_generale(eleve):
    """Moyenne de tous les bulletins enregistres."""
    valeurs = [b["moyenne"] for b in eleve.get("bulletins", [])
               if b.get("moyenne") is not None]
    return round(sum(valeurs) / len(valeurs), 2) if valeurs else None


# ==================== PAGE ====================

st.title("🧭 Questionnaire d'orientation")
st.caption("Apres la 9eme — pour te recommander la voie qui te correspond")

fichiers = lister_fichiers_eleves()

if not fichiers:
    st.warning(
        "Aucun bulletin enregistre. Commence par l'import du bulletin "
        "(app_bulletin.py), puis reviens ici."
    )
    st.stop()

chemin = st.selectbox(
    "Choisis ton dossier",
    fichiers,
    format_func=lambda c: os.path.basename(c).replace(".json", ""),
)

eleve = charger_eleve(chemin)
bulletins = eleve.get("bulletins", [])

# --- Rappel des notes ---
st.subheader(f"Bonjour {eleve.get('nom', '')}")

moyenne = moyenne_generale(eleve)
colonne1, colonne2 = st.columns(2)
colonne1.metric("Bulletins enregistres", len(bulletins))
colonne2.metric("Moyenne actuelle", f"{moyenne} / 20" if moyenne else "—")

if not bulletins:
    st.error("Ce dossier ne contient aucun bulletin exploitable.")
    st.stop()

st.divider()

# --- Le profil deja enregistre, s'il existe ---
profil = eleve.get("profil", {})

# --- Question 1 ---
st.subheader("1. Quelle matiere preferes-tu ?")
st.caption("Celle que tu aimes le plus, meme si tu n'as pas la meilleure note dedans.")

liste_matieres = list(MATIERES.keys())
index_prefere = (liste_matieres.index(profil["matiere_preferee"])
                 if profil.get("matiere_preferee") in liste_matieres else 0)

matiere_preferee = st.selectbox("Ma matiere preferee", liste_matieres,
                                index=index_prefere)

# --- Question 2 ---
st.subheader("2. Dans quelles matieres te sens-tu a l'aise ?")
st.caption("Celles ou tu comprends facilement, sans forcer. Choisis-en autant que tu veux.")

matieres_alaise = st.multiselect(
    "Je me sens a l'aise en...",
    liste_matieres,
    default=[m for m in profil.get("matieres_alaise", []) if m in liste_matieres],
)

# --- Question 3 ---
st.subheader("3. Quel metier aimerais-tu faire plus tard ?")
st.caption("Si tu hesites, choisis celui qui t'attire le plus. Rien n'est definitif.")

metiers = charger_metiers()
noms_metiers = [m["nom"] for m in metiers] + [AUTRE]

index_metier = (noms_metiers.index(profil["ambition"])
                if profil.get("ambition") in noms_metiers else 0)

ambition = st.selectbox("Mon ambition professionnelle", noms_metiers,
                        index=index_metier)

ambition_libre = ""
if ambition == AUTRE:
    ambition_libre = st.text_input(
        "Precise le metier qui t'interesse",
        value=profil.get("ambition_libre", ""),
        placeholder="Exemple : pilote, cuisinier, photographe...",
    )

st.divider()

# --- Enregistrement ---
if st.button("💾 Enregistrer mon profil", type="primary"):
    if ambition == AUTRE and not ambition_libre.strip():
        st.error("Ecris le metier qui t'interesse, ou choisis-en un dans la liste.")
    elif not matieres_alaise:
        st.error("Choisis au moins une matiere ou tu te sens a l'aise.")
    else:
        eleve["profil"] = {
            "matiere_preferee": matiere_preferee,
            "matieres_alaise": matieres_alaise,
            "ambition": ambition,
            "ambition_libre": ambition_libre.strip(),
        }
        enregistrer_eleve(chemin, eleve)
        st.success("Profil enregistre. Tu peux passer a la recommandation.")
        st.json(eleve["profil"])