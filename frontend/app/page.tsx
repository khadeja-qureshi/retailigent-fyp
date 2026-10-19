import Link from "next/link";


const FEATURES = [
  {
    number:
      "01",

    title:
      "Shop naturally",

    body:
      (
        "Search products, check live stock and "
        +
        "manage your shopping using normal English, "
        +
        "Roman Urdu, or both."
      ),
  },

  {
    number:
      "02",

    title:
      "Smart Cart",

    body:
      (
        "Create price and discount rules, receive "
        +
        "alerts, or authorize controlled automatic "
        +
        "purchase workflows."
      ),
  },

  {
    number:
      "03",

    title:
      "Memory that helps",

    body:
      (
        "Retailigent can remember durable preferences "
        +
        "across conversations while keeping those "
        +
        "memories visible and deletable."
      ),
  },
];


const QUICK_LINKS = [
  {
    href:
      "/cart",

    label:
      "Cart",

    description:
      "Review your current shopping bag.",
  },

  {
    href:
      "/wishlist",

    label:
      "Wishlist",

    description:
      "Return to products you saved.",
  },

  {
    href:
      "/orders",

    label:
      "Orders",

    description:
      "View completed mock purchases.",
  },

  {
    href:
      "/smart-cart",

    label:
      "Smart Cart",

    description:
      "Manage intelligent shopping rules.",
  },
];


export default function HomePage() {
  return (
    <main className="min-h-[calc(100dvh-4rem)] overflow-x-hidden bg-[#f8f3ef] text-[#332e34]">

      <section className="relative overflow-hidden">

        <div
          aria-hidden="true"
          className="absolute -left-24 top-12 h-72 w-72 rounded-full bg-[#7779de]/15 blur-3xl"
        />

        <div
          aria-hidden="true"
          className="absolute -right-24 top-52 h-72 w-72 rounded-full bg-[#f54631]/10 blur-3xl"
        />


        <div className="relative mx-auto grid max-w-7xl gap-10 px-4 py-10 sm:px-6 sm:py-14 lg:grid-cols-[1.1fr_0.9fr] lg:items-center lg:gap-12 lg:px-10 lg:py-24">

          <div>

            <div className="inline-flex max-w-full items-center gap-2 rounded-full border border-[#7779de]/20 bg-white/80 px-3.5 py-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[#5f62c7] shadow-sm backdrop-blur sm:px-4 sm:text-xs sm:tracking-[0.18em]">

              <span className="h-2 w-2 shrink-0 rounded-full bg-[#f54631]" />

              <span className="truncate">
                Agentic AI for fashion retail
              </span>
            </div>


            <h1 className="mt-6 max-w-4xl text-[2.55rem] font-semibold leading-[0.98] text-[#332e34] sm:mt-7 sm:text-6xl lg:text-7xl">

              Your intelligent

              <span className="mt-1 block text-[#7779de]">
                shopping companion.
              </span>
            </h1>


            <p className="mt-5 max-w-2xl text-sm leading-7 text-[#716a73] sm:mt-7 sm:text-lg sm:leading-8">
              Retailigent combines conversational AI,
              live retail data, cross-conversation
              memory, Smart Cart automation and
              controlled purchase workflows into one
              shopping experience.
            </p>


            <div className="mt-7 flex flex-col gap-3 sm:mt-9 sm:flex-row sm:flex-wrap">

              <Link
                href="/chat"
                className="inline-flex min-h-12 w-full items-center justify-center gap-3 rounded-xl bg-[#7779de] px-6 py-3.5 font-semibold text-white shadow-lg shadow-[#7779de]/20 transition hover:-translate-y-0.5 hover:bg-[#6668cc] sm:w-auto"
              >
                Start shopping

                <span aria-hidden="true">
                  →
                </span>
              </Link>


              <Link
                href="/profile"
                className="inline-flex min-h-12 w-full items-center justify-center rounded-xl border border-[#d3cdd1] bg-white px-6 py-3.5 font-medium text-[#332e34] shadow-sm transition hover:-translate-y-0.5 hover:border-[#7779de] hover:shadow-md sm:w-auto"
              >
                View my memory
              </Link>
            </div>


            <div className="mt-9 grid grid-cols-3 gap-2 sm:mt-12 sm:flex sm:flex-wrap sm:gap-x-8 sm:gap-y-4">

              <div className="min-w-0 rounded-2xl border border-[#e4dfe2] bg-white/70 p-3 sm:border-0 sm:bg-transparent sm:p-0">

                <strong className="block truncate text-sm text-[#332e34] sm:text-lg">
                  English
                </strong>

                <span className="mt-1 block text-[10px] leading-4 text-[#716a73] sm:text-sm">
                  Natural conversation
                </span>
              </div>


              <div className="min-w-0 rounded-2xl border border-[#e4dfe2] bg-white/70 p-3 sm:border-0 sm:bg-transparent sm:p-0">

                <strong className="block truncate text-sm text-[#332e34] sm:text-lg">
                  Roman Urdu
                </strong>

                <span className="mt-1 block text-[10px] leading-4 text-[#716a73] sm:text-sm">
                  Local language support
                </span>
              </div>


              <div className="min-w-0 rounded-2xl border border-[#e4dfe2] bg-white/70 p-3 sm:border-0 sm:bg-transparent sm:p-0">

                <strong className="block truncate text-sm text-[#332e34] sm:text-lg">
                  Memory
                </strong>

                <span className="mt-1 block text-[10px] leading-4 text-[#716a73] sm:text-sm">
                  Across conversations
                </span>
              </div>
            </div>
          </div>


          <div className="relative mx-auto w-full max-w-lg">

            <div
              aria-hidden="true"
              className="absolute -left-3 -top-3 h-20 w-20 rounded-3xl bg-[#7779de] sm:-left-6 sm:-top-6 sm:h-28 sm:w-28"
            />

            <div
              aria-hidden="true"
              className="absolute -bottom-3 -right-3 h-16 w-16 rounded-full bg-[#f54631] sm:-bottom-6 sm:-right-6 sm:h-24 sm:w-24"
            />


            <div className="relative overflow-hidden rounded-[1.75rem] border border-white/60 bg-[#332e34] p-4 text-white shadow-2xl shadow-[#332e34]/20 sm:rounded-[2rem] sm:p-8">

              <div className="flex items-center justify-between gap-4">

                <div className="min-w-0">
                  <p className="truncate text-[10px] uppercase tracking-[0.18em] text-white/50 sm:text-xs sm:tracking-[0.2em]">
                    Retailigent assistant
                  </p>

                  <p className="mt-1 text-sm font-medium sm:text-base">
                    How can I help?
                  </p>
                </div>


                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#7779de] font-semibold">
                  R
                </span>
              </div>


              <div className="mt-6 space-y-3 sm:mt-8 sm:space-y-4">

                <div className="ml-auto max-w-[88%] rounded-2xl rounded-br-md bg-[#7779de] px-3.5 py-3 text-xs leading-5 sm:max-w-[82%] sm:px-4 sm:text-sm sm:leading-6">
                  Show me kurtas for Eid.
                </div>


                <div className="max-w-[94%] rounded-2xl rounded-bl-md bg-white px-3.5 py-3.5 text-xs leading-5 text-[#332e34] sm:max-w-[88%] sm:px-4 sm:py-4 sm:text-sm sm:leading-6">

                  I found several matching options.

                  <div className="mt-3 grid grid-cols-3 gap-2 sm:mt-4">
                    <div className="h-16 rounded-xl bg-[#eeedfb] sm:h-24" />

                    <div className="h-16 rounded-xl bg-[#ffebe7] sm:h-24" />

                    <div className="h-16 rounded-xl bg-[#f1eeec] sm:h-24" />
                  </div>
                </div>


                <div className="ml-auto max-w-[88%] rounded-2xl rounded-br-md bg-[#7779de] px-3.5 py-3 text-xs leading-5 sm:max-w-[82%] sm:px-4 sm:text-sm sm:leading-6">
                  Show them in my usual size.
                </div>


                <div className="max-w-[94%] rounded-2xl rounded-bl-md bg-white px-3.5 py-3 text-xs leading-5 text-[#332e34] sm:max-w-[88%] sm:px-4 sm:text-sm sm:leading-6">
                  I remember your usual size is M.
                </div>
              </div>


              <div className="mt-5 flex min-w-0 items-center gap-2 rounded-2xl border border-white/10 bg-white/5 p-2.5 sm:mt-7 sm:gap-3 sm:p-3">

                <span className="min-w-0 flex-1 truncate text-xs text-white/40 sm:text-sm">
                  Ask Retailigent anything...
                </span>

                <span className="shrink-0 rounded-xl bg-[#f54631] px-3 py-2 text-xs font-medium sm:px-4 sm:text-sm">
                  Send
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>


      <section className="mx-auto max-w-7xl px-4 pb-8 sm:px-6 sm:pb-10 lg:px-10">

        <div className="grid gap-3 sm:gap-4 md:grid-cols-3">

          {
            FEATURES.map(
              (
                feature
              ) => (
                <article
                  key={
                    feature.number
                  }
                  className="rounded-2xl border border-[#e4dfe2] bg-white p-5 shadow-sm transition duration-200 hover:-translate-y-1 hover:shadow-xl sm:p-6"
                >
                  <span className="text-xs font-semibold tracking-[0.18em] text-[#7779de]">
                    {
                      feature.number
                    }
                  </span>

                  <h2 className="mt-4 text-xl font-semibold text-[#332e34] sm:mt-5 sm:text-2xl">
                    {
                      feature.title
                    }
                  </h2>

                  <p className="mt-2 text-sm leading-6 text-[#716a73] sm:mt-3 sm:leading-7">
                    {
                      feature.body
                    }
                  </p>
                </article>
              )
            )
          }
        </div>
      </section>


      <section className="mx-auto max-w-7xl px-4 pb-12 pt-6 sm:px-6 sm:pb-20 sm:pt-8 lg:px-10">

        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">

          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7779de]">
              Shopping workspace
            </p>

            <h2 className="mt-2 text-2xl font-semibold sm:text-3xl">
              Pick up where you left off.
            </h2>
          </div>


          <Link
            href="/chat"
            className="w-fit text-sm font-semibold text-[#5f62c7] hover:underline"
          >
            Open assistant →
          </Link>
        </div>


        <div className="mt-5 grid gap-3 sm:mt-6 sm:grid-cols-2 sm:gap-4 lg:grid-cols-4">

          {
            QUICK_LINKS.map(
              (
                item
              ) => (
                <Link
                  key={
                    item.href
                  }
                  href={
                    item.href
                  }
                  className="group rounded-2xl border border-[#e4dfe2] bg-white p-4 shadow-sm transition hover:-translate-y-1 hover:border-[#7779de]/40 hover:shadow-lg sm:p-5"
                >
                  <div className="flex items-center justify-between gap-3">

                    <h3 className="text-base font-semibold sm:text-lg">
                      {
                        item.label
                      }
                    </h3>

                    <span className="shrink-0 text-[#7779de] transition group-hover:translate-x-1">
                      →
                    </span>
                  </div>


                  <p className="mt-2 text-sm leading-6 text-[#716a73]">
                    {
                      item.description
                    }
                  </p>
                </Link>
              )
            )
          }
        </div>
      </section>


      <footer className="border-t border-[#e4dfe2] bg-white/60">

        <div className="mx-auto flex max-w-7xl flex-col gap-1.5 px-4 py-6 text-xs leading-5 text-[#716a73] sm:flex-row sm:items-center sm:justify-between sm:px-6 sm:py-8 sm:text-sm lg:px-10">

          <span className="font-semibold text-[#332e34]">
            Retailigent
          </span>

          <span>
            Agentic AI-powered intelligent clothing
            retail assistant
          </span>
        </div>
      </footer>
    </main>
  );
}