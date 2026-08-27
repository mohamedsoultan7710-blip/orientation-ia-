"""
Separe la serie SG en ses trois specialites dans le CALCUL du score.

  GFM  : tronc commun + SES coef 7 + IG coef 3
  IAG  : tronc commun + IG  coef 7 + SES coef 3
  OGRH : tronc commun + SES coef 1 + IG  coef 1
  tronc commun SG : Francais 7, Arabe 4, Anglais 4, Mathematiques 3, HG 2

Le classement passe de 4 a 6 lignes. Les diagnostics existants
(diagnostic_gfm / _iag / _ogrh) sont reutilises tels quels.

Lancer depuis C:\\Users\\Gebruiker\\Desktop\\orientation-ia
    .\\venv\\Scripts\\python.exe patch_seconde_sg.py
"""
import io, os, shutil, sys

FICHIER = os.path.join("modules", "recommandation_seconde.py")

OLD1 = '''NOMS_SERIES = {"S": "Scientifique", "ES": "Economique et Sociale",
               "L": "Litteraire", "SG": "Sciences de Gestion"}'''
NEW1 = '''NOMS_SERIES = {"S": "Scientifique", "ES": "Economique et Sociale",
               "L": "Litteraire", "SG": "Sciences de Gestion",
               "GFM": "SG - Gestion Financiere et Mecatronique",
               "IAG": "SG - Informatique Appliquee a la Gestion",
               "OGRH": "SG - Organisation et Gestion des Ressources Humaines"}
SPE_SG = ("GFM", "IAG", "OGRH")'''

OLD2 = '''    "SG": {"Francais": 7, "Arabe": 4, "Anglais": 4, "Mathematiques": 3, "HG": 2},
}'''
NEW2 = '''    # Tronc commun SG + les coefficients propres a chaque specialite
    "GFM":  {"Francais": 7, "Arabe": 4, "Anglais": 4, "Mathematiques": 3,
             "HG": 2, "SES": 7, "IG": 3},
    "IAG":  {"Francais": 7, "Arabe": 4, "Anglais": 4, "Mathematiques": 3,
             "HG": 2, "IG": 7, "SES": 3},
    "OGRH": {"Francais": 7, "Arabe": 4, "Anglais": 4, "Mathematiques": 3,
             "HG": 2, "SES": 1, "IG": 1},
}'''

OLD3 = '''    if nom_serie == "SG":
        valide, validees, detail = diagnostic_sg(notes, moy_generale)'''
NEW3 = '''    if nom_serie == "GFM":
        return diagnostic_gfm(notes, moy_generale)
    if nom_serie == "IAG":
        return diagnostic_iag(notes)
    if nom_serie == "OGRH":
        return diagnostic_ogrh(notes, moy_generale)
    if nom_serie == "SG":
        valide, validees, detail = diagnostic_sg(notes, moy_generale)'''

OLD4 = '''    if serie_top == "SG" or "SG" in validees:'''
NEW4 = '''    if (serie_top in SPE_SG or serie_top == "SG"
            or any(v in SPE_SG or v == "SG" for v in validees)):'''


def main():
    if not os.path.exists(FICHIER):
        print("ERREUR : lance ce script depuis le dossier du projet.")
        return 1
    with io.open(FICHIER, encoding="utf-8") as f:
        src = f.read()

    if "SPE_SG" in src:
        print("Deja applique. Rien a faire.")
        return 0

    paires = [(OLD1, NEW1), (OLD2, NEW2), (OLD3, NEW3), (OLD4, NEW4)]
    for i, (old, _) in enumerate(paires, 1):
        if src.count(old) != 1:
            print("ERREUR : motif %d introuvable ou en double (%d). Rien modifie."
                  % (i, src.count(old)))
            return 1

    shutil.copyfile(FICHIER, os.path.join("modules",
                    "recommandation_seconde_avant_sg.py"))
    for old, new in paires:
        src = src.replace(old, new)
    with io.open(FICHIER, "w", encoding="utf-8", newline="") as f:
        f.write(src)

    print("OK - SG separee en GFM / IAG / OGRH.")
    print("  GFM  : SES 7 | IG 3")
    print("  IAG  : IG  7 | SES 3")
    print("  OGRH : SES 1 | IG 1")
    print("Sauvegarde : modules\\recommandation_seconde_avant_sg.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
