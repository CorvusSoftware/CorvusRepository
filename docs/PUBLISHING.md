# Publication et maintenance du catalogue

Le dépôt CorvusRepository est le **point de publication des métadonnées**, pas le
code source des moteurs. La version initiale reprend exactement les six ZIP
`CorvusCore 0.14.1` publiés dans la release CorvusRetro `v0.13.0`.

## Publication actuelle

- **Catalogue public :** `cores-v3.json` à la racine.
- **Archives ZIP actuellement servies :** release `CorvusRetro/v0.13.0`.
- **Clients déjà publiés :** récupèrent toujours
  `CorvusRetro/main/core-repository/cores-v3.json`.
- **Anciens clients :** les formats 1 et 2 restent à leurs anciennes URL
  CorvusRetro. Ne jamais les supprimer à l'occasion de la migration.

## Nouvelle version des moteurs

1. Qualifier les modules construits par les workflows CorvusCore/CorvusRetro.
   Conserver les révisions exactes des sources, les résultats CI et les licences.
2. Publier les six ZIP sous un **nouveau tag immuable** ; ne jamais remplacer
   silencieusement un ZIP déjà distribué.
3. Relever les tailles et empreintes SHA-256 des fichiers **publiés**, non une
   estimation locale. La réponse API des releases GitHub expose `size` et
   `digest` sur chaque asset.
4. Modifier `cores-v3.json`, puis exécuter :

   ```sh
   python3 tools/validate_catalog.py cores-v3.json
   python3 -m unittest discover -s tests -v
   python3 -m tools.check_release_assets cores-v3.json
   ```

5. Vérifier la CI de la modification avant de promouvoir le nouveau catalogue.

Le validateur actuel accepte **uniquement les URLs de release CorvusRetro**,
comme le téléchargeur déjà publié. Pour héberger ultérieurement les ZIP dans
les releases **CorvusRepository**, modifier et tester **d'abord** la liste
d'origines acceptées par CorvusRetro et le validateur. Ne pas élargir cette
liste à des domaines arbitraires et ne pas réécrire les anciens assets.

## Intégration de CorvusRetro

L'URL attendue pour un prochain client est :

```text
https://raw.githubusercontent.com/CorvusSoftware/CorvusRepository/main/cores-v3.json
```

Aujourd'hui, `CoreRepository.java` utilise toujours le catalogue hébergé
dans CorvusRetro. Modifier la constante `INDEX` dans une PR dédiée,
vérifier les tests de téléchargement et produire une nouvelle version
de CorvusRetro. **Une modification du catalogue externe n'actualise pas les
APK déjà publiés.**

## Sécurité et licences

- Pas de ROM, BIOS, APK de base, secret ni clé de signature dans ce dépôt.
- Conserver l'ABI et les identifiants reconnus par le téléchargeur actuel.
- Chaque taille/hash est calculé sur les **octets ZIP**, pas sur le module
  extrait.
- Les sources CorvusCore, les moteurs distribués et leurs notices AGPL-3.0
  restent dans le dépôt du fournisseur. CorvusRepository MIT ne les relicencie pas.
