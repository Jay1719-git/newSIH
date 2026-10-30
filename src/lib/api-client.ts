import { getInMemoryAccessToken, setInMemoryAccessToken } from './auth';
import type {
  InstitutionSummary,
  StudentBatch,
  StudentRecord,
  ConflictCase,
  AttestationRecord,
  AuditEvent,
  UserRole,
} from './weaveEngine';
import type { DemoAccount } from './syntheticSeed';

const configuredBaseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const API_BASE_PATH = `${configuredBaseUrl}/api/v1`;
const mockApiMode = import.meta.env.VITE_API_MODE !== 'live';

type BackendDuplicateCase = {
  case_id: string;
  match_type: 'EXACT_WITHIN_INSTITUTION' | 'POTENTIAL_WITHIN_INSTITUTION' | 'POTENTIAL_CROSS_INSTITUTION';
  confidence_band: 'HIGH' | 'MEDIUM';
  masked_fields: Array<{
    institution_id: string;
    institution_name: string | null;
    student_reference: string | null;
    name: string | null;
    apaar: string | null;
  }>;
  explanation: string;
  reason_codes: string[];
  review_status: string;
  outcome: string | null;
  decision_history: Array<{ outcome: string; reviewer_user_id: string; reviewed_at: string }>;
  created_at: string;
};

function mapBackendDuplicate(item: BackendDuplicateCase): ConflictCase {
  const first = item.masked_fields[0];
  const second = item.masked_fields[1];
  const status: ConflictCase['status'] = item.review_status === 'OPEN' || item.review_status === 'INFO_REQUESTED'
    ? item.review_status
    : 'RESOLVED';
  return {
    id: item.case_id,
    apaar_masked: first?.apaar || second?.apaar || 'NOT PROVIDED',
    apaar_hash: '',
    student_name: first?.name || 'Masked record',
    primary_institution_id: first?.institution_id || '',
    primary_institution_name: first?.institution_name || 'Institution record',
    primary_program_code: '',
    competing_institution_id: second?.institution_id || '',
    competing_institution_name: second?.institution_name || 'Institution record',
    competing_program_code: '',
    enrollment_year: 0,
    academic_year_overlap: '',
    conflict_type: item.match_type !== 'POTENTIAL_CROSS_INSTITUTION'
      ? 'INTRA_BATCH_DUPLICATE'
      : 'CROSS_INSTITUTION_DUPLICATE',
    match_evidence: [item.explanation, ...item.reason_codes],
    severity: item.confidence_band,
    status,
    assigned_reviewer: '',
    resolution_action: item.outcome as ConflictCase['resolution_action'],
    decision_history: item.decision_history.map((entry, index) => ({
      id: `${item.case_id}-${index}`,
      action: entry.outcome,
      actor_email: '',
      actor_role: '',
      notes: '',
      timestamp: entry.reviewed_at,
    })),
    detected_at: item.created_at,
  };
}

// API records intentionally omit the engine-only HMAC digest. The frontend's
// local synthetic engine model remains unchanged and must never be sent by the API.
export type ApiStudentRecord = Omit<StudentRecord, 'apaar_hash' | 'validation_results'> & {
  apaar_status: 'NOT_PROVIDED' | 'FORMAT_VALID' | 'FORMAT_INVALID';
  row_status: 'READY' | 'WARNING' | 'REVIEW_REQUIRED' | 'REJECTED' | 'COMMITTED';
  admission_date: string | null;
  admission_status: 'ADMITTED' | 'WITHDRAWN' | 'PENDING_REVIEW';
  seat_category_code: string | null;
  supernumerary_seat: boolean;
  nri_status: boolean;
  oci_status: boolean;
  foreign_national_status: boolean;
  validation_results: Array<{
    rule_code: string;
    stu_code: string;
    rule_name: string;
    outcome: 'PASS' | 'WARN' | 'REVIEW' | 'FAIL';
    reason: string;
    expected_value?: string;
    affected_field: string | null;
    actual_masked: string | null;
    remediation: string | null;
    ruleset_version: string;
  }>;
};

export class ApiClientError extends Error {
  code: string;
  requestId: string;
  status: number;
  details: Array<{ field?: string; reason: string }>;

  constructor(params: {
    code: string;
    message: string;
    requestId: string;
    status: number;
    details?: Array<{ field?: string; reason: string }>;
  }) {
    super(params.message);
    this.name = 'ApiClientError';
    this.code = params.code;
    this.requestId = params.requestId;
    this.status = params.status;
    this.details = params.details || [];
  }
}

async function requestWithRefresh<T>(
  endpoint: string,
  options: RequestInit = {},
  hasRetried = false
): Promise<T> {
  const token = getInMemoryAccessToken();
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_PATH}${endpoint}`, {
    ...options,
    headers,
  });

  // Refresh-once behavior for 401 responses (no infinite loop)
  if (response.status === 401 && !hasRetried && !endpoint.startsWith('/auth/')) {
    const refreshRes = await fetch(`${API_BASE_PATH}/auth/refresh`, {
      method: 'POST',
      credentials: 'same-origin',
    });
    if (refreshRes.ok) {
      const refreshData = await refreshRes.json();
      if (refreshData?.access_token) {
        setInMemoryAccessToken(refreshData.access_token);
        return requestWithRefresh<T>(endpoint, options, true);
      }
    }
    setInMemoryAccessToken(null);
    window.dispatchEvent(new Event('weave:session-expired'));
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const errObj = data?.error || {};
    throw new ApiClientError({
      code: errObj.code || `HTTP_${response.status}`,
      message: errObj.message || `Request failed with status ${response.status}.`,
      requestId: errObj.request_id || 'req_unknown',
      status: response.status,
      details: errObj.details || [],
    });
  }

  return data as T;
}

export const weaveQueryKeys = {
  institutions: (role: UserRole, institutionId?: string) =>
    ['weave', 'institutions', role, institutionId || 'all'] as const,
  validationResults: (role: UserRole, institutionId?: string) =>
    ['weave', 'validation-results', role, institutionId || 'all'] as const,
  batchDetail: (batchId: string) => ['weave', 'batch', batchId] as const,
  conflicts: (role: UserRole, institutionId?: string) =>
    ['weave', 'conflicts', role, institutionId || 'all'] as const,
  attestations: (role: UserRole, institutionId?: string) =>
    ['weave', 'attestations', role, institutionId || 'all'] as const,
  auditEvents: (role: UserRole, institutionId?: string) =>
    ['weave', 'audit-events', role, institutionId || 'all'] as const,
  verifyToken: (token: string) => ['weave', 'verify-token', token] as const,
};

export const weaveApiClient = {
  login: (email: string, password: string) =>
    requestWithRefresh<{
      environment: string;
      access_token: string;
      expires_in: number;
      user: DemoAccount;
    }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  getInstitutionsOverview: (role: UserRole, institutionId?: string) =>
    requestWithRefresh<{
      environment: string;
      active_institution_id: string;
      role: UserRole;
      institutions: InstitutionSummary[];
      all_institutions: InstitutionSummary[];
    }>(mockApiMode
      ? `/institutions/me?role=${encodeURIComponent(role)}&institution_id=${encodeURIComponent(
          institutionId || 'INST-KKR-101'
        )}`
      : '/institutions/me'),

  getValidationResults: (role: UserRole, institutionId?: string) =>
    requestWithRefresh<{
      environment: string;
      ruleset_version: string;
      batches: StudentBatch[];
      students: ApiStudentRecord[];
    }>(mockApiMode
      ? `/students/validation-results?role=${encodeURIComponent(
          role
        )}&institution_id=${encodeURIComponent(institutionId || 'INST-KKR-101')}`
      : '/students/validation-results'),

  getBatchDetail: (batchId: string) =>
    requestWithRefresh<{
      environment: string;
      ruleset_version: string;
      batch: StudentBatch;
      records: ApiStudentRecord[];
    }>(`/students/batches/${encodeURIComponent(batchId)}`),

  uploadBatch: (params: {
    institution_id: string;
    filename: string;
    csv_content: string;
    actor_role: UserRole;
    actor_email: string;
  }) =>
    requestWithRefresh<{
      environment: string;
      ruleset_version: string;
      batch: StudentBatch;
      records: ApiStudentRecord[];
      conflicts_created: ConflictCase[];
      review_cases_created: string[];
      audit_event: AuditEvent | null;
      idempotent_replay: boolean;
    }>('/students/batches/upload', {
      method: 'POST',
      body: JSON.stringify(
        mockApiMode
          ? params
          : { filename: params.filename, csv_content: params.csv_content }
      ),
    }),

  commitBatch: (params: {
    batchId: string;
    actor_role: UserRole;
    actor_email: string;
  }) =>
    requestWithRefresh<{
      environment: string;
      batch: StudentBatch;
      newly_committed: number;
      audit_event: AuditEvent | null;
    }>(`/students/batches/${encodeURIComponent(params.batchId)}/commit`, {
      method: 'POST',
      body: JSON.stringify(
        mockApiMode
          ? { actor_role: params.actor_role, actor_email: params.actor_email }
          : {}
      ),
    }),

  getConflicts: async (role: UserRole, institutionId?: string) => {
      if (mockApiMode) {
        return requestWithRefresh<{
          environment: string;
          conflicts: ConflictCase[];
        }>(`/conflicts?role=${encodeURIComponent(role)}&institution_id=${encodeURIComponent(
          institutionId || 'INST-KKR-101'
        )}`);
      }
      const result = await requestWithRefresh<{ environment: string; cases: BackendDuplicateCase[] }>(
        '/students/duplicates'
      );
      return { environment: result.environment, conflicts: result.cases.map(mapBackendDuplicate) };
    },

  resolveConflict: async (params: {
    caseId: string;
    resolution_action: string;
    resolution_notes: string;
    actor_role: UserRole;
    actor_email: string;
  }) => {
    if (mockApiMode) {
      return requestWithRefresh<{
        conflict: ConflictCase;
        audit_event: AuditEvent;
      }>(`/conflicts/${encodeURIComponent(params.caseId)}/resolve`, {
        method: 'POST',
        body: JSON.stringify(params),
      });
    }
    const outcomeByAction: Record<string, string> = {
      CONFIRM_DUPLICATE: 'CONFIRMED_DUPLICATE',
      NOT_A_DUPLICATE: 'DISTINCT_STUDENTS',
      REQUEST_INFO: 'INSUFFICIENT_EVIDENCE',
      CONFIRMED_DUPLICATE: 'CONFIRMED_DUPLICATE',
      DISTINCT_STUDENTS: 'DISTINCT_STUDENTS',
      INSUFFICIENT_EVIDENCE: 'INSUFFICIENT_EVIDENCE',
      ESCALATED: 'ESCALATED',
    };
    const updated = await requestWithRefresh<BackendDuplicateCase>(
      `/students/duplicates/${encodeURIComponent(params.caseId)}/decisions`, {
      method: 'POST',
      body: JSON.stringify({ outcome: outcomeByAction[params.resolution_action] }),
    });
    return { conflict: mapBackendDuplicate(updated), audit_event: null };
  },

  scanDuplicates: () =>
    requestWithRefresh<{
      environment: string;
      candidates_examined: number;
      cases_created: number;
      cases_rescanned: number;
    }>('/students/duplicates/scan', { method: 'POST' }),

  getAttestations: (role: UserRole, institutionId?: string) =>
    requestWithRefresh<{
      environment: string;
      attestations: AttestationRecord[];
    }>(
      `/attestations?role=${encodeURIComponent(role)}&institution_id=${encodeURIComponent(
        institutionId || 'INST-KKR-101'
      )}`
    ),

  issueAttestation: (params: {
    student_record_id: string;
    purpose: string;
    validity_days: number;
    actor_role: UserRole;
    actor_email: string;
  }) =>
    requestWithRefresh<{
      attestation: AttestationRecord;
      audit_event: AuditEvent;
    }>('/attestations', {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  revokeAttestation: (params: {
    id: string;
    reason: string;
    actor_role: UserRole;
    actor_email: string;
  }) =>
    requestWithRefresh<{
      attestation: AttestationRecord;
      audit_event: AuditEvent;
    }>(`/attestations/${encodeURIComponent(params.id)}/revoke`, {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  verifyTokenPublic: (token: string) =>
    requestWithRefresh<{
      environment: string;
      disclaimer: string;
      attestation: {
        id: string;
        token: string;
        issuer: string;
        institution_name: string;
        institution_id: string;
        student_ref: string;
        apaar_masked: string;
        program_code: string;
        enrollment_year: number;
        purpose: string;
        consent_id: string;
        issued_at: string;
        expires_at: string;
        status: 'ACTIVE' | 'REVOKED' | 'EXPIRED';
        revocation_reason?: string;
        revoked_at?: string;
        ed25519_key_id: string;
        ed25519_signature: string;
      };
      verification: {
        valid: boolean;
        signature_match: boolean;
        not_revoked: boolean;
        not_expired: boolean;
        status_code: string;
        reason: string;
      };
    }>(`/verify/${encodeURIComponent(token)}`),

  getAuditEvents: (role: UserRole, institutionId?: string) =>
    requestWithRefresh<{
      environment: string;
      chain_integrity: {
        intact: boolean;
        checkedCount: number;
        brokenAtEventId?: string;
      };
      events: AuditEvent[];
    }>(
      `/audit-events?role=${encodeURIComponent(role)}&institution_id=${encodeURIComponent(
        institutionId || 'INST-KKR-101'
      )}`
    ),

  queryAssistant: (params: {
    prompt: string;
    role: UserRole;
    institution_id?: string;
  }) =>
    requestWithRefresh<{
      environment: string;
      advisory_only: boolean;
      facts: string[];
      suggestions: string[];
      uncertainty: string;
      sources: Array<{ label: string; route: string }>;
    }>('/assistant/query', {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  chatWithAssistant: (params: {
    messages: Array<{ role: 'user' | 'model'; text: string }>;
    model: 'gemini-4-argon' | 'gemini-3.8-flash' | 'gemini-3.1-flash-lite';
    role: UserRole;
    institution_id?: string;
  }) =>
    requestWithRefresh<{
      environment: string;
      advisory_only: boolean;
      model_used: string;
      requested_model: string;
      reply: string;
      sources: Array<{ label: string; route: string }>;
    }>('/assistant/chat', {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  transcribeAudio: (params: {
    audioBase64: string;
    mimeType: string;
    samplePromptHint?: string;
  }) =>
    requestWithRefresh<{
      environment: string;
      model: string;
      transcript: string;
    }>('/assistant/transcribe', {
      method: 'POST',
      body: JSON.stringify(params),
    }),
};

