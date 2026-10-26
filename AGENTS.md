# Consignes pour les agents - CorvusRepository

Ce dépôt publie seulement le catalogue des modules CorvusAPI et ses outils
de validation. Il n'est ni un moteur d'émulation, ni une copie de CorvusCore,
ni le frontend Android CorvusRetro.

- `cores-v3.json` est le catalogue public du téléchargeur actuel. Ne changer
  ni le schéma, ni les identifiants, ni les URL historiques sans migration
  coordonnée de CorvusRetro.
- Les empreintes et tailles doivent correspondre aux ZIP réels publiés sur
  GitHub Releases ; ne jamais inventer des valeurs.
- Conserver la liste de fournisseurs/URL autorisés et les limites de taille
  dans `tools/validate_catalog.py` et ses tests.
- Les bibliothèques distribuées restent sous leurs licences propres.
  La licence MIT de ce dépôt ne s'applique pas automatiquement aux ZIP.
- Aucune ROM commerciale, BIOS, secret, clé de signature, binaire téléchargé
  ou code d'émulation dans ce dépôt.
- Avant chaque modification du catalogue, lancer :
  `python3 tools/validate_catalog.py cores-v3.json`
  et `python3 -m unittest discover -s tests -v`.
- Pour publier des mises à jour, lire `docs/PUBLISHING.md` ; conserver
  les fichiers de release immuables et les anciennes URL accessibles.
- Travailler par pull request pour les futures mises à jour de catalogue,
  avec contrôle de la CI. Ne pas déclarer un asset vérifié si sa métadonnée
  de release n'a pas été consultée.
