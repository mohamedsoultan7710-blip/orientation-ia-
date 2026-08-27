"""
Couche de redaction - Terminale (classement des 18 filieres universitaires).

Meme principe que modules/redaction.py (College) et modules/redaction_seconde.py
(Seconde) : le CODE ecrit un brouillon complet et exact a partir du
dictionnaire renvoye par modules.recommandation_terminale.recommander_terminale().
Le modele de langage ne fait que le REFORMULER. Il n'a aucun trou a combler,
rien a inventer.

L'eleve utilise cet outil APRES avoir eu son bac : le texte lit donc son
releve officiel du bac (eleve["releve_bac"]) et sa mention
(eleve["mention"]), jamais un bulletin de classe. Les 3 carnets
trimestriels (eleve["carnets"]) ne sont pas utilises ici pour l'instant.

Structure imposee par les donnees (redaction_ia.structure_imposee dans
ud_18_filieres.json), en 7 parties : lecture du releve (moyenne, points
forts/faibles, mention), rappel du systeme (2 voies + le classement ne
garantit pas l'affectation), le classement propose (18 filieres),
l'explication par les notes et les coefficients, les filieres a egalite
et comment le profil les a departagees, des conseils concrets avant la
rentree, et le rappel final que rien n'est decide.

Les 4 filieres sur concours ne sont PAS couvertes ici : redaction_ia (dans
ud_18_filieres.json) ne les mentionne pas du tout, et leur regle est plus
simple (jamais de score, jamais de %, voir recommandation_terminale.
correspondance_concours) : elles sont affichees comme fiche factuelle
directement dans l'app, sans passer par l'IA.
"""

import os
import re
import random
import sys

# Rend le dossier du projet (parent de modules/) importable, que ce fichier
# soit lance directement en script (python modules\redaction_terminale.py)
# ou importe depuis app_orientation.py : sans ca, l'import ci-dessous
# echoue en mode script avec "No module named 'modules'".
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.recommandation_terminale import _grappes_de_quasi_egalite, _correspond_au_metier

MODELE = "qwen2.5:1.5b"
TEMPERATURE = 0.5
ESSAIS_MAX = 2
DELAI_GENERATION = 120

CONSIGNE = """Tu reformules un texte destine a un eleve djiboutien de
Terminale, sur son classement des 18 filieres de l'universite de Djibouti.

REGLE ABSOLUE : tu ne peux utiliser QUE les informations du texte fourni.
Tu n'ajoutes aucun chiffre, aucune note, aucun nom de filiere, aucune
statistique qui ne soit pas deja ecrite dans le texte. Si une information
n'y est pas, elle n'existe pas.

TA TACHE : reecrire ce texte avec d'autres mots, dans un ordre different,
en gardant exactement les memes faits, les memes chiffres et les memes
18 filieres.

FORME :
- Tutoie l'eleve. Jamais de "vous", jamais de "nous".
- Ne dis jamais "je suis la pour t'aider" : tu es un outil, pas une personne.
- Texte suivi, en paragraphes. Pas de liste a puces, pas de tirets, pas de
  titres.
- Francais simple et correct, sans familiarite.
- Termine tes phrases : n'arrete jamais un texte au milieu d'une phrase.
- Recopie les noms de filieres EXACTEMENT comme ils sont ecrits. Ne les
  raccourcis pas, ne les traduis pas, ne les modifie jamais.
- Recopie la mention du bac EXACTEMENT comme elle est ecrite (par exemple
  "Assez Bien" reste "Assez Bien", jamais "Bien" ni "Tres Bien").
- Recopie les 18 filieres et leurs rangs : n'en oublie aucune, n'en
  ajoute aucune.
- Ne dis JAMAIS "tu seras affecte", "tu auras", "tu es sur d'obtenir" :
  le classement est un voeu, pas une garantie d'affectation.
- Ne donne JAMAIS de pourcentage ni de probabilite d'admission.
- N'invente JAMAIS un nombre de places ou une barre d'admission.
- Ne dis JAMAIS qu'une filiere est faible, au rabais ou un second choix.
- N'essaie jamais de decourager l'eleve d'une filiere : tu peux expliquer
  que c'est exigeant, jamais fermer la porte.
"""

ANGLES = [
    "Commence par la lecture de son releve du bac.",
    "Commence par le classement lui-meme.",
    "Commence par expliquer pourquoi ses meilleures notes comptent autant.",
    "Commence par rappeler comment fonctionne l'admission a l'universite.",
]

INTERDITS = [
    # -- ton et forme, communs aux autres parcours --
    r"\bnous\b", r"\bvous\b", r"\bvotre\b", r"\bvos\b",
    r"je suis l[àa]", r"n'h[ée]site pas",
    r"ma petite", r"mon petit", r"\bmon ami\b", r"\bma ch[èe]re\b",
    r"\bmon cher\b", r"je t'assure", r"\bma belle\b",
    r"\bs'pr", r"\bt'as\b", r"\by'a\b", r"\bchais\b",
    r"\bsuivez\b", r"\bposez\b", r"\btravaillez\b", r"\bprenez\b",
    r"\bdemandez\b", r"\bessayez\b", r"\bchoisissez\b", r"\bfaites\b",
    r"\bsoyez\b", r"\bgardez\b", r"\bcontinuez\b", r"\ballez\b",
    r"\bpr[ée]parez\b", r"\brel[âa]chez\b",
    # -- les 7 interdits absolus de redaction_ia (Terminale) --
    r"tu seras affect[ée]", r"\btu auras\b",
    r"tu es s[ûu]r[e]? d'obtenir",
    r"%", r"pourcent", r"probabilit[ée]",
    r"chances? d[' ]?[êe]tre admis",
    r"barre d'admission", r"seuil d'admission", r"\d+\s*places?\b",
    r"filiere faible", r"au rabais", r"second choix", r"deuxieme choix",
    r"filiere par defaut",
    r"n'as pas le niveau", r"trop difficile pour toi",
    r"hors de (ta |ma )?port[ée]e", r"\babandonne\b", r"\brenonce\b",
    r"ce n'est pas pour toi", r"oublie cette filiere",
]


# ---------------------------------------------------------------
#  Le brouillon : ecrit par le code, jamais par l'IA
# ---------------------------------------------------------------

def _moyenne_et_extremes(notes):
    """Moyenne generale simple du bulletin (non ponderee - le calcul de
    classement, lui, pondere par filiere et par serie, voir
    recommandation_terminale.score_filiere) + les 3 matieres les plus
    fortes et les 3 plus faibles. Sert uniquement a la partie 'lecture du
    carnet' du texte."""
    if not notes:
        return None, [], []
    moyenne = round(sum(notes.values()) / len(notes), 2)
    fortes = sorted(notes.items(), key=lambda x: -x[1])[:3]
    faibles = sorted(notes.items(), key=lambda x: x[1])[:3]
    return moyenne, fortes, faibles


def brouillon(r, eleve, familles=None):
    """
    r = dictionnaire renvoye par recommandation_terminale.recommander_terminale()
    eleve = le dictionnaire d'entree original : releve_bac (notes
            officielles du bac), mention (optionnelle), profil - jamais un
            chiffre qui ne soit pas dans le releve, cf. interdits_absolus.
            eleve["carnets"] (3 bulletins trimestriels), s'il est fourni,
            n'est pas utilise ici pour l'instant.
    familles = donnees["familles"] (liste de {id, nom, filieres}), pour
               eventuellement nommer une famille en toutes lettres
    """
    prenom = (r.get("nom") or "toi").split()[0]
    serie = r.get("serie") or ""
    notes = eleve.get("releve_bac") or {}
    mention = eleve.get("mention")
    profil = eleve.get("profil") or {}
    classement = sorted(r["classement"], key=lambda l: l["rang_departage"])
    para = []

    calculables_ok = [l for l in classement if l["calculable"]]
    if not calculables_ok:
        return (f"{prenom}, je n'ai pas pu calculer de classement pour la "
                f"serie \"{serie}\". Verifie que la serie et les notes "
                f"saisies correspondent bien a un profil de Terminale "
                f"connu (S, ES, L ou SG).")

    premier = classement[0]  # rang 1 selon rang_departage, toujours calculable

    # ---- 1. Lecture du releve du bac ----
    moyenne, fortes, faibles = _moyenne_et_extremes(notes)
    if fortes:
        txt_fortes = ", ".join(f"{m} ({n})" for m, n in fortes)
        phrase_mention = f", mention {mention}" if mention else ""
        para.append(f"{prenom}, tu as obtenu ton bac en serie {serie}"
                    f"{phrase_mention}. Ta moyenne sur les matieres de ton "
                    f"releve est de {moyenne} sur 20. Tes points forts sont "
                    f"{txt_fortes}.")
    if faibles:
        txt_faibles = ", ".join(f"{m} ({n})" for m, n in faibles)
        para.append(f"Tes notes les plus basses sont en {txt_faibles}.")

    # ---- 2. Rappel du systeme (2 voies, aucune garantie d'affectation) ----
    para.append(
        "A l'universite de Djibouti, il y a deux voies separees : le "
        "classement de 18 filieres que tu vois ici, ou tu classes tes "
        "voeux et l'affectation se fait ensuite selon tes notes, ta serie "
        "et les places disponibles ; et 4 filieres sur concours "
        "(Ingenieurs, Medecine, BBA, ATID), ou l'admission se fait par une "
        "epreuve ecrite, independamment de ce classement. Etre bien "
        "classe ici ne garantit pas une place : cela depend aussi du "
        "nombre de places et des candidatures des autres eleves cette "
        "annee."
    )

    # ---- 3. Le classement propose (les 18 filieres, rang 1 a 18) ----
    items = "; ".join(f"{l['rang_departage']}. {l['nom']}" for l in classement)
    para.append(f"Voici ton classement, du rang 1 au rang 18 : {items}.")

    # ---- 4. L'explication par les notes et les coefficients ----
    if premier["matieres_utilisees"]:
        cites = ", ".join(f"{m} ({notes.get(m)})"
                           for m in premier["matieres_utilisees"][:3]
                           if m in notes)
        if cites:
            para.append(f"{premier['nom']} arrive en tete parce que "
                        f"{cites} comptent parmi les matieres qui pesent "
                        f"le plus dans le coefficient de ta serie {serie}, "
                        f"et ce sont des matieres ou tu es fort.")

    # ---- 5. Les filieres a egalite (departage par le profil) ----
    preferees = set(profil.get("matieres_preferees") or [])
    alaise = set(profil.get("matieres_a_l_aise") or [])
    metier = profil.get("metier_vise") or ""

    calculables_tries = sorted(calculables_ok, key=lambda l: -l["score"])
    grappes = _grappes_de_quasi_egalite(calculables_tries, r["seuil_departage"])
    grappe_du_premier = next(
        (g for g in grappes if any(m["nom"] == premier["nom"] for m in g)), [])
    egalite = [m for m in grappe_du_premier if m["nom"] != premier["nom"]]

    if egalite:
        tous_lies = [premier["nom"]] + [m["nom"] for m in egalite]
        # Les noms de filieres contiennent parfois deja une virgule
        # ("Genie Mecanique, Systemes Motorises") : on les separe par des
        # points-virgules pour ne jamais creer d'ambiguite, avec un seul
        # "et" avant le tout dernier nom de la liste.
        if len(tous_lies) > 1:
            liste_liee = "; ".join(tous_lies[:-1]) + " et " + tous_lies[-1]
        else:
            liste_liee = tous_lies[0]
        md_premier = set(premier["matieres_utilisees"])
        communes_pref = md_premier & preferees
        communes_alaise = md_premier & alaise
        if communes_pref:
            raison = f"tes matieres preferees ({', '.join(sorted(communes_pref))})"
        elif communes_alaise:
            raison = f"les matieres ou tu es a l'aise ({', '.join(sorted(communes_alaise))})"
        elif metier and _correspond_au_metier(premier, metier):
            raison = f"le metier que tu vises ({metier})"
        else:
            raison = "un tres leger ecart de notes"
        para.append(f"{liste_liee} obtiennent des scores tres proches chez "
                    f"toi : tes notes seules ne suffisent pas a les "
                    f"departager. C'est {raison} qui a fait pencher la "
                    f"balance vers {premier['nom']}.")
    else:
        para.append(
            "Aucune de tes filieres en tete n'est a egalite chez toi : ton "
            "profil de notes est net, donc ce classement ne change pas "
            "selon tes preferences."
        )

    # ---- 6. Conseils concrets (avant la rentree a l'universite) ----
    matieres_top = premier["matieres_utilisees"]
    faibles_top = [m for m, n in faibles if m in matieres_top]
    if faibles_top:
        para.append(f"D'ici la rentree, le plus utile pour toi est de "
                    f"revoir {', '.join(faibles_top)} : ce sont des "
                    f"matieres qui comptent pour {premier['nom']} et ou tu "
                    f"as encore de la marge.")
    elif fortes:
        deux_fortes = ", ".join(m for m, _ in fortes[:2])
        para.append(f"D'ici la rentree, continue a consolider {deux_fortes} : "
                    f"ce sont des matieres qui comptent pour "
                    f"{premier['nom']}.")

    # ---- 7. Rappel final : rien n'est decide ----
    para.append(
        "Ce classement est une proposition fondee sur ton releve de bac : "
        "rien n'est decide, et c'est toi qui as le dernier mot sur l'ordre "
        "de tes voeux. Tes resultats sont deja un point de depart solide : prends le temps de choisir ce qui te correspond le mieux."
    )

    return "\n\n".join(para)


# ---------------------------------------------------------------
#  Le controle qualite
# ---------------------------------------------------------------

def nombres(texte):
    """Nombres d'un texte, normalises : 17 et 17.0 sont le meme nombre."""
    trouves = set()
    for brut in re.findall(r"\d+(?:[.,]\d+)?", texte):
        try:
            trouves.add(round(float(brut.replace(",", ".")), 2))
        except ValueError:
            pass
    return trouves


def defauts(texte, source, noms_filieres=None, mention=None):
    """Compare le texte reformule au brouillon d'origine. noms_filieres,
    quand fourni, est la liste des 18 noms attendus (aucune filiere ne
    doit disparaitre dans la reformulation, cf. controle_avant_affichage).
    mention, quand fournie, doit survivre telle quelle : une IA qui
    "arrondit" une mention Bien en Tres Bien inventerait un fait."""
    problemes = []
    bas = texte.lower()

    if mention and mention.lower() not in bas:
        problemes.append(f"mention du bac deformee ou disparue : {mention}")

    for motif in INTERDITS:
        if re.search(motif, bas):
            problemes.append(f"expression interdite ({motif})")

    if re.search(r"^\s*[-*•\d]+[.)]?\s", texte, re.MULTILINE):
        problemes.append("liste ou numerotation en debut de ligne")

    inventes = nombres(texte) - nombres(source)
    if inventes:
        problemes.append(f"chiffres inventes : {sorted(inventes)}")

    if texte and texte.rstrip()[-1] not in ".!?":
        problemes.append("texte coupe")

    for mot in ("ta lettre", "ton message", "tu m'as ecrit", "tu m'as écrit"):
        if mot in bas:
            problemes.append(f"invente un echange : {mot}")

    for motif in (r"\bil est\b", r"\belle est\b", r"\bson dossier\b",
                  r"\bses notes\b", r"\bil obtient\b", r"\belle obtient\b",
                  r"\bson profil\b", r"\bdevrait demander\b"):
        if re.search(motif, bas):
            problemes.append(f"parle de l'eleve a la 3e personne ({motif})")

    if noms_filieres:
        manquantes = [n for n in noms_filieres if n.lower() not in bas]
        if manquantes:
            problemes.append(f"filiere(s) manquante(s) : {manquantes}")

    return problemes


# ---------------------------------------------------------------
#  L'appel au modele
# ---------------------------------------------------------------

def rediger(r, eleve, familles=None):
    """
    Ecrit le brouillon, le fait reformuler, puis verifie.
    Retourne toujours un texte : la reformulation si elle est correcte,
    sinon le brouillon lui-meme.
    """
    source = brouillon(r, eleve, familles)
    noms_filieres = [l["nom"] for l in r["classement"]]
    mention = eleve.get("mention")

    try:
        import ollama
    except Exception as erreur:
        print("[redaction_terminale] Ollama indisponible :", erreur)
        return source

    for essai in range(ESSAIS_MAX):
        message = ("Reformule le texte ci-dessous en respectant toutes les "
                   "regles. " + random.choice(ANGLES) +
                   " N'ecris aucun titre et ne recopie aucune consigne.\n\n"
                   + source)
        try:
            reponse = ollama.Client(timeout=DELAI_GENERATION).chat(
                model=MODELE,
                messages=[{"role": "system", "content": CONSIGNE},
                          {"role": "user", "content": message}],
                options={"temperature": TEMPERATURE,
                         "num_predict": 900,
                         "num_ctx": 2048},
                keep_alive="30m",
            )
            texte = reponse["message"]["content"].strip()
        except Exception as erreur:
            print("[redaction_terminale] Erreur Ollama :", erreur)
            return source

        problemes = defauts(texte, source, noms_filieres, mention)
        if not problemes:
            return texte
        print(f"[redaction_terminale] Essai {essai + 1} rejete : {problemes}")

    print("[redaction_terminale] Reformulation abandonnee, texte du code affiche.")
    return source


# ---------------------------------------------------------------
#  Zone de test
# ---------------------------------------------------------------

if __name__ == "__main__":
    import json
    from modules.recommandation_terminale import recommander_terminale, charger_filieres

    if len(sys.argv) < 2:
        print("Utilisation : python modules\\redaction_terminale.py data\\bulletins\\x.json")
        sys.exit()

    with open(sys.argv[1], encoding="utf-8") as f:
        eleve = json.load(f)

    r = recommander_terminale(eleve)
    donnees = charger_filieres()
    familles = donnees.get("familles")

    print("\n" + "=" * 66)
    print("BROUILLON ECRIT PAR LE CODE")
    print("=" * 66)
    print(brouillon(r, eleve, familles))

    for essai in (1, 2):
        print("\n" + "=" * 66)
        print(f"REFORMULATION {essai}")
        print("=" * 66)
        print(rediger(r, eleve, familles))