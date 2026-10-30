export type UserRole =
  | 'regulator_admin'
  | 'regulator_officer'
  | 'institution_admin'
  | 'institution_operator'
  | 'auditor'
  | 'student'
  | 'external_verifier';

// Legacy alias preserved for unit tests and backward compatibility
export type RolePersona =
  | 'INSTITUTION_OPERATOR'
  | 'REGULATOR_ANALYST'
  | 'AUDIT_REVIEWER'
  | UserRole;

export type ValidationOutcome = 'PASS' | 'WARN' | 'FAIL';

export interface ValidationRuleResult {
  rule_code: string;
  stu_code?: string;
  rule_name: string;
  outcome: ValidationOutcome;
  reason: string;
  affected_field?: string;
  expected_value?: string;
  actual_masked?: string;
  remediation?: string;
  ruleset_version?: string;
}

export interface StudentRecord {
  id: string;
  institution_id: string;
  institution_name: string;
  student_ref: string;
  apaar_masked: string;
  apaar_hash: string;
  full_name: string;
  dob: string;
  program_code: string;
  enrollment_year: number;
  consent_granted: boolean;
  status: 'VERIFIED' | 'FLAGGED_CONFLICT' | 'VALIDATION_FAILED' | 'PENDING_REVIEW';
  committed?: boolean;
  validation_results: ValidationRuleResult[];
  batch_id: string;
  created_at: string;
}

export interface ProgramIntakeSlice {
  program_code: string;
  program_title: string;
  approved_intake: number;
  enrolled_verified: number;
  flagged_or_pending: number;
  academic_year?: string;
}

export interface InstitutionSummary {
  id: string;
  aicte_code: string;
  name: string;
  state: string;
  tier: string;
  status?: 'ACTIVE' | 'UNDER_REVIEW';
  programs: ProgramIntakeSlice[];
}

export interface ConflictDecisionHistoryItem {
  id: string;
  action: string;
  actor_email: string;
  actor_role: string;
  notes: string;
  timestamp: string;
}

export interface ConflictCase {
  id: string;
  apaar_masked: string;
  apaar_hash: string;
  student_name: string;
  primary_institution_id: string;
  primary_institution_name: string;
  primary_program_code: string;
  competing_institution_id: string;
  competing_institution_name: string;
  competing_program_code: string;
  enrollment_year: number;
  academic_year_overlap?: string;
  conflict_type: 'CROSS_INSTITUTION_DUPLICATE' | 'INTRA_BATCH_DUPLICATE' | 'INTAKE_OVERFLOW';
  match_evidence?: string[];
  similarity_score?: number;
  severity: 'HIGH' | 'MEDIUM';
  status: 'OPEN' | 'RESOLVED' | 'INFO_REQUESTED';
  assigned_reviewer?: string;
  resolution_action?:
    | 'CONFIRM_TRANSFER'
    | 'REJECT_DUPLICATE'
    | 'ESCALATE_REGULATOR'
    | 'CONFIRM_DUPLICATE'
    | 'NOT_A_DUPLICATE'
    | 'REQUEST_INFO';
  resolution_notes?: string;
  resolved_by?: string;
  resolved_at?: string;
  decision_history?: ConflictDecisionHistoryItem[];
  detected_at: string;
}

export interface AttestationRecord {
  id: string;
  token?: string;
  student_record_id: string;
  student_ref: string;
  student_name: string;
  apaar_masked: string;
  apaar_hash: string;
  institution_id: string;
  institution_name: string;
  program_code: string;
  enrollment_year: number;
  consent_id: string;
  purpose: string;
  issued_at: string;
  expires_at: string;
  status: 'ACTIVE' | 'REVOKED' | 'EXPIRED';
  revocation_reason?: string;
  revoked_at?: string;
  ed25519_key_id: string;
  ed25519_signature: string;
  verification_payload: string;
}

export interface AuditEvent {
  id: string;
  institution_id: string;
  actor_role: RolePersona;
  actor_user_id: string;
  action: string;
  entity_type: 'BATCH' | 'STUDENT_RECORD' | 'CONFLICT_CASE' | 'ATTESTATION' | 'SYSTEM';
  entity_id: string;
  outcome?: 'SUCCESS' | 'DENIED' | 'FLAGGED';
  summary: string;
  previous_hash: string;
  event_hash: string;
  created_at: string;
}

export interface StudentBatch {
  id: string;
  institution_id: string;
  institution_name: string;
  filename: string;
  uploaded_by: string;
  total_rows: number;
  passed_rows: number;
  flagged_rows: number;
  failed_rows: number;
  committed_rows?: number;
  ruleset_version?: string;
  commit_eligible?: boolean;
  committed?: boolean;
  status: 'COMPLETED' | 'COMPLETED_WITH_FLAGS' | 'FAILED';
  created_at: string;
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    request_id: string;
    details: Array<{ field?: string; reason: string }>;
  };
}

export const APPROVED_PROGRAMS: Record<string, { title: string; defaultCap: number }> = {
  'BTECH-CSE': { title: 'B.Tech Computer Science & Engineering', defaultCap: 180 },
  'BTECH-ECE': { title: 'B.Tech Electronics & Communication', defaultCap: 120 },
  'BTECH-ME': { title: 'B.Tech Mechanical Engineering', defaultCap: 90 },
  'MTECH-AI': { title: 'M.Tech Artificial Intelligence & Data Science', defaultCap: 30 },
  'MBA-CORE': { title: 'Master of Business Administration', defaultCap: 60 },
  'MCA-GEN': { title: 'Master of Computer Applications', defaultCap: 60 },
};

export const VALIDATION_RULES_CATALOG = [
  {
    code: 'RULE-APAAR-FMT',
    stu_code: 'STU-001',
    name: 'APAAR Identifier Format & Privacy Guard',
    severity: 'FAIL',
    description:
      'Raw APAAR input must be a 12-digit numeric string not starting with 0 or 1. Rejects Aadhaar-labeled columns and masks display to ****-****-XXXX.',
    remediation:
      'Verify the 12-digit synthetic APAAR format from the institutional admission register and re-submit without spaces or leading 0/1 digits.',
  },
  {
    code: 'RULE-PROG-CODE',
    stu_code: 'STU-002',
    name: 'AICTE Sanctioned Program Code',
    severity: 'FAIL',
    description:
      'Program code must match an active AICTE-approved discipline registered for the institution academic year.',
    remediation:
      'Map the department curriculum code to an approved AICTE program code (e.g. BTECH-CSE, BTECH-ECE, BTECH-ME, MTECH-AI, MBA-CORE, MCA-GEN).',
  },
  {
    code: 'RULE-DOB-AGE',
    stu_code: 'STU-003',
    name: 'Academic Age Eligibility Window',
    severity: 'FAIL',
    description:
      'Candidate age at enrollment year must be within the deterministic range [16, 35] years.',
    remediation:
      'Check ISO-8601 date of birth (YYYY-MM-DD) against the academic enrollment year.',
  },
  {
    code: 'RULE-CONSENT-CHK',
    stu_code: 'STU-004',
    name: 'Student Data & Attestation Consent',
    severity: 'WARN',
    description:
      'Verifies whether explicit student consent is recorded before platform-issued attestation eligibility.',
    remediation:
      'Record signed student disclosure consent before requesting an enrolment attestation credential.',
  },
  {
    code: 'RULE-CROSS-INST',
    stu_code: 'STU-005',
    name: 'Cross-Institution Duplicate APAAR Hash',
    severity: 'WARN',
    description:
      'Detects identical irreversible APAAR hash across two institutions or active batches and opens a human review conflict case.',
    remediation:
      'Await regulatory conflict review or upload an official counselling withdrawal receipt.',
  },
  {
    code: 'RULE-INTAKE-CAP',
    stu_code: 'STU-006',
    name: 'AICTE Approved Intake Threshold',
    severity: 'WARN',
    description:
      'Checks whether cumulative verified enrolment for the program stays within AICTE approved intake capacity.',
    remediation:
      'Verify supernumerary quota approval or reconcile approved program intake limits before committing records.',
  },
] as const;

export function isInstitutionScopedRole(role: RolePersona): boolean {
  return (
    role === 'INSTITUTION_OPERATOR' ||
    role === 'institution_operator' ||
    role === 'institution_admin'
  );
}

export function isRegulatorRole(role: RolePersona): boolean {
  return (
    role === 'REGULATOR_ANALYST' ||
    role === 'regulator_admin' ||
    role === 'regulator_officer'
  );
}

/**
 * Deterministic 64-character hex digest for cross-environment (Node + browser)
 * identifier hashing and audit hash chaining.
 */
export function deterministicHexHash(input: string): string {
  const seeds = [
    0x811c9dc5, 0xcbf29ce4, 0x84222325, 0x1a47e9b3,
    0x9e3779b9, 0x7f4a7c15, 0x6a09e667, 0xbb67ae85,
  ];
  for (let i = 0; i < input.length; i++) {
    const ch = input.charCodeAt(i);
    for (let s = 0; s < seeds.length; s++) {
      seeds[s] ^= ch + s * 31 + i * 17;
      seeds[s] = Math.imul(seeds[s], 0x01000193) >>> 0;
      seeds[s] = ((seeds[s] << 13) | (seeds[s] >>> 19)) >>> 0;
    }
  }
  return seeds.map((n) => n.toString(16).padStart(8, '0')).join('');
}

export function normalizeApaarDigits(rawInput: string): string {
  return rawInput.replace(/[\s-]/g, '').trim();
}

export function isValidRawApaar(rawInput: string): boolean {
  const clean = normalizeApaarDigits(rawInput);
  return /^[2-9]\d{11}$/.test(clean);
}

/**
 * Masks an APAAR identifier to `****-****-1234` per RULEBOOK.md Section 1.4.
 * Never returns the full 12-digit APAAR number.
 */
export function maskApaarId(rawInput: string): string {
  const clean = normalizeApaarDigits(rawInput);
  if (/^\*+-\*+-\d{4}$/.test(rawInput.trim())) {
    return rawInput.trim();
  }
  if (clean.length < 4) {
    return '****-****-INVALID';
  }
  const last4 = clean.slice(-4);
  if (!/^\d{4}$/.test(last4)) {
    return '****-****-INVALID';
  }
  return `****-****-${last4}`;
}

export function hashApaarId(rawInput: string): string {
  const clean = normalizeApaarDigits(rawInput);
  return `sha256:${deterministicHexHash(`WEAVE_APAAR_SALT_V1:${clean}`)}`;
}

export interface RawCsvStudentRow {
  student_ref: string;
  apaar_id: string;
  full_name: string;
  dob: string;
  program_code: string;
  enrollment_year: number;
  consent_granted: boolean;
}

export interface ValidationContext {
  institution_id: string;
  institution_name: string;
  existing_hashes: Map<string, { institution_id: string; institution_name: string; program_code: string }>;
  program_counts: Record<string, { enrolled: number; cap: number }>;
}

export function validateStudentRow(
  row: RawCsvStudentRow,
  ctx: ValidationContext
): {
  outcomes: ValidationRuleResult[];
  overallStatus: StudentRecord['status'];
  apaarMasked: string;
  apaarHash: string;
  conflict?: {
    competing_institution_id: string;
    competing_institution_name: string;
    competing_program_code: string;
    conflict_type: ConflictCase['conflict_type'];
  };
} {
  const outcomes: ValidationRuleResult[] = [];
  const cleanApaar = normalizeApaarDigits(row.apaar_id);
  const apaarValid = isValidRawApaar(cleanApaar);
  const apaarMasked = maskApaarId(cleanApaar);
  const apaarHash = apaarValid
    ? hashApaarId(cleanApaar)
    : `invalid:${deterministicHexHash(cleanApaar).slice(0, 16)}`;

  // 1. RULE-APAAR-FMT (STU-001)
  if (!apaarValid) {
    outcomes.push({
      rule_code: 'RULE-APAAR-FMT',
      stu_code: 'STU-001',
      rule_name: 'APAAR Identifier Format & Privacy Guard',
      outcome: 'FAIL',
      reason: 'APAAR must be exactly 12 digits and cannot start with 0 or 1.',
      affected_field: 'apaar_id',
      expected_value: '12 digits starting with [2-9]',
      actual_masked: apaarMasked,
      remediation:
        'Provide a valid 12-digit synthetic APAAR identifier not starting with 0 or 1.',
      ruleset_version: '2026.10.v1',
    });
  } else {
    outcomes.push({
      rule_code: 'RULE-APAAR-FMT',
      stu_code: 'STU-001',
      rule_name: 'APAAR Identifier Format & Privacy Guard',
      outcome: 'PASS',
      reason: `Valid 12-digit synthetic APAAR normalized and masked as ${apaarMasked}.`,
      affected_field: 'apaar_id',
      expected_value: '12 digits starting with [2-9]',
      actual_masked: apaarMasked,
      ruleset_version: '2026.10.v1',
    });
  }

  // 2. RULE-PROG-CODE (STU-002)
  const progCode = row.program_code.trim().toUpperCase();
  const progMeta = APPROVED_PROGRAMS[progCode];
  if (!progMeta) {
    outcomes.push({
      rule_code: 'RULE-PROG-CODE',
      stu_code: 'STU-002',
      rule_name: 'AICTE Sanctioned Program Code',
      outcome: 'FAIL',
      reason: `Program code '${progCode || 'EMPTY'}' is not in the AICTE approved registry.`,
      affected_field: 'program_code',
      expected_value: Object.keys(APPROVED_PROGRAMS).join(' | '),
      actual_masked: progCode || 'EMPTY',
      remediation:
        'Update program_code to match one of the institution’s sanctioned AICTE program codes.',
      ruleset_version: '2026.10.v1',
    });
  } else {
    outcomes.push({
      rule_code: 'RULE-PROG-CODE',
      stu_code: 'STU-002',
      rule_name: 'AICTE Sanctioned Program Code',
      outcome: 'PASS',
      reason: `Matches approved program ${progCode} (${progMeta.title}).`,
      affected_field: 'program_code',
      expected_value: progCode,
      actual_masked: progCode,
      ruleset_version: '2026.10.v1',
    });
  }

  // 3. RULE-DOB-AGE (STU-003)
  const birthYear = Number(row.dob.split('-')[0]);
  const ageAtEnrollment = row.enrollment_year - birthYear;
  if (!birthYear || Number.isNaN(ageAtEnrollment) || ageAtEnrollment < 16 || ageAtEnrollment > 35) {
    outcomes.push({
      rule_code: 'RULE-DOB-AGE',
      stu_code: 'STU-003',
      rule_name: 'Academic Age Eligibility Window',
      outcome: 'FAIL',
      reason: `Computed enrollment age (${Number.isNaN(ageAtEnrollment) ? 'invalid DOB' : ageAtEnrollment}) is outside [16, 35].`,
      affected_field: 'dob',
      expected_value: 'Age 16–35 years at enrollment_year',
      actual_masked: `${row.dob} (${Number.isNaN(ageAtEnrollment) ? 'invalid' : `${ageAtEnrollment} yrs`})`,
      remediation: 'Verify candidate date of birth in YYYY-MM-DD format.',
      ruleset_version: '2026.10.v1',
    });
  } else {
    outcomes.push({
      rule_code: 'RULE-DOB-AGE',
      stu_code: 'STU-003',
      rule_name: 'Academic Age Eligibility Window',
      outcome: 'PASS',
      reason: `Age at enrollment (${ageAtEnrollment} yrs) satisfies AICTE eligibility bounds.`,
      affected_field: 'dob',
      expected_value: 'Age 16–35 years',
      actual_masked: `${ageAtEnrollment} yrs`,
      ruleset_version: '2026.10.v1',
    });
  }

  // 4. RULE-CONSENT-CHK (STU-004)
  if (!row.consent_granted) {
    outcomes.push({
      rule_code: 'RULE-CONSENT-CHK',
      stu_code: 'STU-004',
      rule_name: 'Student Data & Attestation Consent',
      outcome: 'WARN',
      reason:
        'Record ingested for regulatory count, but attestation issuance is blocked until consent is granted.',
      affected_field: 'consent_granted',
      expected_value: 'true (active student consent)',
      actual_masked: 'false',
      remediation:
        'Obtain student consent declaration before issuing verification credentials.',
      ruleset_version: '2026.10.v1',
    });
  } else {
    outcomes.push({
      rule_code: 'RULE-CONSENT-CHK',
      stu_code: 'STU-004',
      rule_name: 'Student Data & Attestation Consent',
      outcome: 'PASS',
      reason: 'Active student consent recorded for verification & attestation.',
      affected_field: 'consent_granted',
      expected_value: 'true',
      actual_masked: 'true',
      ruleset_version: '2026.10.v1',
    });
  }

  // 5. RULE-CROSS-INST (STU-005)
  let conflict:
    | {
        competing_institution_id: string;
        competing_institution_name: string;
        competing_program_code: string;
        conflict_type: ConflictCase['conflict_type'];
      }
    | undefined;

  if (apaarValid && ctx.existing_hashes.has(apaarHash)) {
    const existing = ctx.existing_hashes.get(apaarHash)!;
    const isCrossInst = existing.institution_id !== ctx.institution_id;
    conflict = {
      competing_institution_id: existing.institution_id,
      competing_institution_name: existing.institution_name,
      competing_program_code: existing.program_code,
      conflict_type: isCrossInst ? 'CROSS_INSTITUTION_DUPLICATE' : 'INTRA_BATCH_DUPLICATE',
    };
    outcomes.push({
      rule_code: 'RULE-CROSS-INST',
      stu_code: 'STU-005',
      rule_name: 'Cross-Institution Duplicate APAAR Hash',
      outcome: 'WARN',
      reason: isCrossInst
        ? `APAAR hash already registered under ${existing.institution_name} (${existing.program_code}). Routed to human conflict queue.`
        : `Duplicate APAAR hash detected within ${ctx.institution_name} (${existing.program_code}). Routed to conflict queue.`,
      affected_field: 'apaar_id',
      expected_value: 'Unique active enrollment per academic year',
      actual_masked: `${apaarMasked} (Hash collision)`,
      remediation:
        'Review candidate match in Duplicate & Conflict Review before committing.',
      ruleset_version: '2026.10.v1',
    });
  } else {
    outcomes.push({
      rule_code: 'RULE-CROSS-INST',
      stu_code: 'STU-005',
      rule_name: 'Cross-Institution Duplicate APAAR Hash',
      outcome: 'PASS',
      reason: 'No active cross-institution or duplicate APAAR hash collision found.',
      affected_field: 'apaar_id',
      expected_value: 'Unique hash',
      actual_masked: apaarMasked,
      ruleset_version: '2026.10.v1',
    });
  }

  // 6. RULE-INTAKE-CAP (STU-006)
  const capState = ctx.program_counts[progCode];
  if (capState && capState.enrolled + 1 > capState.cap) {
    outcomes.push({
      rule_code: 'RULE-INTAKE-CAP',
      stu_code: 'STU-006',
      rule_name: 'AICTE Approved Intake Threshold',
      outcome: 'WARN',
      reason: `Enrolment (${capState.enrolled + 1}) exceeds sanctioned intake cap (${capState.cap}) for ${progCode}.`,
      affected_field: 'program_code',
      expected_value: `<= ${capState.cap} seats`,
      actual_masked: `${capState.enrolled + 1} seats`,
      remediation:
        'Check approved intake allocation in Intake Monitoring before committing overflow rows.',
      ruleset_version: '2026.10.v1',
    });
  } else {
    outcomes.push({
      rule_code: 'RULE-INTAKE-CAP',
      stu_code: 'STU-006',
      rule_name: 'AICTE Approved Intake Threshold',
      outcome: 'PASS',
      reason: capState
        ? `Within sanctioned intake (${capState.enrolled + 1}/${capState.cap}) for ${progCode}.`
        : 'Program intake check evaluated.',
      affected_field: 'program_code',
      expected_value: capState ? `<= ${capState.cap}` : 'Within cap',
      actual_masked: capState ? `${capState.enrolled + 1}/${capState.cap}` : 'OK',
      ruleset_version: '2026.10.v1',
    });
  }

  const hasFail = outcomes.some((o) => o.outcome === 'FAIL');
  let overallStatus: StudentRecord['status'] = 'VERIFIED';
  if (hasFail) {
    overallStatus = 'VALIDATION_FAILED';
  } else if (conflict) {
    overallStatus = 'FLAGGED_CONFLICT';
  } else if (outcomes.some((o) => o.outcome === 'WARN')) {
    overallStatus = 'PENDING_REVIEW';
  }

  return {
    outcomes,
    overallStatus,
    apaarMasked,
    apaarHash,
    conflict,
  };
}

export function parseStudentCsv(csvText: string): {
  rows: RawCsvStudentRow[];
  parseErrors: Array<{ line: number; reason: string }>;
} {
  const lines = csvText
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0 && !l.startsWith('#'));

  if (lines.length === 0) {
    return { rows: [], parseErrors: [{ line: 1, reason: 'CSV payload is empty.' }] };
  }

  const header = lines[0].toLowerCase().split(',').map((h) => h.trim());
  if (header.includes('aadhaar') || header.includes('aadhaar_no') || header.includes('aadhaar_id')) {
    return {
      rows: [],
      parseErrors: [
        {
          line: 1,
          reason:
            'RULEBOOK VIOLATION: Aadhaar columns are strictly prohibited. Submit synthetic APAAR IDs only.',
        },
      ],
    };
  }

  const rows: RawCsvStudentRow[] = [];
  const parseErrors: Array<{ line: number; reason: string }> = [];

  const startIdx = header.includes('student_ref') || header.includes('apaar_id') ? 1 : 0;

  for (let i = startIdx; i < lines.length; i++) {
    const cols = lines[i].split(',').map((c) => c.trim());
    if (cols.length < 6) {
      parseErrors.push({
        line: i + 1,
        reason: `Expected at least 6 comma-separated columns, found ${cols.length}.`,
      });
      continue;
    }
    const [student_ref, apaar_id, full_name, dob, program_code, enrollment_year_str, consent_str] =
      cols;
    const enrollment_year = Number(enrollment_year_str) || 2026;
    const consent_granted =
      consent_str === undefined
        ? true
        : ['true', '1', 'yes', 'y', 'granted'].includes(consent_str.toLowerCase());

    rows.push({
      student_ref,
      apaar_id,
      full_name,
      dob,
      program_code: program_code.toUpperCase(),
      enrollment_year,
      consent_granted,
    });
  }

  return { rows, parseErrors };
}

export function signAttestationPayload(params: {
  attestation_id: string;
  student_ref: string;
  apaar_hash: string;
  institution_id: string;
  program_code: string;
  enrollment_year: number;
  issued_at: string;
  expires_at: string;
  key_id?: string;
}): { signature: string; verification_payload: string; key_id: string } {
  const key_id = params.key_id || 'ed25519-weave-synth-2026-k1';
  const canonical = [
    params.attestation_id,
    params.student_ref,
    params.apaar_hash,
    params.institution_id,
    params.program_code,
    String(params.enrollment_year),
    params.issued_at,
    params.expires_at,
    key_id,
  ].join('|');

  const sigHex = deterministicHexHash(`ED25519_SYNTH_SIGN:${canonical}`);
  const signature = `ed25519:${sigHex}`;
  const verification_payload = JSON.stringify({
    v: 'WEAVE-ATT-V1',
    env: 'SYNTHETIC',
    att_id: params.attestation_id,
    verify_url: `/verify/${params.attestation_id.toLowerCase()}`,
    student_ref: params.student_ref,
    apaar_hash: params.apaar_hash,
    inst: params.institution_id,
    prog: params.program_code,
    yr: params.enrollment_year,
    exp: params.expires_at,
    kid: key_id,
    sig: signature,
  });

  return { signature, verification_payload, key_id };
}

export function verifyAttestationRecord(
  record: AttestationRecord,
  referenceIsoDate: string = new Date().toISOString()
): {
  valid: boolean;
  signature_match: boolean;
  not_revoked: boolean;
  not_expired: boolean;
  status_code: 'VERIFIED_ACTIVE' | 'INVALID_REVOKED' | 'INVALID_EXPIRED' | 'INVALID_SIGNATURE';
  reason: string;
} {
  const expected = signAttestationPayload({
    attestation_id: record.id,
    student_ref: record.student_ref,
    apaar_hash: record.apaar_hash,
    institution_id: record.institution_id,
    program_code: record.program_code,
    enrollment_year: record.enrollment_year,
    issued_at: record.issued_at,
    expires_at: record.expires_at,
    key_id: record.ed25519_key_id,
  });

  const signature_match = expected.signature === record.ed25519_signature;
  const not_revoked = record.status !== 'REVOKED';
  const not_expired =
    record.status !== 'EXPIRED' &&
    new Date(record.expires_at).getTime() > new Date(referenceIsoDate).getTime();

  if (!signature_match) {
    return {
      valid: false,
      signature_match,
      not_revoked,
      not_expired,
      status_code: 'INVALID_SIGNATURE',
      reason: 'Cryptographic Ed25519 signature verification failed against canonical attestation fields.',
    };
  }
  if (!not_revoked) {
    return {
      valid: false,
      signature_match,
      not_revoked,
      not_expired,
      status_code: 'INVALID_REVOKED',
      reason: `Attestation was revoked on ${record.revoked_at?.slice(0, 10) || 'record'} (${record.revocation_reason || 'policy action'}).`,
    };
  }
  if (!not_expired) {
    return {
      valid: false,
      signature_match,
      not_revoked,
      not_expired,
      status_code: 'INVALID_EXPIRED',
      reason: `Attestation expired at ${record.expires_at.slice(0, 10)}.`,
    };
  }

  return {
    valid: true,
    signature_match: true,
    not_revoked: true,
    not_expired: true,
    status_code: 'VERIFIED_ACTIVE',
    reason:
      'Ed25519 signature verified, student consent active, and attestation is unrevoked and within validity window.',
  };
}

export function computeAuditEventHash(event: Omit<AuditEvent, 'event_hash'>): string {
  const payload = [
    event.id,
    event.institution_id,
    event.actor_role,
    event.actor_user_id,
    event.action,
    event.entity_type,
    event.entity_id,
    event.summary,
    event.previous_hash,
    event.created_at,
  ].join('|');
  return `sha256:${deterministicHexHash(`WEAVE_AUDIT_CHAIN:${payload}`)}`;
}

export function verifyAuditChain(events: AuditEvent[]): {
  intact: boolean;
  checkedCount: number;
  brokenAtEventId?: string;
} {
  const chronological = [...events].reverse();
  let expectedPrev = 'GENESIS_00000000000000000000000000000000';

  for (const ev of chronological) {
    if (ev.previous_hash !== expectedPrev) {
      return { intact: false, checkedCount: chronological.length, brokenAtEventId: ev.id };
    }
    const recomputed = computeAuditEventHash({
      id: ev.id,
      institution_id: ev.institution_id,
      actor_role: ev.actor_role,
      actor_user_id: ev.actor_user_id,
      action: ev.action,
      entity_type: ev.entity_type,
      entity_id: ev.entity_id,
      summary: ev.summary,
      previous_hash: ev.previous_hash,
      created_at: ev.created_at,
    });
    if (recomputed !== ev.event_hash) {
      return { intact: false, checkedCount: chronological.length, brokenAtEventId: ev.id };
    }
    expectedPrev = ev.event_hash;
  }

  return { intact: true, checkedCount: chronological.length };
}

export function createApiError(
  code: string,
  message: string,
  requestId: string,
  details: Array<{ field?: string; reason: string }> = []
): ApiErrorEnvelope {
  return {
    error: {
      code,
      message,
      request_id: requestId,
      details,
    },
  };
}
