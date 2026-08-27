"""
Ajoute une alerte visible quand les matieres du BEF sont faibles.
Lancer depuis C:\\Users\\Gebruiker\\Desktop\\orientation-ia
    .\\venv\\Scripts\\python.exe patch_bef.py
"""
import io, os, shutil, sys

FICHIER = "app_orientation.py"
ANCRE = '    st.subheader("Le BEF compte pour 40 %")'

BLOC = '''    # --- Alerte BEF : les 4 epreuves testees ---
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
                "**Attention : le BEF ne teste que 4 matieres sur tes "
                + str(len(_bulls) and 14 or 14)
                + ".** Tes meilleures notes ne sont pas dedans."
            )
            st.markdown("#### Les 4 seules matieres qui comptent au BEF")
            _c = st.columns(4)
            for _i, _nom in enumerate(["Francais", "Mathematiques", "Physique-Chimie", "SVT"]):
                _v = _bef.get(_nom)
                _c[_i].metric(_nom, f"{_v:.1f}", "faible" if _v < 12 else "correct",
                              delta_color="inverse" if _v < 12 else "normal")

            _liste = ", ".join(f"**{_k}** ({_v:.1f})" for _k, _v in _faibles)
            st.markdown(
                "Aujourd'hui tu es en difficulte en " + _liste + ". "
                "Ces notes comptent double a l'examen, et l'examen pese 40 % "
                "de ton admission. Si elles ne montent pas d'ici la fin de "
                "l'annee, ta moyenne d'admission descendra, meme si le reste "
                "de ton bulletin est excellent."
            )

            _bef_now = sum(_bef.values()) / 4
            _adm_now = 0.6 * _moy + 0.4 * _bef_now
            _cible = {k: (12.0 if v < 12 else v) for k, v in _bef.items()}
            _bef_cible = sum(_cible.values()) / 4
            _adm_cible = 0.6 * _moy + 0.4 * _bef_cible

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

'''


def main():
    if not os.path.exists(FICHIER):
        print("ERREUR : lance ce script depuis le dossier du projet.")
        return 1
    with io.open(FICHIER, encoding="utf-8") as f:
        src = f.read()
    if "Alerte BEF : les 4 epreuves testees" in src:
        print("Deja applique. Rien a faire.")
        return 0
    if src.count(ANCRE) != 1:
        print("ERREUR : ancre introuvable ou en double (%d)." % src.count(ANCRE))
        return 1
    shutil.copyfile(FICHIER, "app_orientation_avant_alerte_bef.py")
    with io.open(FICHIER, "w", encoding="utf-8", newline="") as f:
        f.write(src.replace(ANCRE, BLOC + ANCRE))
    print("OK - alerte ajoutee.")
    print("Sauvegarde : app_orientation_avant_alerte_bef.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
