import { supabase } from "@/lib/supabase/client";

import type {
  ChatStreamEvent,
  ConversationHistoryResponse,
  ConversationListResponse,
} from "@/lib/chat-types";


const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000"
).replace(/\/+$/, "");


interface StreamChatOptions {
  message: string;

  latitude?: number | null;
  longitude?: number | null;

  conversationId?: string | null;

  signal?: AbortSignal;

  onEvent: (
    event: ChatStreamEvent
  ) => void;
}


function messageNeedsLocation(
  message: string
): boolean {
  const normalized =
    message.toLowerCase();

  const locationTerms = [
    "nearest",
    "closest",
    "near me",
    "nearby",

    "qareeb",
    "kareeb",

    "nazdeek",
    "nazdik",

    "near my location",
    "closest branch",
    "nearest branch",
    "closest store",
    "nearest store",
  ];

  return locationTerms.some(
    (term) =>
      normalized.includes(term)
  );
}


async function getBrowserLocation(
  message: string
): Promise<
  {
    latitude: number;
    longitude: number;
  }
  | null
> {
  if (
    typeof window === "undefined"
    ||
    !messageNeedsLocation(message)
  ) {
    return null;
  }


  if (
    typeof navigator === "undefined"
    ||
    !("geolocation" in navigator)
  ) {
    return null;
  }


  return new Promise(
    (resolve) => {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          resolve({
            latitude:
              position.coords.latitude,

            longitude:
              position.coords.longitude,
          });
        },

        () => {
          /*
           * Location permission may be denied,
           * unavailable or time out.
           *
           * Chat should continue normally.
           */
          resolve(null);
        },

        {
          enableHighAccuracy: false,
          timeout: 5000,
          maximumAge: 300000,
        }
      );
    }
  );
}


async function getAccessToken():
Promise<string> {
  const {
    data: {
      session,
    },
  } =
    await supabase.auth
      .getSession();


  if (
    !session?.access_token
  ) {
    throw new Error(
      "You must sign in before using chat."
    );
  }


  return session.access_token;
}


async function authenticatedJson<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token =
    await getAccessToken();


  const response =
    await fetch(
      `${API_URL}${path}`,
      {
        ...options,

        headers: {
          "Content-Type":
            "application/json",

          Authorization:
            `Bearer ${token}`,

          ...(
            options.headers
            ?? {}
          ),
        },
      }
    );


  if (!response.ok) {
    let detail =
      `Request failed (${response.status}).`;


    try {
      const payload =
        await response.json();


      if (
        payload
        &&
        typeof payload.detail
          === "string"
      ) {
        detail =
          payload.detail;
      }

    } catch {
      // Keep generic error.
    }


    throw new Error(
      detail
    );
  }


  return (
    await response.json()
  ) as T;
}


function parseSseFrame(
  frame: string
): ChatStreamEvent | null {
  const lines =
    frame.split("\n");


  let event =
    "message";


  const dataLines:
    string[] = [];


  for (
    const rawLine
    of lines
  ) {
    const line =
      rawLine.replace(
        /\r$/,
        ""
      );


    if (
      !line
      ||
      line.startsWith(":")
    ) {
      continue;
    }


    if (
      line.startsWith(
        "event:"
      )
    ) {
      event =
        line
          .slice(
            "event:".length
          )
          .trim();

      continue;
    }


    if (
      line.startsWith(
        "data:"
      )
    ) {
      dataLines.push(
        line
          .slice(
            "data:".length
          )
          .trimStart()
      );
    }
  }


  if (
    dataLines.length === 0
  ) {
    return null;
  }


  const rawData =
    dataLines.join("\n");


  let data: unknown;


  try {
    data =
      JSON.parse(rawData);

  } catch {
    data =
      rawData;
  }


  return {
    event,
    data,
  };
}


export async function listConversations():
Promise<ConversationListResponse> {
  return authenticatedJson<
    ConversationListResponse
  >(
    "/api/v1/chat/conversations"
  );
}


export async function getConversationHistory(
  conversationId: string
): Promise<ConversationHistoryResponse> {
  return authenticatedJson<
    ConversationHistoryResponse
  >(
    "/api/v1/chat/conversations/"
    +
    encodeURIComponent(
      conversationId
    )
  );
}


export async function finalizeConversation(
  conversationId: string
): Promise<void> {
  await authenticatedJson<{
    conversation_id: string;
    memory_saved: number;
    memories: unknown[];
  }>(
    "/api/v1/chat/"
    +
    encodeURIComponent(
      conversationId
    )
    +
    "/finalize",
    {
      method: "POST",
    }
  );
}


export async function streamChat({
  message,
  latitude,
  longitude,
  conversationId,
  signal,
  onEvent,
}: StreamChatOptions):
Promise<void> {

  const token =
    await getAccessToken();


  let resolvedLatitude =
    latitude ?? null;

  let resolvedLongitude =
    longitude ?? null;


  /*
   * Only request browser location for
   * explicitly location-dependent queries.
   */
  if (
    resolvedLatitude == null
    ||
    resolvedLongitude == null
  ) {
    const browserLocation =
      await getBrowserLocation(
        message
      );


    if (
      browserLocation
    ) {
      resolvedLatitude =
        browserLocation.latitude;

      resolvedLongitude =
        browserLocation.longitude;
    }
  }


  const response =
    await fetch(
      `${API_URL}/api/v1/chat`,
      {
        method:
          "POST",

        headers: {
          "Content-Type":
            "application/json",

          Authorization:
            `Bearer ${token}`,
        },

        body:
          JSON.stringify({
            message,

            conversation_id:
              conversationId
              ?? null,

            latitude:
              resolvedLatitude,

            longitude:
              resolvedLongitude,
          }),

        signal,
      }
    );


  if (!response.ok) {
    let detail =
      `Chat request failed (${response.status}).`;


    try {
      const payload =
        await response.json();


      if (
        payload
        &&
        typeof payload.detail
          === "string"
      ) {
        detail =
          payload.detail;
      }

    } catch {
      // Keep generic error.
    }


    throw new Error(
      detail
    );
  }


  if (!response.body) {
    throw new Error(
      "The chat response did not contain a stream."
    );
  }


  const reader =
    response.body
      .getReader();


  const decoder =
    new TextDecoder(
      "utf-8"
    );


  let buffer = "";


  try {
    while (true) {
      const {
        value,
        done,
      } =
        await reader.read();


      if (done) {
        break;
      }


      buffer +=
        decoder.decode(
          value,
          {
            stream: true,
          }
        );


      /*
       * Normalize CRLF before looking
       * for SSE frame separators.
       */
      buffer =
        buffer.replace(
          /\r\n/g,
          "\n"
        );


      let separatorIndex =
        buffer.indexOf(
          "\n\n"
        );


      while (
        separatorIndex !== -1
      ) {
        const frame =
          buffer.slice(
            0,
            separatorIndex
          );


        buffer =
          buffer.slice(
            separatorIndex + 2
          );


        const parsed =
          parseSseFrame(
            frame
          );


        if (parsed) {
          onEvent(
            parsed
          );
        }


        separatorIndex =
          buffer.indexOf(
            "\n\n"
          );
      }
    }


    buffer +=
      decoder.decode();


    const finalFrame =
      buffer.trim();


    if (finalFrame) {
      const parsed =
        parseSseFrame(
          finalFrame
        );


      if (parsed) {
        onEvent(
          parsed
        );
      }
    }

  } finally {
    reader.releaseLock();
  }
}