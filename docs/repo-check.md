# Verification des depots — diagnostic et fonctionnement

## Ce qui ne marchait pas

Le 2026-11-15, le referentiel comptait 134 047 services dont 29 036 marques
`repo_status = '404'`, soit 40% des services verifies. Un sondage de 200 de ces
URLs, interrogees directement avec suivi des redirections, a donne :

| | |
|---|---|
| Depot vivant, acces direct | 166 (83%) |
| Depot vivant, renomme ou transfere | 8 (4%) |
| Depot reellement disparu | 26 (13%) |

**87% de faux positifs**, soit environ 25 000 services valides ecartes a tort.
L'API GitHub repondait bien `200` pour un echantillon de ces depots, sans meme
authentification : ils etaient vivants au moment du controle.

Quatre defauts se cumulaient.

**Tout code different de 200 valait disparition.** `check_repo` testait
`if resp.status_code == 200` puis retournait l'echec. Un 403 de quota, un 401
de jeton refuse, un 500 passager : meme verdict qu'un depot supprime.

**Le pool de jetons tirait a blanc sciemment.** `_get_pool_headers_sync` se
terminait par `# All exhausted — use first one anyway (will be rate limited by
GitHub)`. Chaque rejet ainsi provoque condamnait un service. C'est l'explication
la plus probable des 83% de faux positifs sans redirection.

**Les redirections n'etaient pas suivies.** `httpx` ne les suit pas par defaut.
Un depot renomme repond 301, donc "mort".

**La condamnation etait definitive.** La requete selectionnait
`repo_status IS NULL` : un service etait verifie une fois, jamais deux, et
aucune colonne ne datait le controle. Une coupure reseau de dix secondes
retirait un service du referentiel pour toujours.

S'y ajoutait une confusion de modele : `repo_status` portait aussi
`index_failed` et `no_doc`, ecrits par `indexer/pipeline.py`, qui ecrasait donc
le verdict du depot.

## Comment ca marche maintenant

### Deux colonnes au lieu d'une

- `repo_status` — accessibilite du depot seule : `ok`, `404`, `unsupported`
  (URL hors GitHub, que cette passe ne sait pas verifier), ou `NULL` tant
  qu'aucun verdict n'a ete obtenu.
- `index_status` — resultat de l'indexation : `index_failed`, `no_doc`, `NULL`.
- `repo_checked_at` — date du controle. C'est elle, et non `repo_status`, qui
  determine ce qui reste a verifier.

### Ne jamais ecrire un verdict qu'on n'a pas obtenu

`check_repo` renvoie un `CheckOutcome` :

| Reponse GitHub | Resultat | Effet en base |
|---|---|---|
| 200 | `OK` | `repo_status='ok'`, etoiles, date |
| 404, 410, 451 | `GONE` | `repo_status='404'`, date |
| URL hors GitHub | `UNSUPPORTED` | `repo_status='unsupported'`, date |
| 5xx, timeout, erreur reseau | `UNDETERMINED` | **rien** — la ligne repassera |
| 401 | `CheckAborted` | passe interrompue, jeton a verifier |
| 403, 429 | `CheckAborted` | passe interrompue, quota atteint |

Un incident laisse la ligne intacte. Une panne systemique (quota, jeton) rend
la main au lieu de condamner des milliers de services : c'est tout l'inverse de
l'ancien comportement.

Le compteur `MAX_CONSECUTIVE_UNDETERMINED` arrete aussi la passe apres 25
indetermines d'affilee — a ce stade le probleme n'est plus "ce depot la".

### Balayage par curseur

La requete avance par `_id > cursor` et non en reprenant les premieres lignes
non verifiees. C'est indispensable depuis qu'un lot peut rester entierement
indetermine : avec l'ancienne forme, la boucle aurait resservi les memes lignes
indefiniment.

Deux phases : d'abord les services sans verdict, ensuite ceux qui ont un
verdict mais pas de date. On obtient du signal neuf avant de depenser du quota
a revalider de l'acquis.

### Plus de helper synchrone

`get_github_headers()` et `_get_pool_headers_sync` sont supprimes. Respecter un
quota suppose de pouvoir attendre, ce qu'une fonction synchrone ne sait pas
faire dans une boucle asyncio — d'ou la requete condamnee d'origine. La version
asynchrone `get_headers_for_domain` attendait deja correctement ; tous les
appelants l'utilisent desormais (`repo_checker`, `url_resolver`, `dedup`, et
les connecteurs `docker_registry`, `mcp_registry`, `mcp_servers_repo`).

## Exploitation

```bash
# Verification bornee : le quota GitHub impose de reprendre en plusieurs fois
docker compose exec mcp-backend python -m mcp_manager.cli enrich --pass repo-check --limit 5000

# Sans borne : balaye tout ce qui n'a pas de date de controle
docker compose exec mcp-backend python -m mcp_manager.cli enrich --pass repo-check
```

Le reste a verifier est visible sur le tableau de bord (`Controles de depot en
attente`) et dans `/api/v1/stats` sous `repo_check_backlog`, qui distingue les
services verifiables de ceux qui n'ont aucune URL de depot — ces derniers ne
relevent pas de cette passe mais de `url-resolve`.

## Points non traites

**Les depots renommes gardent leur ancienne URL.** Le suivi des redirections
suffit a les juger vivants, mais `source_url` n'est pas reecrit vers l'URL
canonique. Le faire toucherait `canonical_id` et le dedoublonnage, ce qui
depasse le cadre de cette correction.

**Les services sans `source_url`** (environ un quart des non verifies dans
l'echantillon) restent hors de portee de cette passe. Ils relevent de
`url-resolve`.
