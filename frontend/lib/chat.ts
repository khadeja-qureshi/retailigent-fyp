import { supabase } from "@/lib/supabase/client";

import type {
  ChatStreamEvent,
} from "@/lib/chat-types";


const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";


interface StreamChatOptions {
  message: string;

  conversationId?: string | null;

  signal?: AbortSignal;

  onEvent: (
    event: ChatStreamEvent
  ) => void;
}


function parseSseFrame(
  frame: string
): ChatStreamEvent | null {
  const lines = frame.split("\n");

  let event = "message";

  const dataLines: string[] = [];

  for (const rawLine of lines) {
    const line = rawLine.replace(
      /\r$/,
      ""
    );

    if (
      !line ||
      line.startsWith(":")
    ) {
      continue;
    }

    if (line.startsWith("event:")) {
      event = line
        .slice("event:".length)
        .trim();

      continue;
    }

    if (line.startsWith("data:")) {
      dataLines.push(
        line
          .slice("data:".length)
          .trimStart()
      );
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  const rawData =
    dataLines.join("\n");

  let data: unknown;

  try {
    data = JSON.parse(rawData);
  } catch {
    data = rawData;
  }

  return {
    event,
    data,
  };
}


export async function streamChat({
  message,
  conversationId,
  signal,
  onEvent,
}: StreamChatOptions): Promise<void> {
  const {
    data: {
      session,
    },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new Error(
      "You must sign in before using chat."
    );
  }

  const response = await fetch(
    `${API_URL}/api/v1/chat`,
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",

        Authorization:
          `Bearer ${session.access_token}`,
      },

      body: JSON.stringify({
        message,

        conversation_id:
          conversationId ?? null,
      }),

      signal,
    }
  );

  if (!response.ok) {
    let detail =
      "Chat request failed.";

    try {
      const payload =
        await response.json();

      if (
        payload &&
        typeof payload.detail
          === "string"
      ) {
        detail = payload.detail;
      }
    } catch {
      // Keep generic message.
    }

    throw new Error(detail);
  }

  if (!response.body) {
    throw new Error(
      "The chat response did not contain a stream."
    );
  }

  const reader =
    response.body.getReader();

  const decoder =
    new TextDecoder("utf-8");

  let buffer = "";

  try {
    while (true) {
      const {
        value,
        done,
      } = await reader.read();

      if (done) {
        break;
      }

      buffer += decoder.decode(
        value,
        {
          stream: true,
        }
      );

      buffer = buffer.replace(
        /\r\n/g,
        "\n"
      );

      let separatorIndex =
        buffer.indexOf("\n\n");

      while (
        separatorIndex !== -1
      ) {
        const frame =
          buffer.slice(
            0,
            separatorIndex
          );

        buffer = buffer.slice(
          separatorIndex + 2
        );

        const parsed =
          parseSseFrame(frame);

        if (parsed) {
          onEvent(parsed);
        }

        separatorIndex =
          buffer.indexOf("\n\n");
      }
    }

    buffer += decoder.decode();

    const finalFrame =
      buffer.trim();

    if (finalFrame) {
      const parsed =
        parseSseFrame(
          finalFrame
        );

      if (parsed) {
        onEvent(parsed);
      }
    }
  } finally {
    reader.releaseLock();
  }
}