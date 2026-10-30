# 05 — Security, Privacy and Verification

## Data handling

- Use synthetic student records in development, demos and tests. Do not collect Aadhaar or unnecessary personal data.
- APAAR-like references are normalized and matched server-side using keyed HMAC. Full identifiers must not appear in ordinary API responses, QR data, audit metadata or logs.
- External verification returns only allowlisted claims. No raw identity fields or cross-institution record data are returned.
- Logs contain request IDs, route/status/timing and exception type only. Audit metadata is allowlisted and discards arbitrary text, email, names, tokens and identifiers.

## Consent and verification

Consent is recorded for one verifier, purpose and explicit set of eligible claims, with grant, expiry and revocation timestamps. The student must be authenticated and the enrolment must belong to that student's identity reference. Consent does not replace verifier role authorization or the verifier's approved, unexpired server-side grant.

The verification service checks WEAVE's current enrolment records. It labels responses `WEAVE_RECORD_CHECK` and `external_verification: NOT_PERFORMED`; it is not connected to APAAR, DigiLocker, AICTE or another official source. Claims are restricted to enrolment status, program code, academic year and award status. Missing values are omitted.

Optional signed credentials use Ed25519 from `cryptography`. Set `VERIFICATION_SIGNING_PRIVATE_KEY` to URL-safe base64 encoded DER PKCS8 key material using a secret manager/environment injection. Never commit that value. Tokens contain only issuer, intended audience, issue/expiry time, opaque revocation ID and permitted claims. They expire after five minutes; the verifier endpoint checks signature, issuer, audience, expiry and the server-side revocation record. Consent revocation revokes outstanding credentials for that enrolment/verifier. Keep backups and rotation procedures for signing keys; key IDs/overlap rotation are not yet implemented, so a key replacement invalidates outstanding tokens.

## Audit evidence

Audit events record actor, action, resource reference, event time, outcome, request correlation ID and safe metadata. Events are SHA-256 hash-chained per institution using sorted-key, compact UTF-8 JSON serialization. New events use serialization version 2; integrity checking also recognizes the existing legacy import chain format. The chain detects accidental or unauthorized edits when an earlier trusted hash is retained. It is not absolute immutability: a database administrator able to rewrite every event and hash can recompute the chain. Export/verification/review/consent activity is audited; audit data itself is institution-scoped.

## Threat model and controls

| Threat | Control | Remaining limit |
|---|---|---|
| Unauthorized claim disclosure | Role policy + server-side verifier grant + exact consent scope | Compromised authorized verifier account remains a risk |
| Consent withdrawal after credential issue | Revoke matching unexpired credential rows; online verifier checks revocation | Offline signature-only checks cannot learn revocations |
| Credential alteration/replay | Ed25519 signature, exact audience, short expiry, opaque JTI and online revocation lookup | Signing-key compromise permits forged credentials until key replacement |
| Cross-tenant access | Existing institution-scoped policy and student ownership check | Requires all future record routes to use the same policy discipline |
| Personal data in audit | Safe metadata allowlist; no request payload or free text | Resource UUIDs and actor IDs remain personal-data-adjacent references |
| Audit history rewriting | Per-institution canonical hash chain | Not WORM storage; privileged full-database rewrite is detectable only with trusted external checkpoints |

## Retention assumptions

No statutory retention schedule is configured by this prototype. Audit, consent and issued-credential records are retained in the application database until an institution-approved retention/deletion policy is set. Credentials expire after five minutes; revocation records must remain until expiry plus operational clock skew. Production deployment must define a lawful retention schedule and protected backups before using real records.

## API and integration boundaries

- `POST /api/v1/consents`: student grants a verifier a purpose and claims for an enrolment.
- `POST /api/v1/consents/{consent_id}/revoke`: student withdraws that grant and revokes outstanding credentials.
- `POST /api/v1/verification/credentials`: an authorized external verifier requests an audience-bound signed record check.
- `POST /api/v1/verification/credentials/verify`: checks a signed credential online, including its revocation record.
- `POST /api/v1/verification/grants` and `/api/v1/verification/grants/{grant_id}/revoke`: regulator-admin permission changes, both audited.
- No official external identity or government integration exists. Do not describe these record checks as official verification.
