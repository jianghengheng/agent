import { useState } from 'react';

import type { ApiRequestInfo, ApiResponseInfo, ProcessStep } from '../types/workflow';

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

function ApiRequestPanel({ request }: { request: ApiRequestInfo }) {
  const queryString = Object.entries(request.params)
    .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
    .join('&');
  const fullUrl = `${request.url}?${queryString}`;

  return (
    <div className="mt-3 rounded-xl border border-blue-200 bg-blue-50/60 p-3">
      <div className="flex items-center gap-2">
        <span className="rounded bg-blue-600 px-2 py-0.5 text-[10px] font-bold uppercase text-white">
          {request.method}
        </span>
        <span className="text-xs font-semibold text-blue-900">请求参数</span>
      </div>

      <div className="mt-2 break-all rounded-lg bg-white/80 p-2 font-mono text-xs text-slate-700">
        {fullUrl}
      </div>

      <div className="mt-2">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-blue-700">Headers</p>
        <div className="mt-1 rounded-lg bg-white/80 p-2 font-mono text-xs text-slate-600">
          {Object.entries(request.headers).map(([key, value]) => (
            <div key={key}>
              <span className="text-slate-500">{key}:</span> {value}
            </div>
          ))}
        </div>
      </div>

      <div className="mt-2">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-blue-700">Query Params</p>
        <div className="mt-1 rounded-lg bg-white/80 p-2 font-mono text-xs text-slate-600">
          {Object.entries(request.params).map(([key, value]) => (
            <div key={key}>
              <span className="text-slate-500">{key}:</span> {String(value)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ApiResponsePanel({ response }: { response: ApiResponseInfo }) {
  const [expanded, setExpanded] = useState(false);
  const displayRecords = expanded ? response.records : response.records.slice(0, 3);

  return (
    <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50/60 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="rounded bg-emerald-600 px-2 py-0.5 text-[10px] font-bold uppercase text-white">
            200
          </span>
          <span className="text-xs font-semibold text-emerald-900">
            返回数据 · {response.record_count} 条记录
          </span>
        </div>
        {response.records.length > 3 && (
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-emerald-700 hover:text-emerald-900 underline"
          >
            {expanded ? '收起' : `展开全部 ${response.records.length} 条`}
          </button>
        )}
      </div>

      <div className="mt-2 max-h-[400px] overflow-auto rounded-lg bg-white/80 p-2">
        {displayRecords.map((record, index) => (
          <div key={index} className="border-b border-slate-100 py-2 last:border-b-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-mono text-slate-600">
                #{index + 1}
              </span>
              <span className="text-xs font-semibold text-slate-800">
                {String(record.columnName ?? '未知')}
              </span>
              <span className="text-[10px] text-slate-400">
                {String(record.columnType ?? '')}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-[11px] text-slate-600">
              <div>
                <span className="text-slate-400">销售额:</span>{' '}
                <span className="text-slate-800">{String(record.salesAmount ?? '-')}</span>
                {record.salesAmountGrowthRate != null && (
                  <span className={Number(record.salesAmountGrowthRate) >= 0 ? 'text-emerald-600' : 'text-rose-600'}>
                    {' '}({Number(record.salesAmountGrowthRate) >= 0 ? '+' : ''}{String(record.salesAmountGrowthRate)}%)
                  </span>
                )}
              </div>
              <div>
                <span className="text-slate-400">毛利:</span>{' '}
                <span className="text-slate-800">{String(record.netProfit ?? '-')}</span>
                {record.netProfitGrowthRate != null && (
                  <span className={Number(record.netProfitGrowthRate) >= 0 ? 'text-emerald-600' : 'text-rose-600'}>
                    {' '}({Number(record.netProfitGrowthRate) >= 0 ? '+' : ''}{String(record.netProfitGrowthRate)}%)
                  </span>
                )}
              </div>
              <div>
                <span className="text-slate-400">会员销额:</span>{' '}
                {String(record.salesAmountMember ?? '-')}
              </div>
              <div>
                <span className="text-slate-400">活跃会员:</span>{' '}
                {String(record.activeMemberCount ?? '-')}
              </div>
              <div>
                <span className="text-slate-400">新增会员:</span>{' '}
                {String(record.newMemberCount ?? '-')}
              </div>
              <div>
                <span className="text-slate-400">人效:</span>{' '}
                {String(record.salesAmountPerStaff ?? '-')}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
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

                {step.apiRequest && <ApiRequestPanel request={step.apiRequest} />}
                {step.apiResponse && <ApiResponsePanel response={step.apiResponse} />}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
