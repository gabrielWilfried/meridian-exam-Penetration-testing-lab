#!/usr/bin/env python3
"""
Meridian Health — Cloud Metadata Simulator (AWS IMDS shim)
CAPSTONE EXAMINATION TARGET

Runs at 10.10.20.80. Reachable only via the portal SSRF (/labresult?url=).
Simulates an EC2 instance with an IAM role that can read patient-data backups
from S3. [VULN-19] SSRF-to-cloud-credential chain (T-cloud).
"""
from flask import Flask, jsonify, Response
app = Flask(__name__)

IAM_ROLE = "meridian-portal-role"

@app.route("/latest/meta-data/")
def root():
    return Response("ami-id\nhostname\niam/\ninstance-id\nsecurity-groups\n",
                    content_type="text/plain")

@app.route("/latest/meta-data/iam/security-credentials/")
def role_list():
    return Response(IAM_ROLE, content_type="text/plain")

@app.route(f"/latest/meta-data/iam/security-credentials/{IAM_ROLE}")
def creds():
    # [VULN-19] IAM credentials exposed via SSRF-to-metadata.
    return jsonify({
        "Code": "Success",
        "Type": "AWS-HMAC",
        "AccessKeyId": "ASIAMERIDIAN9EXAMPLE",
        "SecretAccessKey": "wMerId1anFakeSecretKeyForLabUseOnlyXXXXX",
        "Token": "FQoGZXIvYXdzMERIDIANFakeSessionTokenLabOnly==",
        "Expiration": "2099-12-31T23:59:59Z",
        "note": "FLAG{ssrf_cloud_credential_theft}"
    })

@app.route("/api/sim/s3/buckets")
def s3():
    return jsonify({
        "iam_role": IAM_ROLE,
        "accessible_buckets": [
            {"name": "meridian-patient-backups", "objects": 4210,
             "sample_keys": ["phi_export_2024_q1.csv", "ssn_index.json",
                             "FLAG{s3_patient_data_exfiltration}.txt"]},
            {"name": "meridian-app-config", "objects": 12,
             "sample_keys": ["prod.env", "db_credentials.json"]},
        ]
    })

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "meridian-cloud-meta"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
