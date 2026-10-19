"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  finalizeConversation,
  getConversationHistory,
  listConversations,
  streamChat,
} from "@/lib/chat";

import type {
  BlockEventData,
  ChatMessage,
  ConversationEventData,
  ConversationSummary,
  DoneEventData,
  ErrorEventData,
  MessageDeltaEventData,
  MessageStartEventData,
} from "@/lib/chat-types";


function temporaryId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}


function getErrorMessage(
  caught: unknown,
  fallback: string
): string {
  if (caught instanceof Error) {
    return caught.message;
  }

  return fallback;
}


export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const [conversationId, setConversationId] = useState<string | null>(
    null
  );

  const [conversations, setConversations] = useState<
    ConversationSummary[]
  >([]);

  const [isSending, setIsSending] = useState(false);

  const [isHistoryLoading, setIsHistoryLoading] = useState(false);

  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);


  const refreshConversations = useCallback(async () => {
    try {
      const result = await listConversations();

      setConversations(result.conversations);
    } catch {
      /*
       * Conversation history is supplemental.
       * A history-loading failure must not block
       * normal Retailigent chat functionality.
       */
    }
  }, []);


  useEffect(() => {
    queueMicrotask(() => {
      void refreshConversations();
    });
  }, [refreshConversations]);


  const updateAssistantMessage = useCallback(
    (
      messageId: string,
      updater: (current: ChatMessage) => ChatMessage
    ) => {
      setMessages((currentMessages) =>
        currentMessages.map((message) => {
          if (message.id !== messageId) {
            return message;
          }

          return updater(message);
        })
      );
    },
    []
  );


  const sendMessage = useCallback(
    async (rawMessage: string) => {
      const message = rawMessage.trim();

      if (!message || isSending || isHistoryLoading) {
        return;
      }

      setError(null);
      setIsSending(true);

      const controller = new AbortController();

      abortRef.current = controller;

      const userMessage: ChatMessage = {
        id: temporaryId("user"),
        role: "user",
        content: message,
        blocks: [],
      };

      setMessages((current) => [
        ...current,
        userMessage,
      ]);

      let activeAssistantId: string | null = null;

      try {
        await streamChat({
          message,
          conversationId,
          signal: controller.signal,

          onEvent: (streamEvent) => {
            switch (streamEvent.event) {
              case "turn_started":
                break;

              case "conversation": {
                const data =
                  streamEvent.data as ConversationEventData;

                setConversationId(
                  data.conversation_id
                );

                break;
              }

              case "message_start": {
                const data =
                  streamEvent.data as MessageStartEventData;

                activeAssistantId = data.message_id;

                const assistantMessage: ChatMessage = {
                  id: data.message_id,
                  role: "assistant",
                  content: "",
                  language: data.language,
                  blocks: [],
                  isStreaming: true,
                };

                setMessages((current) => [
                  ...current,
                  assistantMessage,
                ]);

                break;
              }

              case "message_delta": {
                const data =
                  streamEvent.data as MessageDeltaEventData;

                updateAssistantMessage(
                  data.message_id,
                  (current) => ({
                    ...current,
                    content:
                      current.content + data.delta,
                  })
                );

                break;
              }

              case "block": {
                const data =
                  streamEvent.data as BlockEventData;

                updateAssistantMessage(
                  data.message_id,
                  (current) => ({
                    ...current,
                    blocks: [
                      ...current.blocks,
                      data.block,
                    ],
                  })
                );

                break;
              }

              case "done": {
                const data =
                  streamEvent.data as DoneEventData;

                setConversationId(
                  data.conversation_id
                );

                updateAssistantMessage(
                  data.message_id,
                  (current) => ({
                    ...current,
                    isStreaming: false,
                  })
                );

                break;
              }

              case "error": {
                const data =
                  streamEvent.data as ErrorEventData;

                setError(data.message);

                if (activeAssistantId) {
                  updateAssistantMessage(
                    activeAssistantId,
                    (current) => ({
                      ...current,
                      isStreaming: false,
                    })
                  );
                }

                break;
              }

              default:
                break;
            }
          },
        });

        void refreshConversations();
      } catch (caught) {
        if (
          caught instanceof DOMException &&
          caught.name === "AbortError"
        ) {
          return;
        }

        setError(
          getErrorMessage(
            caught,
            "Chat request failed."
          )
        );

        if (activeAssistantId) {
          updateAssistantMessage(
            activeAssistantId,
            (current) => ({
              ...current,
              isStreaming: false,
            })
          );
        }
      } finally {
        setIsSending(false);

        if (abortRef.current === controller) {
          abortRef.current = null;
        }
      }
    },
    [
      conversationId,
      isHistoryLoading,
      isSending,
      refreshConversations,
      updateAssistantMessage,
    ]
  );


  const stop = useCallback(() => {
    abortRef.current?.abort();

    abortRef.current = null;

    setIsSending(false);
  }, []);


  const newConversation = useCallback(
    async (): Promise<boolean> => {
      abortRef.current?.abort();

      abortRef.current = null;

      setError(null);
      setIsHistoryLoading(true);

      try {
        if (conversationId) {
          await finalizeConversation(
            conversationId
          );
        }

        setConversationId(null);
        setMessages([]);

        await refreshConversations();

        return true;
      } catch (caught) {
        setError(
          getErrorMessage(
            caught,
            "The current conversation could not be finalized."
          )
        );

        return false;
      } finally {
        setIsHistoryLoading(false);
      }
    },
    [
      conversationId,
      refreshConversations,
    ]
  );


  const loadConversation = useCallback(
    async (
      targetConversationId: string
    ): Promise<void> => {
      if (
        targetConversationId === conversationId
      ) {
        return;
      }

      abortRef.current?.abort();

      abortRef.current = null;

      setError(null);
      setIsHistoryLoading(true);

      try {
        /*
         * Leaving the currently active conversation
         * finalizes its durable memory first.
         */
        if (conversationId) {
          await finalizeConversation(
            conversationId
          );
        }

        const history =
          await getConversationHistory(
            targetConversationId
          );

        setConversationId(
          history.conversation.id
        );

        setMessages(
          history.messages.map(
            (message) => ({
              ...message,
              isStreaming: false,
            })
          )
        );

        await refreshConversations();
      } catch (caught) {
        setError(
          getErrorMessage(
            caught,
            "Conversation could not be opened."
          )
        );
      } finally {
        setIsHistoryLoading(false);
      }
    },
    [
      conversationId,
      refreshConversations,
    ]
  );


  return {
    messages,
    conversationId,
    conversations,
    isSending,
    isHistoryLoading,
    error,
    sendMessage,
    stop,
    newConversation,
    loadConversation,
    refreshConversations,
  };
}