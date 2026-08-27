"""
Recommandation d'orientation - parcours College (apres la 9eme).
C'est l'ecran final : ce que l'eleve voit.
"""

import os
import glob
import json

import pandas as pd
import streamlit as st

from modules.recommandation import recommander

st.set_page_config(page_title="Ma recommandation", page_icon="🎓",
                   layout="centered")

DOSSIER_BULLETINS = os.path.join("data", "bulletins")

# (texte, fond) selon la situation
COULEURS = {
    "lycee":    ("#0f5132", "#d1e7dd"),
    "limite":   ("#664d03", "#fff3cd"),
    "lic":      ("#084298", "#cfe2ff"),
    "inconnue": ("#41464b", "#e2e3e5"),
}

st.markdown("""
<style>
.bandeau { border-radius: 16px; padding: 24px 28px; margin: 8px 0 20px 0; }
.bandeau .surtitre { font-size: .75rem; letter-spacing: .14em;
                     text-transform: uppercase; opacity: .7; }
.bandeau .titre { font-size: 1.9rem; font-weight: 700; margin: 6px 0 0 0;
                  line-height: 1.15; }
.carte { border-radius: 12px; padding: 16px 20px; margin-bottom: 12px;
         background: rgba(128,128,128,.09); }
.carte .etiquette { font-size: .75rem; letter-spacing: .1em;
                    text-transform: uppercase; opacity: .65; }
.ligne-note { display: flex; justify-content: space-between;
              padding: 7px 0; border-bottom: 1px solid rgba(128,128,128,.18); }
.ligne-note:last-child { border-bottom: none; }
.avert { font-size: .85rem; opacity: .75; border-left: 3px solid #adb5bd;
         padding: 8px 14px; margin-top: 8px; }
</style>
""", unsafe_allow_html=True)


def lister_eleves():
    return sorted(glob.glob(os.path.join(DOSSIER_BULLETINS, "*.json")))


def charger(chemin):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


# ==================== PAGE ====================

st.title("🎓 Ma recommandation d'orientation")
st.caption("Apres la 9eme annee — Lycee general ou LIC")

fichiers = lister_eleves()
if not fichiers:
    st.warning("Aucun dossier trouve. Commence par importer ton bulletin.")
    st.stop()

chemin = st.selectbox(
    "Dossier de l'eleve",
    fichiers,
    format_func=lambda c: os.path.basename(c).replace(".json", ""),
)

eleve = charger(chemin)

if not eleve.get("bulletins"):
    st.error("Ce dossier ne contient aucun bulletin.")
    st.stop()

r = recommander(eleve)

if not eleve.get("profil"):
    st.info("Ce dossier n'a pas encore de questionnaire rempli. "
            "La recommandation reste valable, mais elle sera plus precise "
            "une fois le questionnaire complete.")

# ---------- Le bandeau principal ----------

texte, fond = COULEURS.get(r["situation"], COULEURS["inconnue"])

st.markdown(f"""
<div class="bandeau" style="background:{fond}; color:{texte};">
  <div class="surtitre">La voie qui se dessine pour toi</div>
  <div class="titre">{r['voie'] or 'Donnees insuffisantes'}</div>
</div>
""", unsafe_allow_html=True)

st.write(r["message"])

# ---------- Les chiffres ----------

colonne1, colonne2, colonne3 = st.columns(3)
colonne1.metric("Moyenne actuelle", f"{r['moyenne']} / 20" if r["moyenne"] else "—")

if r["tendance"] is not None:
    colonne2.metric("Evolution", f"{r['tendance']:+.2f} pt",
                    delta=f"{r['tendance']:+.2f}")
else:
    colonne2.metric("Evolution", "—", help="Il faut 2 bulletins pour la calculer")

colonne3.metric("Bulletins", len(eleve["bulletins"]))

# ---------- Ton projet ----------

if r["objectif_metier"]:
    st.subheader("🎯 Ton projet")
    st.markdown(
        f'<div class="carte"><div class="etiquette">Metier vise</div>'
        f'<p style="margin:6px 0 0 0;">{r["objectif_metier"]["message"]}</p></div>',
        unsafe_allow_html=True,
    )

# ---------- Les deux voies ----------

st.subheader("Les deux voies")

vers_lycee = r["situation"] in ("lycee", "limite")
onglet1, onglet2 = st.tabs(
    ["✅ Lycee general" if vers_lycee else "Lycee general",
     "LIC" if vers_lycee else "✅ LIC (voie professionnelle)"]
)

with onglet1:
    for ligne in r["description_lycee"]:
        st.write("• " + ligne)

with onglet2:
    for ligne in r["description_lic"]:
        st.write("• " + ligne)
    st.caption("Le LIC n'est pas une voie fermee : des licences "
               "professionnelles existent, et l'insertion y est rapide.")

# ---------- Points forts et matieres a renforcer ----------

st.subheader("Ton profil de notes")
gauche, droite = st.columns(2)

with gauche:
    st.markdown('<div class="carte"><div class="etiquette">Tes points forts</div>',
                unsafe_allow_html=True)
    if r["points_forts"]:
        for matiere, note in r["points_forts"]:
            st.markdown(
                f'<div class="ligne-note"><span>{matiere}</span>'
                f'<strong>{note}</strong></div>', unsafe_allow_html=True)
    else:
        st.write("—")
    st.markdown("</div>", unsafe_allow_html=True)

with droite:
    st.markdown('<div class="carte"><div class="etiquette">A renforcer</div>',
                unsafe_allow_html=True)
    if r["a_renforcer"]:
        for matiere, note in r["a_renforcer"]:
            st.markdown(
                f'<div class="ligne-note"><span>{matiere}</span>'
                f'<strong>{note}</strong></div>', unsafe_allow_html=True)
    else:
        st.write("Aucune matiere sous 12. Continue comme ca.")
    st.markdown("</div>", unsafe_allow_html=True)

# ---------- Le BEF ----------

st.subheader("📈 Le BEF compte pour 40 %")

st.write(
    "Ta moyenne d'admission se calcule ainsi : **60 % ta moyenne de l'annee "
    "+ 40 % ta note au BEF**. Le travail de l'annee pese le plus, mais le BEF "
    "represente quand meme 4 points sur 10 — ne relache rien jusqu'au bout."
)

if r["tableau_bef"]:
    tableau = pd.DataFrame(r["tableau_bef"])
    tableau.columns = ["Note au BEF", "Ta moyenne d'admission"]

    st.bar_chart(tableau.set_index("Note au BEF"), height=260)

    with st.expander("Voir le detail chiffre"):
        st.dataframe(tableau, hide_index=True, width="stretch")

    st.caption("Chaque point gagne au BEF fait monter ton admission de 0,4 point. "
               "Il n'y a pas de note magique a atteindre : plus tu montes, "
               "plus tu remontes dans le classement.")

# ---------- Avertissement final ----------

st.divider()
st.markdown(
    '<div class="avert">Cette recommandation est une aide a la reflexion, '
    'pas une decision. L\'affectation en Seconde est prononcee par la '
    'commission du MENFOP, au classement, et aucun seuil officiel n\'est '
    'publie. Parles-en avec tes professeurs et le Service d\'Orientation '
    'de ton etablissement.</div>',
    unsafe_allow_html=True,
)