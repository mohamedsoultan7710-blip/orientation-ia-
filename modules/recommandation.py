"""
Moteur de recommandation - parcours College (apres la 9eme).
Sortie : Lycee general ou LIC. Rien d'autre.

La moyenne decide la voie, parce que c'est elle qui decide reellement.
L'ambition sert a donner un objectif concret.
Rien n'est confirme : l'affectation se fait au classement, par le MENFOP.
"""

import os
import json

FICHIER_METIERS = os.path.join("data", "metiers.json")

POIDS_ANNEE = 0.60
POIDS_BEF = 0.40
HYPOTHESES_BEF = [8, 10, 12, 14, 16, 18]


def charger_metiers(chemin=FICHIER_METIERS):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)["metiers"]


def notes_moyennes(eleve):
    cumul = {}
    for bulletin in eleve.get("bulletins", []):
        for matiere, note in bulletin.get("notes", {}).items():
            cumul.setdefault(matiere, []).append(note)
    return {m: round(sum(v) / len(v), 2) for m, v in cumul.items()}


def moyennes_trimestres(eleve):
    resultat = {}
    for bulletin in eleve.get("bulletins", []):
        if bulletin.get("moyenne") is not None:
            resultat[bulletin.get("trimestre", 0)] = bulletin["moyenne"]
    return dict(sorted(resultat.items()))


def tendance(eleve):
    valeurs = list(moyennes_trimestres(eleve).values())
    return round(valeurs[-1] - valeurs[-2], 2) if len(valeurs) >= 2 else None


# ---------- La voie ----------

def situation(moyenne):
    """
    (cle, voie, message). Quatre paliers.
    Aucun seuil officiel n'existe : ces reperes servent a adapter le
    conseil, jamais a annoncer une affectation. En dessous de 10, on
    ne recommande aucune orientation — on parle de remontee.
    """
    if moyenne is None:
        return ("inconnue", None, "Je n'ai pas assez de notes pour te situer.")

    if moyenne >= 12:
        return ("favorable", "Lycee general", (
            f"Avec {moyenne}/20, on te recommande de viser le lycee general : "
            "ton dossier est en bonne position. Ce n'est pas une garantie — "
            "l'affectation se fait au classement de toute la promotion, et le "
            "point de coupure change chaque annee. Garde ce rythme, reste "
            "regulier, ne relache pas au 3e trimestre."))

    if moyenne >= 10:
        return ("ouvert", "Lycee general ou LIC", (
            f"Avec {moyenne}/20, les deux voies te restent ouvertes, mais ton "
            "dossier est encore fragile. Chaque dixieme de point te fait "
            "remonter dans le classement. Le 3e trimestre et le BEF sont "
            "l'occasion de consolider ta position — c'est maintenant que ca "
            "se joue."))

    if moyenne >= 8:
        return ("remontee", "Remonter d'abord", (
            f"Avec {moyenne}/20, on ne va pas te recommander une orientation "
            "aujourd'hui : ce serait te donner une fausse idee de ta "
            "situation. Ton objectif immediat n'est pas de choisir une voie, "
            "c'est de remonter ta moyenne. Le 3e trimestre et le BEF peuvent "
            "encore changer beaucoup de choses, mais il faut agir des "
            "maintenant."))

    return ("alerte", "Priorite : remonter", (
        f"Avec {moyenne}/20, ta situation demande une reaction rapide. Parler "
        "d'orientation maintenant n'aurait pas de sens : la vraie question, "
        "c'est comment remonter. Ce n'est pas une fatalite, et ton parcours "
        "n'est pas decide — mais il faut un plan de travail des cette "
        "semaine, et de l'aide autour de toi."))


DESCRIPTION_LYCEE = [
    "Trois ans : Seconde, Premiere, Terminale, puis le Baccalaureat.",
    "En fin de Seconde tu choisiras ta serie parmi S, ES, L, IAG, GFM, OGRH.",
    "Ensuite l'universite : Medecine, Ecole d'Ingenieurs, Droit, Sciences, "
    "Lettres, Economie-Gestion — a Djibouti ou a l'etranger.",
    "C'est la voie des metiers qui demandent des etudes longues.",
]

DESCRIPTION_LIC = [
    "Formation aux metiers de l'Administration, du Commerce et de l'Industrie.",
    "BEP en 2 ans, puis Baccalaureat Professionnel en 2 ans de plus.",
    "Des licences professionnelles existent maintenant (logistique-transport, "
    "commerce international), ouvertes avec des partenaires chinois.",
    "Le secteur transport-logistique-portuaire compte environ 200 entreprises "
    "et 15 000 emplois : c'est le premier employeur du pays.",
]


# ---------- L'ambition ----------

def objectif_metier(profil, metiers, cle):
    nom = profil.get("ambition", "")
    libre = profil.get("ambition_libre", "").strip()

    if nom.startswith("Autre"):
        if not libre:
            return None
        texte = (f"Tu veux devenir {libre}. Je n'ai pas d'information officielle "
                 "sur ce parcours precis a Djibouti — renseigne-toi aupres du "
                 "Service d'Orientation de ton etablissement. Ce que je peux te "
                 "dire : les metiers qui demandent des etudes superieures passent "
                 "par le lycee, puis l'universite.")
        if cle in ("remontee", "alerte"):
            texte += (" Tes notes actuelles n'y menent pas encore, mais il te "
                      "reste du temps : c'est un objectif clair.")
        elif cle == "ouvert":
            texte += " Tu n'en es pas loin — quelques points de plus et tu y es."
        return {"metier": libre, "message": texte}

    for metier in metiers:
        if metier["nom"] != nom:
            continue

        texte = metier["explication"]
        if metier["voie"] == "lycee" and cle in ("remontee", "alerte"):
            texte += (" Ce metier passe par le lycee. Tes notes actuelles n'y "
                      "menent pas encore — mais il te reste du temps, et tu sais "
                      "maintenant exactement quoi viser.")
        elif metier["voie"] == "lycee" and cle == "ouvert":
            texte += (" Ce metier passe par le lycee, et tu n'en es pas loin. "
                      "Quelques points de plus et tu y es.")
        elif metier["voie"] == "lic":
            texte += " Le LIC est la voie directe pour ce metier, avec une insertion rapide."

        return {"metier": nom, "message": texte}

    return None


# ---------- Objectifs chiffres ----------

def tableau_bef(moyenne_annuelle):
    """Moyenne d'admission = 0.60 x moyenne annuelle + 0.40 x note du BEF."""
    if moyenne_annuelle is None:
        return []
    return [{"bef": b,
             "admission": round(POIDS_ANNEE * moyenne_annuelle + POIDS_BEF * b, 2)}
            for b in HYPOTHESES_BEF]


def matieres_a_renforcer(notes, combien=3):
    faibles = sorted((n, m) for m, n in notes.items() if n < 12)
    return [(m, n) for n, m in faibles[:combien]]


def points_forts(notes, combien=3):
    forts = sorted(((n, m) for m, n in notes.items()), reverse=True)
    return [(m, n) for n, m in forts[:combien]]


# ---------- Assemblage ----------

def recommander(eleve, metiers=None):
    if metiers is None:
        metiers = charger_metiers()

    profil = eleve.get("profil", {})
    notes = notes_moyennes(eleve)
    moyennes_t = moyennes_trimestres(eleve)
    valeurs = list(moyennes_t.values())
    moyenne = round(sum(valeurs) / len(valeurs), 2) if valeurs else None

    cle, voie, message = situation(moyenne)

    return {
        "moyenne": moyenne,
        "moyennes_trimestres": moyennes_t,
        "tendance": tendance(eleve),
        "voie": voie,
        "situation": cle,
        "message": message,
        "description_lycee": DESCRIPTION_LYCEE,
        "description_lic": DESCRIPTION_LIC,
        "objectif_metier": objectif_metier(profil, metiers, cle),
        "points_forts": points_forts(notes),
        "a_renforcer": matieres_a_renforcer(notes),
        "tableau_bef": tableau_bef(moyenne),
    }


# --- Zone de test ---
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Utilisation : python modules\\recommandation.py data\\bulletins\\x.json")
        sys.exit()

    with open(sys.argv[1], encoding="utf-8") as f:
        donnees = json.load(f)

    r = recommander(donnees)

    print("=" * 68)
    print("ELEVE :", donnees.get("nom"), "| Moyenne :", r["moyenne"],
          "| Tendance :", r["tendance"])
    print("=" * 68)
    print(">>> CE QU'ON TE RECOMMANDE :", r["voie"])
    print()
    print(r["message"])

    if r["objectif_metier"]:
        print("\nTON PROJET :")
        print("  " + r["objectif_metier"]["message"])

    principale = (r["description_lycee"] if r["situation"] in ("favorable", "ouvert")
                  else r["description_lic"])
    autre = (r["description_lic"] if r["situation"] in ("favorable", "ouvert")
             else r["description_lycee"])
    titre_autre = ("Pour information, le LIC" if r["situation"] in ("favorable", "ouvert")
                   else "Pour information, le lycee general")

    print("\nCE QUI T'ATTEND :")
    for ligne in principale:
        print("  - " + ligne)

    print(f"\n{titre_autre.upper()} :")
    for ligne in autre[:2]:
        print("  - " + ligne)

    print("\nTES POINTS FORTS :", r["points_forts"])
    print("A RENFORCER      :", r["a_renforcer"])

    print("\nPLUS TA NOTE AU BEF MONTE, PLUS TON ADMISSION MONTE :")
    for ligne in r["tableau_bef"]:
        print(f"    BEF {ligne['bef']:>2}/20  ->  admission {ligne['admission']}/20")
    print("=" * 68)