# CorvusRepository — consignes pour les agents

Ce dépôt héberge **uniquement les métadonnées des cœurs**, la documentation de
distribution et leurs validateurs. Les moteurs eux-mêmes résident dans
[CorvusCore](https://github.com/CorvusSoftware/CorvusCore), le frontend dans
[CorvusRetro](https://github.com/CorvusSoftware/CorvusRetro).

## Fichiers de référence

- `catalog/corvuscore.json` : catalogue format 3, utilisé par le téléchargeur.
- `tools/validate_catalog.py` : validation hors réseau du schéma et des origines.
- `tools/check_release_assets.py` : contrôle manuel en ligne des métadonnées de releases.
- `tools/test_catalog.py` : tests de régression du validateur.
- `README.md` : présentation, commandes et procédure de publication.
- `.github/workflows/validate.yml` : CI exécutant les vérifications hors réseau.

## Contraintes

1. Les six entrées actuelles ciblent les modules officiels GB, GBC et GBA pour
   `arm64-v8a` et `x86_64`. Ne pas modifier leurs URL, tailles ou SHA-256
   sans avoir contrôlé les véritables archives publiques.
2. Garder les URL de release autorisées strictement bornées. Toute nouvelle
   origine doit être prise en charge par le frontend et par les tests avant
   une mise à jour du catalogue.
3. Ne pas copier ici les moteurs, des ROMs, des BIOS, des APK, des clés,
   des secrets, ni des archives natives.
4. Le code et les métadonnées de ce dépôt sont sous MIT ; les modules
   CorvusCore distribués par le catalogue restent sous AGPL-3.0-only.
5. Le mainteneur a demandé la suppression des anciens flux de CorvusRetro.
   Ne pas les réintroduire ni affirmer que les APK déjà distribués peuvent encore
   rafraîchir leurs moteurs. La source active est catalog/corvuscore.json.
6. Préserver le schéma public du format 3. Pour un autre fournisseur, utiliser
   un dossier et un fichier à son nom (Fournisseur/Fournisseur.json), mais le
   client doit être explicitement adapté et testé avant d'y accéder.

## Vérifier

```sh
python3 -m tools.validate_catalog catalog/corvuscore.json
python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 -m tools.check_release_assets catalog/corvuscore.json
```

La troisième commande nécessite un accès réseau et vérifie les métadonnées des
assets GitHub. Elle ne télécharge pas les ZIP. Ne pas annoncer une vérification
comme réussie sans l'avoir exécutée.
