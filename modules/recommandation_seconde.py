"""
Recommandation d'orientation - Seconde (Lycee general).
Meme principe que le college : le CODE decide, avec des regles claires.

Deux couches independantes :
  1. Un palier general (favorable / ouvert / remontee / alerte), qui verifie
     si le trimestre est valide AVANT meme de parler de serie. En dessous de
     la moyenne, aucune serie n'est recommandee : il faut d'abord consolider.
  2. Une validation propre a chaque serie : etre en tete du classement ne
     suffit pas, il faut aussi passer un seuil dans les matieres cles de
     cette serie precise. Sinon on montre ce qu'il manque, jamais une
     recommandation en l'air.
"""

MATIERES_SECONDE = ["Francais", "Arabe", "Anglais", "Mathematiques", "HG",
                     "SVT", "Physique-Chimie", "EPS", "IG", "SES"]
LANGUES_RARES = ["Chinois", "Turc"]

NOMS_SERIES = {"S": "Scientifique", "ES": "Economique et Sociale",
               "L": "Litteraire", "SG": "Sciences de Gestion"}
SPECIALITES_SG = {"IAG": "Informatique Appliquee a la Gestion",
                   "OGRH": "Organisation et Gestion des Ressources Humaines",
                   "GFM": "Gestion Financiere et Mecatronique"}

POIDS_SERIE = {
    "S":  {"Mathematiques": 9, "Physique-Chimie": 8, "SVT": 8, "Francais": 5},
    "ES": {"SES": 9, "Mathematiques": 6, "HG": 6},
    "L":  {"Francais": 10, "Arabe": 7, "Anglais": 6, "HG": 5},
    "SG": {"Francais": 7, "Arabe": 4, "Anglais": 4, "Mathematiques": 3, "HG": 2},
}

PASSAGE = 10.0   # note qui valide un trimestre
BON = 12.0       # note correcte et solide
FORT = 14.0      # note d'eleve nettement au-dessus de la moyenne

VALIDATION_SERIE = {
    "S": {"matieres": ["Mathematiques", "Physique-Chimie", "SVT", "Francais"],
          "plancher": BON, "moyenne_cle_min": FORT},
    "ES": {"matieres": ["SES", "Mathematiques", "HG"],
           "plancher": PASSAGE, "moyenne_cle_min": BON},
    "L": {"matieres": ["Francais", "Arabe", "Anglais", "HG"],
          "plancher": BON, "moyenne_cle_min": FORT},
}


def notes_moyennes(eleve):
    """Moyenne de chaque matiere sur l'ensemble des bulletins Seconde."""
    totaux, comptes = {}, {}
    for bulletin in eleve.get("bulletins", []):
        for matiere, note in bulletin.get("notes", {}).items():
            if note is None:
                continue
            totaux[matiere] = totaux.get(matiere, 0) + note
            comptes[matiere] = comptes.get(matiere, 0) + 1
    return {m: round(totaux[m] / comptes[m], 2) for m in totaux}


def moyennes_trimestres(eleve):
    """{numero_trimestre: moyenne generale de ce trimestre}."""
    resultat = {}
    for bulletin in eleve.get("bulletins", []):
        notes = {m: n for m, n in bulletin.get("notes", {}).items()
                  if m in MATIERES_SECONDE and n is not None}
        if notes:
            resultat[bulletin.get("trimestre")] = round(
                sum(notes.values()) / len(notes), 2)
    return resultat


def tendance(trimestres):
    valeurs = list(trimestres.values())
    if len(valeurs) < 2:
        return None
    return round(valeurs[-1] - valeurs[0], 2)


def moyenne_generale(notes):
    valeurs = [notes[m] for m in MATIERES_SECONDE if m in notes]
    if not valeurs:
        return None
    return round(sum(valeurs) / len(valeurs), 2)


def _moyenne_matieres(notes, matieres):
    valeurs = [notes[m] for m in matieres if notes.get(m) is not None]
    if not valeurs:
        return None
    return round(sum(valeurs) / len(valeurs), 2)


def langue_rare(eleve):
    return eleve.get("langue_rare") or None


def points_forts(notes, plancher=BON):
    """Meilleures matieres, mais seulement si elles sont reellement solides.
    Une note sous le plancher n'est jamais un point fort, meme si c'est la
    meilleure note de l'eleve : ce n'en est pas une pour autant."""
    candidats = [(m, notes[m]) for m in MATIERES_SECONDE
                 if m in notes and notes[m] >= plancher]
    candidats.sort(key=lambda x: -x[1])
    return candidats[:3]


def matieres_a_renforcer(notes, plancher=BON):
    candidats = [(m, notes[m]) for m in MATIERES_SECONDE
                 if m in notes and notes[m] < plancher]
    candidats.sort(key=lambda x: x[1])
    return candidats[:3]


def situation_generale(moyenne):
    """Avant de parler de serie, on verifie que le trimestre est valide.
    En dessous de 10, aucune serie n'est recommandee, quel que soit le
    classement des scores entre elles."""
    if moyenne is None:
        return "inconnue"
    if moyenne < 8:
        return "alerte"
    if moyenne < PASSAGE:
        return "remontee"
    return None  # >= 10 : a determiner selon la validation des series


def diagnostic_S_ES_L(nom, notes):
    """(valide, manques) - 'manques' est une liste de phrases pretes a
    afficher, jamais un code a interpreter plus tard."""
    regle = VALIDATION_SERIE[nom]
    manques = []
    for matiere in regle["matieres"]:
        note = notes.get(matiere)
        if note is None:
            manques.append(f"la note de {matiere} manque")
        elif note < regle["plancher"]:
            manques.append(f"{matiere} : {note}/20 (il faut au moins "
                            f"{regle['plancher']:.0f}/20)")
    moyenne_cle = _moyenne_matieres(notes, regle["matieres"])
    if moyenne_cle is not None and moyenne_cle < regle["moyenne_cle_min"]:
        manques.append(
            f"la moyenne sur {', '.join(regle['matieres'])} est de "
            f"{moyenne_cle}/20, il faut au moins {regle['moyenne_cle_min']:.0f}/20")
    return (len(manques) == 0), manques


def diagnostic_iag(notes):
    ig, maths = notes.get("IG"), notes.get("Mathematiques")
    manques = []
    if ig is None:
        manques.append("la note d'IG manque")
    elif ig < PASSAGE:
        manques.append(f"IG : {ig}/20 (il faut au moins {PASSAGE:.0f}/20)")
    if maths is None:
        manques.append("la note de Mathematiques manque")
    elif maths < PASSAGE:
        manques.append(f"Mathematiques : {maths}/20 (il faut au moins {PASSAGE:.0f}/20)")
    moyenne_cle = _moyenne_matieres(notes, ["IG", "Mathematiques"])
    if moyenne_cle is not None and moyenne_cle < BON:
        manques.append(f"la moyenne IG/Mathematiques est de {moyenne_cle}/20, "
                        f"il faut au moins {BON:.0f}/20")
    return (len(manques) == 0), manques


def diagnostic_gfm(notes, moy_generale):
    """Le GFM est plus demande a Djibouti : la barre est plus haute, et
    reussir seulement en SES et IG ne suffit pas, il faut garder un bon
    equilibre general aussi."""
    ses, ig = notes.get("SES"), notes.get("IG")
    manques = []
    if ses is None:
        manques.append("la note de SES manque")
    elif not (ses > 11):
        manques.append(f"SES : {ses}/20 (il faut plus de 11/20)")
    if ig is None:
        manques.append("la note d'IG manque")
    elif not (ig > 11):
        manques.append(f"IG : {ig}/20 (il faut plus de 11/20)")
    if moy_generale is not None and moy_generale < BON:
        manques.append(f"la moyenne generale est de {moy_generale}/20 : le "
                        f"GFM etant tres demande, il faut au moins "
                        f"{BON:.0f}/20 d'equilibre general, pas seulement "
                        "SES et IG")
    return (len(manques) == 0), manques


def diagnostic_ogrh(notes, moy_generale):
    """L'OGRH valide SES/IG a 10, ou alors une moyenne generale nettement
    au-dessus peut compenser ('valider par force')."""
    ses, ig = notes.get("SES"), notes.get("IG")
    if ses is not None and ig is not None and ses >= PASSAGE and ig >= PASSAGE:
        return True, []
    if moy_generale is not None and moy_generale >= FORT:
        return True, []
    manques = [
        f"SES : {ses if ses is not None else '—'}/20 "
        f"(il faut au moins {PASSAGE:.0f}/20)",
        f"IG : {ig if ig is not None else '—'}/20 "
        f"(il faut au moins {PASSAGE:.0f}/20)",
        f"ou, a defaut, une moyenne generale d'au moins {FORT:.0f}/20 "
        f"(actuellement {moy_generale}/20)",
    ]
    return False, manques


def diagnostic_sg(notes, moy_generale):
    """La SG est validee des qu'une specialite l'est. On garde le detail des
    3 pour pouvoir l'afficher, et on retient celle qui s'en rapproche le
    plus quand aucune n'est validee."""
    detail = {
        "IAG": diagnostic_iag(notes),
        "GFM": diagnostic_gfm(notes, moy_generale),
        "OGRH": diagnostic_ogrh(notes, moy_generale),
    }
    validees = [nom for nom, (valide, _) in detail.items() if valide]
    return (len(validees) > 0), validees, detail


def diagnostic(nom_serie, notes, moy_generale):
    if nom_serie in ("S", "ES", "L"):
        return diagnostic_S_ES_L(nom_serie, notes)
    if nom_serie == "SG":
        valide, validees, detail = diagnostic_sg(notes, moy_generale)
        if valide:
            return True, []
        plus_proche = min(detail.items(), key=lambda kv: len(kv[1][1]))
        nom_spe, (_, manques_spe) = plus_proche
        return False, [f"{nom_spe} ({SPECIALITES_SG[nom_spe]}) : " + m
                        for m in manques_spe]
    return False, ["serie inconnue"]


def score_serie(notes, poids):
    """Moyenne ponderee sur les matieres de cette serie. None si aucune note."""
    total, somme_poids, manquantes = 0, 0, []
    for matiere, coef in poids.items():
        note = notes.get(matiere)
        if note is None:
            manquantes.append(matiere)
            continue
        total += note * coef
        somme_poids += coef
    if somme_poids == 0:
        return None, manquantes
    return round(total / somme_poids, 2), manquantes


def classement(notes):
    resultats = []
    for nom, poids in POIDS_SERIE.items():
        score, manquantes = score_serie(notes, poids)
        resultats.append({"serie": nom, "nom_complet": NOMS_SERIES[nom],
                           "score": score, "manquantes": manquantes})
    resultats.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    return resultats


def ecart_tete(resultats):
    scores = [r["score"] for r in resultats if r["score"] is not None]
    if len(scores) < 2:
        return None
    return round(scores[0] - scores[1], 2)


def recommander(eleve):
    notes = notes_moyennes(eleve)
    trims = moyennes_trimestres(eleve)
    moy = moyenne_generale(notes)
    evol = tendance(trims)

    resultat = {
        "moyenne": moy,
        "moyennes_trimestres": trims,
        "tendance": evol,
        "langue_rare": langue_rare(eleve),
        "points_forts": points_forts(notes),
        "a_renforcer": matieres_a_renforcer(notes),
    }

    palier = situation_generale(moy)

    if palier in ("alerte", "remontee", "inconnue"):
        resultat.update({
            "situation": palier,
            "classement": [],
            "serie_recommandee": None,
            "series_validees": [],
            "diagnostic_series": {},
            "specialites_sg": {},
            "note_ig": notes.get("IG"),
            "ecart_premier_deuxieme": None,
            "profil_equilibre": False,
            "message": (
                "Il n'y a pas encore assez de notes pour se prononcer."
                if palier == "inconnue" else
                f"Ta moyenne generale est de {moy}/20. En dessous de "
                f"{PASSAGE:.0f}/20, le trimestre n'est pas valide et aucune "
                "serie ne peut etre recommandee pour l'instant : la priorite "
                "est de faire remonter cette moyenne, pas de choisir une "
                "serie."
            ),
        })
        return resultat

    rang = classement(notes)
    diag = {r["serie"]: diagnostic(r["serie"], notes, moy) for r in rang}
    for r in rang:
        r["valide"] = diag[r["serie"]][0]
        r["manques"] = diag[r["serie"]][1]
    validees = [r["serie"] for r in rang if r["valide"]]

    ecart = ecart_tete(rang)
    equilibre = ecart is not None and ecart < 1.0

    if validees:
        premiere_validee = next(r for r in rang if r["serie"] in validees)
        serie_top = premiere_validee["serie"]
        situation = "favorable"
        message = (f"Ta moyenne generale est de {moy}/20 et tu valides les "
                   f"conditions de la serie {serie_top} "
                   f"({NOMS_SERIES[serie_top]}). C'est elle qu'on te "
                   "recommande en priorite.")
        if len(validees) > 1:
            autres = ", ".join(v for v in validees if v != serie_top)
            message += (f" Tu remplis aussi les conditions de {autres} : "
                        "plusieurs voies te sont ouvertes.")
    else:
        serie_top = rang[0]["serie"]
        situation = "ouvert"
        message = (f"Ta moyenne generale est de {moy}/20, le trimestre est "
                   f"valide, mais aucune serie n'est encore confirmee. "
                   f"C'est {serie_top} ({NOMS_SERIES[serie_top]}) qui te "
                   "correspond le plus pour l'instant, mais il te manque : "
                   + "; ".join(rang[0]["manques"]) + ".")

    specialites_sg = {}
    if serie_top == "SG" or "SG" in validees:
        _, validees_sg, detail_sg = diagnostic_sg(notes, moy)
        specialites_sg = {
            "detail": detail_sg,
            "validees": validees_sg,
            "recommandee": validees_sg[0] if validees_sg else None,
        }

    resultat.update({
        "situation": situation,
        "classement": rang,
        "serie_recommandee": serie_top,
        "series_validees": validees,
        "diagnostic_series": diag,
        "specialites_sg": specialites_sg,
        "note_ig": notes.get("IG"),
        "ecart_premier_deuxieme": ecart,
        "profil_equilibre": equilibre,
        "message": message,
    })
    return resultat


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Utilisation : python modules\\recommandation_seconde.py data\\bulletins\\x.json")
        sys.exit()

    with open(sys.argv[1], encoding="utf-8") as f:
        eleve = json.load(f)

    r = recommander(eleve)

    print("=" * 62)
    print(f"Moyenne generale : {r['moyenne']}/20   Situation : {r['situation']}")
    print("=" * 62)
    print(r["message"])
    print()

    if r["classement"]:
        print("Classement (informatif) :")
        for ligne in r["classement"]:
            marque = "OK " if ligne["valide"] else "   "
            print(f"  {marque} {ligne['serie']:<3} {ligne['nom_complet']:<28} "
                  f"score {ligne['score']}")
            if not ligne["valide"] and ligne["manques"]:
                for m in ligne["manques"]:
                    print(f"        - {m}")

    print()
    print("Points forts :", r["points_forts"] or "aucun pour l'instant")
    print("A renforcer  :", r["a_renforcer"])