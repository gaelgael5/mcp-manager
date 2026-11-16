# Configuration d'execution et `git reset --hard`

Certains fichiers du depot sont a la fois **montes en bind-mount** dans le
conteneur backend et **modifiables depuis l'application**. Ils portent donc de
l'etat d'execution, pas du code. Or `/root/deploy-mcp.sh` livre par
`git fetch && git reset --hard origin/master` : tout fichier **suivi** par git
y est reecrit a chaque livraison, silencieusement.

Les montages concernes (`docker-compose.yml`, service `mcp-backend`) :

```yaml
- ./backend/config:/app/config
- ./backend/prompts:/app/prompts
```

## Le cas constate : les providers LLM

`backend/config/llm_providers.json` etait suivi par git. Consequence mesuree le
2026-11-16 : la configuration saisie dans `/settings` (ici
`http://192.168.10.80:11434/v1` et `qwen3.5:9b`) etait remplacee a chaque
livraison par les valeurs du depot (`http://192.168.10.80:11434` et
`llama3.1:8b`).

Le symptome etait trompeur, parce que deux choses divergeaient sans que l'ecran
ne le montre :

- l'ecran affichait la configuration **relue apres reset**, donc les valeurs du
  depot — mais l'utilisateur se souvenait avoir saisi les siennes ;
- le resultat du test ne disait pas **quoi** avait ete contacte, seulement un
  code HTTP. Un 404 d'endpoint (`/v1/api/generate`) et un 404 de modele absent
  (`model 'x' not found`) y etaient indistinguables, le message de
  `raise_for_status()` ne citant que le code et l'URL, jamais le corps.

### Correction

1. `llm_providers.json` n'est plus suivi. Le depot ne porte plus que
   `llm_providers.example.json`.
2. `.gitignore` ignore `backend/config/*.json` en conservant `*.example.json`.
3. `load_config()` recopie l'exemple quand le fichier manque (machine neuve),
   plutot que de renvoyer une liste vide : un referentiel sans fournisseur ne
   produit aucun message exploitable.
4. Le resultat du test porte un champ `target` : l'URL **normalisee** et le
   modele que le driver va reellement joindre.
5. `OllamaDriver.generate` leve `OllamaError` avec le corps de la reponse
   (500 premiers caracteres) au lieu de laisser `raise_for_status()` le jeter.
6. La fenetre de test n'est plus muette quand il n'y a rien a tester, et ne
   tronque plus les messages a 200 caracteres.

### A faire une fois, a la livraison

Cette livraison-ci efface encore le fichier (git le supprime en meme temps
qu'il cree l'exemple). Le sauver avant :

```bash
cp /root/mcp-manager/backend/config/llm_providers.json /root/llm_providers.json.bak
/root/deploy-mcp.sh
cp /root/llm_providers.json.bak /root/mcp-manager/backend/config/llm_providers.json
docker compose restart mcp-backend
```

Sans sauvegarde, `load_config()` repose l'exemple et il faut resaisir les
valeurs dans `/settings`. Elles y survivront aux livraisons suivantes.

## Exposition restante : les prompts

`backend/prompts/<lang>/*.md` (12 fichiers) est dans la meme situation :
suivi par git, bind-monte, et editable depuis `/settings/prompts`. CLAUDE.md
affirme que le bind-mount assure la « persistance cross-rebuild » : c'est vrai
d'un `docker compose up --build`, faux d'un `deploy-mcp.sh`. **Toute
modification de prompt faite depuis l'interface est perdue a la livraison
suivante.**

Ce n'est pas corrige ici : contrairement a la configuration, les prompts ont
une valeur a etre versionnes (relecture, couverture des 8 langues). La sortie
propre serait de versionner des defauts (`backend/prompts.default/`) et de
bootstrapper `backend/prompts/` a partir d'eux, sur le modele du point 3.
Tant que ce n'est pas fait, editer les prompts dans le depot, pas dans l'app.
