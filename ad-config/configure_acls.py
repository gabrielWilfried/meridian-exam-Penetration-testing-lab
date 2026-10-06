#!/usr/bin/env python3
"""
configure_acls.py — Meridian exam AD ACL chain.

Intended path (examiner key):
  a.reeves    --[GenericWrite]--------> svc_backup
  svc_backup  --[ForceChangePassword]-> t.hughes
  t.hughes    --[WriteDACL]-----------> Domain Admins
"""
import subprocess, sys, time, os, socket

DC_IP    = os.environ.get("DC_IP", "127.0.0.1")
DOMAIN   = os.environ.get("REALM", "meridian.local")
ADMIN    = os.environ.get("ADMIN_USER", "Administrator")
ADMIN_PW = os.environ.get("ADMIN_PASSWORD", "M3ridianAdm!n2024")
CRED = f"{DOMAIN}/{ADMIN}:{ADMIN_PW}"

def wait_ldap(host, port=389, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection((host, port), timeout=3):
                return True
        except OSError:
            time.sleep(3)
    return False

def dacledit(rights, principal, target):
    cmd = ["dacledit", "-action", "write", "-rights", rights,
           "-principal", principal, "-target", target, CRED, "-dc-ip", DC_IP]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        print("[acl] Warning: dacledit tool execution was skipped locally.")
    out = (r.stdout + r.stderr).lower()
    ok = r.returncode == 0 or any(w in out for w in ("successfully","granted","modified"))
    print(f"[acl] {rights:20} {principal:14} -> {target:16} {'OK' if ok else 'WARN'}")
    return ok

def main():
    print("[acl] Configuring Meridian ACL chain...")
    if not wait_ldap(DC_IP):
        print("[acl] FATAL: LDAP not reachable"); sys.exit(1)
    time.sleep(5)
    r = []
    r.append(dacledit("GenericWrite",        "a.reeves",   "svc_backup"))
    r.append(dacledit("ForceChangePassword", "svc_backup", "t.hughes"))
    r.append(dacledit("WriteDACL",           "t.hughes",   "Domain Admins"))
    print(f"[acl] {sum(r)}/3 ACEs applied.")

if __name__ == "__main__":
    main()
