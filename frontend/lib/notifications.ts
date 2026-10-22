import { supabase } from "@/lib/supabase/client";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export interface EmailNotificationPreference {
  allow_email_notifications: boolean;
}

async function accessToken(): Promise<string> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new Error("You must sign in first.");
  }

  return session.access_token;
}

async function preferenceRequest(
  method: "GET" | "PATCH",
  enabled?: boolean,
): Promise<EmailNotificationPreference> {
  const token = await accessToken();
  const response = await fetch(
    `${API_URL}/api/v1/notifications/preferences`,
    {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(method === "PATCH"
          ? { "Content-Type": "application/json" }
          : {}),
      },
      ...(method === "PATCH"
        ? {
            body: JSON.stringify({
              allow_email_notifications: enabled,
            }),
          }
        : {}),
    },
  );

  if (!response.ok) {
    let detail = "Email notification preferences could not be saved.";
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      }
    } catch {
      // Keep the safe default error message.
    }
    throw new Error(detail);
  }

  return (await response.json()) as EmailNotificationPreference;
}

export function getEmailNotificationPreference():
Promise<EmailNotificationPreference> {
  return preferenceRequest("GET");
}

export function updateEmailNotificationPreference(
  enabled: boolean,
): Promise<EmailNotificationPreference> {
  return preferenceRequest("PATCH", enabled);
}
