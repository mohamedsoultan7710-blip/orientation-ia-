"""
Compare plusieurs reglages d'OCR sur une meme photo et designe le meilleur.
"""

import os
import sys
import cv2
import pytesseract

CHEMIN_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(CHEMIN_TESSERACT):
    pytesseract.pytesseract.tesseract_cmd = CHEMIN_TESSERACT

# Mots qu'on doit retrouver si la lecture est bonne
MOTS_CLES = ["anglais", "arabe", "francais", "math", "informatique", "svt",
             "eps", "art", "metiers", "emci", "physique", "stim",
             "moyenne", "trimestre", "rang"]


def preparations(chemin):
    """Retourne plusieurs versions de l'image a tester."""
    image = cv2.imread(chemin)
    if image is None:
        raise FileNotFoundError(f"Image introuvable : {chemin}")

    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    hauteur, largeur = gris.shape
    if largeur < 2000:
        facteur = 2000 / largeur
        gris = cv2.resize(gris, None, fx=facteur, fy=facteur,
                          interpolation=cv2.INTER_CUBIC)

    _, otsu = cv2.threshold(gris, 0, 255,
                            cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    adaptatif = cv2.adaptiveThreshold(
        cv2.medianBlur(gris, 3), 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)

    return {
        "1-aucun traitement": gris,
        "2-otsu": otsu,
        "3-adaptatif": adaptatif,
    }


def score(texte):
    """Combien de mots attendus sont presents dans le texte lu."""
    t = texte.lower()
    return sum(1 for mot in MOTS_CLES if mot in t)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Utilisation : python test_ocr.py photo.jpg")
        sys.exit()

    images = preparations(sys.argv[1])
    resultats = []

    for nom_image, image in images.items():
        for psm in (4, 6, 11, 12):
            config = f"--oem 3 --psm {psm}"
            texte = pytesseract.image_to_string(image, lang="fra", config=config)
            resultats.append((score(texte), len(texte), nom_image, psm, texte))

    resultats.sort(key=lambda r: (-r[0], -r[1]))

    print("=" * 62)
    print("CLASSEMENT DES REGLAGES")
    print("=" * 62)
    for s, longueur, nom_image, psm, _ in resultats:
        print(f"  {s:>2}/{len(MOTS_CLES)} mots | {longueur:>5} car. | "
              f"{nom_image:<20} | psm {psm}")

    meilleur = resultats[0]
    print("=" * 62)
    print(f"MEILLEUR : {meilleur[2]}  avec  psm {meilleur[3]}")
    print("=" * 62)
    print(meilleur[4])