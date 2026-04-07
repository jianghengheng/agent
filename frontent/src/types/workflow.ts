export type StepIdentifier = 'parser' | 'data_fetcher';

export type StepStatus = 'pending' | 'running' | 'completed' | 'failed';

export type RunStatus = 'idle' | 'streaming' | 'completed' | 'failed';

export type WorkflowStreamEventName =
  | 'run_started'
  | 'step_started'
  | 'step_completed'
  | 'api_request'
  | 'api_response'
  | 'answer_started'
  | 'answer_delta'
  | 'run_completed'
  | 'error';

export type ApiRequestInfo = {
  url: string;
  method: string;
  headers: Record<string, string>;
  params: Record<string, string | number>;
};

export type ApiResponseInfo = {
  record_count: number;
  records: Record<string, unknown>[];
};

export type ProcessStep = {
  id: StepIdentifier;
  title: string;
  summary: string;
  status: StepStatus;
  detail?: string;
  startedAt?: number;
  endedAt?: number;
  apiRequest?: ApiRequestInfo;
  apiResponse?: ApiResponseInfo;
};

export type ChatMessageRole = 'user' | 'assistant' | 'system';

export type ChatMessage = {
  id: string;
  role: ChatMessageRole;
  content: string;
  createdAt: number;
  status?: 'streaming' | 'done' | 'error';
};

export type WorkflowApiMessage = {
  role: ChatMessageRole;
  content: string;
};

export type WorkflowApiRequest = {
  task: string;
  context: string;
  messages: WorkflowApiMessage[];
  max_revisions: number;
};

export type WorkflowApiResponse = {
  backend: string;
  approved: boolean;
  revision_count: number;
  plan: string;
  research: string;
  critique: string;
  final_answer: string;
  trace: string[];
};

export type WorkflowStreamEvent = {
  event: WorkflowStreamEventName;
  data: Record<string, unknown>;
};

export function createInitialProcessSteps(): ProcessStep[] {
  return [
    {
      id: 'parser',
      title: 'Parser',
      summary: '识别问句类型并抽取店铺、指标、时间范围',
      status: 'pending',
    },
    {
      id: 'data_fetcher',
      title: 'Data Fetcher',
      summary: '调用经营数据接口获取真实数据并分析',
      status: 'pending',
    },
  ];
}
