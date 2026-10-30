# WEAVE API foundation

This is a local synthetic-data backend with provisioned local accounts and backend
authorization policies. It is not production-ready identity proofing or institutional
authorization and does not connect to APAAR, DigiLocker, or AICTE. Never submit real
student or Aadhaar data. No Aadhaar field is present in the schema.

## Windows PowerShell setup

Run these commands from the repository root (`WEAVE`). Install Python 3.12 and
Docker Desktop first.

```powershell
py -3.12 -m venv apps/api/.venv
& apps/api/.venv/Scripts/Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e "apps/api[dev]"
Copy-Item .env.example .env
```

The default environment template targets the loopback-only `weave_demo` database.
Replace the local placeholder password and generate a new random
`APAAR_HMAC_KEY`; do not reuse a key from another deployment. Keep
`VITE_API_MODE=mock` for fixture mode until FastAPI is running. Set it to `live`
only when using the same-origin root-server proxy described below.

Generate a local HMAC key and set its output as `APAAR_HMAC_KEY` in `.env`:

```powershell
$bytes = [byte[]]::new(32)
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$key = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
Write-Output $key
```

Keep `.env` private. Identity matching requires this key and never falls back to
an ordinary hash. Keep the key version alongside each digest and retain old key
material for a controlled re-key migration. Simply changing the key/version stops
matching old identity digests and idempotency fingerprints; the current single-key
configuration does not look up old versions. Do not rotate a live key without a
migration that re-keys stored synthetic digests and fingerprints. The upload
fingerprint is keyed and institution-scoped; it ignores filename and CSV column
order.

## Local accounts and authorization

There are no seeded credentials or hard-coded demo passwords. Create a local
synthetic account interactively after applying migrations:

```powershell
python -m app.cli create-user
python -m app.cli set-password
```

Passwords are stored as salted scrypt hashes. Login issues a random opaque bearer
token that expires after 15 minutes; only its digest is stored in PostgreSQL.
Refresh tokens are rotated in an HttpOnly, SameSite=Strict cookie with an 8-hour
lifetime. Revoke an active bearer session with `POST /api/v1/auth/logout`.
Retrieve the active account with `GET /api/v1/auth/me`. Provision verifier grants
through the local administrative command:

```powershell
python -m app.cli grant-verifier
```

The command requires an AICTE administrator approver and allows only
`enrolment_status`, `program_code`, `academic_year`, and `consent_status` claims
for up to 30 days. This grants no official verification connectivity.

Backend roles preserve the current frontend role names: `regulator_admin` maps to
AICTE administrator authority; `regulator_officer` maps to AICTE officer authority;
`institution_admin`, `institution_operator`, `auditor`, `student`, and
`external_verifier` are separately scoped. Institution and student scope comes
from the authenticated database account, never browser query/body fields. Student
accounts must be linked to their identity reference. Auditors are read-only and
tenant-scoped. External verifiers require an expiring grant with an exact purpose
and allowlisted claims. AICTE administrators can read authorized cross-institution
aggregates and investigate cases; officers have read/aggregate access only. Neither
AICTE role receives general student-record export access.

Login throttling is process-local and suitable only for a single-process synthetic
demo. Production requires a shared limiter, TLS, managed account provisioning,
operational key management, and security review before exposure. Configure explicit
CORS origins. Set `AUTH_COOKIE_SECURE=true` behind HTTPS; production settings reject
an insecure cookie configuration. The API does not allow credentialed cross-origin
requests; use a same-origin reverse proxy for the frontend and API.

Start PostgreSQL 16 bound to loopback:

```powershell
docker compose --env-file .env -f infra/compose.yaml up -d db
```

Apply the migration and start the loopback-only API:

```powershell
python -m alembic -c apps/api/alembic.ini upgrade head
python -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8000 --reload
```

Health checks: `http://127.0.0.1:8000/health` and
`http://127.0.0.1:8000/api/v1/health`. Both identify the environment as
`SYNTHETIC`; they do not claim external verification.

## Reproducible synthetic demonstration

After migrations, seed reference records and deterministic CSV files:

```powershell
python -m app.cli seed-demo
```

This command is limited to `APP_ENV=synthetic` and a loopback database named
`weave_demo`. It inserts two fictional institutions, one fictional programme and
academic year per institution, and approved total/category capacity. It writes
the CSV fixtures and `manifest.json` under `synthetic/generated/`; the generator
uses fixed contents and seed `26263`. It does not create accounts or passwords.
Use printed institution UUIDs with `create-user` to provision synthetic
institution admin/operator and regulator admin users, then `set-password` to set
local passwords.

`reset-demo` is destructive and additionally requires both a typed command
confirmation and `WEAVE_ALLOW_DEMO_RESET=I_UNDERSTAND`. It refuses non-synthetic,
non-loopback, or non-`weave_demo` databases and preserves Alembic history:

```powershell
$env:WEAVE_ALLOW_DEMO_RESET = 'I_UNDERSTAND'
python -m app.cli reset-demo --confirm-demo-reset RESET-WEAVE-DEMO
python -m app.cli seed-demo
Remove-Item Env:WEAVE_ALLOW_DEMO_RESET
```

For frontend live mode, set `VITE_API_MODE=live` and
`WEAVE_FASTAPI_URL=http://127.0.0.1:8000` in the root `.env`; keep
`VITE_API_BASE_URL` empty so login and refresh cookies use the root app's
same-origin proxy. Start FastAPI on port 8000 and run `npm run dev` from the
repository root. If live mode is enabled without an upstream, the Express API
returns a safe 503 and does not serve in-memory demo data.

## Student CSV ingestion (synthetic only)

The authenticated account's institution membership selects the tenant; the
legacy `institution_id`, `actor_role`, and `actor_email` request properties are
ignored for authorization. Upload remains JSON (`filename`, `csv_content`) for
compatibility with the existing web client. Required columns are
`student_ref,apaar_id,full_name,dob,program_code,enrollment_year,consent_granted`.
Optional columns are `admission_date,seat_category_code,supernumerary_seat,
nri_status,oci_status,foreign_national_status,admission_status`. The final
column is explicitly mapped to an academic year code or its configured start
year (for example `2026`); institution and programme/year association come from
database configuration. No seat pool is inferred from nationality or
supernumerary flags. APAAR is only format-checked, masked in responses, and
matched through a secret-keyed HMAC; absence alone is a warning and yields a
provisional identity reference.

Uploads are limited to 5 MiB, 10,000 data rows, and 16,384 characters per field.
Malformed file structure returns `MALFORMED_CSV`; valid CSV with invalid values
returns row findings. Identical canonical content for the same institution and
HMAC key version returns the prior batch (filename does not affect identity)
without another batch or upload audit event. Review-required and rejected rows
are never committed. Only `READY` and `WARNING` rows are eligible; commits lock
the configured programme/year and recheck approved category and total pools in
one transaction. Capacity conflict marks the whole attempted set for manual
review and commits no enrolments. Repeated commit returns zero newly committed.
Error reports mask APAAR and neutralize spreadsheet formulas.

The ingestion routes are `POST /api/v1/students/batches/upload`,
`GET /api/v1/students/batches/{batch_id}`,
`GET /api/v1/students/validation-results`,
`GET /api/v1/students/batches/{batch_id}/error-report`, and
`POST /api/v1/students/batches/{batch_id}/commit`. They use the existing bearer
authentication and institution policy layer. Demo account role or institution
metadata is not identity or authorization. The implementation does not connect
to official APAAR, DigiLocker, or AICTE services.

## Privacy-aware duplicate detection

`POST /api/v1/students/duplicates/scan` compares the authenticated institution's
completed imports with its own rows and committed counterpart rows. Regulator
administrators can run a global scan. `GET /api/v1/students/duplicates` returns
only cases involving the institution for institution roles; regulator officers
and administrators can read the queue. `POST
/api/v1/students/duplicates/{case_id}/decisions` is restricted to regulator
administrators and records one of `CONFIRMED_DUPLICATE`, `DISTINCT_STUDENTS`,
`INSUFFICIENT_EVIDENCE`, or `ESCALATED` in case history.

Exact APAAR comparison uses the identity references' keyed HMAC linkage. Secondary
matching blocks on a domain-separated HMAC of normalized date of birth and compares
normalized names in server memory using the configurable
`DUPLICATE_NAME_SIMILARITY_THRESHOLD` (default `0.88`). The normalization marker is
stored with each identity reference. Set `APAAR_HMAC_PREVIOUS_KEYS` to a JSON object
of retained version-to-base64-key entries during rotation; keep old keys available
until legacy references have been safely re-linked. No ordinary hash fallback is
used. Candidate explanations and reason codes are deterministic; each candidate
remains an investigation lead and requires a human outcome. API cases expose only
masked display fields and source institution references, never full APAAR IDs,
student names, birth dates, or another institution's student reference. Missing
APAAR is not itself a match signal. Gender and nationality are not used.

## Tests

From the repository root:

```powershell
python -m ruff format --check apps/api
python -m ruff check apps/api
python -m pytest apps/api/tests
```

Database tests require a separate disposable PostgreSQL database whose name ends
in `_test`; set `WEAVE_TEST_DATABASE_URL` to its URL. Tests refuse other database
names and apply/revert Alembic migrations there. Never point tests at a shared or
production database.

FastAPI exposes health, authentication, institution aggregates, student
ingestion/detail/validation/error export/commit, duplicate scan/review, scoped
consent, verifier grants, and short-lived audience-bound WEAVE record-check
credentials. It does not expose the legacy `/conflicts`, attestation registry,
`/audit-events`, public `/verify/:token`, or assistant endpoints used by some
mock-mode screens. The frontend explicitly reports these as unavailable in
live mode. Signed record checks are not official APAAR/DigiLocker/AICTE
verification. The Express prototype remains a fixture-only API in mock mode and
must never be used as an authentication authority.
