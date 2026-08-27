"""
Correctif 3 - COEFFICIENTS REELS DU BEF
Source : CRIPEN, annales BEF (3 epreuves, Sciences = PC + SVT)
    Francais 2 | Mathematiques 2 | Physique-Chimie 1 | SVT 0,5   -> total 5,5

Lancer depuis C:\\Users\\Gebruiker\\Desktop\\orientation-ia
    .\\venv\\Scripts\\python.exe patch_bef3.py
"""
import io, os, shutil, sys

FICHIER = "app_orientation.py"

# 1) moyenne du BEF ponderee au lieu de /4
OLD1 = '''            _bef_now = sum(_bef.values()) / 4'''
NEW1 = '''            _COEF_BEF = {"Francais": 2.0, "Mathematiques": 2.0,
                         "Physique-Chimie": 1.0, "SVT": 0.5}
            _TOT_BEF = sum(_COEF_BEF.values())
            _bef_now = sum(_bef[_k] * _COEF_BEF[_k] for _k in _COEF_BEF) / _TOT_BEF'''

OLD2 = '''            _bef_cible = sum(_cible.values()) / 4'''
NEW2 = '''            _bef_cible = sum(_cible[_k] * _COEF_BEF[_k] for _k in _COEF_BEF) / _TOT_BEF'''

# 2) afficher le coefficient sur chaque matiere
OLD3 = '''                _c[_i].metric(_nom, f"{_v:.1f}",
                              "sous le seuil" if _v < 12 else "correct",
                              delta_color="inverse" if _v < 12 else "off")'''
NEW3 = '''                _cf = {"Francais": "2", "Mathematiques": "2",
                       "Physique-Chimie": "1", "SVT": "0,5"}[_nom]
                _c[_i].metric(f"{_nom} (coef {_cf})", f"{_v:.1f}",
                              "sous le seuil" if _v < 12 else "correct",
                              delta_color="inverse" if _v < 12 else "off")'''

# 3) le texte d'explication
OLD4 = '''    st.write("Ta moyenne d'admission = **60 % ta moyenne de l'annee "
             "+ 40 % ta note au BEF**. Le BEF porte sur 4 epreuves a "
             "coefficient 2 : Francais, Mathematiques, Physique-Chimie et SVT.")'''
NEW4 = '''    st.write("Ta moyenne d'admission = **60 % ta moyenne de l'annee "
             "+ 40 % ta note au BEF**. Le BEF porte sur 3 epreuves : "
             "Francais (coef 2), Mathematiques (coef 2) et Sciences, "
             "elle-meme divisee en Physique-Chimie (coef 1) et SVT (coef 0,5). "
             "Total des coefficients : 5,5.")'''

# 4) la phrase de l'alerte
OLD5 = '''                "**Attention : le BEF ne teste que 4 matieres sur tes "'''
NEW5 = '''                "**Attention : le BEF ne teste que ces 4 matieres sur tes "'''


def main():
    if not os.path.exists(FICHIER):
        print("ERREUR : lance ce script depuis le dossier du projet.")
        return 1
    with io.open(FICHIER, encoding="utf-8") as f:
        src = f.read()

    if "_COEF_BEF" in src:
        print("Deja applique. Rien a faire.")
        return 0
    if "Alerte BEF : les 4 epreuves testees" not in src:
        print("ERREUR : les correctifs 1 et 2 ne sont pas appliques.")
        return 1

    paires = [(OLD1, NEW1), (OLD2, NEW2), (OLD3, NEW3), (OLD4, NEW4), (OLD5, NEW5)]
    for i, (old, _) in enumerate(paires, 1):
        if src.count(old) != 1:
            print("ERREUR : motif %d introuvable ou en double (%d). Rien modifie."
                  % (i, src.count(old)))
            return 1

    shutil.copyfile(FICHIER, "app_orientation_avant_coef_bef.py")
    for old, new in paires:
        src = src.replace(old, new)
    with io.open(FICHIER, "w", encoding="utf-8", newline="") as f:
        f.write(src)

    print("OK - coefficients reels du BEF appliques.")
    print("  Francais 2 | Maths 2 | Physique-Chimie 1 | SVT 0,5  (total 5,5)")
    print("Sauvegarde : app_orientation_avant_coef_bef.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
