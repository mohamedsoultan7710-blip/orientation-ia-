import streamlit as st
from core.matching import recommander, get_bourses

st.set_page_config(page_title="Assistant d'orientation", page_icon="🎓")

st.title("🎓 Assistant d'orientation scolaire et universitaire")
st.write("Renseigne ton profil pour recevoir des recommandations personnalisées.")

with st.form("formulaire_profil"):
    nom = st.text_input("Ton prénom")

    niveau = st.selectbox(
        "Ton niveau actuel",
        options=["college", "lycee"],
        format_func=lambda x: "Collégien (je choisis ma série de bac)" if x == "college" else "Lycéen / nouveau bachelier (je choisis ma filière universitaire)"
    )

    matieres = st.text_input("Tes matières préférées (séparées par des virgules)", placeholder="ex: Mathematiques, Physique-Chimie")
    aptitudes = st.text_input("Tes points forts (séparés par des virgules)", placeholder="ex: logique, calcul")
    interets = st.text_input("Tes centres d'intérêt (séparés par des virgules)", placeholder="ex: technologie, sciences")

    notes_texte = st.text_input(
        "Tes notes (optionnel, format: Matiere:note, separees par des virgules)",
        placeholder="ex: Mathematiques:15, Physique-Chimie:14"
    )

    ambitions = st.text_area("Ton ambition professionnelle")

    serie_bac = None
    if niveau == "lycee":
        serie_bac = st.selectbox(
            "Ta série de bac (si tu la connais)",
            options=["", "serie_s", "serie_l", "serie_es", "serie_sg_ogrh", "serie_sg_gfm", "serie_sg_iag"],
            format_func=lambda x: "Non precise" if x == "" else x
        )

    valider = st.form_submit_button("Obtenir mes recommandations")

if valider:
    notes = {}
    if notes_texte:
        for paire in notes_texte.split(","):
            if ":" in paire:
                matiere, valeur = paire.split(":", 1)
                try:
                    notes[matiere.strip()] = float(valeur.strip())
                except ValueError:
                    pass

    profil = {
        "nom": nom,
        "niveau": niveau,
        "matieres_preferees": [m.strip() for m in matieres.split(",") if m.strip()],
        "aptitudes": [a.strip() for a in aptitudes.split(",") if a.strip()],
        "centres_interet": [i.strip() for i in interets.split(",") if i.strip()],
        "ambitions": ambitions,
        "notes": notes,
    }
    if serie_bac:
        profil["serie_bac"] = serie_bac

    resultats = recommander(profil, nombre_resultats=3)

    st.subheader(f"Voici tes recommandations, {nom} :")

    for i, r in enumerate(resultats, start=1):
        with st.container(border=True):
            st.markdown(f"### {i}. {r['nom']} — {r['score']}%")
            st.write(f"**Mode d'admission :** {r['mode_admission']}")
            if r.get("conditions"):
                st.write(f"**Conditions :** {r['conditions']}")
            st.write(f"**Débouchés :** {', '.join(r['debouches'])}")
            st.write(f"**Pour renforcer ton dossier :** {r['action_recommandee']}")

    st.divider()
    st.subheader("🌍 Bourses possibles a l'etranger")
    for bourse in get_bourses():
        st.write(f"**{bourse['pays']}** — {bourse['notes']}")