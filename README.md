# Meridian Health Systems — Capstone Examination Lab

Final assessment environment for the M.Sc. Advanced Penetration Testing module.

## Start the lab
    docker compose up -d
    # Allow ~3 minutes for the Active Directory domain to provision on first boot.
    ./scripts/healthcheck.sh

## Targets (in scope)
| Service            | Address              | Notes                                    |
|--------------------|----------------------|------------------------------------------|
| Patient portal     | http://localhost      | Main web application                     |
| Internal API       | http://localhost:8081 | Also reachable internally at 10.10.20.11 |
| MediBot assistant  | http://localhost:8082 | AI chatbot                               |
| Cloud metadata     | 10.10.20.80           | Reachable ONLY via portal SSRF           |
| Domain Controller  | 10.10.20.60           | meridian.local (LDAP/Kerberos/SMB)       |

## Rules
- Everything on 10.10.20.0/24 and the localhost ports above is in scope.
- Do NOT attack the Docker host, other students, or anything outside the lab.
- The lab resets nightly is NOT automatic — treat it as a persistent engagement.

See the Examination Brief (separate PDF) for full scope, timeline, and deliverables.

## First-boot note (IMPORTANT — read before reporting a problem)
The Active Directory domain controller provisions itself on first boot, which
takes 2-4 MINUTES. During that window ./scripts/healthcheck.sh will show LDAP,
Kerberos, SMB and the domain as "pending (…)" — this is expected, not a fault.
Wait 2-3 minutes and run the healthcheck again; they will come up.

Watch progress with:   docker logs -f meridian-dc
"# meridian-exam-Penetration-testing-lab" 
