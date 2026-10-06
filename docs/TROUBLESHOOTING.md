# Meridian Exam Lab — Troubleshooting

## The DC container (`meridian-dc`) crashes or restarts, or the domain never comes up

Symptoms you might see in `docker logs meridian-dc`:

```
WARNING: Module [samba_secrets] not found - do you need to set LDB_MODULES_PATH?
Unable to load modules for /var/lib/samba/private/secrets.ldb: (null)
ERROR(ldb): uncaught exception - None
```
or the container shows `Restarting (255)` in `docker ps`.

### What causes it
The Active Directory database lives on a Docker **named volume** (`meridian-ad-data`).
If a previous run left a *partial* database on that volume — for example the container
was stopped mid-provision — Samba tries to load a half-written `secrets.ldb` and fails.
On Docker Desktop / WSL2 this showed up as an instant crash loop.

The current lab version fixes this (self-healing entrypoint, explicit
`LDB_MODULES_PATH`, and no crash-loop restart policy). If you are on the fixed
version and still see it, the volume from an **earlier** run is the culprit — clear
it once with the steps below.

### The fix — clean the stale volume and rebuild (one time)

```bash
# 1. Tear down and REMOVE the old volume (this wipes the broken AD database):
docker compose down -v

# 2. Rebuild the DC image fresh (picks up the corrected Dockerfile):
docker compose build --no-cache meridian-dc

# 3. Bring the lab back up:
docker compose up -d

# 4. Watch the DC provision (this takes 2-4 minutes on first boot):
docker logs -f meridian-dc
#    Wait until you see: "Starting Samba (foreground) ..."

# 5. Verify:
./scripts/healthcheck.sh
```

> `docker compose down -v` deletes the AD data volume. That is intended here — the
> domain is rebuilt automatically on the next `up`. It does **not** delete your own
> notes or anything outside the lab.

### Still stuck?
With the fixed version, a failed provision no longer loops — the container stays up
so you can look inside:

```bash
docker exec -it meridian-dc bash
echo $LDB_MODULES_PATH          # should be /usr/lib/x86_64-linux-gnu/samba/ldb
ls -la /var/lib/samba/private/  # secrets.ldb should exist and be non-empty
```

If `LDB_MODULES_PATH` is empty inside the container, you are still on the old image —
re-run step 2 above with `--no-cache`.

---

## Other quick checks

- **Web services fine but AD "pending" in healthcheck:** normal for the first 2-4
  minutes while the DC provisions. Wait and re-run `./scripts/healthcheck.sh`.
- **Windows line-ending errors on the shell scripts** (`bad interpreter`): run
  `sed -i 's/\r$//' ad-config/*.sh scripts/*.sh` then rebuild.
- **Port already in use (80/389/445):** another service is using it on your host.
  Stop it, or edit the port mappings in `docker-compose.yml`.
