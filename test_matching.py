import json
from core.matching import recommander, get_bourses


with open("data/profils_exemple.json", "r", encoding="utf-8") as f:
    profils = json.load(f)

for profil in profils:
    print("=" * 50)
    print(f"Profil : {profil['nom']} (niveau: {profil['niveau']})")
    print(f"Ambitions : {profil['ambitions']}")
    print("-" * 50)

    resultats = recommander(profil, nombre_resultats=3)

    for i, r in enumerate(resultats, start=1):
        print(f"{i}. {r['nom']} — score: {r['score']}%")
        print(f"   Mode d'admission : {r['mode_admission']}")
        print(f"   Débouchés : {', '.join(r['debouches'])}")
    print()

print("=" * 50)
print("Bourses disponibles a l'etranger :")
for bourse in get_bourses():
    print(f"- {bourse['pays']} : {bourse['notes']}")