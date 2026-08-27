"""
Couche de redaction.

Principe : le CODE ecrit un brouillon complet et exact a partir des
donnees calculees. Le modele de langage ne fait que le REFORMULER.
Il n'a aucun trou a combler, donc rien a inventer.

Un controle relit ensuite le texte : chaque nombre doit exister dans le
brouillon, aucune expression interdite, aucune phrase coupee. Si le
controle echoue, c'est le brouillon du code qui est affiche.
"""

import os
import re
import json
import random

MODELE = "qwen2.5:3b"
TEMPERATURE = 0.5
ESSAIS_MAX = 2
FICHIER_VOIES = os.path.join("data", "voies.json")

CONSIGNE = """Tu reformules un texte destine a un eleve djiboutien de 9eme annee.

REGLE ABSOLUE : tu ne peux utiliser QUE les informations du texte fourni.
Tu n'ajoutes aucun chiffre, aucune date, aucun nom, aucune matiere, aucun
pourcentage qui ne soit pas deja ecrit dans le texte. Si une information
n'y est pas, elle n'existe pas.

TA TACHE : reecrire ce texte avec d'autres mots, dans un ordre different,
en gardant exactement les memes faits et les memes chiffres.

FORME :
- Tutoie l'eleve. Jamais de "vous", jamais de "nous".
- Ne dis jamais "je suis la pour t'aider" : tu es un outil, pas une personne.
- Texte suivi, en paragraphes. Pas de liste, pas de tirets, pas de titres.
- Francais simple et correct, sans familiarite.
- Termine tes phrases : n'arrete jamais un texte au milieu d'une phrase.
- Recopie les noms de matieres EXACTEMENT comme ils sont ecrits. Ne les
  traduis pas, ne les raccourcis pas, ne les modifies jamais.
- Ne developpe JAMAIS un sigle (EMCI, LIC, BEF, EPS...). Recopie-le tel quel.
- L'eleve ne t'a envoye aucune lettre et ne t'a rien ecrit. Ne dis jamais
  "dans ta lettre", "tu m'as ecrit" ou "d'apres ton message".
- Ne fusionne jamais deux informations en une seule.
- Si les notes baissent, dis qu'elles baissent. N'ecris jamais "ameliore",
  "progresse" ou "en hausse" pour une baisse.
- Ne remplace aucun mot par un autre : "frequentations" ne devient pas
  "matieres", "trimestre" ne devient pas "moitie d'annee".
"""

ANGLES = [
    "Commence par ses points forts.",
    "Commence par l'evolution entre ses deux trimestres.",
    "Commence par ce qu'on lui recommande.",
    "Commence par sa moyenne generale.",
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
    r"redoubl", r"\brenvoy", r"\bexclu",
]


def charger_voies(chemin=FICHIER_VOIES):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def disponible():
    try:
        import ollama
        ollama.list()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------
#  Le brouillon : ecrit par le code, jamais par l'IA
# ---------------------------------------------------------------

def brouillon(c, voies=None):
    """
    Deux cas totalement differents :
      - moyenne suffisante -> on parle d'orientation
      - moyenne trop basse -> on ne parle QUE de remontee
    Les paragraphes sont separes par une ligne vide.
    """
    prenom = c.get("prenom") or "toi"
    moy = c.get("moyenne_generale")
    voie = c.get("voie_qui_se_dessine", "")
    cle = c.get("situation", "")
    voies = voies or {}
    forts = c.get("points_forts") or []
    faibles = c.get("matieres_a_renforcer") or []
    trims = list((c.get("moyennes_par_trimestre") or {}).values())
    para = []

    # ---- Le niveau, dans tous les cas ----
    if len(trims) >= 2:
        ecart = round(trims[-1] - trims[0], 2)
        sens = ("en progression" if ecart > 0 else
                "en baisse" if ecart < 0 else "stable")
        para.append(f"{prenom}, ta moyenne sur les deux trimestres est de "
                    f"{moy} sur 20, {sens} : {trims[0]} puis {trims[-1]}.")
    else:
        para.append(f"{prenom}, ta moyenne generale est de {moy} sur 20.")

    # ===============================================================
    #  CAS 1 : il faut d'abord remonter
    # ===============================================================
    if cle in ("remontee", "alerte"):

        if len(trims) >= 2 and trims[-1] > trims[0] and trims[-1] < 10:
            gain = round(trims[-1] - trims[0], 2)
            para.append(f"Tu as gagne {gain} point entre les deux trimestres, "
                        f"et c'est un vrai signe. Mais tu es encore loin de "
                        f"10, et c'est 10 qu'il faut viser.")
        elif len(trims) >= 2 and trims[-1] < trims[0]:
            para.append("Tes notes ont baisse entre les deux trimestres. "
                        "Il faut inverser cette tendance des maintenant.")

        if faibles:
            liste = ", ".join(f"{m} ({n})" for m, n in faibles[:3])
            para.append(f"Tes notes sont basses dans presque toutes les "
                        f"matieres. Les plus urgentes sont {liste} : commence "
                        f"par celles-la, une ou deux a la fois, pas tout en "
                        f"meme temps.")

        if forts and forts[0][1] >= 10:
            para.append(f"Tu tiens en {forts[0][0]} ({forts[0][1]}) : c'est "
                        f"la-dessus que tu peux reprendre confiance.")
        elif forts:
            para.append(f"Ta meilleure note est {forts[0][1]} en "
                        f"{forts[0][0]}. Meme celle-la reste sous la moyenne : "
                        f"aucune matiere n'est encore acquise, et c'est "
                        f"justement pour cela qu'il faut de l'aide.")

        actions = voies.get("actions_renforcement") or []
        if actions:
            choisies = random.sample(actions, min(2, len(actions)))
            para.append("Concretement : " + ", et ".join(choisies) + ".")

        para.append("Sois lucide sur un point : si ta moyenne reste a ce "
                    "niveau jusqu'a la fin de l'annee, la suite de ton "
                    "parcours sera difficile a construire. Ce n'est pas dit "
                    "pour te decourager, mais parce que tu as encore le temps "
                    "d'agir, et que c'est maintenant.")

        para.append("Parles-en des cette semaine a ton professeur principal "
                    "et a tes parents. A ce niveau, on ne remonte pas seul, "
                    "et demander de l'aide n'est pas un aveu de faiblesse. Il "
                    "te reste le 3e trimestre et le BEF, qui compte pour 40 "
                    "pour cent de ta moyenne d'admission.")

        return "\n\n".join(para)

    # ===============================================================
    #  CAS 2 : on peut parler d'orientation
    # ===============================================================
    infos = voies.get("lic" if ("LIC" in voie or "Industriel" in voie)
                      else "lycee_general") or {}

    if forts:
        liste = ", ".join(f"{m} ({n})" for m, n in forts[:3])
        phrase = f"Tu es le plus solide en {liste}"
        if faibles:
            manque = ", ".join(m for m, _ in faibles[:2])
            phrase += f", et c'est en {manque} que l'effort rapportera le plus"
        para.append(phrase + ".")

    reco = f"On te recommande de viser le {voie}."
    if infos.get("pour_qui"):
        reco += f" Cette voie convient a {infos['pour_qui']}."
    para.append(reco)

    detail = []
    if infos.get("on_y_etudie"):
        detail.append(f"On y suit {infos['on_y_etudie']}")
        if infos.get("duree"):
            detail.append(f"sur {infos['duree']}")
    if infos.get("ou_ca_mene"):
        detail.append(f"Cela mene {infos['ou_ca_mene']}")
    if detail:
        para.append(", ".join(detail) + ".")

    metier = c.get("metier_vise")
    if metier:
        para.append(f"Tu vises le metier de {metier} : c'est bien cette voie "
                    f"qui y conduit.")

    actions = voies.get("actions_renforcement") or []
    if actions:
        choisies = random.sample(actions, min(2, len(actions)))
        para.append("Pour renforcer ton dossier, " + ", et ".join(choisies)
                    + ". Rien n'est encore decide : l'affectation est "
                      "prononcee par la commission du MENFOP, au classement "
                      "de toute la promotion.")

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
    bas = texte.lower()

    for motif in INTERDITS:
        if re.search(motif, bas):
            problemes.append(f"expression interdite ({motif})")

    if re.search(r"^\s*[-*\u2022\d]+[.)]?\s", texte, re.MULTILINE):
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

    if "Concretement" in source and "40 pour cent" in source:
        for mot in ("lycee general", "lycée général", "baccalaureat",
                    "baccalauréat", "universite", "université", " lic "):
            if mot in bas:
                problemes.append(f"parle d'orientation alors qu'il faut "
                                 f"remonter : {mot}")

    if "\u00e9" not in texte and "e" in texte and len(texte) > 400:
        pass  # rien : les accents sont optionnels

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
        print("[redaction] Ollama indisponible :", erreur)
        return source

    for essai in range(ESSAIS_MAX):
        message = ("Reformule le texte ci-dessous en respectant toutes les "
                   "regles. " + random.choice(ANGLES) +
                   " N'ecris aucun titre et ne recopie aucune consigne.\n\n"
                   + source)
        try:
            reponse = ollama.chat(
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
            print("[redaction] Erreur Ollama :", erreur)
            return source

        problemes = defauts(texte, source)
        if not problemes:
            return texte
        print(f"[redaction] Essai {essai + 1} rejete : {problemes}")

    print("[redaction] Reformulation abandonnee, texte du code affiche.")
    return source


# ---------------------------------------------------------------
#  Zone de test
# ---------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from modules.recommandation import recommander

    if len(sys.argv) < 2:
        print("Utilisation : python modules\\redaction.py data\\bulletins\\x.json")
        sys.exit()

    with open(sys.argv[1], encoding="utf-8") as f:
        eleve = json.load(f)

    r = recommander(eleve)
    voies = charger_voies()
    profil = eleve.get("profil", {})

    contexte = {
        "prenom": eleve.get("nom", "").split()[0],
        "moyenne_generale": r["moyenne"],
        "moyennes_par_trimestre": r["moyennes_trimestres"],
        "evolution_entre_trimestres": r["tendance"],
        "voie_qui_se_dessine": r["voie"],
        "situation": r["situation"],
        "points_forts": r["points_forts"],
        "matieres_a_renforcer": r["a_renforcer"],
        "metier_vise": (r["objectif_metier"]["metier"]
                        if r["objectif_metier"] else None),
        "matiere_preferee": profil.get("matiere_preferee"),
        "matieres_alaise": profil.get("matieres_alaise", []),
    }

    print("\n" + "=" * 66)
    print("BROUILLON ECRIT PAR LE CODE  (palier :", r["situation"], ")")
    print("=" * 66)
    print(brouillon(contexte, voies))

    for essai in (1, 2):
        print("\n" + "=" * 66)
        print(f"REFORMULATION {essai}")
        print("=" * 66)
        print(rediger(contexte, None, voies))
