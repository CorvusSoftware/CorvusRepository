# CorvusRepository

**Catalogue officiel des cœurs téléchargeables pour CorvusRetro.**

[![Validation du catalogue](https://github.com/CorvusSoftware/CorvusRepository/actions/workflows/validate.yml/badge.svg)](https://github.com/CorvusSoftware/CorvusRepository/actions/workflows/validate.yml)
[![Licence MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

CorvusRepository sépare les **métadonnées de distribution** de l'application [CorvusRetro](https://github.com/CorvusSoftware/CorvusRetro) et des sources des moteurs [CorvusCore](https://github.com/CorvusSoftware/CorvusCore).

## Catalogue officiel

**[cores-v3.json](cores-v3.json)** est le catalogue pour le téléchargeur natif de CorvusRetro (format 3, CorvusAPI 0).

| Cœur | Console | Plateformes |
| --- | --- | --- |
| **CorvusGB** | Game Boy | Android ARM64 et x86_64 |
| **CorvusGBC** | Game Boy Color | Android ARM64 et x86_64 |
| **CorvusGBA** | Game Boy Advance (expérimental) | Android ARM64 et x86_64 |

URL publique du catalogue :

```text
https://raw.githubusercontent.com/CorvusSoftware/CorvusRepository/main/cores-v3.json
```

Chaque entrée contient l'identifiant du cœur, sa version, l'architecture, le nom de la bibliothèque, la version de CorvusAPI, une URL HTTPS d'archive, sa **taille exacte** et son **SHA-256**.

**État de la migration :** le premier catalogue référence les six fichiers déjà publiés et vérifiés de [CorvusRetro v0.13.0](https://github.com/CorvusSoftware/CorvusRetro/releases/tag/v0.13.0), pour les cœurs 0.14.1. Les fichiers n'ont pas été déplacés ni reconstruits. Les applications CorvusRetro déjà publiées consultent encore leur ancienne URL de catalogue ; l'intégration de la nouvelle URL doit se faire par une mise à jour du frontend.

## Vérifier une modification

```sh
python3 tools/validate_catalog.py cores-v3.json
python3 -m unittest discover -s tests -v
```

La CI vérifie le schéma, les tailles, l'intégrité des identifiants, les deux architectures, les liens HTTPS autorisés et les empreintes déclarées. Elle ne télécharge ni n'exécute de code natif.

Le catalogue **ne doit jamais être publié** avec des URL fictives, des empreintes supposées ou des artefacts non vérifiés. Pour ajouter une version :

1. Compiler et qualifier les modules à partir d'une révision identifiée de CorvusCore et de CorvusAPI.
2. Publier les ZIP immuables sur une release officielle ; contrôler pour chacun la taille et le SHA-256 des **octets publiés**.
3. Modifier `cores-v3.json`, lancer le validateur et faire passer la CI avant d'exposer le catalogue aux applications.

Ce dépôt **ne remplace pas** les dépôts sources des moteurs et ne reconstruit pas les bibliothèques à chaque modification de catalogue. Il ne doit jamais contenir de ROM commerciale, de BIOS propriétaire ou de clés de signature.

## Compatibilité

- Le catalogue `cores-v3.json` suit le format 3 du téléchargeur CorvusRetro actuel.
- Les anciens catalogues des versions 0.10 et 0.11 restent hébergés dans [CorvusRetro/core-repository](https://github.com/CorvusSoftware/CorvusRetro/tree/main/core-repository) : ne pas casser leurs URL.
- Les clients actuels n'acceptent que les identifiants officiels et les URL d'archives issues des releases **CorvusRetro**. Des archives hébergées dans CorvusRepository nécessiteront une adaptation contrôlée du client avant leur activation.

## Licence

Les **catalogues, la documentation et les outils originaux de ce dépôt** sont sous **[MIT](LICENSE)**, © 2026 CorvusSoftware.

Les **moteurs CorvusCore** distribués par les liens du catalogue restent sous **AGPL-3.0-only**, conformément à [CorvusCore/LICENSE](https://github.com/CorvusSoftware/CorvusCore/blob/main/LICENSE). Le contrat [CorvusAPI](https://github.com/CorvusSoftware/CorvusAPI) est sous MIT. La licence de ce dépôt **ne requalifie pas** les logiciels hébergés à l'extérieur.
