"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  deleteMemory,
  getMemories,
} from "@/lib/memory";

import type {
  CustomerMemory,
} from "@/lib/memory";


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

  return (
    words
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
      .join(" ")
  );
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


export default function ProfilePage() {
  const [
    memories,
    setMemories,
  ] =
    useState<
      CustomerMemory[]
    >([]);

  const [
    loading,
    setLoading,
  ] =
    useState(true);

  const [
    deletingId,
    setDeletingId,
  ] =
    useState<
      string | null
    >(null);

  const [
    error,
    setError,
  ] =
    useState<
      string | null
    >(null);


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
            await (
              getMemories()
            );

          setMemories(
            result.memories
          );

        } catch (
          caught
        ) {
          setError(
            caught instanceof
              Error
              ? caught.message
              : (
                "Retailigent memories "
                + "could not be loaded."
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
        void (
          loadMemories()
        );
      }
    );
  }, [
    loadMemories,
  ]);


  async function handleDelete(
    memory:
      CustomerMemory
  ) {
    const confirmed =
      window.confirm(
        (
          "Delete this remembered fact?\n\n"
          + memoryLabel(
            memory.memory_key
          )
          + ": "
          + memoryValue(
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

      await (
        deleteMemory(
          memory.id
        )
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
        caught instanceof
          Error
          ? caught.message
          : (
            "The remembered fact "
            + "could not be deleted."
          )
      );

    } finally {
      setDeletingId(
        null
      );
    }
  }


  return (
    <main className="min-h-[calc(100vh-3.5rem)] bg-[#f1e6de] px-4 py-8 text-[#2c1c20] sm:px-6">
      <div className="mx-auto max-w-4xl">
        <section className="rounded-3xl border border-[#dccbc4] bg-[#fffaf7] p-6 shadow-sm sm:p-8">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7f2a3c]">
            Privacy & Memory
          </p>

          <h1 className="mt-2 text-3xl font-bold">
            What Retailigent remembers about you
          </h1>

          <p className="mt-3 max-w-2xl text-sm leading-6 text-[#756369]">
            These durable facts help Retailigent avoid
            asking you to repeat useful preferences
            across separate conversations. You remain
            in control and can delete any fact.
          </p>

          <div className="mt-5 rounded-2xl bg-[#f7ece7] px-4 py-3 text-sm text-[#674f56]">
            Deleted memories are excluded from future
            conversation context snapshots.
          </div>
        </section>


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


        <section className="mt-6">
          {
            loading
              ? (
                <div className="rounded-3xl border border-[#dccbc4] bg-[#fffaf7] p-8 text-center text-[#756369]">
                  Loading your memories...
                </div>
              )
              : memories.length
                === 0
                ? (
                  <div className="rounded-3xl border border-[#dccbc4] bg-[#fffaf7] p-8 text-center">
                    <h2 className="text-lg font-semibold">
                      Nothing remembered yet
                    </h2>

                    <p className="mt-2 text-sm text-[#756369]">
                      Durable preferences saved from
                      future conversations will appear
                      here.
                    </p>
                  </div>
                )
                : (
                  <div className="grid gap-4 sm:grid-cols-2">
                    {
                      memories.map(
                        (
                          memory
                        ) => (
                          <article
                            key={
                              memory.id
                            }
                            className="rounded-2xl border border-[#dccbc4] bg-[#fffaf7] p-5 shadow-sm"
                          >
                            <div className="flex items-start justify-between gap-4">
                              <div>
                                <span className="inline-flex rounded-full bg-[#f4ded8] px-2.5 py-1 text-[11px] font-semibold text-[#7f2a3c]">
                                  {
                                    memoryTypeLabel(
                                      memory
                                        .memory_type
                                    )
                                  }
                                </span>

                                <h2 className="mt-3 font-semibold">
                                  {
                                    memoryLabel(
                                      memory
                                        .memory_key
                                    )
                                  }
                                </h2>
                              </div>

                              <span className="shrink-0 text-xs text-[#8c777c]">
                                {
                                  Math.round(
                                    Number(
                                      memory
                                        .confidence
                                    )
                                    * 100
                                  )
                                }
                                % confidence
                              </span>
                            </div>

                            <pre className="mt-4 whitespace-pre-wrap break-words font-sans text-sm leading-6 text-[#5d484e]">
                              {
                                memoryValue(
                                  memory
                                    .memory_value
                                )
                              }
                            </pre>

                            <button
                              type="button"
                              disabled={
                                deletingId
                                === memory.id
                              }
                              onClick={() => {
                                void (
                                  handleDelete(
                                    memory
                                  )
                                );
                              }}
                              className="mt-5 rounded-xl border border-[#ce4d42] px-3.5 py-2 text-sm font-medium text-[#a53d35] transition hover:bg-[#fff0ed] disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {
                                deletingId
                                === memory.id
                                  ? "Deleting..."
                                  : "Delete memory"
                              }
                            </button>
                          </article>
                        )
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