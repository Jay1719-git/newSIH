import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ShieldCheck,
  Lock,
  Send,
  ExternalLink,
  AlertCircle,
  CheckCircle2,
  Ban,
  Mic,
  Square,
  RotateCcw,
  Cpu,
  Volume2,
} from 'lucide-react';
import { useAuth } from '../../lib/auth';
import { weaveApiClient, weaveQueryKeys } from '../../lib/api-client';
import { VALIDATION_RULES_CATALOG } from '../../lib/weaveEngine';

/**
 * 1. /app/audit — Chronological Audit Timeline (Section 14)
 */
export const AuditTimelinePage: React.FC = () => {
  const { user, apiMode } = useAuth();
  const [actionFilter, setActionFilter] = useState<string>('ALL');
  const [dateFilter, setDateFilter] = useState<string>('');

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: weaveQueryKeys.auditEvents(user.role, user.institution_id),
    queryFn: () => weaveApiClient.getAuditEvents(user.role, user.institution_id),
  });

  if (isLoading) {
    return (
      <div role="status" className="bg-white border border-[#DEDDD5] rounded-md p-6 animate-pulse h-64" />
    );
  }

  if (isError && apiMode === 'live') {
    return (
      <div role="status" className="bg-white border border-[#DEDDD5] rounded-md p-6 text-xs text-[#686B65]">
        Audit event listing is not implemented by the FastAPI backend yet. The in-memory Express timeline is not shown in live mode.
      </div>
    );
  }

  const events = data?.events || [];
  const chainIntegrity = data?.chain_integrity;

  const filtered = events.filter((ev) => {
    if (actionFilter !== 'ALL' && ev.action !== actionFilter) return false;
    if (dateFilter && !ev.created_at.startsWith(dateFilter)) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Hash Chain Verification Banner */}
      {chainIntegrity && (
        <div className="p-4 bg-white border border-[#DEDDD5] rounded-md flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="w-4 h-4 text-[#1E563B] shrink-0" />
            <div>
              <span className="font-semibold text-[#20241F]">
                Backend Hash-Chain Verification:{' '}
                {chainIntegrity.intact ? 'INTACT' : 'TAMPER_DETECTED'}
              </span>
              <p className="text-[#686B65]">
                Verified {chainIntegrity.checkedCount} linked events (`previous_hash` →
                `event_hash`). Passwords, tokens, and raw CSV contents are never logged.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => refetch()}
            className="px-3 py-1.5 text-xs font-medium text-[#20241F] bg-[#F7F6F2] border border-[#DEDDD5] rounded-sm hover:bg-[#E9E7DF] shrink-0"
          >
            Re-Verify Chain
          </button>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-white border border-[#DEDDD5] rounded-md p-4 flex flex-wrap items-center gap-3">
        <select
          aria-label="Filter by audit action type"
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="px-3 py-1.5 text-xs font-mono bg-[#F7F6F2] border border-[#DEDDD5] rounded-md"
        >
          <option value="ALL">All Action Types</option>
          <option value="BATCH_INGESTED">BATCH_INGESTED</option>
          <option value="BATCH_COMMITTED">BATCH_COMMITTED</option>
          <option value="CONFLICT_RESOLVED">CONFLICT_RESOLVED</option>
          <option value="ATTESTATION_ISSUED">ATTESTATION_ISSUED</option>
          <option value="ATTESTATION_REVOKED">ATTESTATION_REVOKED</option>
        </select>

        <input
          type="date"
          aria-label="Filter audit events by date"
          value={dateFilter}
          onChange={(e) => setDateFilter(e.target.value)}
          className="px-3 py-1.5 text-xs font-mono bg-[#F7F6F2] border border-[#DEDDD5] rounded-md"
        />

        {dateFilter && (
          <button
            type="button"
            onClick={() => setDateFilter('')}
            className="text-xs text-[#244C3A] underline"
          >
            Clear date
          </button>
        )}
      </div>

      {/* Audit Timeline Table */}
      <div className="bg-white border border-[#DEDDD5] rounded-md divide-y divide-[#DEDDD5]">
        {filtered.map((ev) => (
          <div key={ev.id} className="p-5 space-y-2 hover:bg-[#F7F6F2]/60 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-2 font-mono">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-[#20241F]">{ev.id}</span>
                <span>·</span>
                <span className="text-[#244C3A] font-semibold">{ev.action}</span>
                <span>·</span>
                <span className="text-[#686B65]">
                  Target: {ev.entity_type} ({ev.entity_id})
                </span>
              </div>
              <span className="text-[#686B65] tabular-nums">
                {ev.created_at.replace('T', ' ').slice(0, 19)} UTC
              </span>
            </div>

            <p className="text-sm text-[#20241F]">{ev.summary}</p>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] text-[#686B65]">
              <span>Actor Role: {ev.actor_role}</span>
              <span>·</span>
              <span>Institution: {ev.institution_id}</span>
              <span>·</span>
              <span>Outcome: {ev.outcome || 'SUCCESS'}</span>
            </div>

            <div className="pt-1 grid grid-cols-1 md:grid-cols-2 gap-2 font-mono text-[11px] text-[#686B65] tabular-nums">
              <div className="truncate">
                <Lock className="w-3 h-3 inline mr-1" />
                prev: {ev.previous_hash}
              </div>
              <div className="truncate text-[#20241F]">hash: {ev.event_hash}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Ruleset Reference Table */}
      <div className="bg-white border border-[#DEDDD5] rounded-md overflow-hidden">
        <div className="px-6 py-4 border-b border-[#DEDDD5]">
          <h2 className="font-display text-base font-semibold text-[#20241F]">
            Deterministic Validation Ruleset Catalog (v2026.10.v1)
          </h2>
        </div>
        <div className="divide-y divide-[#DEDDD5] text-xs">
          {VALIDATION_RULES_CATALOG.map((r) => (
            <div key={r.code} className="p-4 space-y-1">
              <div className="font-mono font-semibold text-[#20241F]">
                {r.stu_code} ({r.code}) · {r.name}
              </div>
              <p className="text-[#686B65]">{r.description}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

// Helper to synthesize a tiny valid WAV base64 buffer for testing gemini-3.5-transcribe in headless environments
function createSilentWavBase64(durationSec = 0.25): string {
  const sampleRate = 16000;
  const numSamples = Math.floor(sampleRate * durationSec);
  const buffer = new ArrayBuffer(44 + numSamples * 2);
  const view = new DataView(buffer);

  const writeStr = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  };

  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + numSamples * 2, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, 'data');
  view.setUint32(40, numSamples * 2, true);

  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

type GeminiChatModel = 'gemini-3.8-flash' | 'gemini-3.1-flash-lite' | 'gemini-4-argon';

interface ChatThreadMessage {
  id: string;
  role: 'user' | 'model';
  text: string;
  modelUsed?: string;
  timestamp: string;
  sources?: Array<{ label: string; route: string }>;
}

/**
 * 2. /app/assistant — Multi-Turn Gemini Institutional Copilot + Audio Transcription (gemini-3.5-transcribe)
 */
export const AssistantPage: React.FC = () => {
  const { user } = useAuth();
  const [selectedModel, setSelectedModel] = useState<GeminiChatModel>('gemini-3.8-flash');
  const [promptInput, setPromptInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [transcribeStatus, setTranscribeStatus] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const threadEndRef = useRef<HTMLDivElement | null>(null);

  const [messages, setMessages] = useState<ChatThreadMessage[]>([
    {
      id: 'msg-welcome',
      role: 'model',
      text: `Welcome to the **WEAVE Institutional Compliance & Verification Copilot** (Role scope: \`${user.role}\` · Tenant: \`${user.institution_id || 'AICTE-ALL'}\`).\n\nAsk multi-turn questions about deterministic validation rules (\`STU-001\` through \`STU-006\`), cross-institution APAAR duplicate candidates, or AICTE approved intake caps—or use the microphone to transcribe spoken queries via \`gemini-3.5-transcribe\`.`,
      modelUsed: 'gemini-3.8-flash',
      timestamp: 'System Initialized',
      sources: [
        { label: 'Batch BAT-2026-003 Validation Results', route: '/app/imports/BAT-2026-003' },
        { label: 'Duplicate & Conflict Review', route: '/app/duplicates' },
        { label: '3D Spatial Topology', route: '/app/topology' },
      ],
    },
  ]);

  const suggestedPrompts = [
    'Explain the most common validation issues in batch BAT-2026-003.',
    'Summarize open cross-institution APAAR duplicate candidates and privacy rules.',
    'Which programs are approaching or exceeding AICTE approved intake?',
    'How does rule STU-002 validate sanctioned discipline codes?',
  ];

  const chatMutation = useMutation({
    mutationFn: async (nextMessages: Array<{ role: 'user' | 'model'; text: string }>) => {
      return weaveApiClient.chatWithAssistant({
        messages: nextMessages,
        model: selectedModel,
        role: user.role,
        institution_id: user.institution_id,
      });
    },
    onSuccess: (res) => {
      setMessages((prev) => [
        ...prev,
        {
          id: `msg-${Date.now()}`,
          role: 'model',
          text: res.reply,
          modelUsed: res.model_used || selectedModel,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          sources: res.sources,
        },
      ]);
    },
  });

  const transcribeMutation = useMutation({
    mutationFn: (params: { audioBase64: string; mimeType: string; samplePromptHint?: string }) =>
      weaveApiClient.transcribeAudio(params),
    onSuccess: (res) => {
      setPromptInput(res.transcript);
      setTranscribeStatus(`Transcribed via ${res.model}`);
    },
    onError: () => {
      setTranscribeStatus('Audio transcription could not be completed.');
    },
  });

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [messages.length]);

  const handleSendMessage = (textToSend: string) => {
    const clean = textToSend.trim();
    if (!clean || chatMutation.isPending) return;

    const userMsg: ChatThreadMessage = {
      id: `msg-u-${Date.now()}`,
      role: 'user',
      text: clean,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    const updatedThread = [...messages, userMsg];
    setMessages(updatedThread);
    setPromptInput('');
    setTranscribeStatus(null);

    chatMutation.mutate(
      updatedThread.map((m) => ({
        role: m.role,
        text: m.text,
      }))
    );
  };

  const handleToggleMicrophone = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }

    setTranscribeStatus('Listening via microphone...');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(audioChunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        const reader = new FileReader();
        reader.onloadend = () => {
          const dataUrl = String(reader.result || '');
          const base64 = dataUrl.includes(',') ? dataUrl.split(',')[1] : '';
          if (base64) {
            setTranscribeStatus('Transcribing with gemini-3.5-transcribe...');
            transcribeMutation.mutate({
              audioBase64: base64,
              mimeType: blob.type || 'audio/webm',
            });
          }
        };
        reader.readAsDataURL(blob);
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
    } catch {
      // Fallback when browser environment has no physical microphone device attached
      setTranscribeStatus('Transcribing synthetic voice clip via gemini-3.5-transcribe...');
      transcribeMutation.mutate({
        audioBase64: createSilentWavBase64(0.25),
        mimeType: 'audio/wav',
        samplePromptHint:
          'Summarize open cross-institution APAAR conflicts and STU-002 validation failures in batch BAT-2026-003.',
      });
    }
  };

  const handleSampleVoiceClip = () => {
    setTranscribeStatus('Transcribing voice sample via gemini-3.5-transcribe...');
    transcribeMutation.mutate({
      audioBase64: createSilentWavBase64(0.25),
      mimeType: 'audio/wav',
      samplePromptHint:
        'Check AICTE approved intake utilization for NIT Kurukshetra BTECH-CSE and explain rule STU-005.',
    });
  };

  return (
    <div className="space-y-6">
      {/* Mandatory Advisory & Permission Disclaimer */}
      <div className="p-4 bg-[#F0EFE9] border border-[#DEDDD5] rounded-md flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-4 h-4 text-[#244C3A] shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <div className="font-semibold text-[#20241F]">
              Multi-Turn Gemini Institutional Copilot &amp; Voice Transcription (`gemini-3.5-transcribe`)
            </div>
            <p className="text-[#686B65]">
              Scoped to role `{user.role}`. Strictly read-only advisory output—never modifies
              records, never unmasks APAAR identifiers, and never overrides deterministic validation
              rules.
            </p>
          </div>
        </div>

        {/* Model Selector (gemini-3.8-flash, gemini-3.1-flash-lite, gemini-4-argon) */}
        <div className="flex items-center gap-2 shrink-0">
          <Cpu className="w-3.5 h-3.5 text-[#244C3A]" />
          <label htmlFor="gemini-model-select" className="text-[11px] font-mono text-[#686B65]">
            Model:
          </label>
          <select
            id="gemini-model-select"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value as GeminiChatModel)}
            className="px-2.5 py-1.5 text-xs font-mono bg-white border border-[#DEDDD5] rounded text-[#20241F]"
          >
            <option value="gemini-3.8-flash">gemini-3.8-flash (General Tasks)</option>
            <option value="gemini-3.1-flash-lite">gemini-3.1-flash-lite (Fast / Low-Latency)</option>
            <option value="gemini-4-argon">gemini-4-argon (Complex Reasoning)</option>
          </select>
        </div>
      </div>

      {/* Multi-turn Chat Container */}
      <div className="bg-white border border-[#DEDDD5] rounded-md flex flex-col h-[560px]">
        {/* Header Bar */}
        <div className="px-5 py-3.5 border-b border-[#DEDDD5] flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-[#20241F]">Conversation Thread</span>
            <span className="font-mono text-[11px] px-2 py-0.5 bg-[#F7F6F2] border border-[#DEDDD5] rounded text-[#686B65]">
              {messages.length} message(s) · Active model: {selectedModel}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setMessages(messages.slice(0, 1))}
            className="inline-flex items-center gap-1 text-xs text-[#686B65] hover:text-[#20241F]"
          >
            <RotateCcw className="w-3.5 h-3.5" /> Reset Thread
          </button>
        </div>

        {/* Scrollable Message History */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-[#F7F6F2]/40">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
            >
              <div
                className={`max-w-2xl rounded-md p-4 text-xs space-y-2.5 border ${
                  msg.role === 'user'
                    ? 'bg-[#244C3A] text-white border-[#244C3A]'
                    : 'bg-white text-[#20241F] border-[#DEDDD5]'
                }`}
              >
                <div className="flex items-center justify-between gap-4 text-[10px] font-mono opacity-80">
                  <span>
                    {msg.role === 'user'
                      ? `${user.name} (${user.role})`
                      : `WEAVE Copilot · ${msg.modelUsed || selectedModel}`}
                  </span>
                  <span>{msg.timestamp}</span>
                </div>

                <div className="whitespace-pre-line leading-relaxed">{msg.text}</div>

                {msg.sources && msg.sources.length > 0 && (
                  <div className="pt-2 border-t border-[#DEDDD5]/70 flex flex-wrap items-center gap-2.5">
                    <span className="text-[11px] font-mono text-[#686B65]">Citations:</span>
                    {msg.sources.map((src) => (
                      <Link
                        key={src.route}
                        to={src.route}
                        className="inline-flex items-center gap-1 text-[11px] font-medium text-[#244C3A] underline hover:text-[#193B2C]"
                      >
                        <span>{src.label}</span>
                        <ExternalLink className="w-3 h-3" />
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {chatMutation.isPending && (
            <div className="flex items-start">
              <div className="bg-white border border-[#DEDDD5] rounded-md px-4 py-3 text-xs text-[#686B65] font-mono">
                Generating grounded response with {selectedModel}...
              </div>
            </div>
          )}
          <div ref={threadEndRef} />
        </div>

        {/* Quick Prompts + Input + Microphone Audio Transcription Bar */}
        <div className="p-4 border-t border-[#DEDDD5] bg-white space-y-3">
          <div className="flex flex-wrap items-center gap-1.5">
            {suggestedPrompts.map((sp) => (
              <button
                key={sp}
                type="button"
                onClick={() => handleSendMessage(sp)}
                disabled={chatMutation.isPending}
                className="px-2.5 py-1 text-[11px] bg-[#F7F6F2] hover:bg-[#E9E7DF] border border-[#DEDDD5] rounded text-[#20241F] transition-colors text-left"
              >
                {sp}
              </button>
            ))}
          </div>

          {transcribeStatus && (
            <div className="flex items-center justify-between px-3 py-1.5 bg-[#EAF2EE] border border-[#1E563B]/20 rounded text-[11px] font-mono text-[#1E563B]">
              <span>{transcribeStatus}</span>
              <button
                type="button"
                onClick={() => setTranscribeStatus(null)}
                className="underline ml-2"
              >
                Dismiss
              </button>
            </div>
          )}

          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage(promptInput);
            }}
            className="flex flex-wrap sm:flex-nowrap items-center gap-2"
          >
            <input
              type="text"
              aria-label="Ask a multi-turn question or transcribe voice audio"
              value={promptInput}
              onChange={(e) => setPromptInput(e.target.value)}
              placeholder="Ask a follow-up question or click Record Mic to transcribe with gemini-3.5-transcribe..."
              className="flex-1 px-3 py-2 text-xs bg-[#F7F6F2] border border-[#DEDDD5] rounded-md text-[#20241F]"
            />

            <button
              type="button"
              onClick={handleToggleMicrophone}
              disabled={transcribeMutation.isPending}
              className={`inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-md border transition-colors ${
                isRecording
                  ? 'bg-[#99322B] text-white border-[#99322B]'
                  : 'bg-[#F7F6F2] text-[#20241F] border-[#DEDDD5] hover:bg-[#E9E7DF]'
              }`}
              title="Record microphone audio and transcribe using gemini-3.5-transcribe"
            >
              {isRecording ? (
                <>
                  <Square className="w-3.5 h-3.5" />
                  <span>Stop Mic</span>
                </>
              ) : (
                <>
                  <Mic className="w-3.5 h-3.5 text-[#244C3A]" />
                  <span>{transcribeMutation.isPending ? 'Transcribing...' : 'Record Mic'}</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={handleSampleVoiceClip}
              disabled={transcribeMutation.isPending}
              className="inline-flex items-center gap-1 px-2.5 py-2 text-xs font-mono text-[#686B65] bg-[#F7F6F2] hover:text-[#20241F] border border-[#DEDDD5] rounded-md"
              title="Test gemini-3.5-transcribe with a synthetic audio buffer"
            >
              <Volume2 className="w-3.5 h-3.5 text-[#244C3A]" />
              <span className="hidden md:inline">Voice Sample</span>
            </button>

            <button
              type="submit"
              disabled={chatMutation.isPending || !promptInput.trim()}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-white bg-[#244C3A] hover:bg-[#193B2C] disabled:opacity-50 rounded-md"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Send</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

/**
 * 3. /app/settings — Profile, API Mode & Attestation Management Page
 */
export const SettingsPage: React.FC = () => {
  const { user, apiMode } = useAuth();
  const queryClient = useQueryClient();

  const attQuery = useQuery({
    queryKey: weaveQueryKeys.attestations(user.role, user.institution_id),
    queryFn: () => weaveApiClient.getAttestations(user.role, user.institution_id),
    enabled: apiMode === 'mock',
  });

  const stuQuery = useQuery({
    queryKey: weaveQueryKeys.validationResults(user.role, user.institution_id),
    queryFn: () => weaveApiClient.getValidationResults(user.role, user.institution_id),
  });

  const eligibleStudents = (stuQuery.data?.students || []).filter(
    (s) => s.status === 'VERIFIED' && s.consent_granted
  );
  const [selectedStudentId, setSelectedStudentId] = useState<string>(
    eligibleStudents[0]?.id || 'REC-2026-101'
  );
  const [purpose, setPurpose] = useState<string>(
    'National Scholarship Portal (NSP) Bonafide Verification'
  );
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const issueMutation = useMutation({
    mutationFn: () =>
      weaveApiClient.issueAttestation({
        student_record_id: selectedStudentId,
        purpose,
        validity_days: 365,
        actor_role: user.role,
        actor_email: user.email,
      }),
    onSuccess: (res) => {
      setStatusMsg(`Issued Ed25519 attestation ${res.attestation.id}.`);
      queryClient.invalidateQueries({ queryKey: ['weave'] });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) =>
      weaveApiClient.revokeAttestation({
        id,
        reason: 'Revoked by administrator via credential settings',
        actor_role: user.role,
        actor_email: user.email,
      }),
    onSuccess: (res) => {
      setStatusMsg(`Revoked attestation ${res.attestation.id}.`);
      queryClient.invalidateQueries({ queryKey: ['weave'] });
    },
  });

  const attestations = attQuery.data?.attestations || [];

  return (
    <div className="space-y-8">
      {/* Session & API Mode Settings */}
      <div className="bg-white border border-[#DEDDD5] rounded-md p-6 space-y-4">
        <h2 className="font-display text-base font-semibold text-[#20241F]">
          Session Profile &amp; Environment Configuration
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-mono">
          <div className="p-3 bg-[#F7F6F2] border border-[#DEDDD5] rounded-sm">
            <div className="text-[#686B65]">Active User</div>
            <div className="font-semibold text-[#20241F] mt-0.5">{user.email}</div>
          </div>
          <div className="p-3 bg-[#F7F6F2] border border-[#DEDDD5] rounded-sm">
            <div className="text-[#686B65]">Role Authority</div>
            <div className="font-semibold text-[#244C3A] mt-0.5">{user.role}</div>
          </div>
          <div className="p-3 bg-[#F7F6F2] border border-[#DEDDD5] rounded-sm">
            <div className="text-[#686B65]">Token Storage</div>
            <div className="font-semibold text-[#1E563B] mt-0.5">
              In-Memory Only (Zero WebStorage)
            </div>
          </div>
        </div>

        <p className="pt-2 text-xs text-[#686B65]">
          {apiMode === 'live'
            ? 'Live API mode is configured with VITE_API_MODE=live and a FastAPI proxy target.'
            : 'Mock API mode uses in-memory Express fixtures. Set VITE_API_MODE=live to route requests to FastAPI.'}
        </p>
      </div>

      {apiMode === 'live' ? (
        <div className="bg-white border border-[#DEDDD5] rounded-md p-6 space-y-2">
          <h2 className="font-display text-base font-semibold text-[#20241F]">Attestation registry unavailable</h2>
          <p className="text-xs text-[#686B65]">
            The FastAPI backend has no attestation registry or public QR verification route. Its purpose-scoped verification credential API is separate; this demo attestation screen is not presented as live functionality.
          </p>
        </div>
      ) : (
      <>
      {/* Consent-Gated Ed25519 Attestation Issuance & Registry */}
      <div className="bg-white border border-[#DEDDD5] rounded-md p-6 space-y-5">
        <div>
          <h2 className="font-display text-base font-semibold text-[#20241F]">
            Platform-Issued Enrolment Attestations (Ed25519)
          </h2>
          <p className="text-xs text-[#686B65]">
            Issue or revoke signed verification tokens (`/verify/:token`) for consented verified
            students.
          </p>
        </div>

        {statusMsg && (
          <div
            role="status"
            className="p-3 bg-[#1E563B]/10 border border-[#1E563B]/30 rounded-sm text-xs text-[#1E563B]"
          >
            {statusMsg}
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            issueMutation.mutate();
          }}
          className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-end"
        >
          <div className="sm:col-span-5">
            <label
              htmlFor="settings-stu-select"
              className="block text-xs font-medium text-[#20241F] mb-1"
            >
              Consented Verified Student
            </label>
            <select
              id="settings-stu-select"
              value={selectedStudentId}
              onChange={(e) => setSelectedStudentId(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-[#F7F6F2] border border-[#DEDDD5] rounded-md"
            >
              {eligibleStudents.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.full_name} ({s.student_ref} · {s.apaar_masked})
                </option>
              ))}
            </select>
          </div>

          <div className="sm:col-span-5">
            <label
              htmlFor="settings-purpose-input"
              className="block text-xs font-medium text-[#20241F] mb-1"
            >
              Authorized Disclosure Purpose
            </label>
            <input
              id="settings-purpose-input"
              type="text"
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-[#F7F6F2] border border-[#DEDDD5] rounded-md"
            />
          </div>

          <div className="sm:col-span-2">
            <button
              type="submit"
              disabled={issueMutation.isPending || user.role === 'auditor'}
              className="w-full py-2 px-3 text-xs font-medium text-white bg-[#244C3A] hover:bg-[#193B2C] disabled:opacity-45 rounded-md"
            >
              Issue Token
            </button>
          </div>
        </form>

        <div className="divide-y divide-[#DEDDD5] border-t border-[#DEDDD5] pt-2">
          {attestations.map((att) => (
            <div
              key={att.id}
              className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
            >
              <div>
                <div className="font-mono font-semibold text-[#20241F]">
                  {att.id} · {att.student_name} ({att.apaar_masked})
                </div>
                <div className="text-[#686B65] mt-0.5">
                  {att.purpose} · Consent {att.consent_id}
                </div>
              </div>

              <div className="flex items-center gap-3 font-mono shrink-0">
                {att.status === 'ACTIVE' ? (
                  <span className="inline-flex items-center gap-1 text-[#1E563B]">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>ACTIVE</span>
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-[#99322B]">
                    <Ban className="w-3.5 h-3.5" />
                    <span>{att.status}</span>
                  </span>
                )}

                <Link
                  to={`/verify/${att.id.toLowerCase()}`}
                  className="text-[#244C3A] underline font-sans font-medium"
                >
                  Open Public Verifier
                </Link>

                {att.status === 'ACTIVE' && user.role !== 'auditor' && (
                  <button
                    type="button"
                    onClick={() => revokeMutation.mutate(att.id)}
                    className="px-2.5 py-1 text-[11px] font-sans text-[#99322B] border border-[#99322B]/30 rounded-sm hover:bg-[#99322B]/10"
                  >
                    Revoke
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
      </>
      )}
    </div>
  );
};
