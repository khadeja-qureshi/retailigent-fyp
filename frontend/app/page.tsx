import Link from "next/link";


const FEATURES = [
  {
    number: "01",
    title: "Shop naturally",
    body:
      "Search products, check live stock and manage your shopping using normal English, Roman Urdu, or both.",
  },

  {
    number: "02",
    title: "Smart Cart",
    body:
      "Create price and discount rules, receive alerts, or authorize controlled automatic purchase workflows.",
  },

  {
    number: "03",
    title: "Memory that helps",
    body:
      "Retailigent can remember durable preferences across conversations while keeping those memories visible and deletable.",
  },
];


const QUICK_LINKS = [
  {
    href: "/cart",
    label: "Cart",
    description:
      "Review your current shopping bag.",
  },

  {
    href: "/wishlist",
    label: "Wishlist",
    description:
      "Return to products you saved.",
  },

  {
    href: "/orders",
    label: "Orders",
    description:
      "View completed mock purchases.",
  },

  {
    href: "/smart-cart",
    label: "Smart Cart",
    description:
      "Manage intelligent shopping rules.",
  },
];


export default function HomePage() {
  return (
    <main className="min-h-[calc(100vh-4rem)] overflow-hidden">
      <section className="relative">
        <div
          aria-hidden="true"
          className="absolute -left-24 top-12 h-72 w-72 rounded-full bg-[#7779de]/15 blur-3xl"
        />

        <div
          aria-hidden="true"
          className="absolute -right-24 top-52 h-72 w-72 rounded-full bg-[#f54631]/10 blur-3xl"
        />


        <div className="relative mx-auto grid max-w-7xl gap-12 px-6 py-16 lg:grid-cols-[1.1fr_0.9fr] lg:items-center lg:px-10 lg:py-24">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-[#7779de]/20 bg-white/70 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#5f62c7] shadow-sm backdrop-blur">
              <span className="h-2 w-2 rounded-full bg-[#f54631]" />

              Agentic AI for fashion retail
            </div>


            <h1 className="mt-7 max-w-4xl text-5xl font-semibold leading-[0.98] text-[#332e34] sm:text-6xl lg:text-7xl">
              Your intelligent
              <span className="block text-[#7779de]">
                shopping companion.
              </span>
            </h1>


            <p className="mt-7 max-w-2xl text-base leading-8 text-[#716a73] sm:text-lg">
              Retailigent combines conversational AI,
              live retail data, cross-conversation memory,
              Smart Cart automation and controlled purchase
              workflows into one shopping experience.
            </p>


            <div className="mt-9 flex flex-wrap gap-3">
              <Link
                href="/chat"
                className="ri-button-primary inline-flex items-center gap-3 px-6 py-3.5 font-semibold"
              >
                Start shopping

                <span aria-hidden="true">
                  →
                </span>
              </Link>

              <Link
                href="/profile"
                className="inline-flex items-center rounded-xl border border-[#d3cdd1] bg-white px-6 py-3.5 font-medium text-[#332e34] shadow-sm transition hover:-translate-y-0.5 hover:border-[#7779de] hover:shadow-md"
              >
                View my memory
              </Link>
            </div>


            <div className="mt-12 flex flex-wrap gap-x-8 gap-y-4 text-sm text-[#716a73]">
              <div>
                <strong className="block text-lg text-[#332e34]">
                  English
                </strong>

                Natural conversation
              </div>

              <div>
                <strong className="block text-lg text-[#332e34]">
                  Roman Urdu
                </strong>

                Local language support
              </div>

              <div>
                <strong className="block text-lg text-[#332e34]">
                  Memory
                </strong>

                Across conversations
              </div>
            </div>
          </div>


          <div className="relative mx-auto w-full max-w-lg">
            <div
              aria-hidden="true"
              className="absolute -left-6 -top-6 h-28 w-28 rounded-3xl bg-[#7779de]"
            />

            <div
              aria-hidden="true"
              className="absolute -bottom-6 -right-6 h-24 w-24 rounded-full bg-[#f54631]"
            />


            <div className="relative overflow-hidden rounded-[2rem] border border-white/60 bg-[#332e34] p-6 text-white shadow-2xl shadow-[#332e34]/20 sm:p-8">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-white/50">
                    Retailigent assistant
                  </p>

                  <p className="mt-1 font-medium">
                    How can I help?
                  </p>
                </div>

                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#7779de] font-semibold">
                  R
                </span>
              </div>


              <div className="mt-8 space-y-4">
                <div className="ml-auto max-w-[82%] rounded-2xl rounded-br-md bg-[#7779de] px-4 py-3 text-sm leading-6">
                  Show me kurtas for Eid.
                </div>


                <div className="max-w-[88%] rounded-2xl rounded-bl-md bg-white px-4 py-4 text-sm leading-6 text-[#332e34]">
                  I found several matching options.

                  <div className="mt-4 grid grid-cols-3 gap-2">
                    <div className="h-24 rounded-xl bg-[#eeedfb]" />

                    <div className="h-24 rounded-xl bg-[#ffebe7]" />

                    <div className="h-24 rounded-xl bg-[#f1eeec]" />
                  </div>
                </div>


                <div className="ml-auto max-w-[82%] rounded-2xl rounded-br-md bg-[#7779de] px-4 py-3 text-sm leading-6">
                  Show them in my usual size.
                </div>


                <div className="max-w-[88%] rounded-2xl rounded-bl-md bg-white px-4 py-3 text-sm leading-6 text-[#332e34]">
                  I remember your usual size is M.
                </div>
              </div>


              <div className="mt-7 flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 p-3">
                <span className="flex-1 text-sm text-white/40">
                  Ask Retailigent anything...
                </span>

                <span className="rounded-xl bg-[#f54631] px-4 py-2 text-sm font-medium">
                  Send
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>


      <section className="mx-auto max-w-7xl px-6 pb-10 lg:px-10">
        <div className="grid gap-4 md:grid-cols-3">
          {FEATURES.map(
            (feature) => (
              <article
                key={feature.number}
                className="ri-card p-6 transition duration-200 hover:-translate-y-1 hover:shadow-xl"
              >
                <span className="text-xs font-semibold tracking-[0.18em] text-[#7779de]">
                  {feature.number}
                </span>

                <h2 className="mt-5 text-2xl font-semibold text-[#332e34]">
                  {feature.title}
                </h2>

                <p className="mt-3 text-sm leading-7 text-[#716a73]">
                  {feature.body}
                </p>
              </article>
            )
          )}
        </div>
      </section>


      <section className="mx-auto max-w-7xl px-6 pb-20 pt-8 lg:px-10">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7779de]">
              Shopping workspace
            </p>

            <h2 className="mt-2 text-3xl font-semibold">
              Pick up where you left off.
            </h2>
          </div>

          <Link
            href="/chat"
            className="text-sm font-semibold text-[#5f62c7] hover:underline"
          >
            Open assistant →
          </Link>
        </div>


        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {QUICK_LINKS.map(
            (item) => (
              <Link
                key={item.href}
                href={item.href}
                className="group rounded-2xl border border-[#e4dfe2] bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:border-[#7779de]/40 hover:shadow-lg"
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold">
                    {item.label}
                  </h3>

                  <span className="text-[#7779de] transition group-hover:translate-x-1">
                    →
                  </span>
                </div>

                <p className="mt-2 text-sm leading-6 text-[#716a73]">
                  {item.description}
                </p>
              </Link>
            )
          )}
        </div>
      </section>


      <footer className="border-t border-[#e4dfe2] bg-white/60">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-6 py-8 text-sm text-[#716a73] sm:flex-row sm:items-center sm:justify-between lg:px-10">
          <span>
            Retailigent
          </span>

          <span>
            Agentic AI-powered intelligent clothing retail assistant
          </span>
        </div>
      </footer>
    </main>
  );
}