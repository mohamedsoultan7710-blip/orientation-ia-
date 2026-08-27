"""
Extraction : transforme le texte brut d'un bulletin en donnees structurees.
Adapte au vrai format des bulletins de 9eme annee djiboutiens.

Structure d'une ligne de matiere :
    matiere | enseignant | NB Note | Rang | Moyenne Eleve | Moyenne Classe
La note qui nous interesse est la MOYENNE ELEVE = le premier nombre a virgule.
"""

import re
import unicodedata
from rapidfuzz import fuzz

# --- Les 14 matieres du bulletin de 9eme ---
# Cle = nom officiel. Valeur = toutes les facons dont l'OCR peut l'ecrire.
MATIERES = {
    "Anglais": ["anglais", "english", "angl"],
    "Arabe": ["arabe", "langue arabe"],
    "Art plastique": ["art plastique", "arts plastiques", "art"],
    "Decouverte des metiers": ["decouverte des metiers", "dec metiers",
                               "decouverte metiers", "dec metier"],
    "EMCI": ["emci", "education morale civile et islamique",
             "education morale civique et islamique"],
    "EPS": ["eps", "education physique et sportive", "education physique"],
    "Francais": ["francais", "langue francaise"],
    "Histoire-Geographie": ["hg", "histoire geographie", "histoire geo"],
    "Informatique": ["informatique", "info"],
    "Mathematiques": ["maths", "math", "mathematiques", "mathematique"],
    "Physique-Chimie": ["physique chimie", "sciences physiques", "pc"],
    "STIM": ["stim", "estim"],
    "SVT": ["svt", "sciences de la vie et de la terre", "sciences naturelles"],
    "Vie scolaire": ["vs", "vie scolaire"],
}

SEUIL_RESSEMBLANCE = 85


def normaliser(texte):
    """Minuscules, sans accents, sans ponctuation. Pour comparer facilement."""
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    texte = texte.lower()
    texte = re.sub(r"[^a-z0-9 ]", " ", texte)
    return re.sub(r"\s+", " ", texte).strip()


def trouver_matiere(ligne):
    """Retourne le nom officiel de la matiere de cette ligne, ou None."""
    texte = normaliser(ligne)
    sans_chiffres = re.sub(r"\d+", " ", texte)
    sans_chiffres = re.sub(r"\s+", " ", sans_chiffres).strip()
    if not sans_chiffres:
        return None

    mots = sans_chiffres.split()

    # 1er passage : les abreviations courtes doivent etre un mot entier
    for officiel, variantes in MATIERES.items():
        for variante in variantes:
            v = normaliser(variante)
            if len(v) <= 4 and v in mots:
                return officiel

    # 2e passage : ressemblance floue pour les noms complets
    meilleur, meilleur_score = None, 0
    for officiel, variantes in MATIERES.items():
        for variante in variantes:
            v = normaliser(variante)
            if len(v) <= 4:
                continue
            score = fuzz.token_set_ratio(v, sans_chiffres)
            if score > meilleur_score:
                meilleur, meilleur_score = officiel, score

    return meilleur if meilleur_score >= SEUIL_RESSEMBLANCE else None


def trouver_note(ligne):
    """
    Retourne la moyenne de l'eleve.
    Sur le vrai bulletin il y a plusieurs nombres par ligne :
        ANGLAIS  ...  3   15   15.00   13.15
                      |    |     |       |
                 nb notes rang ELEVE  classe
    Les nombres a virgule sont donc prioritaires, et on prend le PREMIER.
    """
    decimaux = re.findall(r"\d{1,2}[.,]\d{1,3}", ligne)
    for c in decimaux:
        valeur = float(c.replace(",", "."))
        if 0 <= valeur <= 20:
            return valeur

    # Repli : aucun nombre a virgule sur la ligne
    for c in re.findall(r"\b\d{1,2}\b", ligne):
        valeur = float(c)
        if 0 <= valeur <= 20:
            return valeur

    return None


def extraire_notes(texte):
    """Parcourt le texte ligne par ligne et retourne {matiere: note}."""
    resultat = {}
    for ligne in texte.splitlines():
        matiere = trouver_matiere(ligne)
        if matiere is None or matiere in resultat:
            continue
        note = trouver_note(ligne)
        if note is not None:
            resultat[matiere] = note
    return resultat


def premier_decimal(ligne):
    """Le premier nombre a virgule de la ligne, ou None."""
    trouve = re.search(r"\d{1,2}[.,]\d{1,3}", ligne)
    return float(trouve.group(0).replace(",", ".")) if trouve else None


def extraire_entete(texte):
    """Recupere les informations hors tableau des notes."""
    infos = {
        "nom": None,
        "classe": None,
        "trimestre": None,
        "moyenne_generale": None,
        "moyennes_trimestres": {},
        "moyenne_annuelle": None,
        "moyenne_bef": None,
        "moyenne_admission": None,
        "decision": None,
    }

    for ligne in texte.splitlines():
        n = normaliser(ligne)

        # --- du plus precis au plus general ---
        if "moyenne admission" in n or "moyen admission" in n:
            infos["moyenne_admission"] = premier_decimal(ligne)

        elif "moyenne bef" in n or "moyen bef" in n:
            infos["moyenne_bef"] = premier_decimal(ligne)

        elif "annuelle" in n and "moyen" in n:
            infos["moyenne_annuelle"] = premier_decimal(ligne)

        elif "trimestre" in n and "moyen" in n:
            numero = re.search(r"trimestre\s*([123])", n)
            valeur = premier_decimal(ligne)
            if numero and valeur is not None:
                infos["moyennes_trimestres"][int(numero.group(1))] = valeur

        elif "moyenne generale" in n and infos["moyenne_generale"] is None:
            infos["moyenne_generale"] = premier_decimal(ligne)

        # --- decision d'orientation ---
        if infos["decision"] is None and "admis" in n:
            if re.search(r"\blg\b", n) or "lycee general" in n:
                infos["decision"] = "Lycee general"
            elif re.search(r"\blic\b", n):
                infos["decision"] = "LIC"
            else:
                infos["decision"] = ligne.strip()

        # --- nom, s'il y a une etiquette ---
        if infos["nom"] is None and re.search(r"\bnom\b", n):
            trouve = re.search(r"nom[^:]*:\s*(.+)", ligne, re.IGNORECASE)
            if trouve:
                infos["nom"] = trouve.group(1).strip()

        # --- classe, s'il y a une etiquette ---
        if infos["classe"] is None and re.search(r"\bclasse\b", n):
            trouve = re.search(r"classe\s*:?\s*(.+)", ligne, re.IGNORECASE)
            if trouve:
                infos["classe"] = trouve.group(1).strip()

    # Repli classe : le vrai bulletin ecrit juste "9eme - 9EME11"
    if infos["classe"] is None:
        trouve = re.search(r"\b([6-9])\s*eme", normaliser(texte))
        if trouve:
            infos["classe"] = trouve.group(1) + "eme"

    # Le trimestre du bulletin = le dernier trimestre renseigne
    if infos["moyennes_trimestres"]:
        infos["trimestre"] = max(infos["moyennes_trimestres"])
    else:
        for ligne in texte.splitlines():
            n = normaliser(ligne)
            if "trimestre" in n:
                trouve = re.search(r"([123])\s*(er|eme|e)?\s*trimestre", n)
                if trouve:
                    infos["trimestre"] = int(trouve.group(1))
                    break

    return infos


def analyser(texte):
    """Assemble tout : entete + notes + moyenne recalculee."""
    donnees = extraire_entete(texte)
    donnees["notes"] = extraire_notes(texte)

    valeurs = list(donnees["notes"].values())
    donnees["moyenne_calculee"] = round(sum(valeurs) / len(valeurs), 2) if valeurs else None

    return donnees


# --- Zone de test ---
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ocr_bulletin import lire_texte

    if len(sys.argv) < 2:
        print("Utilisation : python modules\\extraction_bulletin.py photo.jpg")
        sys.exit()

    texte_lu = lire_texte(sys.argv[1])
    d = analyser(texte_lu)

    print("=" * 58)
    print("Classe            :", d["classe"])
    print("Trimestre         :", d["trimestre"])
    print("Moyenne du bull.  :", d["moyenne_generale"])
    print("Moyenne recalculee:", d["moyenne_calculee"])
    print("-" * 58)
    print("Moyennes trimestres :", d["moyennes_trimestres"])
    print("Moyenne annuelle    :", d["moyenne_annuelle"])
    print("Moyenne BEF         :", d["moyenne_bef"])
    print("Moyenne admission   :", d["moyenne_admission"])
    print("Decision            :", d["decision"])
    print("-" * 58)
    print(f"{len(d['notes'])} matieres trouvees :")
    for matiere, note in d["notes"].items():
        print(f"   {matiere:<25} {note}")
    print("=" * 58)