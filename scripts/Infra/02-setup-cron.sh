#!/bin/bash
###############################################################################
# Script 02 : Installation du cron MCP Manager
#
# A executer DANS le container LXC (en tant que root).
# Installe le script cron + active le crontab toutes les 6h.
#
# Usage depuis l'hote Proxmox :
#   pct exec <CTID> -- bash -c "$(cat 02-setup-cron.sh)"
#
# Ou via SSH :
#   ssh root@192.168.10.99 "bash -s" < scripts/Infra/02-setup-cron.sh
###############################################################################
set -eu

PROJECT_DIR="/root/mcp-manager"
CRON_SCRIPT="/root/cron-mcp-manager.sh"
CRON_LOG="/root/cron-mcp.log"

echo "==========================================="
echo "  Setup Cron MCP Manager"
echo "==========================================="
echo ""

# ── 1. Creer le script cron ─────────────────────────────────────────────────
echo "[1/3] Creation du script cron..."

cat > "${CRON_SCRIPT}" << 'CRONSCRIPT'
#!/bin/bash
# MCP Manager — Cron job (sync + enrich + index)
LOG="/root/cron-mcp.log"
cd /root/mcp-manager

echo "$(date '+%Y-%m-%d %H:%M:%S') === CRON START ===" >> $LOG

# 1. Sync all sources
echo "$(date +%H:%M:%S) — Sync..." >> $LOG
docker compose exec -T mcp-backend python -m mcp_manager.cli sync 2>&1 | grep "^Sync complete:" >> $LOG

# 2. Dedup
echo "$(date +%H:%M:%S) — Dedup..." >> $LOG
docker compose exec -T mcp-backend python -m mcp_manager.cli enrich --pass dedup 2>&1 | grep "complete:" >> $LOG

# 3. Repo check (s'arrete proprement quand rate limit epuise)
echo "$(date +%H:%M:%S) — Repo check..." >> $LOG
docker compose exec -T mcp-backend python -m mcp_manager.cli enrich --pass repo-check 2>&1 | grep "complete:" >> $LOG

# 4. Flag new services for indexation
docker compose exec -T mcp-manager-postgres psql -U langgraph -d langgraph -c "
UPDATE mcp_services SET needs_reindex = TRUE
WHERE id NOT IN (SELECT DISTINCT mcp_service_id FROM mcp_summaries)
AND needs_reindex = FALSE AND index_attempts < 2;
" >> $LOG 2>&1

# 5. Index batch (summary + embeddings + params + recettes)
echo "$(date +%H:%M:%S) — Index..." >> $LOG
docker compose exec -T mcp-backend python -m mcp_manager.cli index --limit 500 2>&1 | grep "^Index complete:" >> $LOG

# 6. Update search vectors for newly indexed services
docker compose exec -T mcp-manager-postgres psql -U langgraph -d langgraph -c "
UPDATE mcp_services s SET search_vector = to_tsvector('english',
  coalesce(s.name, '') || ' ' || coalesce(s.category, '') || ' ' ||
  coalesce((SELECT summary FROM mcp_summaries WHERE mcp_service_id = s.id AND culture = 'en'), '')
) WHERE id IN (SELECT DISTINCT mcp_service_id FROM mcp_summaries);
" >> $LOG 2>&1

echo "$(date '+%Y-%m-%d %H:%M:%S') === CRON DONE ===" >> $LOG

# Rotate log (keep last 1000 lines)
tail -1000 $LOG > ${LOG}.tmp && mv ${LOG}.tmp $LOG
CRONSCRIPT

chmod +x "${CRON_SCRIPT}"
echo "  -> ${CRON_SCRIPT} cree"

# ── 2. Installer le crontab ─────────────────────────────────────────────────
echo "[2/3] Installation du crontab..."

# Supprimer l'ancien cron si existant
crontab -l 2>/dev/null | grep -v "cron-mcp-manager" > /tmp/crontab.tmp || true

# Ajouter le nouveau cron toutes les 6h
echo "0 */6 * * * ${CRON_SCRIPT}" >> /tmp/crontab.tmp

crontab /tmp/crontab.tmp
rm /tmp/crontab.tmp

echo "  -> Crontab installe (toutes les 6h)"

# ── 3. Verifier ─────────────────────────────────────────────────────────────
echo "[3/3] Verification..."

echo ""
echo "  Crontab actuel :"
crontab -l 2>/dev/null | grep "cron-mcp"
echo ""
echo "  Script : ${CRON_SCRIPT}"
echo "  Log    : ${CRON_LOG}"
echo ""
echo "  Pour lancer manuellement :"
echo "    ${CRON_SCRIPT}"
echo ""
echo "  Pour voir les logs :"
echo "    tail -50 ${CRON_LOG}"
echo ""
echo "  Pour desactiver :"
echo "    crontab -l | grep -v cron-mcp-manager | crontab -"
echo ""
echo "==========================================="
