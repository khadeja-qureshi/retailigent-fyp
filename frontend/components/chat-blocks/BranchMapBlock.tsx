"use client";

import type {
  BranchMapChatBlock,
} from "@/lib/chat-types";


export default function BranchMapBlock({
  block,
}: {
  block:
    BranchMapChatBlock;
}) {
  return (
    <section className="rounded-2xl border border-[#d8d2dd] bg-[#f7f4f8] p-4 text-[#332e34]">

      <h3 className="text-base font-semibold text-[#332e34]">
        {
          block.title
        }
      </h3>


      {
        block.branches.length
        === 0
          ? (
            <p className="mt-3 text-sm text-[#716a73]">
              No matching active branches were found.
            </p>
          )
          : (
            <div className="mt-4 space-y-3">

              {
                block.branches.map(
                  (
                    branch
                  ) => {
                    const hasCoordinates =
                      (
                        branch.latitude
                        != null
                        &&
                        branch.longitude
                        != null
                      );


                    const mapsUrl =
                      hasCoordinates
                        ? (
                          "https://www.google.com/maps/search/"
                          +
                          "?api=1&query="
                          +
                          `${branch.latitude},${branch.longitude}`
                        )
                        : (
                          branch.address
                            ? (
                              "https://www.google.com/maps/search/"
                              +
                              "?api=1&query="
                              +
                              encodeURIComponent(
                                [
                                  branch.address,
                                  branch.area,
                                  branch.city,
                                ]
                                  .filter(
                                    Boolean
                                  )
                                  .join(
                                    ", "
                                  )
                              )
                            )
                            : null
                        );


                    return (
                      <article
                        key={
                          branch.branch_id
                        }
                        className="rounded-xl border border-[#ded8e2] bg-white p-4 shadow-sm"
                      >

                        <h4 className="font-semibold text-[#332e34]">
                          {
                            branch.name
                          }
                        </h4>


                        <p className="mt-1 text-sm text-[#716a73]">
                          {
                            [
                              branch.area,
                              branch.city,
                            ]
                              .filter(
                                Boolean
                              )
                              .join(
                                ", "
                              )
                          }
                        </p>


                        {
                          branch.address
                          &&
                          (
                            <p className="mt-2 text-sm text-[#4f4851]">
                              {
                                branch.address
                              }
                            </p>
                          )
                        }


                        {
                          branch.distance_km
                          != null
                          &&
                          (
                            <p className="mt-2 text-sm font-medium text-[#5f62c7]">
                              Approximately{" "}
                              {
                                branch
                                  .distance_km
                                  .toFixed(
                                    2
                                  )
                              }{" "}
                              km away
                            </p>
                          )
                        }


                        {
                          (
                            branch.opening_time
                            ||
                            branch.closing_time
                          )
                          &&
                          (
                            <p className="mt-2 text-sm text-[#4f4851]">

                              <span className="text-[#716a73]">
                                Hours:{" "}
                              </span>

                              {
                                branch
                                  .opening_time
                                ??
                                "Not listed"
                              }

                              {" – "}

                              {
                                branch
                                  .closing_time
                                ??
                                "Not listed"
                              }

                            </p>
                          )
                        }


                        {
                          branch.phone
                          &&
                          (
                            <p className="mt-2 text-sm text-[#4f4851]">

                              <span className="text-[#716a73]">
                                Phone:{" "}
                              </span>


                              <a
                                href={
                                  `tel:${branch.phone}`
                                }
                                className="underline underline-offset-2"
                              >
                                {
                                  branch.phone
                                }
                              </a>

                            </p>
                          )
                        }


                        {
                          mapsUrl
                          &&
                          (
                            <a
                              href={
                                mapsUrl
                              }
                              target="_blank"
                              rel="noopener noreferrer"
                              className="mt-3 inline-flex text-sm font-medium text-[#6667d9] underline underline-offset-4 hover:text-[#5052bd]"
                            >
                              Open in Google Maps
                            </a>
                          )
                        }

                      </article>
                    );
                  }
                )
              }

            </div>
          )
      }

    </section>
  );
}