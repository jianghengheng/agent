import { create } from 'zustand';

import {
  type ChatMessage,
  type ProcessStep,
  type RunStatus,
  type StepIdentifier,
  type StepStatus,
  createInitialProcessSteps,
} from '../types/workflow';

const WELCOME_MESSAGE: ChatMessage = {
  id: 'welcome-message',
  role: 'assistant',
  content: '你好，我是零售经营助手。你可以直接问我门店经营问题。',
  createdAt: Date.now(),
  status: 'done',
};

type StartConversationInput = {
  prompt: string;
  assistantMessageId: string;
};

type AnswerStreamState = {
  messages: ChatMessage[];
  status: RunStatus;
  statusNote: string;
  backendLabel: string;
  errorMessage: string;
  activeRole: StepIdentifier | null;
  activeAssistantMessageId: string | null;
  processSteps: ProcessStep[];
  startConversationTurn: (input: StartConversationInput) => void;
  prepareRun: (steps: ProcessStep[]) => void;
  updateProcessStep: (
    stepId: StepIdentifier,
    patch: Partial<ProcessStep> & { status?: StepStatus },
  ) => void;
  appendAnswer: (delta: string) => void;
  setStatusNote: (note: string) => void;
  setBackendLabel: (label: string) => void;
  setActiveRole: (role: StepIdentifier | null) => void;
  completeRun: () => void;
  failRun: (message: string) => void;
  clearConversation: () => void;
};

function createUserMessage(prompt: string): ChatMessage {
  return {
    id: `user-${crypto.randomUUID()}`,
    role: 'user',
    content: prompt,
    createdAt: Date.now(),
    status: 'done',
  };
}

function createAssistantPlaceholder(messageId: string): ChatMessage {
  return {
    id: messageId,
    role: 'assistant',
    content: '',
    createdAt: Date.now(),
    status: 'streaming',
  };
}

export const useAnswerStreamStore = create<AnswerStreamState>((set) => ({
  messages: [WELCOME_MESSAGE],
  status: 'idle',
  statusNote: '准备就绪，可以直接发起一轮问答。',
  backendLabel: '未启动',
  errorMessage: '',
  activeRole: null,
  activeAssistantMessageId: null,
  processSteps: createInitialProcessSteps(),
  startConversationTurn: ({ prompt, assistantMessageId }) =>
    set((state) => ({
      messages: [
        ...state.messages,
        createUserMessage(prompt),
        createAssistantPlaceholder(assistantMessageId),
      ],
      activeAssistantMessageId: assistantMessageId,
      status: 'streaming',
      statusNote: '任务已提交，正在建立回答流。',
      backendLabel: '连接中',
      errorMessage: '',
      activeRole: null,
      processSteps: createInitialProcessSteps(),
    })),
  prepareRun: (steps) =>
    set({
      status: 'streaming',
      statusNote: '任务已提交，正在接收工作流进度。',
      backendLabel: '连接中',
      errorMessage: '',
      activeRole: null,
      processSteps: steps,
    }),
  updateProcessStep: (stepId, patch) =>
    set((state) => ({
      processSteps: state.processSteps.map((step) => {
        if (step.id !== stepId) {
          return step;
        }

        return {
          ...step,
          ...patch,
        };
      }),
    })),
  appendAnswer: (delta) =>
    set((state) => {
      if (!state.activeAssistantMessageId) {
        return state;
      }

      return {
        messages: state.messages.map((message) => {
          if (message.id !== state.activeAssistantMessageId) {
            return message;
          }

          return {
            ...message,
            content: `${message.content}${delta}`,
            status: 'streaming',
          };
        }),
      };
    }),
  setStatusNote: (note) => set({ statusNote: note }),
  setBackendLabel: (label) => set({ backendLabel: label }),
  setActiveRole: (role) => set({ activeRole: role }),
  completeRun: () =>
    set((state) => ({
      status: 'completed',
      statusNote: '回答完成，可以继续追问。',
      activeRole: null,
      activeAssistantMessageId: null,
      messages: state.messages.map((message) => {
        if (message.id !== state.activeAssistantMessageId) {
          return message;
        }

        return {
          ...message,
          status: 'done',
        };
      }),
    })),
  failRun: (message) =>
    set((state) => ({
      status: 'failed',
      statusNote: '本轮执行失败。',
      errorMessage: message,
      activeRole: null,
      activeAssistantMessageId: null,
      messages: state.messages.map((item) => {
        if (item.id !== state.activeAssistantMessageId) {
          return item;
        }

        return {
          ...item,
          content: item.content || '本轮回答失败，请重试。',
          status: 'error',
        };
      }),
    })),
  clearConversation: () =>
    set({
      messages: [WELCOME_MESSAGE],
      status: 'idle',
      statusNote: '会话已清空。',
      backendLabel: '未启动',
      errorMessage: '',
      activeRole: null,
      activeAssistantMessageId: null,
      processSteps: createInitialProcessSteps(),
    }),
}));
