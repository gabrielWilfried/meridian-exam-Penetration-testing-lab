#!/usr/bin/env python3
"""
Meridian Health — Internal API Service (api.meridianhealth.io)
CAPSTONE EXAMINATION TARGET

Simulates a MongoDB-backed API. Contains a NoSQL injection vulnerability
[VULN-16] (T3). Reachable directly, or via SSRF from the main portal.
"""
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# In-memory "Mongo-like" store
STAFF = [
    {"username": "a.reeves",  "password": "Spring2024!",   "role": "doctor",  "api_key": "n/a"},
    {"username": "m.chen",    "password": "MeridianIT#2024","role": "admin",   "api_key": "n/a"},
    # [VULN-17] Privileged API key leaks via NoSQL injection auth bypass.
    {"username": "svc_api",   "password": "Ap1Sv c!2024",  "role": "service",
     "api_key": "FLAG{nosql_injection_auth_bypass}"},
]

def matches(record, query):
    """Naive re-implementation of Mongo operators — the vulnerable part."""
    for k, v in query.items():
        if isinstance(v, dict):
            # Handle operators like {"$ne": null}, {"$gt": ""}
            for op, opval in v.items():
                if op == "$ne" and record.get(k) == opval:
                    return False
                if op == "$gt" and not (record.get(k, "") > opval):
                    return False
                if op == "$regex":
                    import re
                    if not re.search(opval, str(record.get(k, ""))):
                        return False
        else:
            if record.get(k) != v:
                return False
    return True

# [VULN-16] NoSQL injection — JSON body passed straight into the query.
# Auth bypass:            {"username":"svc_api","password":{"$ne":""}}
# Enumerate all records:  {"username":{"$ne":null},"password":{"$ne":null}}
#                         (returns ALL matches, like a real Mongo find())
@app.route("/api/v1/auth", methods=["POST"])
def auth():
    query = request.get_json(force=True, silent=True) or {}
    # VULNERABLE: attacker-controlled operators reach the matcher.
    # Returns EVERY matching record (real find() semantics) — so an operator
    # injection that matches all users leaks all of them, flag included.
    hits = [r for r in STAFF if matches(r, query)]
    if hits:
        return jsonify({
            "authenticated": True,
            "matched": len(hits),
            "records": [
                {"username": r["username"], "role": r["role"], "api_key": r["api_key"]}
                for r in hits
            ],
        })
    return jsonify({"authenticated": False}), 401

@app.route("/api/v1/")
def api_root():
    return jsonify({
        "service": "meridian-internal-api",
        "endpoints": ["/api/v1/auth (POST)", "/api/v1/staff (requires api_key)"],
        "note": "internal use only — not for public exposure"
    })

@app.route("/api/v1/staff")
def staff():
    key = request.headers.get("X-API-Key", "")
    if key.startswith("FLAG{"):
        return jsonify({"staff": [{"u": s["username"], "role": s["role"]} for s in STAFF]})
    return jsonify({"error": "valid X-API-Key required"}), 403

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
