"""
Verification : ce document est-il un bulletin scolaire ?

Principe : on ne cherche PAS a lire parfaitement. On verifie seulement
qu'il s'agit bien d'un bulletin. Les notes que l'OCR arrive a lire
servent de pre-remplissage ; l'eleve corrige et complete ensuite.
"""

from rapidfuzz import fuzz

try:
    from modules.extraction_bulletin import normaliser, MATIERES
except ImportError:
    from extraction_bulletin import normaliser, MATIERES


# Mots reellement presents sur un bulletin djiboutien
MARQUEURS_BULLETIN = [
    "matiere", "enseignant", "rang", "appreciation", "moyenne",
    "trimestre", "annee scolaire", "eleve", "classe", "absences",
    "professeur principal", "conseil de classe", "bulletin", "college",
]

MARQUEURS_MINIMUM = 3       # en dessous : ce n'est pas un bulletin
TOLERANCE_MOYENNE = 0.5
SEUIL_NOM = 80


def comparer_nom(nom_a, nom_b):
    """Pourcentage de ressemblance entre deux noms, ou None."""
    if not nom_a or not nom_b:
        return None
    return int(fuzz.token_set_ratio(normaliser(nom_a), normaliser(nom_b)))


def verifier(texte_brut, donnees, nom_saisi=None):
    """
    Retourne un rapport : controles, score, niveau.
    NON RECONNU = ce n'est pas un bulletin (seul cas de rejet).
    """
    controles = []
    score = 0
    total = 0

    texte = normaliser(texte_brut)

    # --- Controle 1 : est-ce un bulletin ? (le seul qui peut rejeter) ---
    total += 50
    trouves = [m for m in MARQUEURS_BULLETIN if normaliser(m) in texte]
    nb_marqueurs = len(trouves)

    if nb_marqueurs >= 6:
        score += 50
        controles.append(("ok", "Bulletin scolaire reconnu",
                          f"{nb_marqueurs} elements de bulletin identifies"))
    elif nb_marqueurs >= MARQUEURS_MINIMUM:
        score += 30
        controles.append(("attention", "Probablement un bulletin",
                          f"{nb_marqueurs} elements identifies seulement"))
    else:
        controles.append(("erreur", "Ce n'est pas un bulletin",
                          f"{nb_marqueurs} element(s) de bulletin trouve(s)"))

    # --- Controle 2 : combien de notes pre-remplies ? (jamais bloquant) ---
    total += 20
    notes = donnees.get("notes", {})
    nb = len(notes)
    attendu = len(MATIERES)

    if nb >= 10:
        score += 20
        controles.append(("ok", "Notes lues",
                          f"{nb} matieres sur {attendu} pre-remplies"))
    elif nb >= 1:
        score += 10
        controles.append(("attention", "Lecture partielle",
                          f"{nb} matiere(s) lue(s) — complete les autres a la main"))
    else:
        controles.append(("attention", "Notes illisibles",
                          "Aucune note lue — saisis-les toi-meme ci-dessous"))

    # --- Controle 3 : coherence du calcul (seulement si assez de notes) ---
    lue = donnees.get("moyenne_generale")
    calculee = donnees.get("moyenne_calculee")

    if nb >= 10 and lue is not None and calculee is not None:
        total += 20
        ecart = abs(lue - calculee)
        if ecart <= TOLERANCE_MOYENNE:
            score += 20
            controles.append(("ok", "Calcul coherent",
                              f"Lue {lue} / recalculee {calculee}"))
        else:
            controles.append(("attention", "Ecart de calcul",
                              f"Lue {lue} mais recalculee {calculee} "
                              f"(ecart {ecart:.2f}) — verifie les notes"))
    else:
        controles.append(("attention", "Calcul non verifiable",
                          "Pas assez de notes lues pour verifier la moyenne"))

    # --- Controle 4 : la classe ---
    total += 10
    classe = donnees.get("classe")
    if classe:
        score += 10
        controles.append(("ok", "Classe lue", classe))
    else:
        controles.append(("attention", "Classe illisible",
                          "A confirmer ci-dessous"))

    pourcentage = round(100 * score / total) if total else 0
    pas_un_bulletin = any(c[1] == "Ce n'est pas un bulletin" for c in controles)

    if pas_un_bulletin:
        niveau = "NON RECONNU"
    elif pourcentage >= 75:
        niveau = "CONFORME"
    else:
        niveau = "A COMPLETER"

    return {
        "niveau": niveau,
        "pourcentage": pourcentage,
        "controles": controles,
    }


# --- Zone de test ---
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ocr_bulletin import lire_texte
    from extraction_bulletin import analyser

    if len(sys.argv) < 2:
        print("Utilisation : python modules\\verification_bulletin.py photo.jpg")
        sys.exit()

    texte_lu = lire_texte(sys.argv[1])
    donnees_lues = analyser(texte_lu)
    rapport = verifier(texte_lu, donnees_lues)

    symboles = {"ok": "[OK]", "attention": "[!]", "erreur": "[X]"}

    print("=" * 62)
    print(f"NIVEAU : {rapport['niveau']}   ({rapport['pourcentage']}%)")
    print("=" * 62)
    for etat, titre, detail in rapport["controles"]:
        print(f"{symboles[etat]:<5} {titre:<28} {detail}")
    print("=" * 62)
    print("Classe    :", donnees_lues["classe"])
    print("Trimestre :", donnees_lues["trimestre"])
    print("Notes     :", donnees_lues["notes"])