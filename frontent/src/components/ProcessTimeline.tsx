import type { ProcessStep } from '../types/workflow';

type ProcessTimelineProperties = {
  processSteps: ProcessStep[];
};

function getStatusClassName(status: ProcessStep['status']) {
  if (status === 'completed') {
    return 'bg-emerald-500 ring-emerald-100';
  }

  if (status === 'running') {
    return 'bg-orange-500 ring-orange-100';
  }

  if (status === 'failed') {
    return 'bg-rose-500 ring-rose-100';
  }

  return 'bg-slate-300 ring-slate-100';
}

function getStatusLabel(status: ProcessStep['status']) {
  if (status === 'completed') {
    return '已完成';
  }

  if (status === 'running') {
    return '进行中';
  }

  if (status === 'failed') {
    return '失败';
  }

  return '待执行';
}

export function ProcessTimeline({ processSteps }: ProcessTimelineProperties) {
  return (
    <section className="panel-surface rounded-[28px] border border-white/70 p-6">
      <div className="flex items-center justify-between gap-3 border-b border-slate-200/70 pb-5">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Execution Trace</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">回答过程</h2>
        </div>

        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
          {processSteps.length} 个阶段
        </span>
      </div>

      <div className="mt-6 space-y-4">
        {processSteps.map((step, index) => (
          <div
            key={step.id}
            className="relative rounded-[24px] border border-slate-200 bg-white/75 p-4"
          >
            {index < processSteps.length - 1 ? (
              <div className="absolute left-[27px] top-[54px] h-[calc(100%-18px)] w-px bg-slate-200" />
            ) : null}

            <div className="relative flex gap-4">
              <div
                className={`mt-1 h-4 w-4 shrink-0 rounded-full ring-8 ${getStatusClassName(step.status)}`}
              />

              <div className="min-w-0 flex-1">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h3 className="text-base font-semibold text-slate-900">{step.title}</h3>
                    <p className="text-sm text-slate-500">{step.summary}</p>
                  </div>

                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                    {getStatusLabel(step.status)}
                  </span>
                </div>

                <p className="mt-3 text-sm leading-6 text-slate-700">
                  {step.detail ?? '等待执行到该阶段。'}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
