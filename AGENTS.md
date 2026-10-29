# CorvusRepository - consignes pour les agents

Ce dépôt possède la distribution des cœurs CorvusAPI : déclarations de fournisseurs, catalogues, outils, workflows et archives dans ses propres releases. Les sources d'émulation restent chez leurs fournisseurs ; l'application reste dans CorvusRetro. Les fichiers binaires ne sont jamais versionnés dans Git.

## Références

- `catalog/*.json` : catalogues publiés format 3, un fichier par fournisseur.
- `providers/` : déclarations des fournisseurs approuvés pour la publication.
- `tools/validate_catalog.py` : schéma, origines et espaces de noms.
- `tools/check_release_assets.py` : métadonnées des vraies releases GitHub.
- `.github/workflows/` : validation et publication autonomes.
- `CONTRIBUTING.md`, `docs/catalog-format.md`, `docs/publication.md` : contrats et procédures.

## Contraintes

1. Ne modifier une URL, taille ou empreinte du catalogue qu'après contrôle des vrais fichiers publics. Publier les archives avant de promouvoir leurs métadonnées ; une URL prévue n'est pas une preuve.
2. Distribuer les nouveaux lots dans les releases CorvusRepository. Préserver les références historiques CorvusRetro et ne pas supprimer leurs anciens fichiers. Ne jamais remplacer des octets sous un tag ou un nom d'asset déjà référencé.
3. Maintenir l'indépendance des mises à jour de cœurs : aucun build Gradle de CorvusRetro, signature d'APK ou modification de l'application ne doit être nécessaire pour publier un moteur compatible.
4. Conserver le format 3, CorvusAPI 0, la découverte automatique de `catalog/*.json` et les bornes du client. Un changement de contrat ou d'origine demande une adaptation explicite et testée des consommateurs avant promotion.
5. Réserver `corvus.gb`, `corvus.gbc` et `corvus.gba` au fournisseur officiel. Les autres fichiers `catalog/fournisseur.json` utilisent `fournisseur.identifiant` ; ne pas changer les ID permanents pendant une mise à jour.
6. Revoir les sources, la licence et la procédure de compilation d'un nouveau fournisseur. Les PR de forks ne doivent ni exécuter des modules non approuvés ni disposer de droits de publication. Les nouveaux JSON ne constituent pas une approbation automatique de code natif.
7. Les archives natives contiennent exactement la bibliothèque annoncée pour une ABI. Vérifier taille, SHA-256, CorvusAPI, architecture ELF et segments de 16 Ko. Ne pas contourner les restrictions du chargeur Android ni accepter une origine arbitraire.
8. Ne pas copier ici les sources des moteurs, ROMs, BIOS propriétaires, APK, clés ou secrets. Les builds temporaires restent des artefacts ignorés ; ZIP et bibliothèques sont publiés uniquement comme assets de releases.
9. Conserver les licences : outils, métadonnées et documentation de ce dépôt sous MIT ; les bibliothèques conservent leur propre licence, notamment AGPL-3.0-only pour CorvusCore. Ne pas requalifier une archive tierce sous MIT.
10. Ne pas réintroduire les anciens flux JSON retirés de CorvusRetro. Les APK qui les utilisaient ne retrouvent pas automatiquement les catalogues actuels.

## Vérifier

```sh
python3 -m tools.validate_catalog catalog
python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 -m tools.check_release_assets catalog
```

La troisième commande utilise le réseau et ne télécharge pas les ZIP. Les validations de schéma et de métadonnées ne prouvent pas l'exécution d'un moteur. Distinguer build, contrôle des octets, tests hôtes, émulateur et appareil physique ; n'annoncer que les preuves réellement obtenues.

Lire les workflows et les outils concernés avant leur modification. Préserver les contrôles avant publication, les SHA source précis, la gestion des échecs et les catalogues publics précédents. Ne pas ajouter de long tiret Unicode dans les nouveaux textes.
