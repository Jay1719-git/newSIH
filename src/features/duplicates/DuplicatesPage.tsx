import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  CheckCircle2,
  Lock,
  GitCompare,
  Clock,
} from 'lucide-react';
import { useAuth } from '../../lib/auth';
import { weaveApiClient, weaveQueryKeys, ApiClientError } from '../../lib/api-client';
import { isInstitutionScopedRole, isRegulatorRole } from '../../lib/weaveEngine';

export const DuplicatesPage: React.FC = () => {
  const { user, switchRolePersona, apiMode } = useAuth();
  const queryClient = useQueryClient();
  const instScoped = isInstitutionScopedRole(user.role);
  const canScan = apiMode === 'live' && [
    'institution_admin',
    'institution_operator',
    'regulator_admin',
  ].includes(user.role);
  const canAdjudicate = apiMode === 'mock'
    ? isRegulatorRole(user.role)
    : user.role === 'regulator_admin';

  const [statusFilter, setStatusFilter] = useState<'ALL' | 'OPEN' | 'RESOLVED' | 'INFO_REQUESTED'>(
    'ALL'
  );
  const [selectedId, setSelectedId] = useState<string>('CNF-2026-019');
  const [decisionAction, setDecisionAction] = useState<
    | 'CONFIRM_DUPLICATE'
    | 'NOT_A_DUPLICATE'
    | 'REQUEST_INFO'
    | 'CONFIRMED_DUPLICATE'
    | 'DISTINCT_STUDENTS'
    | 'INSUFFICIENT_EVIDENCE'
    | 'ESCALATED'
  >('NOT_A_DUPLICATE');
  const [reasonNotes, setReasonNotes] = useState<string>('');
  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: weaveQueryKeys.conflicts(user.role, user.institution_id),
    queryFn: () => weaveApiClient.getConflicts(user.role, user.institution_id),
  });

  const conflicts = data?.conflicts || [];
  const filtered = conflicts.filter((c) =>
    statusFilter === 'ALL' ? true : c.status === statusFilter
  );
  const activeCase =
    filtered.find((c) => c.id === selectedId) || filtered[0] || null;

  const resolveMutation = useMutation({
    mutationFn: () => {
      if (!activeCase) throw new Error('No candidate selected.');
      return weaveApiClient.resolveConflict({
        caseId: activeCase.id,
        resolution_action: decisionAction,
        resolution_notes: reasonNotes,
        actor_role: user.role,
        actor_email: user.email,
      });
    },
    onSuccess: (res) => {
      setFeedback({
        type: 'success',
        text: res.audit_event
          ? `Recorded decision ${res.conflict.resolution_action} on ${res.conflict.id} and appended audit event ${res.audit_event.id}.`
          : `Recorded decision ${res.conflict.resolution_action} on ${res.conflict.id}.`,
      });
      setReasonNotes('');
      queryClient.invalidateQueries({ queryKey: ['weave'] });
    },
    onError: (err) => {
      if (err instanceof ApiClientError) {
        setFeedback({ type: 'error', text: `${err.message} (${err.code})` });
      } else {
        setFeedback({ type: 'error', text: 'Failed to submit review decision.' });
      }
    },
  });

  const scanMutation = useMutation({
    mutationFn: () => weaveApiClient.scanDuplicates(),
    onSuccess: (result) => {
      setFeedback({
        type: 'success',
        text: `Scanned ${result.candidates_examined} candidate pair(s); ${result.cases_created} new case(s), ${result.cases_rescanned} refreshed.`,
      });
      queryClient.invalidateQueries({ queryKey: weaveQueryKeys.conflicts(user.role, user.institution_id) });
    },
    onError: (err) => {
      setFeedback({
        type: 'error',
        text: err instanceof ApiClientError ? `${err.message} (${err.code})` : 'Duplicate scan failed.',
      });
    },
  });

  if (isLoading) {
    return (
      <div role="status" className="bg-white border border-[#DEDDD5] rounded-md p-6 animate-pulse h-64" />
    );
  }

  if (isError) {
    return (
      <div role="alert" className="bg-white border border-[#99322B] rounded-md p-6 text-xs text-[#99322B]">
        <p>{error instanceof Error ? error.message : 'Unable to load review cases.'}</p>
        <button type="button" onClick={() => refetch()} className="mt-3 underline font-medium">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Mandatory Non-Fraud & Permission Scope Notice */}
      <div className="p-4 bg-[#F0EFE9] border border-[#DEDDD5] rounded-md flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
        <div className="space-y-1">
          <div className="font-semibold text-[#20241F]">
            Adjudication Safeguard: A candidate hash match is not proof of fraud.
          </div>
          <p className="text-[#686B65]">
            WEAVE never automatically merges or deletes student records. Authorized officers must
            verify counselling withdrawal documentation and record a reason before confirming.
          </p>
        </div>

        {instScoped && apiMode === 'mock' && (
          <button
            type="button"
            onClick={() => switchRolePersona('regulator_officer')}
            className="px-3 py-1.5 text-xs font-medium text-white bg-[#244C3A] hover:bg-[#193B2C] rounded-sm shrink-0"
          >
            Switch to Regulator Officer to Adjudicate
          </button>
        )}
      </div>

      {/* Permission-Restricted Notice for Institution Roles */}
      {instScoped && (
        <div
          role="region"
          aria-label="Permission-restricted counterpart redaction notice"
          className="p-4 bg-white border border-[#8E6218]/40 rounded-md flex items-center gap-3 text-xs text-[#8E6218]"
        >
          <Lock className="w-4 h-4 shrink-0" />
          <span>
            Institution-Level Privacy Scope (`{user.role}`): Counterpart institution identities are
            redacted (`INST-REDACTED`), and adjudication controls are restricted to
            `regulator_officer` and `regulator_admin` roles.
          </span>
        </div>
      )}

      {/* Filter Bar */}
      {canScan && (
        <div className="flex items-center gap-3">
          <button
            type="button"
            disabled={scanMutation.isPending}
            onClick={() => scanMutation.mutate()}
            className="px-3 py-2 text-xs font-medium text-white bg-[#244C3A] rounded-sm disabled:opacity-50"
          >
            {scanMutation.isPending ? 'Scanning records…' : 'Scan for duplicate candidates'}
          </button>
          <span className="text-xs text-[#686B65]">Candidates are review leads, not fraud findings.</span>
        </div>
      )}
      {feedback && scanMutation.isError && (
        <p role="alert" className="text-xs text-[#99322B]">{feedback.text}</p>
      )}
      <div className="flex flex-wrap items-center gap-1 p-1 bg-[#E9E7DF] rounded-md w-fit">
        {(
          [
            { id: 'ALL', label: `All Candidates (${conflicts.length})` },
            {
              id: 'OPEN',
              label: `Open Review (${conflicts.filter((c) => c.status === 'OPEN').length})`,
            },
            {
              id: 'INFO_REQUESTED',
              label: `Info Requested (${
                conflicts.filter((c) => c.status === 'INFO_REQUESTED').length
              })`,
            },
            {
              id: 'RESOLVED',
              label: `Resolved (${conflicts.filter((c) => c.status === 'RESOLVED').length})`,
            },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setStatusFilter(tab.id)}
            className={`px-3 py-1.5 text-xs font-medium rounded-sm transition-colors ${
              statusFilter === tab.id
                ? 'bg-white text-[#20241F]'
                : 'text-[#686B65] hover:text-[#20241F]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Queue List + Adjudication Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-7 bg-white border border-[#DEDDD5] rounded-md divide-y divide-[#DEDDD5]">
          {filtered.length === 0 ? (
            <p className="p-6 text-xs text-[#686B65]">No review cases are available in this backend scope.</p>
          ) : filtered.map((c) => {
            const active = activeCase?.id === c.id;
            return (
              <div
                key={c.id}
                onClick={() => {
                  setSelectedId(c.id);
                  setFeedback(null);
                }}
                className={`p-5 cursor-pointer transition-colors space-y-2 ${
                  active ? 'bg-[#F0EFE9]' : 'hover:bg-[#F7F6F2]'
                }`}
              >
                <div className="flex items-center justify-between gap-2 text-xs font-mono">
                  <span className="font-semibold text-[#20241F]">
                    {c.id} · {c.conflict_type}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    {c.status === 'OPEN' && (
                      <>
                        <AlertTriangle className="w-3.5 h-3.5 text-[#8E6218]" />
                        <span className="text-[#8E6218] font-semibold">OPEN</span>
                      </>
                    )}
                    {c.status === 'INFO_REQUESTED' && (
                      <>
                        <Clock className="w-3.5 h-3.5 text-[#475863]" />
                        <span className="text-[#475863] font-semibold">INFO_REQUESTED</span>
                      </>
                    )}
                    {c.status === 'RESOLVED' && (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5 text-[#1E563B]" />
                        <span className="text-[#1E563B] font-semibold">RESOLVED</span>
                      </>
                    )}
                  </span>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="font-display text-sm font-semibold text-[#20241F]">
                    {c.student_name} ·{' '}
                    <span className="font-mono text-xs text-[#686B65]">
                      APAAR {c.apaar_masked}
                    </span>
                  </h3>
                  {c.similarity_score !== undefined && (
                    <span className="font-mono text-xs text-[#244C3A] tabular-nums">
                      Similarity: {(c.similarity_score * 100).toFixed(0)}%
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-[#686B65]">
                  <div>
                    Primary: <span className="text-[#20241F]">{c.primary_institution_name}</span>
                    {c.primary_program_code && <> (<span className="font-mono">{c.primary_program_code}</span>)</>}
                  </div>
                  <div>
                    Counterpart:{' '}
                    <span className="text-[#20241F]">{c.competing_institution_name}</span>
                    {c.competing_program_code && <> (<span className="font-mono">{c.competing_program_code}</span>)</>}
                  </div>
                </div>

                <div className="text-[11px] font-mono text-[#686B65] tabular-nums">
                  {c.academic_year_overlap || (c.enrollment_year ? `AY ${c.enrollment_year}` : 'Academic year not supplied')} · Assigned:{' '}
                  {c.assigned_reviewer || 'Unassigned'}
                </div>
              </div>
            );
          })}
        </div>

        {/* Right: Candidate Evidence & Regulator Decision Form */}
        <div className="lg:col-span-5 bg-white border border-[#DEDDD5] rounded-md p-6 space-y-5">
          {activeCase ? (
            <>
              <div className="pb-4 border-b border-[#DEDDD5]">
                <div className="flex items-center justify-between text-xs font-mono text-[#686B65]">
                  <span>{activeCase.id}</span>
                  <GitCompare className="w-4 h-4" />
                </div>
                <h2 className="mt-1 font-display text-lg font-semibold text-[#20241F]">
                  {activeCase.student_name}
                </h2>
                <p className="text-xs font-mono text-[#686B65] mt-0.5 tabular-nums">
                  Masked APAAR: {activeCase.apaar_masked} ·{' '}
                  {activeCase.academic_year_overlap || (activeCase.enrollment_year ? `AY ${activeCase.enrollment_year}` : 'Academic year not supplied')}
                </p>
              </div>

              {/* Match Evidence */}
              <div className="space-y-2 text-xs">
                <div className="font-semibold text-[#20241F]">Backend Match Evidence</div>
                <ul className="space-y-1.5 text-[#686B65] list-disc pl-4">
                  {(activeCase.match_evidence || ['No match evidence was supplied by the API.']).map((ev, i) => (
                    <li key={i}>{ev}</li>
                  ))}
                </ul>
              </div>

              {/* Decision History */}
              {activeCase.decision_history && activeCase.decision_history.length > 0 && (
                <div className="space-y-2 text-xs pt-2 border-t border-[#DEDDD5]">
                  <div className="font-semibold text-[#20241F]">Decision History</div>
                  <div className="space-y-2">
                    {activeCase.decision_history.map((dh) => (
                      <div
                        key={dh.id}
                        className="p-2.5 bg-[#F7F6F2] border border-[#DEDDD5] rounded-sm space-y-1"
                      >
                        <div className="flex justify-between font-mono text-[11px] text-[#686B65]">
                          <span>{dh.action}</span>
                          <span>{dh.timestamp.slice(0, 10)}</span>
                        </div>
                        <p className="text-[#20241F]">{dh.notes}</p>
                        {(dh.actor_email || dh.actor_role) && (
                          <div className="font-mono text-[10px] text-[#686B65]">
                            Actor: {dh.actor_email} {dh.actor_role && `(${dh.actor_role})`}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Regulator Adjudication Form */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  setFeedback(null);
                  resolveMutation.mutate();
                }}
                className="pt-3 border-t border-[#DEDDD5] space-y-3"
              >
                <div>
                  <label
                    htmlFor="conflict-decision-select"
                    className="block text-xs font-medium text-[#20241F] mb-1"
                  >
                    Review Decision
                  </label>
                  <select
                    id="conflict-decision-select"
                    disabled={!canAdjudicate}
                    value={decisionAction}
                    onChange={(e) => setDecisionAction(e.target.value as typeof decisionAction)}
                    className="w-full px-3 py-2 text-xs bg-[#F7F6F2] border border-[#DEDDD5] rounded-md disabled:opacity-50"
                  >
                    {apiMode === 'mock' ? (
                      <>
                        <option value="NOT_A_DUPLICATE">Mark as Not a Duplicate</option>
                        <option value="CONFIRM_DUPLICATE">Confirm Duplicate</option>
                        <option value="REQUEST_INFO">Request Additional Information</option>
                      </>
                    ) : (
                      <>
                        <option value="DISTINCT_STUDENTS">Distinct students</option>
                        <option value="CONFIRMED_DUPLICATE">Confirmed duplicate</option>
                        <option value="INSUFFICIENT_EVIDENCE">Insufficient evidence</option>
                        <option value="ESCALATED">Escalate</option>
                      </>
                    )}
                  </select>
                </div>

                {apiMode === 'mock' ? <div>
                  <label
                    htmlFor="conflict-reason-textarea"
                    className="block text-xs font-medium text-[#20241F] mb-1"
                  >
                    Mandatory Review Reason (min 8 characters)
                  </label>
                  <textarea
                    id="conflict-reason-textarea"
                    rows={3}
                    disabled={!canAdjudicate}
                    value={reasonNotes}
                    onChange={(e) => setReasonNotes(e.target.value)}
                    placeholder="Document evidence reviewed (e.g. JoSAA withdrawal slip ref)..."
                    className="w-full p-2.5 text-xs bg-[#F7F6F2] border border-[#DEDDD5] rounded-md disabled:opacity-50"
                  />
                </div> : (
                  <p className="text-xs text-[#686B65]">The live API records the supported outcome only; reviewer notes are not part of its contract.</p>
                )}

                {feedback && (
                  <div
                    role="status"
                    className={`p-3 rounded-sm text-xs ${
                      feedback.type === 'success'
                        ? 'bg-[#1E563B]/10 text-[#1E563B] border border-[#1E563B]/30'
                        : 'bg-[#99322B]/10 text-[#99322B] border border-[#99322B]/30'
                    }`}
                  >
                    {feedback.text}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={!canAdjudicate || resolveMutation.isPending}
                  className="w-full py-2 px-4 text-xs font-medium text-white bg-[#244C3A] hover:bg-[#193B2C] disabled:opacity-45 rounded-md transition-colors"
                >
                  {canAdjudicate
                    ? resolveMutation.isPending
                      ? 'Submitting Decision...'
                      : 'Record Review Decision'
                    : 'Restricted to Regulator Roles'}
                </button>
              </form>
            </>
          ) : (
            <p className="text-xs text-[#686B65]">Select a candidate to review.</p>
          )}
        </div>
      </div>
    </div>
  );
};
