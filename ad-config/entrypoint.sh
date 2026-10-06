#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Meridian DC entrypoint — robust against Docker Desktop / WSL2 restarts.
# Key fixes vs. the crash-looping version:
#   * LDB_MODULES_PATH exported so secrets.ldb modules load (no "samba_secrets" error)
#   * verifies a REAL provision (loadable secrets.ldb), not a fragile marker file
#   * self-heals a corrupt/partial volume instead of crash-looping
#   * never exits non-zero on a transient error (no Restarting(255) loop)
# ─────────────────────────────────────────────────────────────────────────────
REALM="${REALM:-MERIDIAN.LOCAL}"
export LDB_MODULES_PATH="${LDB_MODULES_PATH:-/usr/lib/x86_64-linux-gnu/samba/ldb}"
HOSTNAME="$(hostname)"
grep -q "${HOSTNAME}.${REALM,,}" /etc/hosts 2>/dev/null || \
    echo "127.0.0.1 ${HOSTNAME}.${REALM,,} ${HOSTNAME}" >> /etc/hosts

# Is there a COMPLETE, loadable provision already on the volume?
provisioned() {
    [ -f /var/lib/samba/private/secrets.ldb ] && \
    ldbsearch -H /var/lib/samba/private/secrets.ldb -b "" -s base dn >/dev/null 2>&1
}

if provisioned; then
    echo "[startup] Existing valid domain found — skipping provisioning."
else
    echo "[startup] No valid domain on the volume — provisioning meridian.local ..."
    if /provision.sh; then
        echo "[startup] Provisioning succeeded. Applying ACL chain..."
        samba >/dev/null 2>&1 &
        sleep 10
        python3 /configure_acls.py || echo "[startup] WARN: ACL setup issue (non-fatal)"
        killall samba 2>/dev/null || true
        sleep 3
    else
        echo "[startup] ERROR: provisioning failed. Dumping diagnostics and holding."
        echo "         LDB_MODULES_PATH=$LDB_MODULES_PATH"
        ls -la /var/lib/samba/private/ 2>/dev/null || true
        echo "[startup] Container will stay up for troubleshooting (no restart loop)."
        tail -f /dev/null
    fi
fi

[ -f /var/lib/samba/private/krb5.conf ] && cp /var/lib/samba/private/krb5.conf /etc/krb5.conf
echo "[startup] Starting Samba (foreground) with LDB_MODULES_PATH=$LDB_MODULES_PATH"
exec samba --foreground --no-process-group
