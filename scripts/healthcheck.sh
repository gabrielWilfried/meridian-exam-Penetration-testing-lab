#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# Meridian Exam Lab — Health Check
# Confirms every service is up and reachable. Does NOT reveal exploit steps.
# Run after: docker compose up -d  (allow ~3 min for the DC to provision)
# ═══════════════════════════════════════════════════════════════════════════════
set -u
pass=0; fail=0; warn=0
ok(){    printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
no(){    printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }
wait_(){ printf '  \033[33m…\033[0m %s\n' "$1"; warn=$((warn+1)); }

# Portable TCP-port test: uses bash's built-in /dev/tcp (works on macOS + Linux
# without depending on a specific nc variant, which was the old bug).
port_open(){ # host port
  (exec 3<>"/dev/tcp/$1/$2") >/dev/null 2>&1 && { exec 3>&- 3<&-; return 0; } || return 1
}

echo "=== Meridian Health — Capstone Exam Lab Health Check ==="
echo

echo "[ Web services ]"
curl -sf http://localhost/health         >/dev/null 2>&1 && ok "Patient portal (:80)"     || no "Patient portal (:80)"
curl -sf http://localhost:8081/health    >/dev/null 2>&1 && ok "Internal API (:8081)"     || no "Internal API (:8081)"
curl -sf http://localhost:8082/health    >/dev/null 2>&1 && ok "MediBot chatbot (:8082)"  || no "MediBot chatbot (:8082)"
echo

echo "[ Internal-only services (via SSRF path) ]"
# Cloud meta has no host port; reach it through the portal SSRF endpoint after auth.
# Here we just confirm the container answers on the internal network via the web container.
# The web image has no curl, so we test cloud-meta the way students actually reach
# it: through the portal SSRF endpoint. If the portal proxies to the metadata IP
# and gets a healthy response, the internal service is up.
CM=$(curl -sf "http://localhost/labresult?url=http://10.10.20.80/health" 2>/dev/null || true)
if echo "$CM" | grep -q '"status"'; then
  ok "Cloud metadata sim (10.10.20.80) reachable via SSRF path"
elif echo "$CM" | grep -qi 'auth'; then
  # SSRF endpoint requires a session first — that still proves the portal is wired.
  ok "Cloud metadata path present (portal SSRF requires auth first — expected)"
else
  # Fall back to a direct container check using the DC container, which has curl.
  if docker exec meridian-dc curl -sf http://10.10.20.80/health >/dev/null 2>&1; then
    ok "Cloud metadata sim (10.10.20.80) up (checked from DC container)"
  else
    no "Cloud metadata sim (10.10.20.80) — check: docker logs meridian-cloud-meta"
  fi
fi
echo

echo "[ Active Directory ]"
# First, is the domain actually provisioned? This is the authoritative check —
# the port tests below are secondary. Provisioning takes 2-4 min on first boot.
DC_UP=false
if docker exec meridian-dc samba-tool user list 2>/dev/null | grep -q a.reeves; then
  DC_UP=true
fi

if $DC_UP; then
  ok "Domain meridian.local provisioned (users present)"
  # Now the ports should be open; test them portably.
  port_open localhost 389 && ok "LDAP (:389)"    || no "LDAP (:389)"
  port_open localhost 88  && ok "Kerberos (:88)" || no "Kerberos (:88)"
  port_open localhost 445 && ok "SMB (:445)"     || no "SMB (:445)"
else
  # Distinguish "still provisioning" (normal) from "actually broken".
  if docker ps --format '{{.Names}}' | grep -q meridian-dc; then
    if docker logs meridian-dc 2>&1 | grep -qi "provision.*complete\|samba.*started"; then
      no "DC container up but domain missing — check: docker logs meridian-dc"
    else
      wait_ "DC still provisioning (normal on first boot) — wait 2-3 min, then re-run"
      wait_ "LDAP/Kerberos/SMB will come up once provisioning finishes"
    fi
  else
    no "meridian-dc container is not running — check: docker compose ps"
  fi
fi
echo

echo "──────────────────────────────────────────────"
printf 'RESULT: \033[32m%d up\033[0m, \033[33m%d pending\033[0m, \033[31m%d down\033[0m\n' "$pass" "$warn" "$fail"
if [ "$fail" -eq 0 ] && [ "$warn" -eq 0 ]; then
  echo "All exam services are live. The lab is ready for students."
elif [ "$fail" -eq 0 ] && [ "$warn" -gt 0 ]; then
  echo "Core services are up. The domain controller is still provisioning —"
  echo "this is normal on first boot. Wait 2-3 minutes and run this script again."
else
  echo "Some services are genuinely down. See the messages above."
  echo "Most common cause: the DC needs 2-3 min on first boot — wait and re-run."
fi
