import type { RunStatus, StepIdentifier } from '../types/workflow';

type StreamAnswerPanelProperties = {
  answerText: string;
  status: RunStatus;
  statusNote: string;
  backendLabel: string;
  activeRole: StepIdentifier | null;
  errorMessage: string;
};

function getRoleLabel(activeRole: StepIdentifier | null) {
  if (!activeRole) {
    return '待命';
  }

  return activeRole;
}

export function StreamAnswerPanel({
  answerText,
  status,
  statusNote,
  backendLabel,
  activeRole,
  errorMessage,
}: StreamAnswerPanelProperties) {
  const isStreaming = status === 'streaming';

  return (
    <section className="panel-surface rounded-[28px] border border-white/70 p-6">
      <div className="flex flex-col gap-4 border-b border-slate-200/70 pb-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Answer Stream</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">最终回答</h2>
        </div>

        <div className="flex flex-wrap gap-2">
          <span className="rounded-full bg-slate-900 px-3 py-1 text-xs text-white">
            {backendLabel}
          </span>
          <span className="rounded-full bg-teal-50 px-3 py-1 text-xs text-teal-700">
            当前角色 {getRoleLabel(activeRole)}
          </span>
        </div>
      </div>

      <div className="mt-5 rounded-[24px] bg-slate-950 p-5 text-sm text-slate-100 shadow-inner">
        {answerText ? (
          <div className="min-h-[280px] whitespace-pre-wrap leading-7">
            {answerText}
            {isStreaming ? <span className="streaming-cursor ml-1" /> : null}
          </div>
        ) : (
          <div className="flex min-h-[280px] flex-col justify-center text-slate-400">
            <p className="text-base text-slate-200">回答尚未开始输出</p>
            <p className="mt-2 text-sm">点击左侧“开始回答”后，这里会按流式块逐步展示最终答案。</p>
          </div>
        )}
      </div>

      <div className="mt-5 flex flex-col gap-3 rounded-[24px] border border-slate-200 bg-white/70 p-4">
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm font-medium text-slate-800">运行状态</span>
          <span
            className={`rounded-full px-3 py-1 text-xs ${
              status === 'completed'
                ? 'bg-emerald-50 text-emerald-700'
                : status === 'failed'
                  ? 'bg-rose-50 text-rose-700'
                  : status === 'streaming'
                    ? 'bg-orange-50 text-orange-700'
                    : 'bg-slate-100 text-slate-600'
            }`}
          >
            {status}
          </span>
        </div>

        <p className="text-sm leading-6 text-slate-600">{statusNote}</p>

        {errorMessage ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {errorMessage}
          </div>
        ) : null}
      </div>
    </section>
  );
}
