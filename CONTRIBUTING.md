# Ajouter ou mettre à jour un cœur

CorvusRepository accepte des fournisseurs distincts de CorvusCore. Une contribution fournit un module natif compatible CorvusAPI et les informations permettant de le construire, de le contrôler et de le redistribuer.

## Préparer le moteur

- Exposer le contrat public [CorvusAPI](https://github.com/CorvusSoftware/CorvusAPI), API de base 0, avec `corvus_get_api`. Un module construit uniquement pour une autre ABI d'émulateur nécessite un adaptateur CorvusAPI.
- Fournir les sources publiques, une révision précise, la licence SPDX, les avis requis et les instructions de compilation reproductibles.
- Construire pour chaque ABI annoncée : Android `arm64-v8a` ou `x86_64`. Une archive contient une seule bibliothèque ELF correspondant à cette ABI, avec des segments compatibles avec les pages de 16 Ko.
- Fournir une bibliothèque autonome ; ne pas dépendre d'une bibliothèque privée de CorvusRetro ni de fichiers exécutables ajoutés après installation.
- Tester le chargement, l'exécution, les entrées et les capacités déclarées. Les états et batteries ne doivent être annoncés que s'ils fonctionnent ; les options et sous-systèmes utilisent les extensions publiques négociées.

Les sources, les tests et les archives ne doivent contenir aucune ROM, BIOS propriétaire, clé, donnée personnelle ou autre contenu dont la redistribution n'est pas autorisée.

## Premier fournisseur

1. Ouvrir une pull request décrivant le fournisseur, ses sources, sa licence et sa procédure de build. Choisir un nom de fournisseur stable et un préfixe d'identifiants propre.
2. Ajouter `providers/<fournisseur>.json` avec son ID, son dépôt, sa licence,
   son workflow CI et les noms de ses assets de manifeste et de provenance,
   selon le [contrat de publication](docs/publication.md). La revue du
   fournisseur et des sources précède la première publication de code natif.
3. Fournir une release amont précise avec les archives, le manifeste format 3
   et la provenance du commit/CI exacts. La publication CorvusRepository
   vérifie ces références, les octets, le contenu du ZIP et le module avant
   de les héberger dans ses propres releases.
4. Après publication réelle, proposer le fichier `catalog/<fournisseur>.json` généré par les outils et faire passer la validation et la CI.

Le mainteneur lance la publication des fournisseurs approuvés. Une pull request venant d'un fork ne reçoit aucun droit de publication ni secret. La validation d'un catalogue n'exécute jamais le code natif proposé.

## Identité et catalogue

Le nom du fichier établit l'espace de noms : `atelier.json` utilise des identifiants comme `atelier.handheld`. Les noms officiels `corvus.gb`, `corvus.gbc` et `corvus.gba` restent réservés au fournisseur officiel.

Conserver un identifiant lorsqu'un moteur est mis à jour. Il identifie notamment les jeux, les réglages et les sauvegardes dans les clients ; ce n'est pas un simple libellé d'affichage.

Chaque couple `(id, abi)` apparaît une seule fois dans les catalogues. Le champ `version` décrit la version du cœur ; il n'est pas lié à la version de CorvusRetro. Le tag d'une release CorvusRepository identifie un lot de distribution et doit être disponible et immuable.

Le [contrat du catalogue](docs/catalog-format.md) détaille les champs et les limites. Ne pas ajouter d'exemple, de catalogue vide de démonstration ou de métadonnées provisoires dans `catalog/`, car ce dossier est découvert par les applications.

## Mise à jour d'un fournisseur existant

Garder les ID, le préfixe, le nom des bibliothèques et les formats de sauvegarde compatibles, ou documenter précisément toute rupture. Fournir les résultats des tests et la révision source. Publier de nouvelles archives sous une nouvelle release ; ne pas écraser un fichier déjà référencé.

Générer les tailles et SHA-256 depuis les fichiers réels. Une URL prévue, une taille estimée ou une empreinte calculée sur un autre build ne peut pas être promue dans le catalogue public.

## Vérifier sa contribution

```sh
python3 -m tools.validate_catalog catalog
python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 -m tools.check_release_assets catalog
```

Indiquer séparément les builds réussis, tests hôtes, essais Android et essais sur appareil physique. Les validations de schéma ou de métadonnées GitHub ne prouvent pas qu'un jeu fonctionne dans le moteur.
