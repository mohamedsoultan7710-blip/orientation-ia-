"""
Moteur de recommandation - Terminale (Universite de Djibouti).

Deux voies independantes, toutes les deux couvertes ici :
  - Le CLASSEMENT des 18 filieres (voeux classes par l'eleve, affectation
    selon les notes du bac + la serie + les places disponibles). C'est un
    calcul, 100% deterministe, fonde sur les donnees de ud_18_filieres.json.
  - Les 4 filieres sur CONCOURS (Ingenieurs, Medecine, BBA, ATID). Admission
    par epreuve ecrite, pas par les notes de Terminale : l'app ne calcule
    donc PAS de score ici, elle affiche une fiche + une indication
    qualitative de correspondance de profil (jamais un pourcentage, jamais
    une promesse d'admission - interdit explicite des donnees).

L'eleve utilise cet outil APRES avoir obtenu son bac (comme la vraie
plateforme de voeux de l'universite) : le classement se calcule donc sur
le releve officiel du bac (eleve["releve_bac"]), jamais sur un bulletin de
classe. Les 3 carnets trimestriels de Terminale peuvent etre fournis en
plus (eleve["carnets"]) pour le texte uniquement (montrer le chemin
parcouru), jamais pour le calcul.

Principe general (identique a la Seconde) : les notes decident, les
preferences de l'eleve ne font que departager en cas de quasi-egalite,
jamais renverser un ecart de notes reel.
"""

import os
import json
import unicodedata

FICHIER_FILIERES = os.path.join("data", "ud_18_filieres.json")
FICHIER_CONCOURS = os.path.join("data", "ud_filieres_concours.json")

SEUIL_DEPARTAGE_DEFAUT = 0.3   # points sur 20 ; reglable, voir "algorithme.niveau_2_departage" dans les donnees
NB_VOEUX_OUVERTURE = 6         # cf. classements_proposes[2] ("L'ouverture")
MIN_FAMILLES_OUVERTURE = 2


# ---------------------------------------------------------------
#  Chargement des donnees (aucune donnee n'est codee en dur : tout
#  vient des fichiers fournis par l'equipe, seule la mecanique de
#  calcul est du code)
# ---------------------------------------------------------------

def charger_filieres(chemin=FICHIER_FILIERES):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def charger_filieres_concours(chemin=FICHIER_CONCOURS):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ---------------------------------------------------------------
#  Niveau 1 : le score par les notes (le calcul principal)
# ---------------------------------------------------------------

def _matiere_reelle(nom_matiere, serie, matieres_par_serie):
    """
    Resout un motif du type "SES|Eco-droit" (ecrit ainsi dans les donnees
    quand deux series different sur cette matiere) vers la matiere que
    l'eleve possede vraiment selon sa serie. Renvoie None si aucune des
    alternatives n'existe dans sa serie (matiere non calculable).
    """
    dispo = set(matieres_par_serie.get(serie, []))
    for alternative in nom_matiere.split("|"):
        if alternative in dispo:
            return alternative
    return None


def score_filiere(filiere, notes, serie, coefficients_bac, matieres_par_serie):
    """
    score = somme(poids_filiere x coef_bac_serie x note)
            / somme(poids_filiere x coef_bac_serie)
    uniquement sur les matieres que l'eleve possede reellement dans sa
    serie (cf. "algorithme.niveau_1_notes" et "matieres_par_serie" dans
    ud_18_filieres.json).

    Renvoie (score_ou_None, matieres_utilisees). score=None signifie
    filiere non calculable : soit aucune de ses matieres determinantes
    n'existe dans la serie de l'eleve, soit la filiere porte un champ
    "series_ouvertes" explicite (donnees, jamais code en dur ici) qui
    exclut la serie de l'eleve - cf. ud_18_filieres.json, filieres 1, 2,
    3, 4, 7, 9, 10, 16 (jamais interprete comme un 0 dans les deux cas).
    """
    series_ouvertes = filiere.get("series_ouvertes")
    if series_ouvertes is not None and serie not in series_ouvertes:
        return None, []

    coefs_serie = coefficients_bac.get(serie, {})
    numerateur = 0.0
    denominateur = 0.0
    utilisees = []

    for md in filiere["matieres_determinantes"]:
        matiere = _matiere_reelle(md["matiere"], serie, matieres_par_serie)
        if matiere is None:
            continue
        note = notes.get(matiere)
        coef = coefs_serie.get(matiere)
        if note is None or coef is None:
            continue
        poids = md["poids"]
        numerateur += poids * coef * note
        denominateur += poids * coef
        utilisees.append(matiere)

    if denominateur == 0:
        return None, []
    return round(numerateur / denominateur, 2), utilisees


# ---------------------------------------------------------------
#  Niveau 2 : le departage par les preferences (jamais le calcul)
# ---------------------------------------------------------------

def _grappes_de_quasi_egalite(calculables_tries, seuil):
    """
    Regroupe les filieres (deja triees par score decroissant) en grappes de
    quasi-egalite. Chaque nouveau membre est compare au MAXIMUM de la
    grappe (son tout premier membre, le mieux note) et non au dernier
    ajoute : un chainage par voisin immediat laisserait une derive
    cumulative (plusieurs ecarts de 0,2 bout a bout) depasser le seuil
    entre les deux extremes de la grappe, ce qui violerait la regle
    absolue. En ancrant sur le maximum, l'ecart entre n'importe quelle
    paire de la meme grappe reste garanti strictement sous le seuil.

    Cela couvre aussi l'exemple des donnees ou Genie Civil / Electrique /
    Mecanique, a score identique, doivent rester groupes ensemble.
    """
    grappes = []
    for ligne in calculables_tries:
        if grappes and (grappes[-1][0]["score"] - ligne["score"]) < seuil:
            grappes[-1].append(ligne)
        else:
            grappes.append([ligne])
    return grappes


def _sans_accents(texte):
    """Retire les accents : un eleve peut taper 'ingenieur' ou 'ingénieur',
    et les donnees du JSON sont ecrites sans accent - la comparaison ne
    doit dependre d'aucune des deux facons d'ecrire."""
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")


def _correspond_au_metier(ligne, metier):
    """Rapprochement volontairement simple (nom de la filiere + ses
    debouches) : les preferences departagent seulement en cas de
    quasi-egalite, une correspondance approximative n'est donc jamais
    lourde de consequence sur le classement final. Une racine commune de
    5 caracteres ou plus capte des cas evidents comme "mecanicien" vis-a-vis
    de "mecanique" sans pretendre a une vraie analyse linguistique."""
    if not metier:
        return False
    metier = _sans_accents(metier.lower().strip())
    texte = _sans_accents((ligne["nom"] + " " + " ".join(ligne.get("debouches", []))).lower())
    if metier in texte:
        return True
    # Compare chaque mot du metier (5 lettres ou plus) a chaque mot du
    # texte, pas seulement les 5 premieres lettres de la phrase entiere :
    # "ingenieur electrique" doit reconnaitre "electrique" meme si le mot
    # generique "ingenieur" ne depart rien a lui seul (il decrirait aussi
    # bien Genie Civil, Genie Mecanique, etc.).
    mots_texte = texte.replace(",", " ").replace("'", " ").split()
    for mot_metier in metier.replace(",", " ").replace("'", " ").split():
        if len(mot_metier) < 5:
            continue
        for mot in mots_texte:
            if len(mot) >= 5 and mot[:5] == mot_metier[:5]:
                return True
    return False


def classer_filieres(filieres, notes, serie, coefficients_bac, matieres_par_serie,
                      profil=None, seuil=SEUIL_DEPARTAGE_DEFAUT):
    """
    Calcule les 3 versions du classement decrites dans
    "classements_proposes" : le miroir des notes (rang_brut), les notes
    departagees par les gouts (rang_departage), et une version "ouverture"
    qui diversifie le haut du classement si les 6 premiers voeux
    proviennent tous de la meme famille (rang_ouverture).

    Renvoie une liste de 18 dictionnaires (+ les filieres non calculables),
    tries par rang_departage, chacun portant ses 3 rangs.
    """
    profil = profil or {}
    preferees = set(profil.get("matieres_preferees") or [])
    alaise = set(profil.get("matieres_a_l_aise") or [])
    metier = profil.get("metier_vise") or ""

    lignes = []
    for f in filieres:
        score, utilisees = score_filiere(f, notes, serie, coefficients_bac, matieres_par_serie)
        lignes.append({
            "numero": f["numero"], "nom": f["nom"], "famille": f["famille"],
            "campus": f.get("campus"), "debouches": f.get("debouches", []),
            "contenu": f.get("contenu"), "score": score,
            "calculable": score is not None,
            "matieres_utilisees": utilisees,
        })

    calculables = sorted([l for l in lignes if l["calculable"]], key=lambda l: -l["score"])
    non_calculables = sorted([l for l in lignes if not l["calculable"]], key=lambda l: l["numero"])

    # ---- Version 1 : "Le miroir de tes notes" (aucune preference) ----
    ordre_brut = calculables + non_calculables
    for rang, ligne in enumerate(ordre_brut, start=1):
        ligne["rang_brut"] = rang

    # ---- Version 2 : "Tes notes, departagees par tes gouts" ----
    def cle_departage(ligne):
        # Les 3 premiers niveaux sont les criteres officiels, dans l'ordre.
        # Le score vient ENSUITE, avant le numero : ca garantit que sans
        # aucun signal de preference (le cas le plus frequent), une grappe
        # de quasi-egalite garde l'ordre de ses scores reels au lieu
        # d'etre reordonnee sans raison par le numero de filiere. Le
        # numero croissant ne tranche plus qu'une egalite de score exacte.
        md = set(ligne["matieres_utilisees"])
        return (
            -len(md & preferees),
            -len(md & alaise),
            0 if _correspond_au_metier(ligne, metier) else 1,
            -ligne["score"],
            ligne["numero"],
        )

    grappes = _grappes_de_quasi_egalite(calculables, seuil)
    ordre_departage = []
    for grappe in grappes:
        ordre_departage.extend(sorted(grappe, key=cle_departage))
    ordre_departage += non_calculables
    for rang, ligne in enumerate(ordre_departage, start=1):
        ligne["rang_departage"] = rang

    # ---- Version 3 : "L'ouverture" (diversite de famille dans le top 6) ----
    top = ordre_departage[:NB_VOEUX_OUVERTURE]
    familles_top = {l["famille"] for l in top if l["calculable"]}
    ordre_ouverture = list(ordre_departage)
    if len(familles_top) < MIN_FAMILLES_OUVERTURE:
        famille_dominante = top[0]["famille"]
        reste = ordre_departage[NB_VOEUX_OUVERTURE:]
        alternative = next(
            (l for l in reste if l["calculable"] and l["famille"] != famille_dominante),
            None,
        )
        if alternative is not None:
            ordre_ouverture.remove(alternative)
            # Remonte l'alternative juste apres la 1ere place : elle
            # elargit le haut du classement sans pretendre remplacer le
            # numero 1, qui reste le mieux note.
            ordre_ouverture.insert(1, alternative)
    for rang, ligne in enumerate(ordre_ouverture, start=1):
        ligne["rang_ouverture"] = rang

    resultat = sorted(lignes, key=lambda l: l["rang_departage"])
    return resultat


def familles_diversifiees(classement, nb_voeux=NB_VOEUX_OUVERTURE, seuil_familles=MIN_FAMILLES_OUVERTURE):
    """Vrai si les nb_voeux premiers voeux (rang_departage) couvrent au
    moins seuil_familles familles distinctes."""
    top = sorted(classement, key=lambda l: l["rang_departage"])[:nb_voeux]
    return len({l["famille"] for l in top if l["calculable"]}) >= seuil_familles


# ---------------------------------------------------------------
#  Niveau 3 : coherence (verification, jamais une regle bloquante)
# ---------------------------------------------------------------

def famille_dominante(classement, top_n=6):
    """La famille la plus representee dans les top_n premiers voeux
    departages. Sert a verifier que le classement "a du sens" par
    rapport a la serie de l'eleve (cf. algorithme.niveau_3_coherence)."""
    top = sorted([l for l in classement if l["calculable"]], key=lambda l: l["rang_departage"])[:top_n]
    if not top:
        return None
    compte = {}
    for l in top:
        compte[l["famille"]] = compte.get(l["famille"], 0) + 1
    return max(compte, key=compte.get)


# ---------------------------------------------------------------
#  Les 4 filieres sur concours : fiche + correspondance qualitative
#  (jamais un score, jamais un pourcentage - admission par epreuve
#  ecrite, pas par le carnet de Terminale)
# ---------------------------------------------------------------

PLANCHER_PROFIL_ALIGNE = 12.0
PLANCHER_PROFIL_PARTIEL = 10.0


ALIAS_CONCOURS = {"Mathematiques": "Maths", "Physique": "Physique-Chimie"}


def _nom_base(nom):
    """Retire une precision entre parentheses : 'SVT (accent marque sur la
    partie biologie)' -> 'SVT'. Le libelle complet reste tel quel dans les
    donnees d'origine, pour l'affichage de la fiche."""
    return nom.split("(")[0].strip()


def _matiere_concours_vers_serie(nom_concours, dispo):
    """Les 2 fichiers de donnees ne nomment pas toujours une matiere de la
    meme facon ('Mathematiques' au concours, 'Maths' dans
    matieres_par_serie ; 'Physique' au concours, 'Physique-Chimie' au
    lycee). Resout vers le nom reellement utilise dans la serie de
    l'eleve, ou None si cette matiere n'existe pas du tout dans sa serie
    (distinct d'une simple note manquante : ca veut dire que l'eleve ne
    l'etudie pas en Terminale)."""
    base = _nom_base(nom_concours)
    candidat = ALIAS_CONCOURS.get(base, base)
    return candidat if candidat in dispo else None


def correspondance_concours(filiere_concours, notes, serie, matieres_par_serie):
    """
    Indication qualitative (jamais numerique) de correspondance entre le
    profil de l'eleve et une filiere sur concours, plus un message ecrit
    par le code (pas par l'IA - ces textes sont fixes et deterministes,
    aucune reformulation Ollama n'intervient ici, donc rien a valider
    apres coup) qui explique la situation et encourage a tenter sa
    chance : le concours reste ouvert a toute serie, meme quand une
    matiere testee n'existe pas dans le programme de l'eleve.
    """
    matieres_concours = (filiere_concours.get("concours") or {}).get("matieres") or []
    dispo = set(matieres_par_serie.get(serie, []))

    notes_pertinentes = {}
    matieres_absentes = []
    for nom_concours in matieres_concours:
        matiere = _matiere_concours_vers_serie(nom_concours, dispo)
        if matiere is None:
            matieres_absentes.append(nom_concours)
        elif matiere in notes:
            notes_pertinentes[matiere] = notes[matiere]

    if not notes_pertinentes:
        raison = ("Les matieres testees a ce concours n'existent pas dans "
                   "ta serie, ou tes notes n'y sont pas encore renseignees. "
                   "Le concours reste ouvert : rien ne t'empeche de le "
                   "preparer en autonomie.")
        return {"niveau": "indetermine", "matieres_utilisees": {},
                "matieres_absentes": matieres_absentes, "message": raison,
                "raison": raison}

    moyenne = sum(notes_pertinentes.values()) / len(notes_pertinentes)
    plancher_ok = all(n >= PLANCHER_PROFIL_PARTIEL for n in notes_pertinentes.values())

    if moyenne >= PLANCHER_PROFIL_ALIGNE and plancher_ok:
        niveau = "aligne"
    elif moyenne >= PLANCHER_PROFIL_PARTIEL:
        niveau = "partiel"
    else:
        niveau = "eloigne"

    matieres_ok = ", ".join(notes_pertinentes)
    if niveau == "aligne":
        message = (f"Ton profil correspond bien aux matieres testees a ce "
                   f"concours ({matieres_ok}). Ce n'est jamais garanti a "
                   f"l'avance, mais tu pars avec de bonnes bases pour le "
                   f"tenter.")
    elif niveau == "partiel":
        message = (f"Ton profil correspond en partie a ce concours : tes "
                   f"notes en {matieres_ok} sont un point d'appui, meme si "
                   f"ce concours reste exigeant. Rien n'est jamais garanti, "
                   f"mais tu as ta place pour le tenter.")
    else:
        message = (f"D'apres tes notes actuelles en {matieres_ok}, ce "
                   f"concours demande encore un effort de preparation "
                   f"important. Ca ne veut pas dire que c'est ferme : rien "
                   f"n'est jamais garanti dans un sens comme dans l'autre, "
                   f"et te preparer serieusement peut changer beaucoup de "
                   f"choses d'ici l'epreuve.")

    # Une matiere testee au concours peut manquer entierement au programme
    # de la serie de l'eleve (pas juste une note faible) : le niveau
    # ci-dessus ne juge alors que sur les matieres disponibles, jamais sur
    # celle qui manque. On le precise toujours, sans jamais fermer la
    # porte : le concours reste ouvert a toutes les series.
    if matieres_absentes:
        message += (f" Attention, tu n'as pas {', '.join(matieres_absentes)} "
                    f"dans ta serie {serie} : ce jugement ne porte donc que "
                    f"sur {matieres_ok}, pas sur l'ensemble des matieres du "
                    f"concours. Le concours reste ouvert a toutes les "
                    f"series, et rien n'empeche de preparer cette matiere "
                    f"en autonomie.")

    return {"niveau": niveau, "matieres_utilisees": notes_pertinentes,
            "matieres_absentes": matieres_absentes, "message": message,
            "raison": None}


# ---------------------------------------------------------------
#  Point d'entree principal
# ---------------------------------------------------------------

def recommander_terminale(eleve, chemin_filieres=FICHIER_FILIERES,
                           chemin_concours=FICHIER_CONCOURS):
    """
    L'eleve utilise cet outil APRES avoir eu son bac (comme la vraie
    plateforme de voeux) : le classement se calcule donc sur le releve du
    bac, pas sur un bulletin de classe. Les 3 carnets de l'annee restent
    disponibles dans "carnets" pour le texte (ce qu'ils montrent, avant que
    le bac ne confirme), mais n'entrent jamais dans le calcul du score.

    eleve = {
        "nom": str,
        "serie": "S" | "ES" | "L" | "SG",
        "releve_bac": {matiere: note, ...}   # notes officielles du bac, matieres de sa serie uniquement
        "mention": str,                       # ex. "Assez Bien", "Bien", "Tres Bien", ou None/"Sans mention"
        "carnets": [{matiere: note, ...}, ...],  # les 3 bulletins trimestriels de Terminale (optionnel, jamais utilise pour le score)
        "profil": {
            "matieres_preferees": [...], "matieres_a_l_aise": [...],
            "domaines_preferes": [...], "metier_vise": str,
        }
    }
    """
    donnees = charger_filieres(chemin_filieres)
    serie = eleve.get("serie")
    notes = eleve.get("releve_bac") or {}
    profil = eleve.get("profil") or {}

    coefficients_bac = {
        s: {k: v for k, v in d.items() if k != "total"}
        for s, d in donnees["coefficients_bac"].items()
        if s in ("S", "ES", "L", "SG")
    }
    matieres_par_serie = {
        s: donnees["matieres_par_serie"][s]
        for s in ("S", "ES", "L", "SG")
    }

    classement = classer_filieres(
        donnees["filieres"], notes, serie, coefficients_bac,
        matieres_par_serie, profil, SEUIL_DEPARTAGE_DEFAUT,
    )

    donnees_concours = charger_filieres_concours(chemin_concours)
    concours = []
    for fc in donnees_concours.get("filieres_concours", []):
        concours.append({
            "id": fc["id"], "nom": fc["nom"], "faculte": fc.get("faculte"),
            "duree_annees": fc.get("duree_annees"), "diplome": fc.get("diplome"),
            "matieres_testees": (fc.get("concours") or {}).get("matieres") or [],
            "profil_qui_reussit": fc.get("profil_qui_reussit"),
            "debouches": fc.get("nature_du_travail"),
            "correspondance": correspondance_concours(fc, notes, serie, matieres_par_serie),
        })

    return {
        "nom": eleve.get("nom"),
        "serie": serie,
        "mention": eleve.get("mention"),
        "classement": classement,
        "diversifie": familles_diversifiees(classement),
        "famille_dominante": famille_dominante(classement),
        "non_calculables": [l for l in classement if not l["calculable"]],
        "concours": concours,
        "seuil_departage": SEUIL_DEPARTAGE_DEFAUT,
    }


# ---------------------------------------------------------------
#  Zone de test
# ---------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Utilisation : python modules\\recommandation_terminale.py data\\bulletins\\x.json")
        sys.exit()

    with open(sys.argv[1], encoding="utf-8") as f:
        eleve = json.load(f)

    r = recommander_terminale(eleve)
    print(f"\nEleve : {r['nom']}  (serie {r['serie']})")
    print(f"Famille dominante du top 6 : {r['famille_dominante']}   "
          f"Diversifie : {r['diversifie']}\n")
    print(f"{'Rang':>4} {'#':>3} {'Filiere':<38} {'Score':>7}")
    print("-" * 58)
    for ligne in r["classement"]:
        score_txt = f"{ligne['score']:.2f}" if ligne["calculable"] else "  n/c"
        print(f"{ligne['rang_departage']:>4} {ligne['numero']:>3} "
              f"{ligne['nom']:<38} {score_txt:>7}")

    if r["non_calculables"]:
        print("\nFilieres non calculables pour cette serie :")
        for l in r["non_calculables"]:
            print(f"  - {l['nom']}")

    print("\nFilieres sur concours :")
    for c in r["concours"]:
        corr = c["correspondance"]
        print(f"  - {c['nom']} -- correspondance : {corr['niveau']}")
        print(f"      {corr['message']}")