"""
Couche de redaction - Seconde.

Meme principe que modules/redaction.py (College) : le CODE ecrit un
brouillon complet et exact a partir du dictionnaire renvoye par
modules.recommandation_seconde.recommander(). Le modele de langage ne fait
que le REFORMULER. Il n'a aucun trou a combler, donc rien a inventer.

Un controle relit ensuite le texte : chaque nombre doit exister dans le
brouillon, aucune expression interdite, aucune phrase coupee, et surtout
aucune serie evoquee comme recommandee si le brouillon dit qu'il faut
d'abord consolider. Si le controle echoue, c'est le brouillon du code qui
est affiche.
"""

import os
import re
import random

MODELE = "qwen2.5:3b"
TEMPERATURE = 0.5
ESSAIS_MAX = 2; DELAI_GENERATION = 120

CONSIGNE = """Tu reformules un texte destine a un eleve djiboutien de Seconde
(Lycee general).

REGLE ABSOLUE : tu ne peux utiliser QUE les informations du texte fourni.
Tu n'ajoutes aucun chiffre, aucune date, aucun nom, aucune matiere, aucune
serie qui ne soit pas deja ecrite dans le texte. Si une information n'y
est pas, elle n'existe pas.

TA TACHE : reecrire ce texte avec d'autres mots, dans un ordre different,
en gardant exactement les memes faits et les memes chiffres.

FORME :
- Tutoie l'eleve. Jamais de "vous", jamais de "nous".
- Ne dis jamais "je suis la pour t'aider" : tu es un outil, pas une personne.
- Texte suivi, en paragraphes. Pas de liste, pas de tirets, pas de titres.
- Francais simple et correct, sans familiarite.
- Termine tes phrases : n'arrete jamais un texte au milieu d'une phrase.
- Recopie les noms de matieres et de series EXACTEMENT comme ils sont
  ecrits (S, ES, L, SG, IAG, OGRH, GFM...). Ne les traduis pas, ne les
  raccourcis pas, ne les modifie jamais.
- Ne developpe JAMAIS un sigle (IG, SES, HG, EPS, SG, GFM, IAG, OGRH...).
  Recopie-le tel quel.
- L'eleve ne t'a envoye aucune lettre et ne t'a rien ecrit. Ne dis jamais
  "dans ta lettre", "tu m'as ecrit" ou "d'apres ton message".
- Ne fusionne jamais deux informations en une seule.
- Si les notes baissent, dis qu'elles baissent. N'ecris jamais "ameliore",
  "progresse" ou "en hausse" pour une baisse.
- Si le texte dit qu'aucune serie n'est validee, ne fais JAMAIS croire
  qu'une serie est confirmee : garde la nuance exacte (ce qui "se dessine"
  n'est pas ce qui est "recommande").
- Si le mot "redoublement" figure dans le texte fourni, garde-le tel quel :
  ne le remplace pas par une expression plus douce.
- Ne remplace aucun mot par un autre : "trimestre" ne devient pas "moitie
  d'annee", "valider" ne devient pas "reussir".
"""

ANGLES = [
    "Commence par tes points forts.",
    "Commence par l'evolution entre tes deux trimestres.",
    "Commence par ce qu'on te recommande.",
    "Commence par ta moyenne generale.",
    "Commence par les matieres a travailler.",
]

INTERDITS = [
    r"\bnous\b", r"\bvous\b", r"\bvotre\b", r"\bvos\b",
    r"je suis l[àa]", r"n'h[ée]site pas",
    r"ma petite", r"mon petit", r"\bmon ami\b", r"\bma ch[èe]re\b",
    r"\bmon cher\b", r"je t'assure", r"\bma belle\b",
    r"\bs'pr", r"\bt'as\b", r"\by'a\b", r"\bchais\b",
    r"\bsuivez\b", r"\bposez\b", r"\btravaillez\b", r"\bprenez\b",
    r"\bdemandez\b", r"\bessayez\b", r"\bchoisissez\b", r"\bfaites\b",
    r"\bsoyez\b", r"\bgardez\b", r"\bcontinuez\b", r"\ballez\b",
    r"\bpr[ée]parez\b", r"\brel[âa]chez\b",
    r"tu as all[ée]", r"tu as venu", r"tu as rest[ée]",
    r"\bton pr[ée]f[ée]rence\b", r"\bta objectif\b",
    r"\brenvoy", r"\bexclu",
]

NOMS_SERIES_LONGS = ["scientifique", "economique et sociale", "litteraire",
                      "sciences de gestion"]
SIGLES_SERIES = ["serie s", "serie es", "serie l", "serie sg",
                  "gfm", "iag", "ogrh"]


# ---------------------------------------------------------------
#  Le brouillon : ecrit par le code, jamais par l'IA
# ---------------------------------------------------------------

def brouillon(c, voies=None):
    """
    Deux cas totalement differents :
      - trimestre valide (favorable/ouvert) -> on parle de serie
      - trimestre pas valide (remontee/alerte) -> on ne parle QUE de
        consolider, jamais d'une serie precise
    Les paragraphes sont separes par une ligne vide.
    """
    prenom = c.get("prenom") or "toi"
    moy = c.get("moyenne_generale")
    situation = c.get("situation", "")
    voies = voies or {}
    forts = c.get("points_forts") or []
    faibles = c.get("a_renforcer") or []
    trims = list((c.get("moyennes_par_trimestre") or {}).values())
    para = []

    # ---- Le niveau, dans tous les cas ----
    if len(trims) >= 2:
        ecart = round(trims[-1] - trims[0], 2)
        sens = ("en progression" if ecart > 0 else
                "en baisse" if ecart < 0 else "stable")
        para.append(f"{prenom}, ta moyenne generale sur les deux trimestres "
                    f"est de {moy} sur 20, {sens} : {trims[0]} puis {trims[-1]}.")
    else:
        para.append(f"{prenom}, ta moyenne generale est de {moy} sur 20.")

    # ===============================================================
    #  CAS 1 : il faut d'abord consolider, aucune serie n'est evoquee
    # ===============================================================
    if situation in ("remontee", "alerte"):

        if len(trims) >= 2 and trims[-1] > trims[0] and trims[-1] < 10:
            gain = round(trims[-1] - trims[0], 2)
            para.append(f"Tu as gagne {gain} point entre les deux trimestres, "
                        f"et c'est un vrai signe. Mais tu es encore loin de "
                        f"10, et c'est 10 qu'il faut viser en premier.")
        elif len(trims) >= 2 and trims[-1] < trims[0]:
            para.append("Tes notes ont baisse entre les deux trimestres. "
                        "Il faut inverser cette tendance des maintenant.")

        if faibles:
            liste = ", ".join(f"{m} ({n})" for m, n in faibles[:3])
            para.append(f"Tes notes sont basses dans plusieurs matieres. Les "
                        f"plus urgentes sont {liste} : commence par "
                        f"celles-la, une ou deux a la fois, pas tout en "
                        f"meme temps.")

        if forts:
            para.append(f"Tu tiens en {forts[0][0]} ({forts[0][1]}) : c'est "
                        f"la-dessus que tu peux reprendre confiance.")
        else:
            para.append("Aucune matiere n'atteint encore 12 sur 20 pour "
                        "l'instant. Aucune n'est encore acquise, et c'est "
                        "justement pour cela qu'il faut de l'aide des "
                        "maintenant.")

        actions = voies.get("actions_renforcement") or []
        if actions:
            choisies = random.sample(actions, min(2, len(actions)))
            para.append("Concretement : " + ", et ".join(choisies) + ".")

        para.append("Sois lucide sur un point : en dessous de 10 de moyenne "
                    "generale, aucune serie ne peut etre recommandee. Si ce "
                    "niveau reste le meme jusqu'a la fin de l'annee, le "
                    "redoublement devient un risque reel. Ce n'est pas dit "
                    "pour te decourager, mais parce que tu as encore le "
                    "temps d'agir, et que c'est maintenant.")

        para.append("Parles-en des cette semaine a ton professeur principal "
                    "et a tes parents. A ce niveau, on ne remonte pas seul, "
                    "et demander de l'aide n'est pas un aveu de faiblesse.")

        return "\n\n".join(para)

    # ===============================================================
    #  CAS 2 : le trimestre est valide, on peut parler de serie
    # ===============================================================
    serie = c.get("serie_recommandee")
    nom_serie = c.get("nom_serie") or ""
    validees = c.get("series_validees") or []
    manques = c.get("manques_serie_top") or []

    if forts:
        liste = ", ".join(f"{m} ({n})" for m, n in forts[:3])
        phrase = f"Tu es le plus solide en {liste}"
        if faibles:
            manque_m = ", ".join(m for m, _ in faibles[:2])
            phrase += f", et c'est en {manque_m} que l'effort rapportera le plus"
        para.append(phrase + ".")

    if situation == "favorable":
        reco = (f"Tu valides les conditions de la serie {serie} "
                f"({nom_serie}) : c'est elle qu'on te recommande en "
                f"priorite.")
        if len(validees) > 1:
            autres = ", ".join(v for v in validees if v != serie)
            reco += f" Tu remplis aussi les conditions de {autres}."
        para.append(reco)
    else:  # ouvert
        reco = (f"Aucune serie n'est encore confirmee, mais c'est {serie} "
                f"({nom_serie}) qui te correspond le plus pour l'instant.")
        if manques:
            reco += " Pour la valider, il te manque : " + "; ".join(manques) + "."
        para.append(reco)

    langue = c.get("langue_rare")
    if langue:
        para.append(f"Tu suis aussi le {langue} : ca ne compte pas dans le "
                    f"choix de serie, mais garde-le, c'est un vrai atout.")

    metier = c.get("metier_vise")
    if metier:
        para.append(f"Tu vises le metier de {metier}. Garde cet objectif en "
                    f"tete pour choisir entre les series qui te sont "
                    f"ouvertes.")

    actions = voies.get("actions_renforcement") or []
    if actions:
        choisies = random.sample(actions, min(2, len(actions)))
        para.append("Pour renforcer ton dossier, " + ", et ".join(choisies)
                    + ". Rien n'est encore decide : le passage en serie est "
                      "prononce par le conseil de classe.")

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


def defauts(texte, source):
    """Compare le texte reformule au brouillon d'origine."""
    problemes = []
    bas = texte.lower(); problemes.extend(["invente une evolution"] if ("puis" not in source and any(m in bas for m in ("augment", "entre les deux trimestres", "s'est amelior", "s'est amélior", "a progress", "a evolu", "a évolu"))) else []); problemes.extend(["contredit la baisse"] if (("en baisse" in source or "ont baisse" in source) and any(m in bas for m in ("amelior", "amélior", "progress", "en hausse"))) else []); problemes.extend(["contredit la baisse : monte"] if (("en baisse" in source or "ont baisse" in source) and re.search(r"\bmonte\b", bas)) else []) 

    for motif in INTERDITS:
        if re.search(motif, bas):
            problemes.append(f"expression interdite ({motif})")

    if re.search(r"^\s*[-*•\d]+[.)]?\s", texte, re.MULTILINE):
        problemes.append("liste ou numerotation")

    inventes = nombres(texte) - nombres(source)
    if inventes:
        problemes.append(f"chiffres inventes : {sorted(inventes)}")

    if texte and texte.rstrip()[-1] not in ".!?":
        problemes.append("texte coupe")

    for mot in ("ta lettre", "ton message", "tu m'as ecrit", "tu m'as écrit"):
        if mot in bas:
            problemes.append(f"invente un echange : {mot}")

    # Le texte doit parler A l'eleve, jamais DE lui a la troisieme personne.
    for motif in (r"\bil est\b", r"\belle est\b", r"\bson dossier\b",
                  r"\bses notes\b", r"\bil obtient\b", r"\belle obtient\b",
                  r"\bil aime\b", r"\belle aime\b", r"\bsa promotion\b",
                  r"\bson profil\b", r"\bdevrait demander\b", r"\bson pere\b"):
        if re.search(motif, bas):
            problemes.append(f"parle de l'eleve a la 3e personne ({motif})")

    for matiere in re.findall(r"\b[A-Z][a-zé]+-[A-Z][a-zé]+\b", source):
        if matiere.lower() not in bas and matiere.split("-")[0].lower() not in bas:
            problemes.append(f"nom de matiere deforme : {matiere}")

    # Si le brouillon dit qu'aucune serie ne peut etre recommandee, la
    # reformulation ne doit JAMAIS nommer une serie precise : ce serait
    # contredire, de facon convaincante, le message le plus important.
    if "aucune serie ne peut etre recommandee" in source.lower():
        for mot in SIGLES_SERIES + NOMS_SERIES_LONGS:
            if mot in bas:
                problemes.append(f"evoque une serie alors qu'il faut "
                                 f"d'abord consolider : {mot}")

    return problemes


# ---------------------------------------------------------------
#  L'appel au modele
# ---------------------------------------------------------------

def rediger(contexte, demande=None, base=None):
    """
    Ecrit le brouillon, le fait reformuler, puis verifie.
    Retourne toujours un texte : la reformulation si elle est correcte,
    sinon le brouillon lui-meme.
    """
    source = brouillon(contexte, base)

    try:
        import ollama
    except Exception as erreur:
        print("[redaction_seconde] Ollama indisponible :", erreur)
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
                         "num_predict": 600,
                         "num_ctx": 2048},
                keep_alive="30m",
            )
            texte = reponse["message"]["content"].strip()
        except Exception as erreur:
            print("[redaction_seconde] Erreur Ollama :", erreur)
            return source

        problemes = defauts(texte, source)
        if not problemes:
            return texte
        print(f"[redaction_seconde] Essai {essai + 1} rejete : {problemes}")

    print("[redaction_seconde] Reformulation abandonnee, texte du code affiche.")
    return source


# ---------------------------------------------------------------
#  Zone de test
# ---------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from modules.recommandation_seconde import recommander, NOMS_SERIES
    from modules.redaction import charger_voies

    if len(sys.argv) < 2:
        print("Utilisation : python modules\\redaction_seconde.py data\\bulletins\\x.json")
        sys.exit()

    with open(sys.argv[1], encoding="utf-8") as f:
        eleve = json.load(f)

    r = recommander(eleve)
    voies = charger_voies()
    profil = eleve.get("profil", {})

    manques_top = []
    if r["classement"]:
        ligne_top = next((l for l in r["classement"]
                          if l["serie"] == r["serie_recommandee"]), None)
        if ligne_top:
            manques_top = ligne_top["manques"]

    contexte = {
        "prenom": eleve.get("nom", "").split()[0],
        "moyenne_generale": r["moyenne"],
        "moyennes_par_trimestre": r["moyennes_trimestres"],
        "situation": r["situation"],
        "points_forts": r["points_forts"],
        "a_renforcer": r["a_renforcer"],
        "serie_recommandee": r["serie_recommandee"],
        "nom_serie": NOMS_SERIES.get(r["serie_recommandee"], "") if r["serie_recommandee"] else "",
        "series_validees": r["series_validees"],
        "manques_serie_top": manques_top,
        "langue_rare": r["langue_rare"],
        "metier_vise": (profil.get("ambition_libre")
                        if profil.get("ambition") == "Autre — je precise moi-meme"
                        and profil.get("ambition_libre")
                        else profil.get("ambition")),
    }

    print("\n" + "=" * 66)
    print("BROUILLON ECRIT PAR LE CODE  (situation :", r["situation"], ")")
    print("=" * 66)
    print(brouillon(contexte, voies))

    for essai in (1, 2):
        print("\n" + "=" * 66)
        print(f"REFORMULATION {essai}")
        print("=" * 66)
        print(rediger(contexte, None, voies))