FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
# LDB_MODULES_PATH must point at Samba's LDB modules or secrets.ldb fails to load
# with "Module [samba_secrets] not found" — the crash students hit on WSL2/Docker.
ENV LDB_MODULES_PATH=/usr/lib/x86_64-linux-gnu/samba/ldb
RUN apt-get update && apt-get install -y --no-install-recommends \
        samba samba-dsdb-modules samba-vfs-modules \
        krb5-user winbind dnsutils python3 python3-pip \
        python3-samba net-tools ldb-tools curl \
    && pip3 install --no-cache-dir impacket \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
# Verify the samba_secrets module is actually present (this is the module the
# student's error said was missing). Fail the build early if the layout changes.
RUN test -d "$LDB_MODULES_PATH" && ls "$LDB_MODULES_PATH"/*.so >/dev/null 2>&1 || \
    (echo "FATAL: LDB modules missing at $LDB_MODULES_PATH" && \
     find /usr/lib -type d -name ldb 2>/dev/null && exit 1)
RUN mkdir -p /var/lib/samba/private /var/log/samba /run/samba
COPY entrypoint.sh /entrypoint.sh
COPY provision.sh /provision.sh
COPY configure_acls.py /configure_acls.py
RUN chmod +x /entrypoint.sh /provision.sh
EXPOSE 53/tcp 53/udp 88/tcp 88/udp 135/tcp 139/tcp 389/tcp 445/tcp 464/tcp 636/tcp 3268/tcp
VOLUME ["/var/lib/samba"]
ENTRYPOINT ["/entrypoint.sh"]
