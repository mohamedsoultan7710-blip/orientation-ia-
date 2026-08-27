"""
Correctif 2 de l'alerte BEF :
  - retire la fleche montante trompeuse a cote du mot "faible"
  - nomme explicitement l'ecart entre la moyenne du bulletin
    et la moyenne d'admission estimee

Lancer depuis C:\\Users\\Gebruiker\\Desktop\\orientation-ia
    .\\venv\\Scripts\\python.exe patch_bef2.py
"""
import io, os, shutil, sys

FICHIER = "app_orientation.py"

# --- 1) la fleche ---
OLD1 = '''                _c[_i].metric(_nom, f"{_v:.1f}", "faible" if _v < 12 else "correct",
                              delta_color="inverse" if _v < 12 else "normal")'''
NEW1 = '''                _c[_i].metric(_nom, f"{_v:.1f}",
                              "sous le seuil" if _v < 12 else "correct",
                              delta_color="inverse" if _v < 12 else "off")'''

# --- 2) l'ecart moyenne / admission ---
OLD2 = '''            st.markdown("#### Ce que tu gagnes si tu montes ces matieres a 12")'''
NEW2 = '''            if _moy - _adm_now >= 0.5:
                st.warning(
                    "**Ta moyenne de bulletin est de "
                    + f"{_moy:.2f}"
                    + ", mais ta moyenne d'admission estimee est de "
                    + f"{_adm_now:.2f}"
                    + ".** L'ecart vient de la : tes meilleures notes ne sont "
                    "pas testees au BEF. C'est sur ces 4 matieres que se joue "
                    "ton passage en Seconde."
                )

            st.markdown("#### Ce que tu gagnes si tu montes ces matieres a 12")'''

# le calcul doit exister avant le warning : on le remonte
OLD3 = '''            _bef_now = sum(_bef.values()) / 4
            _adm_now = 0.6 * _moy + 0.4 * _bef_now
            _cible = {k: (12.0 if v < 12 else v) for k, v in _bef.items()}
            _bef_cible = sum(_cible.values()) / 4
            _adm_cible = 0.6 * _moy + 0.4 * _bef_cible

'''
NEW3 = ''''''

OLD4 = '''            _liste = ", ".join(f"**{_k}** ({_v:.1f})" for _k, _v in _faibles)'''
NEW4 = '''            _bef_now = sum(_bef.values()) / 4
            _adm_now = 0.6 * _moy + 0.4 * _bef_now
            _cible = {k: (12.0 if v < 12 else v) for k, v in _bef.items()}
            _bef_cible = sum(_cible.values()) / 4
            _adm_cible = 0.6 * _moy + 0.4 * _bef_cible

            _liste = ", ".join(f"**{_k}** ({_v:.1f})" for _k, _v in _faibles)'''


def main():
    if not os.path.exists(FICHIER):
        print("ERREUR : lance ce script depuis le dossier du projet.")
        return 1
    with io.open(FICHIER, encoding="utf-8") as f:
        src = f.read()

    if "Alerte BEF : les 4 epreuves testees" not in src:
        print("ERREUR : le premier correctif n'est pas applique.")
        return 1
    if "L'ecart vient de la" in src:
        print("Deja applique. Rien a faire.")
        return 0

    for i, old in enumerate([OLD1, OLD4, OLD3, OLD2], 1):
        if src.count(old) != 1:
            print("ERREUR : motif %d introuvable ou en double (%d)."
                  % (i, src.count(old)))
            return 1

    shutil.copyfile(FICHIER, "app_orientation_avant_correctif2.py")
    src = src.replace(OLD1, NEW1)
    src = src.replace(OLD3, NEW3)   # d'abord retirer l'ancien calcul
    src = src.replace(OLD4, NEW4)   # puis le remonter avant _liste
    src = src.replace(OLD2, NEW2)   # puis inserer le warning
    if src.count("_adm_now = 0.6") != 1:
        print("ERREUR : le calcul n'est pas present une seule fois. Annule.")
        return 1
    with io.open(FICHIER, "w", encoding="utf-8", newline="") as f:
        f.write(src)

    print("OK - correctif 2 applique.")
    print("Sauvegarde : app_orientation_avant_correctif2.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
