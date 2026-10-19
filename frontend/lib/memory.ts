import {
  supabase,
} from "@/lib/supabase/client";


const API_URL =
  process.env
    .NEXT_PUBLIC_API_URL
  ??
  "http://127.0.0.1:8000";


export interface CustomerMemory {
  id: string;

  memory_type:
    | "product_interest"
    | "occasion_context"
    | "communication_style"
    | "fabric_or_style_note"
    | "other";

  memory_key: string;

  memory_value: unknown;

  confidence: number;

  source_conversation_id?:
    | string
    | null;

  is_active: boolean;

  last_confirmed_at?:
    | string
    | null;

  created_at?:
    | string
    | null;

  updated_at?:
    | string
    | null;
}


export interface MemoryListResponse {
  memories:
    CustomerMemory[];

  count:
    number;
}


async function token():
Promise<string> {
  const {
    data: {
      session,
    },
  } =
    await supabase
      .auth
      .getSession();

  if (
    !session
      ?.access_token
  ) {
    throw new Error(
      "You must sign in first."
    );
  }

  return (
    session.access_token
  );
}


export async function getMemories():
Promise<MemoryListResponse> {
  const accessToken =
    await token();

  const response =
    await fetch(
      `${API_URL}/api/v1/memory`,
      {
        headers: {
          Authorization:
            `Bearer ${accessToken}`,
        },
      }
    );

  if (!response.ok) {
    throw new Error(
      "Retailigent memories could not be loaded."
    );
  }

  return (
    await response.json()
  ) as
    MemoryListResponse;
}


export async function deleteMemory(
  memoryId: string
): Promise<void> {
  const accessToken =
    await token();

  const response =
    await fetch(
      (
        `${API_URL}/api/v1/memory/`
        + encodeURIComponent(
          memoryId
        )
      ),
      {
        method:
          "DELETE",

        headers: {
          Authorization:
            `Bearer ${accessToken}`,
        },
      }
    );

  if (!response.ok) {
    let detail =
      "The remembered fact could not be deleted.";

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
      // Keep generic message.
    }

    throw new Error(
      detail
    );
  }
}