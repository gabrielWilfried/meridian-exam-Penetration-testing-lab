#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# provision.sh — Meridian Health AD provisioning (CAPSTONE EXAM)
# Domain: meridian.local   DC: MERIDIAN-DC01
#
# Intended internal attack chain (see examiner key):
#   a.reeves (foothold, from portal cred reuse)
#     --[GenericWrite]--> svc_backup  (Kerberoastable, weak pw)
#     --[ForceChangePassword]--> t.hughes (Server Operators / IT)
#     --[WriteDACL]--> Domain Admins
# Plus svc_legacy = AS-REP roastable.
# ─────────────────────────────────────────────────────────────────────────────
set -e
DOMAIN="${DOMAIN:-MERIDIAN}"
REALM="${REALM:-MERIDIAN.LOCAL}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-M3ridianAdm!n2024}"

echo "[provision] Provisioning ${REALM} ..."
export LDB_MODULES_PATH="${LDB_MODULES_PATH:-/usr/lib/x86_64-linux-gnu/samba/ldb}"

# Only remove a PARTIAL/broken provision, never a working one. A complete provision
# has a loadable secrets.ldb; a broken one (the crash-loop state) does not.
# Blindly deleting *.ldb (the old behaviour) corrupted the persistent volume and
# caused the "Module [samba_secrets] not found" crash on restart — do NOT do that.
if [ -f /var/lib/samba/private/secrets.ldb ]; then
    if ! ldbsearch -H /var/lib/samba/private/secrets.ldb -b "" -s base dn >/dev/null 2>&1; then
        echo "[provision] Detected a corrupt/partial private dir — clearing it for a clean provision."
        rm -rf /var/lib/samba/private/* /var/lib/samba/*.ldb 2>/dev/null || true
    fi
fi
rm -f /etc/samba/smb.conf

samba-tool domain provision \
    --domain="${DOMAIN}" --realm="${REALM}" \
    --server-role=dc --dns-backend=SAMBA_INTERNAL \
    --adminpass="${ADMIN_PASSWORD}" --use-rfc2307 \
    --option="dns forwarder = 8.8.8.8" --option="log level = 1" \
    --option="vfs objects = dfs_samba4 xattr_tdb" \
    --option="xattr_tdb:file = /var/lib/samba/private/xattr.tdb"

cp /var/lib/samba/private/krb5.conf /etc/krb5.conf
echo "[provision] Domain provisioned. Creating users..."

# Foothold — password matches the portal doctor account (credential reuse pivot)
samba-tool user create a.reeves "Spring2024!" \
    --given-name="Alice" --surname="Reeves" --description="Cardiology"

# Kerberoastable service account (weak, crackable password) — chain hop 1 target
samba-tool user create svc_backup "Backup2019!" \
    --given-name="Backup" --surname="Service" --description="Backup service account"

# Second Kerberoastable service account (harder pw — red herring, won't crack easily)
samba-tool user create svc_sql "K7#mNp2xQ9!vLw4Z" \
    --given-name="SQL" --surname="Service" --description="SQL service account"

# AS-REP roastable account (pre-auth disabled below)
samba-tool user create svc_legacy "L3gacy!Pass2020" \
    --given-name="Legacy" --surname="Service" --description="Legacy integration (no pre-auth)"

# Mid-chain privileged IT account — target of ForceChangePassword
samba-tool user create t.hughes "Th0mas#Hughes24" \
    --given-name="Thomas" --surname="Hughes" --description="Senior IT Administrator"

# A decoy admin-sounding account with NO useful privileges (red herring)
samba-tool user create admin_helpdesk "Helpdesk!2024" \
    --given-name="Helpdesk" --surname="Admin" --description="Helpdesk (limited)"

for u in svc_backup svc_sql svc_legacy t.hughes admin_helpdesk; do
    samba-tool user setexpiry "${u}" --noexpiry
done

echo "[provision] Setting SPNs (Kerberoasting surface)..."
samba-tool spn add "MSSQLSvc/meridian-db.meridian.local:1433" svc_sql
samba-tool spn add "CIFS/meridian-backup.meridian.local" svc_backup
samba-tool spn add "HTTP/meridian-rpt.meridian.local" svc_backup

echo "[provision] Disabling pre-auth on svc_legacy (AS-REP roasting)..."
# ─── REPLACE THE ENTIRE DISABLING PRE-AUTH LINE/BLOCK WITH THIS ───
echo -e "dn: CN=Legacy Service,CN=Users,DC=meridian,DC=local\nchangetype: modify\nreplace: userAccountControl\nuserAccountControl: 4194816" | ldbmodify -H /var/lib/samba/private/sam.ldb



# Plant a flag in a readable share for the AD objective
mkdir -p /srv/share
echo "FLAG{domain_admin_achieved} — you compromised meridian.local" > /srv/share/proof.txt

echo "[provision] Provision complete."
