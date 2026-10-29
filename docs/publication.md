# Publication indépendante

CorvusRepository possède les catalogues, les archives publiées et leur chaîne de distribution. Une publication de cœur ne construit pas l'application, ne dépend pas d'une release CorvusRetro et n'utilise pas sa clé de signature Android.

## CorvusCore

Le workflow `publish-corvuscore.yml` construit les modules directement depuis une révision exacte de CorvusCore. La révision doit avoir passé les contrôles du fournisseur et sa version doit correspondre à celle annoncée.

Le build utilise la chaîne Android native pour produire GB, GBC et GBA en ARM64 et x86_64. Il vérifie les bibliothèques et prépare six ZIP, leur provenance et le catalogue correspondant. Il n'embarque aucun moteur dans un APK et ne modifie pas CorvusRetro.

## Autre fournisseur

Le workflow `publish-provider.yml` importe une release d'un fournisseur approuvé. Les archives sont vérifiées puis hébergées dans les releases CorvusRepository. Les sources amont et les archives d'origine restent identifiées dans la provenance de publication.

Le formulaire reçoit `provider`, `upstream_tag`, `release_tag` et `dry_run`.
`provider` désigne une déclaration existante dans `providers/` ; `upstream_tag`
désigne sa release source au format `vMAJEUR.MINEUR.CORRECTIF`.
`release_tag` est un tag de lot CorvusRepository disponible, au même format,
distinct de la version du cœur et de celle de l'application. Le mode `dry_run`
est activé par défaut : il prépare et vérifie le lot sans publier ni promouvoir
le catalogue.

L'approbation du fournisseur ne vaut pas approbation automatique de chaque octet futur. La révision, la version, les fichiers et les résultats de validation du lot publié doivent être contrôlés. Un simple changement d'URL ne permet pas de charger un nouveau fournisseur depuis une origine arbitraire.

Les commandes de distribution sont fournies par `tools.core_distribution`.
Utiliser son aide et le formulaire du workflow à la révision courante.

Le parcours d'import en ligne de commande est :

```sh
python3 -m tools.core_distribution import --provider NOM \
  --upstream-tag vMAJEUR.MINEUR.CORRECTIF --tag vLOT.MINEUR.CORRECTIF \
  --output-dir /chemin/lot --dry-run
```

Remplacer les noms et versions du gabarit par la déclaration approuvée et
les vrais tags. Le dossier de sortie est temporaire et ne doit pas être
ajouté au dépôt Git.

## Déclaration d'un fournisseur

`providers/<fournisseur>.json` est une déclaration relue dans ce dépôt. Elle
contient exactement les informations suivantes :

| Champ | Valeur |
| :--- | :--- |
| `format` | Entier `1`. |
| `id` | Identifiant du fournisseur, identique au nom du fichier sans `.json`. |
| `name` | Nom affiché du fournisseur. |
| `repository` | Dépôt GitHub public `Propriétaire/Dépôt`, pour les sources et les releases amont approuvées. |
| `license` | Identifiant SPDX de la licence du fournisseur. |
| `ci_workflow` | Nom du fichier de workflow CI à vérifier, par exemple `ci.yml`. |
| `manifest_asset` | Nom du catalogue amont attaché à sa release, par exemple `corvus-catalog.json`. |
| `provenance_asset` | Nom de sa provenance attachée à la release, par exemple `source.json`. |

Le workflow officiel CorvusCore construit depuis les sources qualifiées.
L'import des autres fournisseurs utilise les assets désignés par leur déclaration ;
modifier `repository` ou un contrôle de provenance nécessite une nouvelle revue.
Ce fichier n'est pas un catalogue découvert directement par les applications.

## Assets de la release amont

La release du fournisseur contient ses ZIP et les deux fichiers déclarés :

- Le manifeste `manifest_asset` utilise le [format 3](catalog-format.md).
  Ses URL désignent exclusivement les assets de ce dépôt approuvé et de ce
  tag amont ; les ID restent préfixés par le fournisseur.
- La provenance `provenance_asset` contient `format` égal à `1`, `provider`,
  `repository`, `source_sha` complet de 40 caractères hexadécimaux, `version`
  et `ci_run_id`, l'identifiant numérique du passage CI correspondant.

L'import vérifie le commit du tag, la provenance et la CI exacte avant
d'inspecter les archives. Il ne les exécute pas. Les URL amont ne sont jamais
promues telles quelles dans le catalogue public : la publication réécrit
les références vers les fichiers vérifiés dans CorvusRepository.
La provenance conservée ajoute `upstream_tag`, afin de retrouver la release
source depuis le dépôt approuvé. Le publisher recontrôle son commit avant
la publication centrale.

## Ordre de promotion

1. Identifier la source et le fournisseur, puis qualifier le build ou les archives proposées.
2. Vérifier l'ABI Android, le contrat CorvusAPI, le nom de bibliothèque, le contenu unique du ZIP, les limites de taille et les segments ELF de 16 Ko.
3. Publier les nouveaux fichiers dans une release CorvusRepository sous un tag disponible. Un fichier public déjà référencé n'est pas remplacé.
4. Télécharger ou contrôler les vrais fichiers publics ; comparer les octets, tailles et SHA-256 au lot qualifié.
5. Créer la pull request du catalogue généré et lancer explicitement sa CI.
   Les événements produits par `GITHUB_TOKEN` ne relancent pas automatiquement
   les workflows ; cette exécution explicite garde la vérification du commit
   de catalogue. Le mainteneur contrôle puis fusionne la PR. Les clients
   découvrent alors la mise à jour sans nouveau build de l'APK.

Si la politique du dépôt interdit à `GITHUB_TOKEN` de créer une pull request,
la publication laisse la branche de catalogue, sa CI explicite et une URL de
comparaison. Le mainteneur peut créer la PR depuis cette comparaison. Ce
chemin conserve les mêmes contrôles et n'exige pas de nouveau secret de
publication ; le catalogue public précédent reste actif jusqu'à la fusion.

Le tag de release identifie le lot de distribution. Il n'a pas à suivre la version de l'application et peut regrouper plusieurs versions de moteurs ; chaque entrée conserve sa propre version de cœur.

## Reprise après échec

Si un build ou une vérification échoue, conserver le catalogue public précédent. Si les fichiers sont publiés mais que le catalogue n'a pas été promu, reprendre les vérifications et la revue du catalogue ; ne pas republier des octets différents sous le même nom.

Une annulation de catalogue peut rétablir les références précédentes sans supprimer les anciennes archives ni changer les ID des moteurs. Les sauvegardes des clients ne doivent pas être migrées par une opération de distribution.

## Migration des archives historiques

La migration initiale de CorvusCore 0.15.0 reprend les six archives déjà qualifiées dans CorvusRetro v0.18.0. Elle conserve exactement leurs octets, noms, versions et SHA-256, puis change uniquement l'emplacement d'hébergement après vérification de la copie publique.

Les futures publications peuvent être produites directement par CorvusRepository depuis les sources qualifiées. Les anciennes releases CorvusRetro restent accessibles afin de préserver les clients et les références historiques.
