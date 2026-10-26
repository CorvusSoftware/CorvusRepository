<div align="center">

# CorvusRepository

**Catalogue officiel des cœurs CorvusSoftware.**

Les métadonnées des moteurs téléchargeables par [CorvusRetro](https://github.com/CorvusSoftware/CorvusRetro), indépendantes de l'application et des sources d'émulation.

[![Catalogue](https://github.com/CorvusSoftware/CorvusRepository/actions/workflows/validate.yml/badge.svg)](https://github.com/CorvusSoftware/CorvusRepository/actions/workflows/validate.yml)
[![Licence MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

[Catalogue JSON](catalog/corvuscore.json) · [Moteurs CorvusCore](https://github.com/CorvusSoftware/CorvusCore) · [CorvusAPI](https://github.com/CorvusSoftware/CorvusAPI)

</div>

---

## Catalogue

| Moteur | Console | Architectures Android |
| :--- | :--- | :--- |
| **CorvusGB** | Game Boy | ARM64 · x86_64 |
| **CorvusGBC** | Game Boy Color | ARM64 · x86_64 |
| **CorvusGBA** | Game Boy Advance (expérimental) | ARM64 · x86_64 |

Le catalogue **[catalog/corvuscore.json](catalog/corvuscore.json)** contient six entrées au format 3 de CorvusAPI 0 : identifiant, version, architecture, bibliothèque, URL, taille et SHA-256 de chaque archive.

**Adresse publique du catalogue :**

```text
https://raw.githubusercontent.com/CorvusSoftware/CorvusRepository/main/catalog/corvuscore.json
```

Les archives actuellement référencées sont les ZIP officiels **CorvusCore 0.14.1** de la [release CorvusRetro v0.14.0](https://github.com/CorvusSoftware/CorvusRetro/releases/tag/v0.14.0). Ce dépôt ne contient pas les fichiers binaires : il fournit leurs références et les outils permettant de vérifier le catalogue.

## Organisation

```text
catalog/
  corvuscore.json             Catalogue public
tools/
  validate_catalog.py        Validation du format et des origines
  check_release_assets.py    Vérification des releases GitHub
  test_catalog.py            Tests du validateur
.github/workflows/
  validate.yml               Vérification automatique
```

Les fichiers `README.md`, `AGENTS.md` et `LICENSE` sont conservés à la racine.

## Vérification

Seul Python 3 est nécessaire pour les contrôles locaux :

```sh
python3 -m tools.validate_catalog catalog/corvuscore.json
python3 -m unittest discover -s tools -p 'test_*.py' -v
```

Pour comparer les tailles et les SHA-256 du catalogue aux **métadonnées des fichiers publiés sur GitHub Releases** (nécessite Internet) :

```sh
python3 -m tools.check_release_assets catalog/corvuscore.json
```

La [CI](https://github.com/CorvusSoftware/CorvusRepository/actions/workflows/validate.yml) exécute les vérifications hors réseau. Ces tests n'exécutent pas de moteurs et ne téléchargent pas les ZIP.

## Publier une mise à jour

1. Compiler et tester les modules à partir d'une révision connue de CorvusCore et CorvusAPI.
2. Publier les archives sur une **release immuable** et vérifier leurs tailles et empreintes sur les fichiers réellement publiés.
3. Mettre à jour `catalog/corvuscore.json`, lancer les vérifications ci-dessus et valider la CI avant de promouvoir le catalogue.

**Découverte automatique :** chaque fichier `catalog/<fournisseur>.json` ajouté à ce dossier est découvert via l'API publique des contenus GitHub. Aucun index manuel n'est nécessaire. Chaque fournisseur possède son espace de noms (`fournisseur.identifiant`) et doit passer la validation et la revue avant publication. Les catalogues utilisent le format 3, CorvusAPI 0 et des archives publiées dans les releases officielles **CorvusRetro** ou **CorvusRepository**. Les nouveaux cœurs proposés restent du **code natif exécutable** : aucune PR non vérifiée ne doit être fusionnée. L'ajout d'un JSON n'implique aucune approbation automatique de son contenu.

**Compatibilité :** les anciens catalogues de CorvusRetro ont été supprimés volontairement. Les anciens APK qui les téléchargeaient (notamment v0.13.0) ne peuvent plus rafraîchir les cœurs ; une nouvelle version du frontend est nécessaire.

Les URL de ZIP restent actuellement hébergées dans les **releases CorvusRetro** et doivent conserver l'origine autorisée par son téléchargeur. Pour les héberger plus tard dans des releases CorvusRepository, il faudra d'abord adapter le frontend, sa liste d'origines autorisées et les tests.

## Licence

Les métadonnées, la documentation et les outils originaux de CorvusRepository sont publiés sous **[MIT](LICENSE)**, © 2026 CorvusSoftware.

Les bibliothèques des moteurs [CorvusCore](https://github.com/CorvusSoftware/CorvusCore) restent sous **AGPL-3.0-only**. Le contrat [CorvusAPI](https://github.com/CorvusSoftware/CorvusAPI) conserve sa licence MIT. Ce dépôt ne redistribue ni ROM, ni BIOS commercial, ni clés de signature.
