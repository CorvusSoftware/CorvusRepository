# Contrat des catalogues

Un catalogue publié est un fichier `catalog/<fournisseur>.json`. Le format 3 reste compatible avec le téléchargeur CorvusRetro existant ; aucun index manuel ne doit être ajouté dans l'application.

## Champs

La racine contient exactement `format`, égal à l'entier `3`, et `cores`, une liste d'entrées.

| Champ de chaque entrée | Signification |
| :--- | :--- |
| `id` | Identifiant permanent préfixé par le fournisseur, de 95 caractères maximum. |
| `name` | Nom du moteur, non vide, de 128 caractères maximum. |
| `description` | Description non vide, de 128 caractères maximum. |
| `version` | Version du moteur au format `MAJEUR.MINEUR.CORRECTIF`. |
| `abi` | `arm64-v8a` ou `x86_64`. |
| `api_version` | Entier `0` pour l'API de base CorvusAPI actuelle. |
| `library_name` | Nom exact de l'unique bibliothèque du ZIP, au format `libnom.so`. |
| `size` | Taille exacte, en octets, du ZIP public, au maximum 32 Mio. |
| `sha256` | SHA-256 des octets du ZIP public, en 64 caractères hexadécimaux minuscules. |
| `archive_url` | URL HTTPS autorisée de l'archive publiée dans une release CorvusRepository. |

Les URL historiques CorvusRetro restent acceptées pour préserver les archives déjà distribuées. Aucun champ supplémentaire, URL avec paramètres ou fragment, chemin de traversée ou nom de bibliothèque contenant un répertoire n'est accepté.

Les six entrées officielles CorvusCore couvrent GB, GBC et GBA pour les deux ABIs. Un autre fournisseur annonce uniquement les architectures qu'il fournit réellement. Les couples `(id, abi)` sont uniques dans l'ensemble du dossier.

Les limites actuelles sont 16 catalogues, 32 entrées cumulées et 96 Kio par fichier. Les contrôles du client restent également applicables ; une extension du schéma ou de ces limites doit être coordonnée avec lui.

## Gabarit de travail

Ce gabarit contient volontairement des valeurs à remplacer. Il ne constitue pas un catalogue valide et ne doit pas être déposé dans `catalog/` :

```text
{
  "format": 3,
  "cores": [
    {
      "id": "<fournisseur>.<moteur>",
      "name": "<nom>",
      "description": "<console ou fonction>",
      "version": "<version du cœur>",
      "abi": "<ABI Android>",
      "api_version": 0,
      "library_name": "<bibliothèque .so>",
      "size": <taille exacte du ZIP>,
      "sha256": "<empreinte exacte du ZIP>",
      "archive_url": "<URL réelle de la release CorvusRepository>"
    }
  ]
}
```

La publication génère ces données depuis les archives contrôlées. Ne pas copier une taille ou une empreinte d'une ancienne version, d'une autre ABI ou d'un build local différent.
