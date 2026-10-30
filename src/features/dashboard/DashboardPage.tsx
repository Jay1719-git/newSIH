import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import {
  ArrowUpRight,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { useAuth } from '../../lib/auth';
import { weaveApiClient, weaveQueryKeys } from '../../lib/api-client';
import { isInstitutionScopedRole } from '../../lib/weaveEngine';

export const DashboardPage: React.FC = () => {
  const { user, apiMode } = useAuth();
  const instScoped = isInstitutionScopedRole(user.role);

  const instQuery = useQuery({
    queryKey: weaveQueryKeys.institutions(user.role, user.institution_id),
    queryFn: () => weaveApiClient.getInstitutionsOverview(user.role, user.institution_id),
  });

  const stuQuery = useQuery({
    queryKey: weaveQueryKeys.validationResults(user.role, user.institution_id),
    queryFn: () => weaveApiClient.getValidationResults(user.role, user.institution_id),
  });

  const cnfQuery = useQuery({
    queryKey: weaveQueryKeys.conflicts(user.role, user.institution_id),
    queryFn: () => weaveApiClient.getConflicts(user.role, user.institution_id),
  });

  const audQuery = useQuery({
    queryKey: weaveQueryKeys.auditEvents(user.role, user.institution_id),
    queryFn: () => weaveApiClient.getAuditEvents(user.role, user.institution_id),
  });

  if (instQuery.isLoading || stuQuery.isLoading || cnfQuery.isLoading) {
    return (
      <div
        role="status"
        aria-label="Loading dashboard metrics"
        className="space-y-6 animate-pulse"
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-white border border-[#DEDDD5] rounded-md p-5" />
          ))}
        </div>
        <div className="h-72 bg-white border border-[#DEDDD5] rounded-md p-6" />
      </div>
    );
  }

  if (instQuery.isError || stuQuery.isError || cnfQuery.isError) {
    return (
      <div
        role="alert"
        className="bg-white border border-[#99322B] rounded-md p-6 flex items-center justify-between"
      >
        <div className="text-xs text-[#99322B]">
          Unable to load dashboard metrics from /api/v1. Verify backend connectivity.
        </div>
        <button
          type="button"
          onClick={() => {
            instQuery.refetch();
            stuQuery.refetch();
            cnfQuery.refetch();
          }}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[#F7F6F2] border border-[#DEDDD5] rounded-md"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry</span>
        </button>
      </div>
    );
  }

  const institutions = instQuery.data?.institutions || [];
  const students = stuQuery.data?.students || [];
  const batches = stuQuery.data?.batches || [];
  const conflicts = cnfQuery.data?.conflicts || [];
  const auditEvents = audQuery.data?.events || [];

  const totalApproved = institutions.reduce(
    (sum, i) => sum + i.programs.reduce((s, p) => s + p.approved_intake, 0),
    0
  );
  const totalEnrolled = institutions.reduce(
    (sum, i) => sum + i.programs.reduce((s, p) => s + p.enrolled_verified, 0),
    0
  );
  const openIssuesCount = students.filter((s) => s.status !== 'VERIFIED').length;
  const openConflictsCount = conflicts.filter((c) => c.status === 'OPEN').length;

  const programsNearOrOver = institutions.flatMap((inst) =>
    inst.programs
      .filter((p) => p.enrolled_verified / p.approved_intake >= 0.92)
      .map((p) => ({
        institution_id: inst.id,
        institution_name: inst.name,
        ...p,
        pct: Math.round((p.enrolled_verified / p.approved_intake) * 100),
      }))
  );

  const chartData = institutions.flatMap((inst) =>
    inst.programs.map((p) => ({
      label: instScoped ? p.program_code : `${inst.id.split('-')[1]}·${p.program_code}`,
      Approved: p.approved_intake,
      Enrolled: p.enrolled_verified,
    }))
  );

  const verifiedCount = students.filter((s) => s.status === 'VERIFIED').length;
  const conflictCount = students.filter((s) => s.status === 'FLAGGED_CONFLICT').length;
  const failedCount = students.filter((s) => s.status === 'VALIDATION_FAILED').length;
  const pendingCount = students.filter((s) => s.status === 'PENDING_REVIEW').length;

  return (
    <div className="space-y-8">
      {/* Role Scope Banner */}
      <div className="p-4 bg-[#F0EFE9] border border-[#DEDDD5] rounded-md flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
        <div>
          <span className="font-semibold text-[#20241F]">
            {instScoped
              ? `Institution Workspace — ${institutions[0]?.name || user.institution_id}`
              : 'Regulatory & Cross-Institution Oversight Workspace'}
          </span>
          <span className="text-[#686B65] ml-2">
            · Viewing {institutions.length} institution(s) and {students.length} synthetic student
            records
          </span>
        </div>
        <span className="font-mono text-[11px] text-[#244C3A]">
          Active Role: {user.role}
        </span>
      </div>

      {/* 4-Metric Summary Strip */}
      {instScoped ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 bg-white border border-[#DEDDD5] rounded-md">
            <div className="text-xs text-[#686B65]">Student Records Processed</div>
            <div className="mt-2 font-mono text-2xl font-semibold text-[#20241F] tabular-nums">
              {students.length}
            </div>
            <div className="mt-1.5 text-xs text-[#1E563B] font-mono tabular-nums">
              {verifiedCount} verified · {batches.length} batches
            </div>
          </div>

          <div className="p-5 bg-white border border-[#DEDDD5] rounded-md">
            <div className="text-xs text-[#686B65]">Current Enrolment</div>
            <div className="mt-2 font-mono text-2xl font-semibold text-[#20241F] tabular-nums">
              {totalEnrolled}
            </div>
            <div className="mt-1.5 text-xs text-[#686B65] font-mono tabular-nums">
              {totalApproved > 0
                ? `${((totalEnrolled / totalApproved) * 100).toFixed(1)}% of approved intake`
                : '—'}
            </div>
          </div>

          <div className="p-5 bg-white border border-[#DEDDD5] rounded-md">
            <div className="text-xs text-[#686B65]">Approved Intake</div>
            <div className="mt-2 font-mono text-2xl font-semibold text-[#20241F] tabular-nums">
              {totalApproved}
            </div>
            <div className="mt-1.5 text-xs text-[#686B65] font-mono tabular-nums">
              Across {institutions[0]?.programs.length || 0} sanctioned programs
            </div>
          </div>

          <div className="p-5 bg-white border border-[#DEDDD5] rounded-md">
            <div className="text-xs text-[#686B65]">Open Validation Issues</div>
            <div className="mt-2 font-mono text-2xl font-semibold text-[#8E6218] tabular-nums">
              {openIssuesCount}
            </div>
            <div className="mt-1.5 text-xs text-[#686B65] font-mono tabular-nums">
              {conflictCount} conflict · {failedCount} invalid
            </div>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 bg-white border border-[#DEDDD5] rounded-md">
            <div className="text-xs text-[#686B65]">Participating Institutions</div>
            <div className="mt-2 font-mono text-2xl font-semibold text-[#20241F] tabular-nums">
              {institutions.length}
            </div>
            <div className="mt-1.5 text-xs text-[#686B65] font-mono tabular-nums">
              AICTE synthetic registry
            </div>
          </div>

          <div className="p-5 bg-white border border-[#DEDDD5] rounded-md">
            <div className="text-xs text-[#686B65]">Committed Student Records</div>
            <div className="mt-2 font-mono text-2xl font-semibold text-[#20241F] tabular-nums">
              {totalEnrolled}
            </div>
            <div className="mt-1.5 text-xs text-[#1E563B] font-mono tabular-nums">
              Out of {totalApproved} sanctioned seats
            </div>
          </div>

          <div className="p-5 bg-white border border-[#DEDDD5] rounded-md">
            <div className="text-xs text-[#686B65]">Programs Flagged for Intake Review</div>
            <div className="mt-2 font-mono text-2xl font-semibold text-[#8E6218] tabular-nums">
              {programsNearOrOver.length}
            </div>
            <div className="mt-1.5 text-xs text-[#686B65] font-mono tabular-nums">
              &ge;92% utilization or exceeding cap
            </div>
          </div>

          <div className="p-5 bg-white border border-[#DEDDD5] rounded-md">
            <div className="text-xs text-[#686B65]">Unresolved Cross-Institution Conflicts</div>
            <div className="mt-2 font-mono text-2xl font-semibold text-[#99322B] tabular-nums">
              {openConflictsCount}
            </div>
            <div className="mt-1.5 text-xs text-[#686B65] font-mono tabular-nums">
              Awaiting regulator adjudication
            </div>
          </div>
        </div>
      )}

      {/* Middle Row: Recharts Intake vs Enrolment Chart + Validation Status Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <section className="lg:col-span-8 bg-white border border-[#DEDDD5] rounded-md p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h2 className="font-display text-base font-semibold text-[#20241F]">
                Approved Intake vs. Verified Enrolment Comparison
              </h2>
              <p className="text-xs text-[#686B65]">
                Accessible summary: compares AICTE sanctioned seats against verified enrolment per
                program.
              </p>
            </div>
            <Link
              to="/app/intake"
              className="inline-flex items-center gap-1 text-xs font-medium text-[#244C3A] hover:underline"
            >
              <span>Full Intake Monitor</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="h-64 w-full" role="img" aria-label="Bar chart comparing approved intake and verified enrolment across programs">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E9E7DF" vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fill: '#686B65', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                  axisLine={{ stroke: '#DEDDD5' }}
                />
                <YAxis
                  tick={{ fill: '#686B65', fontSize: 11, fontFamily: 'JetBrains Mono' }}
                  axisLine={{ stroke: '#DEDDD5' }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#FFFFFF',
                    borderColor: '#DEDDD5',
                    fontSize: '12px',
                    fontFamily: 'JetBrains Mono',
                  }}
                />
                <Bar dataKey="Approved" fill="#E9E7DF" stroke="#686B65" radius={[2, 2, 0, 0]} />
                <Bar dataKey="Enrolled" fill="#244C3A" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Validation Status Distribution & Programs Approaching Intake */}
        <section className="lg:col-span-4 bg-white border border-[#DEDDD5] rounded-md p-6 space-y-5">
          <div>
            <h2 className="font-display text-base font-semibold text-[#20241F]">
              Validation Status Distribution
            </h2>
            <p className="text-xs text-[#686B65]">
              Internal deterministic rule check breakdown.
            </p>
          </div>

          <div className="space-y-3 text-xs font-mono tabular-nums">
            <div className="flex items-center justify-between p-2.5 bg-[#F7F6F2] border border-[#DEDDD5] rounded-sm">
              <span className="inline-flex items-center gap-1.5 text-[#1E563B] font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Platform Checks Passed</span>
              </span>
              <span className="font-semibold text-[#20241F]">{verifiedCount}</span>
            </div>

            <div className="flex items-center justify-between p-2.5 bg-[#F7F6F2] border border-[#DEDDD5] rounded-sm">
              <span className="inline-flex items-center gap-1.5 text-[#8E6218] font-medium">
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Duplicate / Conflict Candidate</span>
              </span>
              <span className="font-semibold text-[#20241F]">{conflictCount}</span>
            </div>

            <div className="flex items-center justify-between p-2.5 bg-[#F7F6F2] border border-[#DEDDD5] rounded-sm">
              <span className="inline-flex items-center gap-1.5 text-[#8E6218] font-medium">
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Awaiting Consent Review</span>
              </span>
              <span className="font-semibold text-[#20241F]">{pendingCount}</span>
            </div>

            <div className="flex items-center justify-between p-2.5 bg-[#F7F6F2] border border-[#DEDDD5] rounded-sm">
              <span className="inline-flex items-center gap-1.5 text-[#99322B] font-medium">
                <XCircle className="w-3.5 h-3.5" />
                <span>Invalid / Failed Rules</span>
              </span>
              <span className="font-semibold text-[#20241F]">{failedCount}</span>
            </div>
          </div>

          <div className="pt-4 border-t border-[#DEDDD5] space-y-2">
            <div className="text-xs font-semibold text-[#20241F]">
              Programs Approaching / Exceeding Intake
            </div>
            <div className="space-y-2">
              {programsNearOrOver.slice(0, 3).map((p) => (
                <div
                  key={`${p.institution_id}-${p.program_code}`}
                  className="text-xs flex items-center justify-between font-mono tabular-nums"
                >
                  <span className="text-[#20241F]">
                    {p.institution_id.split('-')[1]} · {p.program_code}
                  </span>
                  <span
                    className={
                      p.pct > 100
                        ? 'text-[#99322B] font-semibold'
                        : 'text-[#8E6218] font-semibold'
                    }
                  >
                    {p.enrolled_verified}/{p.approved_intake} ({p.pct}%)
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>

      {/* Bottom Row: Recent Import Batches & Activity Timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <section className="lg:col-span-7 bg-white border border-[#DEDDD5] rounded-md overflow-hidden">
          <div className="px-6 py-4 border-b border-[#DEDDD5] flex items-center justify-between">
            <h2 className="font-display text-base font-semibold text-[#20241F]">
              Recent Import Batches
            </h2>
            <Link
              to="/app/imports"
              className="text-xs font-medium text-[#244C3A] hover:underline"
            >
              View all batches
            </Link>
          </div>
          <div className="divide-y divide-[#DEDDD5]">
            {batches.map((b) => (
              <div
                key={b.id}
                className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-[#F7F6F2]/60"
              >
                <div>
                  <Link
                    to={`/app/imports/${b.id}`}
                    className="font-mono text-xs font-semibold text-[#244C3A] hover:underline"
                  >
                    {b.id} · {b.filename}
                  </Link>
                  <div className="text-xs text-[#686B65] font-mono tabular-nums mt-0.5">
                    {b.total_rows} rows · {b.passed_rows} verified · {b.flagged_rows} flagged ·{' '}
                    {b.failed_rows} failed
                  </div>
                </div>
                <Link
                  to={`/app/imports/${b.id}`}
                  className="px-3 py-1.5 text-xs font-medium text-[#20241F] bg-[#F7F6F2] border border-[#DEDDD5] rounded-sm hover:bg-[#E9E7DF] self-start sm:self-auto"
                >
                  Inspect Results
                </Link>
              </div>
            ))}
          </div>
        </section>

        <section className="lg:col-span-5 bg-white border border-[#DEDDD5] rounded-md overflow-hidden">
          <div className="px-6 py-4 border-b border-[#DEDDD5] flex items-center justify-between">
            <h2 className="font-display text-base font-semibold text-[#20241F]">
              Recent Audit Activity
            </h2>
            <Link
              to="/app/audit"
              className="text-xs font-medium text-[#244C3A] hover:underline"
            >
              Full timeline
            </Link>
          </div>
          <div className="divide-y divide-[#DEDDD5]">
            {auditEvents.slice(0, 4).map((ev) => (
              <div key={ev.id} className="p-4 space-y-1 text-xs">
                <div className="flex items-center justify-between font-mono text-[11px] text-[#686B65]">
                  <span>
                    {ev.id} · {ev.action}
                  </span>
                  <span>{ev.created_at.slice(0, 10)}</span>
                </div>
                <p className="text-[#20241F]">{ev.summary}</p>
              </div>
            ))}
            {apiMode === 'live' && audQuery.isError && (
              <p className="p-4 text-xs text-[#686B65]">
                Audit listing is not implemented in the FastAPI backend. No demo timeline is substituted.
              </p>
            )}
            {!audQuery.isError && auditEvents.length === 0 && (
              <p className="p-4 text-xs text-[#686B65]">No audit events are available.</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
};
