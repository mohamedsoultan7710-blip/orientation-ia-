"""
Module OCR : lit la photo d'un bulletin et en extrait le texte brut.
"""

import os
import cv2
import pytesseract

# --- Securite : on indique le chemin de Tesseract directement ---
CHEMIN_TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(CHEMIN_TESSERACT):
    pytesseract.pytesseract.tesseract_cmd = CHEMIN_TESSERACT


def preparer_image(chemin_image):
    """
    Nettoie la photo avant lecture.
    Une photo de telephone a souvent des ombres et peu de contraste.
    Ces 4 traitements ameliorent beaucoup la lecture.
    """
    image = cv2.imread(chemin_image)
    if image is None:
        raise FileNotFoundError(f"Image introuvable ou illisible : {chemin_image}")

    # 1. Noir et blanc (la couleur ne sert a rien pour lire du texte)
    gris = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 2. Agrandir si la photo est petite
    hauteur, largeur = gris.shape
    if largeur < 1500:
        facteur = 1500 / largeur
        gris = cv2.resize(gris, None, fx=facteur, fy=facteur,
                          interpolation=cv2.INTER_CUBIC)

    # 3. Reduire le bruit
    gris = cv2.medianBlur(gris, 3)

    # 4. Texte bien noir sur fond bien blanc
    net = cv2.adaptiveThreshold(
        gris, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31, 15
    )
    return net


def lire_texte(chemin_image, langues="fra+eng"):
    """
    Retourne le texte brut lu sur l'image.
    psm 6 = traiter l'image comme un bloc de texte uniforme,
            ce qui convient bien aux tableaux de bulletins.
    """
    image_nette = preparer_image(chemin_image)
    configuration = "--oem 3 --psm 6"
    texte = pytesseract.image_to_string(
        image_nette,
        lang=langues,
        config=configuration
    )
    return texte


# --- Zone de test ---
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Utilisation : python modules\\ocr_bulletin.py photo.jpg")
        sys.exit()

    chemin = sys.argv[1]
    resultat = lire_texte(chemin)

    print("=" * 60)
    print(resultat)
    print("=" * 60)
    print(f"--> {len(resultat)} caracteres lus.")
