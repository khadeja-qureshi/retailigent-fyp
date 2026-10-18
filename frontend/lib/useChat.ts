"use client";

import {
  useCallback,
  useRef,
  useState,
} from "react";

import {
  streamChat,
} from "@/lib/chat";

import type {
  BlockEventData,
  ChatMessage,
  ConversationEventData,
  DoneEventData,
  ErrorEventData,
  MessageDeltaEventData,
  MessageStartEventData,
} from "@/lib/chat-types";


function temporaryId(
  prefix: string
) {
  return (
    `${prefix}-` +
    crypto.randomUUID()
  );
}


export function useChat() {
  const [
    messages,
    setMessages,
  ] = useState<ChatMessage[]>([]);

  const [
    conversationId,
    setConversationId,
  ] = useState<string | null>(
    null
  );

  const [
    isSending,
    setIsSending,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(
    null
  );

  const abortRef =
    useRef<AbortController | null>(
      null
    );


  const updateAssistantMessage =
    useCallback(
      (
        messageId: string,
        updater: (
          current: ChatMessage
        ) => ChatMessage
      ) => {
        setMessages(
          (currentMessages) =>
            currentMessages.map(
              (message) =>
                message.id ===
                messageId
                  ? updater(message)
                  : message
            )
        );
      },
      []
    );


  const sendMessage =
    useCallback(
      async (
        rawMessage: string
      ) => {
        const message =
          rawMessage.trim();

        if (
          !message ||
          isSending
        ) {
          return;
        }

        setError(null);
        setIsSending(true);

        const controller =
          new AbortController();

        abortRef.current =
          controller;

        const userMessage: ChatMessage =
          {
            id: temporaryId(
              "user"
            ),
            role: "user",
            content: message,
            blocks: [],
          };

        setMessages(
          (current) => [
            ...current,
            userMessage,
          ]
        );

        let activeAssistantId:
          | string
          | null = null;

        try {
          await streamChat({
            message,

            conversationId,

            signal:
              controller.signal,

            onEvent: (
              streamEvent
            ) => {
              switch (
                streamEvent.event
              ) {
                case "turn_started":
                  break;

                case "conversation": {
                  const data =
                    streamEvent.data as
                      ConversationEventData;

                  setConversationId(
                    data.conversation_id
                  );

                  break;
                }

                case "message_start": {
                  const data =
                    streamEvent.data as
                      MessageStartEventData;

                  activeAssistantId =
                    data.message_id;

                  const assistantMessage:
                    ChatMessage = {
                      id:
                        data.message_id,

                      role:
                        "assistant",

                      content: "",

                      language:
                        data.language,

                      blocks: [],

                      isStreaming:
                        true,
                    };

                  setMessages(
                    (current) => [
                      ...current,
                      assistantMessage,
                    ]
                  );

                  break;
                }

                case "message_delta": {
                  const data =
                    streamEvent.data as
                      MessageDeltaEventData;

                  updateAssistantMessage(
                    data.message_id,
                    (current) => ({
                      ...current,

                      content:
                        current.content +
                        data.delta,
                    })
                  );

                  break;
                }

                case "block": {
                  const data =
                    streamEvent.data as
                      BlockEventData;

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
                    streamEvent.data as
                      DoneEventData;

                  setConversationId(
                    data.conversation_id
                  );

                  updateAssistantMessage(
                    data.message_id,
                    (current) => ({
                      ...current,
                      isStreaming:
                        false,
                    })
                  );

                  break;
                }

                case "error": {
                  const data =
                    streamEvent.data as
                      ErrorEventData;

                  setError(
                    data.message
                  );

                  if (
                    activeAssistantId
                  ) {
                    updateAssistantMessage(
                      activeAssistantId,
                      (current) => ({
                        ...current,
                        isStreaming:
                          false,
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
        } catch (caught) {
          if (
            caught instanceof
              DOMException &&
            caught.name ===
              "AbortError"
          ) {
            return;
          }

          const message =
            caught instanceof Error
              ? caught.message
              : (
                "Chat request "
                + "failed."
              );

          setError(message);

          if (
            activeAssistantId
          ) {
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

          if (
            abortRef.current ===
            controller
          ) {
            abortRef.current =
              null;
          }
        }
      },
      [
        conversationId,
        isSending,
        updateAssistantMessage,
      ]
    );


  const stop =
    useCallback(() => {
      abortRef.current?.abort();

      abortRef.current = null;

      setIsSending(false);
    }, []);


  const newConversation =
    useCallback(() => {
      abortRef.current?.abort();

      abortRef.current = null;

      setConversationId(null);

      setMessages([]);

      setError(null);

      setIsSending(false);
    }, []);


  return {
    messages,
    conversationId,
    isSending,
    error,
    sendMessage,
    stop,
    newConversation,
  };
}