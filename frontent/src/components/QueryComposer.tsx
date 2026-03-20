type QueryComposerProperties = {
  prompt: string;
  context: string;
  maxRevisions: number;
  isRunning: boolean;
  onPromptChange: (value: string) => void;
  onContextChange: (value: string) => void;
  onMaxRevisionsChange: (value: number) => void;
  onStartRun: () => void;
  onResetConversation: () => void;
  onApplyTemplate: (value: string) => void;
};

const templates = [
  '设计一个企业内部知识库问答系统的 MVP 方案',
  '给出一个多智能体客服系统的前后端拆分设计',
  '为 LangGraph 工作流设计一套可观测性与回放方案',
];

export function QueryComposer({
  prompt,
  context,
  maxRevisions,
  isRunning,
  onPromptChange,
  onContextChange,
  onMaxRevisionsChange,
  onStartRun,
  onResetConversation,
  onApplyTemplate,
}: QueryComposerProperties) {
  return (
    <section className="panel-surface mesh-grid relative overflow-hidden rounded-[28px] border border-white/70 p-6 text-slate-900">
      <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-orange-400 via-amber-300 to-teal-500" />

      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Orchestration Panel</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">回答流页面</h1>
        </div>

        <div className="rounded-full border border-orange-200 bg-orange-50 px-3 py-1 text-xs text-orange-700">
          React + Zustand + Tailwind
        </div>
      </div>

      <div className="space-y-5">
        <label className="block">
          <span className="mb-2 block text-sm font-medium text-slate-700">问题</span>
          <textarea
            className="h-36 w-full resize-none rounded-2xl border border-slate-200 bg-white/85 px-4 py-3 text-sm text-slate-900 shadow-sm outline-none transition focus:border-orange-300 focus:ring-4 focus:ring-orange-100"
            value={prompt}
            onChange={(event) => onPromptChange(event.target.value)}
            placeholder="输入你想让多智能体系统回答的问题"
          />
        </label>

        <label className="block">
          <span className="mb-2 block text-sm font-medium text-slate-700">业务上下文</span>
          <textarea
            className="h-28 w-full resize-none rounded-2xl border border-slate-200 bg-white/85 px-4 py-3 text-sm text-slate-900 shadow-sm outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
            value={context}
            onChange={(event) => onContextChange(event.target.value)}
            placeholder="补充背景、约束、优先级或已有系统"
          />
        </label>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-slate-700">最大返工次数</span>
            <select
              className="w-full rounded-2xl border border-slate-200 bg-white/85 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-orange-300 focus:ring-4 focus:ring-orange-100"
              value={maxRevisions}
              onChange={(event) => onMaxRevisionsChange(Number(event.target.value))}
            >
              {[0, 1, 2, 3].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div>
          <p className="mb-3 text-sm font-medium text-slate-700">快速模板</p>
          <div className="flex flex-wrap gap-2">
            {templates.map((template) => (
              <button
                key={template}
                type="button"
                className="rounded-full border border-slate-200 bg-white/75 px-3 py-2 text-xs text-slate-700 transition hover:border-orange-300 hover:bg-orange-50 hover:text-orange-700"
                onClick={() => onApplyTemplate(template)}
              >
                {template}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-3 pt-2 sm:flex-row">
          <button
            type="button"
            className="inline-flex flex-1 items-center justify-center rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            disabled={isRunning || !prompt.trim()}
            onClick={onStartRun}
          >
            {isRunning ? '回答进行中...' : '开始回答'}
          </button>

          <button
            type="button"
            className="inline-flex items-center justify-center rounded-2xl border border-slate-200 bg-white/80 px-4 py-3 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:bg-white"
            onClick={onResetConversation}
          >
            重置
          </button>
        </div>
      </div>
    </section>
  );
}
