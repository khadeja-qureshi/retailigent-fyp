import type {
  ProductCarouselBlock as ProductCarouselBlockData,
} from "@/lib/chat-types";


interface Props {
  block: ProductCarouselBlockData;
}


function money(
  value?: number | null
) {
  if (value == null) {
    return "Price unavailable";
  }

  return `Rs. ${value.toLocaleString()}`;
}


export default function ProductCarouselBlock({
  block,
}: Props) {
  if (block.products.length === 0) {
    return (
      <section className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
        <p className="text-neutral-400">
          No matching products found.
        </p>
      </section>
    );
  }

  return (
    <section>
      <h3 className="mb-3 text-sm font-medium text-neutral-400">
        {block.title}
      </h3>

      <div className="flex gap-4 overflow-x-auto pb-3">
        {block.products.map(
            (product) => (
            <article
              key={product.variant_id}
              className="w-64 shrink-0 overflow-hidden rounded-2xl border border-neutral-800 bg-neutral-900"
            >
              {product.image_url ? (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img
                  src={product.image_url}
                  alt={product.name}
                  className="h-64 w-full object-cover"
                />
              ) : (
                <div className="flex h-64 items-center justify-center bg-neutral-800 text-sm text-neutral-500">
                  No image
                </div>
              )}

              <div className="p-4">
                <h4 className="font-semibold">
                  {product.name}
                </h4>

                <p className="mt-1 text-xs text-neutral-500">
                  {product.sku}
                </p>

                <div className="mt-3 flex flex-wrap gap-2">
                  {product.color && (
                    <span className="rounded-full bg-neutral-800 px-2 py-1 text-xs text-neutral-300">
                      {product.color}
                    </span>
                  )}

                  {product.size && (
                    <span className="rounded-full bg-neutral-800 px-2 py-1 text-xs text-neutral-300">
                      Size {product.size}
                    </span>
                  )}

                  {product.material && (
                    <span className="rounded-full bg-neutral-800 px-2 py-1 text-xs text-neutral-300">
                      {product.material}
                    </span>
                  )}
                </div>

                <p className="mt-4 font-semibold">
                  {money(
                    product.effective_price
                  )}
                </p>

                <p className="mt-2 text-xs text-neutral-500">
                  {(
                    product
                      .max_available_at_one_branch ??
                    0
                  ) > 0
                    ? `Up to ${
                        product
                          .max_available_at_one_branch
                      } available at one branch`
                    : "Currently unavailable"}
                </p>
              </div>
            </article>
          )
        )}
      </div>
    </section>
  );
}
