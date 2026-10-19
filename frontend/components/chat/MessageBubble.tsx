"use client";

import BlockRenderer from "@/components/chat/BlockRenderer";

import type {
  ChatMessage,
} from "@/lib/chat-types";


interface Props {
  message:
    ChatMessage;
}


export default function MessageBubble({
  message,
}: Props) {
  const isUser =
    message.role
    === "user";


  return (
    <div
      className={
        "flex w-full "
        + (
          isUser
            ? "justify-end"
            : "justify-start"
        )
      }
    >
      <div
        className={
          isUser
            ? (
              "max-w-[85%] "
              + "rounded-2xl "
              + "rounded-br-md "
              + "bg-[#7779de] "
              + "px-4 py-3 "
              + "text-[#fffaf7] "
              + "shadow-sm "
              + "sm:max-w-[70%]"
            )
            : (
              "w-full "
              + "max-w-3xl "
              + "rounded-2xl "
              + "rounded-bl-md "
              + "border "
              + "border-[#dccbc4] "
              + "bg-[#fffaf7] "
              + "px-4 py-4 "
              + "text-[#2c1c20] "
              + "shadow-sm"
            )
        }
      >
        {
          message.content
          && (
            <p className="whitespace-pre-wrap text-sm leading-6">
              {
                message.content
              }
            </p>
          )
        }

        {
          message
            .isStreaming
          && (
            <span className="mt-2 inline-flex items-center gap-1 text-xs text-[#756369]">
              <span className="animate-pulse text-[#ce4d42]">
                ●
              </span>

              Responding...
            </span>
          )
        }

        {
          !isUser
          &&
          message
            .blocks
            .length
            > 0
          && (
            <div className="mt-4 space-y-4">
              {
                message
                  .blocks
                  .map(
                    (
                      block,
                      index
                    ) => (
                      <BlockRenderer
                        key={
                          `${message.id}-block-${index}`
                        }
                        block={
                          block
                        }
                      />
                    )
                  )
              }
            </div>
          )
        }
      </div>
    </div>
  );
}