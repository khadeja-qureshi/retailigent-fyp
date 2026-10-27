"use client";

import Link from "next/link";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  deleteMemory,
  getMemories,
  getPersonalizationPreference,
  updatePersonalizationPreference,
} from "@/lib/memory";

import type {
  CustomerMemory,
} from "@/lib/memory";

import {
  getEmailNotificationPreference,
  updateEmailNotificationPreference,
} from "@/lib/notifications";


function memoryLabel(
  key: string
) {
  const words =
    key
      .replace(
        /_/g,
        " "
      )
      .split(" ")
      .filter(Boolean);


  return words
    .map(
      (
        word
      ) =>
        word
          .charAt(0)
          .toUpperCase()
        +
        word.slice(1)
    )
    .join(" ");
}


function memoryValue(
  value: unknown
) {
  if (
    value === null
    ||
    value === undefined
  ) {
    return "Not specified";
  }


  if (
    typeof value
    === "string"
  ) {
    return value;
  }


  if (
    typeof value
    === "number"
    ||
    typeof value
    === "boolean"
  ) {
    return String(
      value
    );
  }


  try {
    return JSON.stringify(
      value,
      null,
      2
    );
  } catch {
    return String(
      value
    );
  }
}


function memoryTypeLabel(
  type:
    CustomerMemory[
      "memory_type"
    ]
) {
  const labels = {
    product_interest:
      "Product interest",

    occasion_context:
      "Occasion",

    communication_style:
      "Communication",

    fabric_or_style_note:
      "Style preference",

    other:
      "Other",
  };


  return labels[type];
}


function formatMemoryDate(
  value?:
    string
    | null
) {
  if (!value) {
    return null;
  }


  const date =
    new Date(
      value
    );


  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return null;
  }


  return date.toLocaleDateString(
    undefined,
    {
      month:
        "short",

      day:
        "numeric",

      year:
        "numeric",
    }
  );
}


export default function ProfilePage() {
  const [
    memories,
    setMemories,
  ] =
    useState<CustomerMemory[]>(
      []
    );

  const [
    loading,
    setLoading,
  ] =
    useState(true);

  const [
    deletingId,
    setDeletingId,
  ] =
    useState<string | null>(
      null
    );

  const [
    error,
    setError,
  ] =
    useState<string | null>(
      null
    );


  const [
    emailNotifications,
    setEmailNotifications,
  ] = useState(false);

  const [
    preferenceLoading,
    setPreferenceLoading,
  ] = useState(true);

  const [
    preferenceSaving,
    setPreferenceSaving,
  ] = useState(false);

  const [
    preferenceError,
    setPreferenceError,
  ] = useState<string | null>(null);

  const [
    preferenceNotice,
    setPreferenceNotice,
  ] = useState<string | null>(null);


  const [
    personalizationEnabled,
    setPersonalizationEnabled,
  ] = useState(false);

  const [
    personalizationLoading,
    setPersonalizationLoading,
  ] = useState(true);

  const [
    personalizationSaving,
    setPersonalizationSaving,
  ] = useState(false);

  const [
    personalizationError,
    setPersonalizationError,
  ] = useState<string | null>(null);

  const [
    personalizationNotice,
    setPersonalizationNotice,
  ] = useState<string | null>(null);


  const loadMemories =
    useCallback(
      async () => {
        try {
          setLoading(
            true
          );

          setError(
            null
          );


          const result =
            await getMemories();


          setMemories(
            result.memories
          );
        } catch (
          caught
        ) {
          setError(
            caught instanceof Error
              ? caught.message
              : (
                "Retailigent memories "
                +
                "could not be loaded."
              )
          );
        } finally {
          setLoading(
            false
          );
        }
      },
      []
    );


  useEffect(() => {
    queueMicrotask(
      () => {
        void loadMemories();
      }
    );
  }, [
    loadMemories,
  ]);


  useEffect(() => {
    let active = true;

    async function loadPreference() {
      try {
        const result = await getEmailNotificationPreference();
        if (active) {
          setEmailNotifications(result.allow_email_notifications);
          setPreferenceError(null);
        }
      } catch (caught) {
        if (active) {
          setPreferenceError(
            caught instanceof Error
              ? caught.message
              : "Email notification preference could not be loaded.",
          );
        }
      } finally {
        if (active) {
          setPreferenceLoading(false);
        }
      }
    }

    void loadPreference();

    return () => {
      active = false;
    };
  }, []);


  useEffect(() => {
    let active = true;

    async function loadPersonalization() {
      try {
        const result = await getPersonalizationPreference();

        if (active) {
          setPersonalizationEnabled(
            result.allow_personalized_recommendations
          );
          setPersonalizationError(null);
        }
      } catch (caught) {
        if (active) {
          setPersonalizationError(
            caught instanceof Error
              ? caught.message
              : "Personalization preference could not be loaded."
          );
        }
      } finally {
        if (active) {
          setPersonalizationLoading(false);
        }
      }
    }

    void loadPersonalization();

    return () => {
      active = false;
    };
  }, []);


  async function handleEmailPreferenceChange(
    enabled: boolean,
  ) {
    if (preferenceSaving || preferenceLoading) {
      return;
    }

    const previousValue = emailNotifications;
    setEmailNotifications(enabled);
    setPreferenceSaving(true);
    setPreferenceError(null);
    setPreferenceNotice(null);

    try {
      const result = await updateEmailNotificationPreference(enabled);
      setEmailNotifications(result.allow_email_notifications);
      setPreferenceNotice("Email notification preference saved.");
    } catch (caught) {
      setEmailNotifications(previousValue);
      setPreferenceError(
        caught instanceof Error
          ? caught.message
          : "Email notification preference could not be saved.",
      );
    } finally {
      setPreferenceSaving(false);
    }
  }


  async function handlePersonalizationChange(
    enabled: boolean,
  ) {
    if (personalizationSaving || personalizationLoading) {
      return;
    }

    const previous = personalizationEnabled;
    setPersonalizationEnabled(enabled);
    setPersonalizationSaving(true);
    setPersonalizationError(null);
    setPersonalizationNotice(null);

    try {
      const result = await updatePersonalizationPreference(enabled);
      setPersonalizationEnabled(
        result.allow_personalized_recommendations
      );
      setPersonalizationNotice(
        enabled
          ? "Personalized recommendations enabled."
          : "Personalized recommendations disabled."
      );
    } catch (caught) {
      setPersonalizationEnabled(previous);
      setPersonalizationError(
        caught instanceof Error
          ? caught.message
          : "Personalization preference could not be saved."
      );
    } finally {
      setPersonalizationSaving(false);
    }
  }


  async function handleDelete(
    memory:
      CustomerMemory
  ) {
    const confirmed =
      window.confirm(
        (
          "Delete this remembered fact?\n\n"
          +
          memoryLabel(
            memory.memory_key
          )
          +
          ": "
          +
          memoryValue(
            memory.memory_value
          )
        )
      );


    if (!confirmed) {
      return;
    }


    try {
      setDeletingId(
        memory.id
      );

      setError(
        null
      );


      await deleteMemory(
        memory.id
      );


      setMemories(
        (
          current
        ) =>
          current.filter(
            (
              item
            ) =>
              item.id
              !== memory.id
          )
      );
    } catch (
      caught
    ) {
      setError(
        caught instanceof Error
          ? caught.message
          : (
            "The remembered fact "
            +
            "could not be deleted."
          )
      );
    } finally {
      setDeletingId(
        null
      );
    }
  }


  return (
    <main className="min-h-[calc(100dvh-4rem)] overflow-x-hidden bg-[#f1e6de] text-[#2c1c20]">

      <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">

        <section className="overflow-hidden rounded-3xl border border-[#dccbc4] bg-[#fffaf7] shadow-sm">

          <div className="relative p-5 sm:p-8">

            <div
              aria-hidden="true"
              className="absolute -right-16 -top-16 h-44 w-44 rounded-full bg-[#7779de]/10 blur-2xl"
            />

            <div
              aria-hidden="true"
              className="absolute -bottom-20 -left-20 h-44 w-44 rounded-full bg-[#f54631]/10 blur-2xl"
            />


            <div className="relative">

              <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">

                <div className="max-w-2xl">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7f2a3c]">
                    Privacy & Memory
                  </p>

                  <h1 className="mt-2 text-3xl font-bold leading-tight sm:text-4xl">
                    What Retailigent remembers about you
                  </h1>

                  <p className="mt-3 text-sm leading-6 text-[#756369] sm:text-base">
                    Durable facts help Retailigent avoid
                    asking you to repeat useful preferences
                    across separate conversations.
                  </p>
                </div>


                <Link
                  href="/chat"
                  className="inline-flex min-h-11 w-full shrink-0 items-center justify-center rounded-xl bg-[#7f2a3c] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#682132] sm:w-auto"
                >
                  Open assistant
                </Link>
              </div>


              <div className="mt-6 grid gap-3 sm:grid-cols-3">

                <div className="rounded-2xl border border-[#e2d5cf] bg-white/80 p-4">
                  <p className="text-xs uppercase tracking-[0.14em] text-[#8c777c]">
                    Remembered facts
                  </p>

                  <strong className="mt-2 block text-2xl text-[#332e34]">
                    {
                      memories.length
                    }
                  </strong>
                </div>


                <div className="rounded-2xl border border-[#e2d5cf] bg-white/80 p-4">
                  <p className="text-xs uppercase tracking-[0.14em] text-[#8c777c]">
                    Privacy
                  </p>

                  <strong className="mt-2 block text-sm text-[#332e34]">
                    Customer controlled
                  </strong>
                </div>


                <div className="rounded-2xl border border-[#e2d5cf] bg-white/80 p-4">
                  <p className="text-xs uppercase tracking-[0.14em] text-[#8c777c]">
                    Context
                  </p>

                  <strong className="mt-2 block text-sm text-[#332e34]">
                    Across conversations
                  </strong>
                </div>
              </div>
            </div>
          </div>
        </section>


        <div className="mt-5 rounded-2xl border border-[#d9cdc7] bg-[#f7ece7] px-4 py-4 text-sm leading-6 text-[#674f56] sm:px-5">
          You remain in control of these memories.
          Deleted memories are excluded from future
          conversation context snapshots.
        </div>


        {
          error
          && (
            <div className="mt-5 rounded-2xl border border-[#e4aaa3] bg-[#fff2ef] px-4 py-3 text-sm text-[#9b352e]">
              {
                error
              }
            </div>
          )
        }


        <section
          aria-labelledby="personalization-heading"
          className="mt-6 rounded-3xl border border-[#dccbc4] bg-[#fffaf7] p-5 shadow-sm sm:p-6"
        >
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7f2a3c]">
            Personalization
          </p>
          <h2
            id="personalization-heading"
            className="mt-1 text-xl font-semibold text-[#332e34]"
          >
            Personalized recommendations
          </h2>
          <p className="mt-2 text-sm leading-6 text-[#756369]">
            Allow Retailigent to use your saved shopping preferences and
            remembered facts when ranking recommendations. Current-message
            filters always remain hard constraints.
          </p>

          <div className="mt-4 flex flex-col gap-4 rounded-2xl border border-[#e2d5cf] bg-white/80 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-semibold text-[#332e34]">
                Use saved preferences
              </p>
              <p className="mt-1 text-sm text-[#756369]">
                {personalizationEnabled
                  ? "Recommendations may use your saved preferences."
                  : "Saved preferences will not affect recommendations."}
              </p>
            </div>

            <button
              type="button"
              role="switch"
              aria-checked={personalizationEnabled}
              aria-label="Use saved preferences for recommendations"
              disabled={personalizationLoading || personalizationSaving}
              onClick={() => {
                void handlePersonalizationChange(!personalizationEnabled);
              }}
              className={`inline-flex min-h-11 shrink-0 items-center justify-center rounded-xl px-5 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
                personalizationEnabled
                  ? "bg-[#7f2a3c] text-white hover:bg-[#682132]"
                  : "border border-[#dccbc4] bg-white text-[#674f56] hover:bg-[#f7ece7]"
              }`}
            >
              {personalizationLoading
                ? "Loading..."
                : personalizationSaving
                  ? "Saving..."
                  : personalizationEnabled
                    ? "Enabled"
                    : "Disabled"}
            </button>
          </div>

          {personalizationError && (
            <p role="alert" className="mt-3 text-sm text-[#9b352e]">
              {personalizationError}
            </p>
          )}

          {personalizationNotice && (
            <p role="status" className="mt-3 text-sm text-[#356b45]">
              {personalizationNotice}
            </p>
          )}
        </section>


        <section
          aria-labelledby="email-preferences-heading"
          className="mt-6 rounded-3xl border border-[#dccbc4] bg-[#fffaf7] p-5 shadow-sm sm:p-6"
        >
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7f2a3c]">
            Notifications
          </p>
          <h2
            id="email-preferences-heading"
            className="mt-1 text-xl font-semibold text-[#332e34]"
          >
            Email notifications
          </h2>
          <p className="mt-2 text-sm leading-6 text-[#756369]">
            Choose whether Retailigent may send you email notifications.
            In-app notifications are controlled separately.
          </p>

          <div className="mt-4 flex flex-col gap-4 rounded-2xl border border-[#e2d5cf] bg-white/80 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-semibold text-[#332e34]">
                Allow email notifications
              </p>
              <p className="mt-1 text-sm text-[#756369]">
                {emailNotifications
                  ? "Email notifications are enabled."
                  : "Email notifications are turned off by default."}
              </p>
            </div>

            <button
              type="button"
              role="switch"
              aria-checked={emailNotifications}
              aria-label="Allow email notifications"
              disabled={preferenceLoading || preferenceSaving}
              onClick={() => {
                void handleEmailPreferenceChange(!emailNotifications);
              }}
              className={`inline-flex min-h-11 shrink-0 items-center justify-center rounded-xl px-5 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
                emailNotifications
                  ? "bg-[#7f2a3c] text-white hover:bg-[#682132]"
                  : "border border-[#dccbc4] bg-white text-[#674f56] hover:bg-[#f7ece7]"
              }`}
            >
              {preferenceLoading
                ? "Loading..."
                : preferenceSaving
                  ? "Saving..."
                  : emailNotifications
                    ? "Enabled"
                    : "Disabled"}
            </button>
          </div>

          {preferenceError && (
            <p role="alert" className="mt-3 text-sm text-[#9b352e]">
              {preferenceError}
            </p>
          )}
          {preferenceNotice && (
            <p role="status" className="mt-3 text-sm text-[#356b45]">
              {preferenceNotice}
            </p>
          )}
        </section>


        <section className="mt-6">

          <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">

            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#7f2a3c]">
                Memory controls
              </p>

              <h2 className="mt-1 text-xl font-semibold text-[#332e34]">
                Remembered facts
              </h2>
            </div>


            {
              !loading
              &&
              memories.length > 0
              && (
                <span className="text-xs text-[#8c777c]">
                  Delete any fact you no longer want used
                </span>
              )
            }
          </div>


          {
            loading
              ? (
                <div className="rounded-3xl border border-[#dccbc4] bg-[#fffaf7] p-8 text-center text-sm text-[#756369] shadow-sm">
                  Loading your memories...
                </div>
              )
              : memories.length
                === 0
                ? (
                  <div className="rounded-3xl border border-[#dccbc4] bg-[#fffaf7] px-5 py-10 text-center shadow-sm sm:p-10">

                    <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#eeeafb] font-bold text-[#5f62c7]">
                      R
                    </div>

                    <h3 className="mt-4 text-lg font-semibold text-[#332e34]">
                      Nothing remembered yet
                    </h3>

                    <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#756369]">
                      Durable preferences extracted from
                      future conversations will appear here.
                    </p>


                    <Link
                      href="/chat"
                      className="mt-5 inline-flex min-h-11 items-center justify-center rounded-xl border border-[#7779de] px-4 py-2.5 text-sm font-semibold text-[#5f62c7] transition hover:bg-[#f0effc]"
                    >
                      Talk to Retailigent
                    </Link>
                  </div>
                )
                : (
                  <div className="grid gap-4 md:grid-cols-2">

                    {
                      memories.map(
                        (
                          memory
                        ) => {
                          const confidence =
                            Math.round(
                              Number(
                                memory.confidence
                              )
                              * 100
                            );

                          const confirmedDate =
                            formatMemoryDate(
                              memory.last_confirmed_at
                              ??
                              memory.updated_at
                            );


                          return (
                            <article
                              key={
                                memory.id
                              }
                              className="min-w-0 rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-4 shadow-sm sm:p-5"
                            >

                              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">

                                <div className="min-w-0">
                                  <span className="inline-flex rounded-full bg-[#f4ded8] px-2.5 py-1 text-[11px] font-semibold text-[#7f2a3c]">
                                    {
                                      memoryTypeLabel(
                                        memory.memory_type
                                      )
                                    }
                                  </span>

                                  <h3 className="mt-3 break-words font-semibold text-[#332e34]">
                                    {
                                      memoryLabel(
                                        memory.memory_key
                                      )
                                    }
                                  </h3>
                                </div>


                                <span className="w-fit shrink-0 rounded-full bg-[#eeeafb] px-2.5 py-1 text-[11px] font-semibold text-[#5f62c7]">
                                  {
                                    confidence
                                  }
                                  % confidence
                                </span>
                              </div>


                              <div className="mt-4 rounded-xl bg-white p-3.5">
                                <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6 text-[#5d484e]">
                                  {
                                    memoryValue(
                                      memory.memory_value
                                    )
                                  }
                                </pre>
                              </div>


                              {
                                confirmedDate
                                && (
                                  <p className="mt-3 text-xs text-[#9a858a]">
                                    Last confirmed{" "}
                                    {
                                      confirmedDate
                                    }
                                  </p>
                                )
                              }


                              <button
                                type="button"
                                disabled={
                                  deletingId
                                  === memory.id
                                }
                                onClick={() => {
                                  void handleDelete(
                                    memory
                                  );
                                }}
                                className="mt-5 min-h-11 w-full rounded-xl border border-[#e4aaa3] px-4 py-2.5 text-sm font-semibold text-[#b33d34] transition hover:bg-[#fff2ef] disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
                              >
                                {
                                  deletingId
                                  === memory.id
                                    ? "Deleting..."
                                    : "Delete memory"
                                }
                              </button>
                            </article>
                          );
                        }
                      )
                    }
                  </div>
                )
          }
        </section>
      </div>
    </main>
  );
}