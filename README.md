<div align="center">

# CorvusRepository

**Distribution indépendante des cœurs CorvusAPI.**

Les catalogues, les archives natives et leur publication évoluent séparément de l'application [CorvusRetro](https://github.com/CorvusSoftware/CorvusRetro).

[![Catalogue](https://github.com/CorvusSoftware/CorvusRepository/actions/workflows/validate.yml/badge.svg)](https://github.com/CorvusSoftware/CorvusRepository/actions/workflows/validate.yml)
[![Licence MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

[Catalogues](catalog/) · [Ajouter un cœur](CONTRIBUTING.md) · [Contrat CorvusAPI](https://github.com/CorvusSoftware/CorvusAPI)

</div>

## Responsabilités

| Projet | Responsabilité |
| :--- | :--- |
| **CorvusRepository** | Compiler ou importer les archives qualifiées, les publier dans ses propres releases, vérifier les fichiers publics et maintenir un catalogue par fournisseur. |
| **CorvusCore ou un autre fournisseur** | Développer et tester ses moteurs, exposer CorvusAPI et fournir leurs sources et leur licence. |
| **CorvusRetro** | Découvrir les catalogues et installer les modules vérifiés à la demande de l'utilisateur. |

Une mise à jour de cœur ne nécessite pas de reconstruire, signer ou publier l'APK. La chaîne de distribution de ce dépôt ne dépend pas d'un build Gradle de CorvusRetro ni de sa clé de signature.

## Catalogues et cœurs

| Catalogue | Moteurs | Architectures Android |
| :--- | :--- | :--- |
| [`catalog/corvuscore.json`](catalog/corvuscore.json) | CorvusGB, CorvusGBC, CorvusGBA expérimental | ARM64 et x86_64 |
| `catalog/<fournisseur>.json` | Cœurs d'un fournisseur ajouté par contribution | Architecture(s) déclarée(s) et vérifiée(s) |

Chaque fichier utilise le format 3 : identifiant permanent, nom, description, version du cœur, architecture, CorvusAPI 0, bibliothèque, URL de l'archive, taille et SHA-256. Les identifiants d'un autre fournisseur commencent par son propre préfixe, par exemple `atelier.handheld` dans `atelier.json` ; les identifiants officiels `corvus.gb`, `corvus.gbc` et `corvus.gba` sont réservés.

CorvusRetro découvre automatiquement les fichiers `catalog/*.json` via l'API des contenus GitHub. Ajouter un fournisseur ne demande aucune modification d'une liste de fichiers dans l'application. Les archives approuvées sont centralisées dans les [releases CorvusRepository](https://github.com/CorvusSoftware/CorvusRepository/releases).

L'adresse du catalogue officiel reste :

```text
https://raw.githubusercontent.com/CorvusSoftware/CorvusRepository/main/catalog/corvuscore.json
```

Les six archives CorvusCore **0.15.0** sont désormais construites et hébergées ici, dans le [lot indépendant v0.15.1](https://github.com/CorvusSoftware/CorvusRepository/releases/tag/v0.15.1). Le numéro du lot n'est pas celui du moteur ou de l'APK. Le [workflow autonome qualifié](https://github.com/CorvusSoftware/CorvusRepository/actions/runs/40802383314) publie les sources exactes, empreintes et fichiers vérifiés ; aucun APK n'a été construit pour cette publication.

Les archives historiques de [CorvusRetro v0.18.0](https://github.com/CorvusSoftware/CorvusRetro/releases/tag/v0.18.0) restent intactes. Les identifiants, la version du moteur et les formats de sauvegarde sont conservés ; les nouveaux téléchargements utilisent les fichiers qualifiés du catalogue actif.

## Publier une mise à jour

Deux parcours sont maintenus dans ce dépôt :

- **CorvusCore** : construire les modules Android depuis une révision précise et qualifiée du fournisseur, sans construire CorvusRetro.
- **Autre fournisseur** : importer les archives d'une release approuvée, vérifier leur contenu et les publier dans CorvusRepository.

Dans les deux cas, les archives sont publiées avant de promouvoir leur catalogue. Le catalogue est généré avec les tailles et empreintes des fichiers réellement distribués. Les contrôles s'appliquent au fournisseur, à l'identité du cœur, à CorvusAPI, à l'ABI Android et à l'archive ; un JSON ajouté seul ne remplace pas la revue d'un nouveau moteur.

Voir le [guide de publication](docs/publication.md) et le [guide de contribution](CONTRIBUTING.md). Le numéro d'un lot de distribution et la version d'un cœur sont indépendants de la version de l'APK. Un tag de release existant et ses archives ne sont pas réutilisés pour des octets différents.

## Vérifier

```sh
python3 -m tools.validate_catalog catalog
python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 -m tools.check_release_assets catalog
```

Les deux premières commandes et la CI contrôlent les catalogues hors réseau. La troisième compare leurs références aux métadonnées des véritables releases GitHub ; elle ne télécharge ni n'exécute les bibliothèques. La publication vérifie aussi les octets téléchargés et le contenu des ZIP.

## Compatibilité

CorvusRetro 0.18 accepte déjà les releases CorvusRepository et les catalogues par fournisseur au format 3. Ses mises à jour de cœurs restent indépendantes de celles de l'application tant que le contrat CorvusAPI et les capacités du client restent compatibles. Les anciennes URL de releases CorvusRetro restent acceptées pour les archives historiques.

Les anciens flux JSON de CorvusRetro ont été retirés volontairement. Les APK qui les utilisaient, notamment v0.13.0, ne peuvent pas retrouver les catalogues par cette migration ; ils doivent être mis à jour. Un cœur proposant une nouvelle API ou une fonctionnalité absente du frontend peut également nécessiter une mise à jour du client.

## Organisation

```text
catalog/                     Un catalogue publié par fournisseur
providers/                   Déclarations des fournisseurs approuvés
tools/                      Validation et distribution des archives
docs/                       Contribution et publication
.github/workflows/           Validation et publication autonomes
```

Les sources des moteurs résident chez leurs fournisseurs. Les ZIP et bibliothèques sont des assets de releases, jamais des fichiers binaires versionnés dans Git.

## Licence

Les métadonnées, la documentation et les outils originaux de CorvusRepository sont sous **[MIT](LICENSE)**, © 2026 CorvusSoftware. Les bibliothèques conservent leur propre licence ; les modules officiels CorvusCore restent sous **AGPL-3.0-only** et le contrat CorvusAPI sous MIT.

Aucune ROM, aucun BIOS commercial, APK ou secret de signature n'est distribué par ce dépôt.
