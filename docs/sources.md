# Sources de donnees — etat et evaluation

Mesures du 2026-11-16, sur 134 047 services.

## Sources actives

| Source | Services | Endpoint | Etat |
|---|---|---|---|
| `glama` | 67 025 | `glama.ai/api/mcp/v1/servers` | 401 sans jeton (normal) |
| `mcp_registry` | 55 493 | `registry.modelcontextprotocol.io/v0.1` | 200 |
| `pulsemcp` | 11 242 | scraping HTML de `www.pulsemcp.com/servers` | 403 depuis l'exterieur, a confirmer depuis le LXC |
| `docker_registry` | 279 | `docker/mcp-registry` via l'API GitHub | 200 |
| `mcp_servers_repo` | 7 | depot de reference | 200 |
| `github_topics` | nouveau | `api.github.com/search/repositories` | 200 |

`api.pulsemcp.com/v0beta/servers` repond 410 Gone, mais le connecteur ne
l'utilise pas : il scrape les pages HTML. Le 403 constate vient probablement
d'une protection anti-robot liee a l'IP appelante — le connecteur envoie un
User-Agent et suit les redirections, ce qui peut suffire depuis le LXC.

## github_topics

Le plus gros gisement disponible : `topic:mcp-server` compte 43 855 depots,
`topic:modelcontextprotocol` 741. Surtout, chaque entree arrive avec l'URL de
son depot, ce dont tout le pipeline depend — lecture du README, verification
d'accessibilite, hash de branche.

### Contraintes de l'API et forme du connecteur

**Plafond de 1000 resultats par requete.** `total_count` annonce le vrai
volume, mais les pages au-dela du millieme resultat sont refusees. Le
connecteur decoupe donc par fenetre de creation (`created:a..b`) depuis
octobre 2024, et bissecte toute fenetre qui depasse le plafond. La recursion a
ete validee sur un jeu simule : couverture complete de l'intervalle, sans trou
ni recouvrement. Une journee qui saturerait a elle seule le plafond est
journalisee en avertissement et paginee jusqu'a 1000 — l'exces est hors
d'atteinte de l'API, autant le dire que le taire.

**30 requetes par minute**, bien en dessous du quota REST que gere le pool de
jetons. Le connecteur impose sa propre cadence (`SEARCH_MIN_INTERVAL`), et
respecte `retry-after` / `x-ratelimit-reset` sur 403 et 429, avec un plafond
d'attente pour ne pas suspendre un sync entier.

### doc_hash sur champs stables uniquement

`doc_hash` est hache sur `full_name`, `description`, `topics`, `archived` et
`default_branch` — pas sur l'item complet. Un `doc_hash` different declenche
`needs_reindex` lors de l'upsert ; inclure `stargazers_count` ou `pushed_at`
ferait donc basculer le hash a chaque sync et declencherait une reindexation
complete et inutile de dizaines de milliers de services.

Les forks sont ecartes : ils dupliquent un depot deja couvert sans rien
ajouter.

### Exploitation

```bash
docker compose exec mcp-backend python -m mcp_manager.cli sync --source github_topics
```

Prevoir du temps : environ 450 appels de recherche au minimum pour 44 000
depots, a 2,2 s d'intervalle, soit un peu moins d'une heure, plus le
decoupage. Un jeton GitHub est indispensable — sans authentification la
recherche est limitee a 10 requetes par minute.

## Smithery — ecarte, et pourquoi

`registry.smithery.ai/servers` repond en JSON sans authentification et annonce
20 752 serveurs. Deux obstacles l'ont fait ecarter comme source.

**Aucune URL de depot.** Ni la liste ni le detail
(`/servers/{qualifiedName}`) n'exposent de lien vers un depot. Le detail
contient `connections`, `tools`, `prompts`, `resources`, `security` — de la
metadonnee d'execution, pas de provenance. `homepage` pointe majoritairement
vers `smithery.ai` lui-meme. Deriver `github.com/{qualifiedName}` serait une
supposition, qui fabriquerait exactement ce que le referentiel a de trop : des
fiches sans depot, donc sans README, donc sans synthese.

**Plafond de 500 resultats.** Quelle que soit la taille de page, l'API ne rend
que 500 lignes par requete (`pageSize=100` donne `totalPages=5`,
`pageSize=1` donne `totalPages=500`). La recherche libre repond 500 Internal
Error (`?q=database`), seuls des filtres du type `is:deployed`, `is:verified`,
`is:remote`, `is:local` fonctionnent. En pratique on atteindrait un millier de
serveurs uniques, pas 20 752.

**Piste a garder.** Smithery reste une excellente source d'*enrichissement* :
`connections[].configSchema` decrit les parametres de configuration, ce qui
alimenterait `mcp_parameters` bien mieux que ce qu'on extrait aujourd'hui. Cela
suppose d'apparier ses `qualifiedName` a des services existants — un autre
chantier que l'ajout d'une source.

## npm — differe

11 588 paquets portent le mot-clef `mcp-server` sur le registre npm. L'interet
n'est pas le volume mais `package_info` : le registre npm donne le nom de
paquet et la commande d'installation, que les registres MCP renseignent mal.
A traiter comme une passe d'enrichissement de `package_info`, pas comme une
source de services.

## Remarque de priorite

Le referentiel compte 134 047 services pour 17 257 depots verifies et 20 540
syntheses. Ajouter des sources augmente le volume, pas l'exploitabilite.
`github_topics` se justifie parce qu'il apporte des depots verifiables ; les
sources qui n'apportent que des fiches sans provenance aggravent le probleme
plutot qu'elles ne l'aident.
