"""
Genere une fausse image de bulletin djiboutien pour tester l'OCR.
On connait exactement son contenu, donc on peut mesurer les erreurs.
"""

from PIL import Image, ImageDraw, ImageFont

LARGEUR, HAUTEUR = 1240, 1754   # format A4 en 150 dpi


def police(taille, gras=False):
    """Charge une police Windows. Repli sur la police par defaut si absente."""
    chemin = r"C:\Windows\Fonts\arialbd.ttf" if gras else r"C:\Windows\Fonts\arial.ttf"
    try:
        return ImageFont.truetype(chemin, taille)
    except OSError:
        return ImageFont.load_default()


# Les notes du bulletin fictif (coefficients egaux, comme au college djiboutien)
NOTES = [
    ("Francais", "13.50"),
    ("Arabe", "15.25"),
    ("Anglais", "11.00"),
    ("Mathematiques", "16.75"),
    ("Sciences de la Vie et de la Terre", "14.00"),
    ("Physique-Chimie", "15.50"),
    ("Histoire-Geographie", "10.25"),
    ("Technologie", "12.00"),
    ("Informatique", "17.00"),
    ("Education islamique", "16.00"),
    ("Education physique et sportive", "13.00"),
]

image = Image.new("RGB", (LARGEUR, HAUTEUR), "white")
d = ImageDraw.Draw(image)

y = 60
d.text((60, y), "REPUBLIQUE DE DJIBOUTI", font=police(28, True), fill="black")
y += 42
d.text((60, y), "MINISTERE DE L'EDUCATION NATIONALE", font=police(20), fill="black")
y += 32
d.text((60, y), "ET DE LA FORMATION PROFESSIONNELLE", font=police(20), fill="black")
y += 32
d.text((60, y), "COLLEGE D'ENSEIGNEMENT MOYEN DE BALBALA", font=police(20), fill="black")

y += 65
d.text((60, y), "BULLETIN DU 1er TRIMESTRE", font=police(26, True), fill="black")
y += 40
d.text((60, y), "Annee scolaire 2025-2026", font=police(22), fill="black")

y += 55
d.text((60, y), "Nom et prenom : AHMED MOHAMED HASSAN", font=police(22), fill="black")
y += 35
d.text((60, y), "Classe : 9eme A", font=police(22), fill="black")
y += 35
d.text((60, y), "Effectif : 42 eleves", font=police(22), fill="black")

# En-tete du tableau
y += 60
d.text((70, y), "MATIERE", font=police(22, True), fill="black")
d.text((720, y), "MOYENNE", font=police(22, True), fill="black")
d.text((950, y), "COEF", font=police(22, True), fill="black")
y += 38
d.line((60, y, LARGEUR - 60, y), fill="black", width=2)
y += 20

# Les lignes du tableau
for matiere, moyenne in NOTES:
    d.text((70, y), matiere, font=police(22), fill="black")
    d.text((720, y), moyenne, font=police(22), fill="black")
    d.text((950, y), "1", font=police(22), fill="black")
    y += 45

y += 15
d.line((60, y, LARGEUR - 60, y), fill="black", width=2)
y += 30
d.text((70, y), "MOYENNE GENERALE : 14.02 / 20", font=police(26, True), fill="black")
y += 48
d.text((70, y), "RANG : 7 sur 42", font=police(22), fill="black")
y += 35
d.text((70, y), "APPRECIATION : Bon trimestre, continuez vos efforts.", font=police(20), fill="black")

image.save("test_bulletin.png")
print("OK -> image creee : test_bulletin.png")