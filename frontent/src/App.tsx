import { MessageOutlined, RobotOutlined, SyncOutlined, UserOutlined } from '@ant-design/icons';
import { Bubble, type BubbleItemType, Sender } from '@ant-design/x';
import { XMarkdown } from '@ant-design/x-markdown';
import { Avatar, Button, Card, ConfigProvider, Space, Tag, Typography } from 'antd';
import { useEffect, useMemo, useRef, useState } from 'react';

import { runWorkflowStream } from './services/workflowStream';
import { useAnswerStreamStore } from './stores/answerStreamStore';
import type { ChatMessage, WorkflowApiMessage } from './types/workflow';

const quickPrompts = [
  '星河店这周的销售额怎么样',
  '南京东路店上周营业额是多少',
];

function formatTime(timestamp: number) {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(timestamp);
}

function getStepTagColor(status: 'pending' | 'running' | 'completed' | 'failed') {
  if (status === 'completed') {
    return 'success';
  }

  if (status === 'running') {
    return 'processing';
  }

  if (status === 'failed') {
    return 'error';
  }

  return 'default';
}

function toConversationHistory(
  messages: ChatMessage[],
  currentPrompt: string,
): WorkflowApiMessage[] {
  return messages
    .filter((message) => message.id !== 'welcome-message')
    .filter((message) => message.status !== 'streaming')
    .filter((message) => message.content.trim())
    .filter((message) => !(message.role === 'user' && message.content.trim() === currentPrompt))
    .map((message) => ({
      role: message.role,
      content: message.content.trim(),
    }));
}

export default function App() {
  const abortControllerReference = useRef<AbortController | null>(null);
  const [draft, setDraft] = useState('');

  const messages = useAnswerStreamStore((state) => state.messages);
  const status = useAnswerStreamStore((state) => state.status);
  const statusNote = useAnswerStreamStore((state) => state.statusNote);
  const backendLabel = useAnswerStreamStore((state) => state.backendLabel);
  const errorMessage = useAnswerStreamStore((state) => state.errorMessage);
  const activeRole = useAnswerStreamStore((state) => state.activeRole);
  const processSteps = useAnswerStreamStore((state) => state.processSteps);

  const startConversationTurn = useAnswerStreamStore((state) => state.startConversationTurn);
  const prepareRun = useAnswerStreamStore((state) => state.prepareRun);
  const updateProcessStep = useAnswerStreamStore((state) => state.updateProcessStep);
  const appendAnswer = useAnswerStreamStore((state) => state.appendAnswer);
  const setStatusNote = useAnswerStreamStore((state) => state.setStatusNote);
  const setBackendLabel = useAnswerStreamStore((state) => state.setBackendLabel);
  const setActiveRole = useAnswerStreamStore((state) => state.setActiveRole);
  const completeRun = useAnswerStreamStore((state) => state.completeRun);
  const failRun = useAnswerStreamStore((state) => state.failRun);
  const clearConversation = useAnswerStreamStore((state) => state.clearConversation);

  useEffect(() => {
    return () => {
      abortControllerReference.current?.abort();
    };
  }, []);

  const bubbleItems = useMemo<BubbleItemType[]>(() => {
    return messages.map((message) => ({
      key: message.id,
      role: message.role === 'assistant' ? 'ai' : message.role === 'system' ? 'system' : 'user',
      content:
        message.role === 'assistant' ? (
          <XMarkdown
            className="chat-markdown"
            content={message.content}
            streaming={{
              enableAnimation: true,
              hasNextChunk: message.status === 'streaming',
              tail: message.status === 'streaming',
            }}
          />
        ) : (
          message.content || '暂无内容'
        ),
      placement: message.role === 'user' ? 'end' : 'start',
      loading: message.role === 'assistant' && message.status === 'streaming' && !message.content,
      footer:
        message.status === 'streaming' ? null : (
          <span className="chat-message__meta">{formatTime(message.createdAt)}</span>
        ),
    }));
  }, [messages]);

  const bubbleRoles = useMemo(() => {
    return {
      ai: {
        placement: 'start' as const,
        avatar: <Avatar className="chat-avatar chat-avatar--assistant" icon={<RobotOutlined />} />,
      },
      user: {
        placement: 'end' as const,
        avatar: <Avatar className="chat-avatar chat-avatar--user" icon={<UserOutlined />} />,
      },
      system: {
        placement: 'start' as const,
        variant: 'borderless' as const,
        avatar: <Avatar className="chat-avatar chat-avatar--system" icon={<MessageOutlined />} />,
      },
    };
  }, []);

  const handleSubmit = async (value: string) => {
    const prompt = value.trim();
    if (!prompt) {
      failRun('问题不能为空。');
      return;
    }

    abortControllerReference.current?.abort();

    const controller = new AbortController();
    abortControllerReference.current = controller;

    const assistantMessageId = `assistant-${crypto.randomUUID()}`;
    const conversationHistory = toConversationHistory(messages, prompt);
    setDraft('');
    startConversationTurn({
      prompt,
      assistantMessageId,
    });

    await runWorkflowStream(
      {
        task: prompt,
        context: '',
        messages: conversationHistory,
        maxRevisions: 1,
        signal: controller.signal,
      },
      {
        onPrepare: (steps) => prepareRun(steps),
        onStatusNote: setStatusNote,
        onBackendLabel: setBackendLabel,
        onActiveRole: setActiveRole,
        onStepChange: updateProcessStep,
        onAnswerDelta: appendAnswer,
        onComplete: completeRun,
        onError: failRun,
      },
    );
  };

  const handleClearConversation = () => {
    abortControllerReference.current?.abort();
    clearConversation();
  };

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#1677ff',
          colorBgBase: '#f5f8fc',
          colorTextBase: '#102033',
          fontFamily:
            "'IBM Plex Sans', 'PingFang SC', 'Hiragino Sans GB', 'Noto Sans SC', sans-serif",
          borderRadius: 18,
        },
      }}
    >
      <main className="chat-shell">
        <div className="chat-shell__noise" />

        <div className="chat-shell__container">
          <header className="chat-header">
    

            <Space size={[8, 8]} wrap>
              <Tag
                color={
                  status === 'streaming' ? 'processing' : status === 'failed' ? 'error' : 'default'
                }
              >
                状态 {status}
              </Tag>
              <Tag color="blue">{backendLabel}</Tag>
              <Button onClick={handleClearConversation}>清空会话</Button>
            </Space>
          </header>

          <Card className="chat-process-card">
            <div className="chat-process-card__header">
              <div>
                <Typography.Text strong>当前过程</Typography.Text>
                <Typography.Paragraph className="chat-process-card__note">
                  {statusNote}
                </Typography.Paragraph>
              </div>
              <Tag
                icon={<SyncOutlined spin={status === 'streaming'} />}
                color={status === 'streaming' ? 'processing' : 'default'}
              >
                {activeRole ?? '待命'}
              </Tag>
            </div>

            <div className="chat-process-card__steps">
              {processSteps.map((step) => (
                <div key={step.id} className="chat-process-step">
                  <Space size={8} wrap>
                    <Tag color={getStepTagColor(step.status)}>{step.title}</Tag>
                    <Typography.Text className="chat-process-step__summary">
                      {step.detail ?? step.summary}
                    </Typography.Text>
                  </Space>
                </div>
              ))}
            </div>

            {errorMessage ? <div className="chat-error-banner">{errorMessage}</div> : null}
          </Card>

          <section className="chat-thread">
            <Bubble.List
              autoScroll
              className="chat-thread__list"
              items={bubbleItems}
              role={bubbleRoles}
            />
          </section>


          <footer className="chat-composer">
            <Sender
              autoSize={{ minRows: 1, maxRows: 6 }}
              className="chat-composer__sender"
              loading={status === 'streaming'}
              onCancel={() => {
                abortControllerReference.current?.abort();
                failRun('本轮回答已取消。');
              }}
              onChange={(value) => {
                setDraft(value);
              }}
              onSubmit={(message) => {
                void handleSubmit(message);
              }}
              placeholder="输入你的问题，按 Enter 发送，Shift + Enter 换行"
              value={draft}
            />
          </footer>

          <div className="chat-quick-prompts">
            {quickPrompts.map((prompt) => (
              <button
                key={prompt}
                className="chat-quick-prompts__item"
                onClick={() => {
                  setDraft(prompt);
                }}
                type="button"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      </main>
    </ConfigProvider>
  );
}
