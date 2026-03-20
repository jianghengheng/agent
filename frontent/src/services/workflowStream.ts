import {
  type StepIdentifier,
  type WorkflowApiMessage,
  type WorkflowApiRequest,
  type WorkflowApiResponse,
  type WorkflowStreamEvent,
  createInitialProcessSteps,
} from '../types/workflow';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
const ONLY_STEP: StepIdentifier = 'parser';

type RunWorkflowStreamInput = {
  task: string;
  context: string;
  messages: WorkflowApiMessage[];
  maxRevisions: number;
  signal: AbortSignal;
};

type RunWorkflowStreamHandlers = {
  onPrepare: ReturnType<typeof createInitialProcessSteps> extends infer StepList
    ? (steps: StepList) => void
    : never;
  onStatusNote: (note: string) => void;
  onBackendLabel: (label: string) => void;
  onActiveRole: (role: StepIdentifier | null) => void;
  onStepChange: (
    stepId: StepIdentifier,
    patch: {
      detail?: string;
      endedAt?: number;
      startedAt?: number;
      status?: 'pending' | 'running' | 'completed' | 'failed';
    },
  ) => void;
  onAnswerDelta: (delta: string) => void;
  onComplete: () => void;
  onError: (message: string) => void;
};

function ensureNotAborted(signal: AbortSignal) {
  if (signal.aborted) {
    throw new DOMException('The operation was aborted.', 'AbortError');
  }
}

function createWorkflowRequest(
  task: string,
  context: string,
  messages: WorkflowApiMessage[],
  maxRevisions: number,
): WorkflowApiRequest {
  return {
    task,
    context,
    messages,
    max_revisions: maxRevisions,
  };
}

function isStepIdentifier(value: unknown): value is StepIdentifier {
  return value === ONLY_STEP;
}

function parseSseEventBlock(rawBlock: string): WorkflowStreamEvent | null {
  const normalizedBlock = rawBlock.trim();
  if (!normalizedBlock) {
    return null;
  }

  let eventName = '';
  const dataLines: string[] = [];

  for (const line of normalizedBlock.split('\n')) {
    if (line.startsWith('event:')) {
      eventName = line.slice('event:'.length).trim();
      continue;
    }

    if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trim());
    }
  }

  if (!eventName || dataLines.length === 0) {
    return null;
  }

  return {
    event: eventName as WorkflowStreamEvent['event'],
    data: JSON.parse(dataLines.join('\n')) as Record<string, unknown>,
  };
}

function getStepCompletedDetail(data: Record<string, unknown>) {
  const traceEntry = typeof data.trace_entry === 'string' ? data.trace_entry : '';
  return traceEntry || '问题解析完成，开始输出 Markdown 回答。';
}

function applyServerEvent(
  event: WorkflowStreamEvent,
  handlers: RunWorkflowStreamHandlers,
): WorkflowApiResponse | null {
  if (event.event === 'run_started') {
    const backend = typeof event.data.backend === 'string' ? event.data.backend : 'unknown';
    handlers.onBackendLabel(`SSE / ${backend}`);
    handlers.onStatusNote('已建立 SSE 连接，正在解析用户问题。');
    return null;
  }

  if (event.event === 'step_started') {
    const stepId = event.data.step;

    if (isStepIdentifier(stepId)) {
      handlers.onActiveRole(stepId);
      handlers.onStepChange(stepId, {
        status: 'running',
        detail: '正在识别问句类型并抽取关键词。',
        startedAt: Date.now(),
      });
      handlers.onStatusNote('Parser 正在解析问题。');
    }
    return null;
  }

  if (event.event === 'step_completed') {
    const stepId = event.data.step;

    if (isStepIdentifier(stepId)) {
      handlers.onStepChange(stepId, {
        status: 'completed',
        detail: getStepCompletedDetail(event.data),
        endedAt: Date.now(),
      });
      handlers.onStatusNote('问题解析完成，准备输出回答。');
    }
    return null;
  }

  if (event.event === 'answer_delta') {
    const delta = typeof event.data.delta === 'string' ? event.data.delta : '';
    if (delta) {
      handlers.onActiveRole(ONLY_STEP);
      handlers.onStepChange(ONLY_STEP, {
        status: 'running',
        detail: '正在流式输出 Markdown 回答。',
        startedAt: Date.now(),
      });
      handlers.onAnswerDelta(delta);
      handlers.onStatusNote('Markdown 回答输出中。');
    }
    return null;
  }

  if (event.event === 'run_completed') {
    const response = event.data.response;
    if (response && typeof response === 'object') {
      const payload = response as WorkflowApiResponse;
      handlers.onBackendLabel(`SSE / ${payload.backend}`);
      handlers.onActiveRole(null);
      handlers.onStepChange(ONLY_STEP, {
        status: 'completed',
        detail: '本轮解析与回答已完成。',
        endedAt: Date.now(),
      });
      handlers.onStatusNote('接口流已完成。');
      return payload;
    }

    throw new Error('SSE 完成事件缺少响应内容。');
  }

  if (event.event === 'error') {
    const message =
      typeof event.data.message === 'string' ? event.data.message : 'SSE 流执行失败。';
    throw new Error(message);
  }

  return null;
}

async function runApiWorkflowStream(
  input: RunWorkflowStreamInput,
  handlers: RunWorkflowStreamHandlers,
) {
  const steps = createInitialProcessSteps();
  handlers.onPrepare(steps);
  handlers.onBackendLabel('SSE connecting');
  handlers.onStatusNote('正在建立 SSE 连接。');

  const request = createWorkflowRequest(
    input.task,
    input.context,
    input.messages,
    input.maxRevisions,
  );

  const response = await fetch(`${API_BASE_URL}/api/v1/workflows/multi-agent/stream`, {
    method: 'POST',
    headers: {
      Accept: 'text/event-stream',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
    signal: input.signal,
  });

  if (!response.ok) {
    throw new Error(`SSE 接口请求失败，状态码 ${response.status}`);
  }

  if (!response.body) {
    throw new Error('SSE 响应没有可读取的数据流。');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResponse: WorkflowApiResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    ensureNotAborted(input.signal);
    buffer += decoder.decode(value, { stream: true }).replaceAll('\r', '');

    while (true) {
      const boundaryIndex = buffer.indexOf('\n\n');
      if (boundaryIndex < 0) {
        break;
      }

      const rawBlock = buffer.slice(0, boundaryIndex);
      buffer = buffer.slice(boundaryIndex + 2);

      const event = parseSseEventBlock(rawBlock);
      if (!event) {
        continue;
      }

      const completedPayload = applyServerEvent(event, handlers);
      if (completedPayload) {
        finalResponse = completedPayload;
      }
    }
  }

  buffer += decoder.decode().replaceAll('\r', '');
  if (buffer.trim()) {
    const lastEvent = parseSseEventBlock(buffer);
    if (lastEvent) {
      const completedPayload = applyServerEvent(lastEvent, handlers);
      if (completedPayload) {
        finalResponse = completedPayload;
      }
    }
  }

  if (!finalResponse) {
    throw new Error('SSE 连接在完成前已关闭。');
  }

  handlers.onComplete();
}

export async function runWorkflowStream(
  input: RunWorkflowStreamInput,
  handlers: RunWorkflowStreamHandlers,
) {
  try {
    await runApiWorkflowStream(input, handlers);
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      return;
    }

    const message = error instanceof Error ? error.message : '回答流执行失败。';
    handlers.onError(message);
  }
}
