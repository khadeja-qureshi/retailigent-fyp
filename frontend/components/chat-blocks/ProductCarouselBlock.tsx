
import type {
  ProductCarouselBlock as ProductCarouselBlockData,
} from "@/lib/chat-types";

interface Props {
  block: ProductCarouselBlockData;
}

function money(value?: number | null) {
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
        {block.products.map((product) => {
          const sizes = product.sizes?.length
            ? product.sizes
            : [
                {
                  variant_id: product.variant_id,
                  size: product.size,
                  sku: product.sku,
                  effective_price: product.effective_price,
                  max_available_at_one_branch:
                    product.max_available_at_one_branch ?? 0,
                  total_available_stock:
                    product.total_available_stock ?? 0,
                },
              ];

          return (
            <article
              key={`${product.product_id}-${product.color ?? ""}`}
              className="w-72 shrink-0 overflow-hidden rounded-2xl border border-neutral-800 bg-neutral-900"
            >
              {product.image_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={product.image_url}
                  alt={`${product.name}${product.color ? ` - ${product.color}` : ""}`}
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

                {product.brand && (
                  <p className="mt-1 text-xs text-neutral-500">
                    {product.brand}
                  </p>
                )}

                <div className="mt-3 flex flex-wrap gap-2">
                  {product.color && (
                    <span className="rounded-full bg-neutral-800 px-2 py-1 text-xs text-neutral-300">
                      {product.color}
                    </span>
                  )}

                  {product.material && (
                    <span className="rounded-full bg-neutral-800 px-2 py-1 text-xs text-neutral-300">
                      {product.material}
                    </span>
                  )}
                </div>

                <div className="mt-4">
                  <h5 className="text-xs font-medium uppercase tracking-wide text-neutral-400">
                    Available sizes
                  </h5>

                  <div className="mt-2 space-y-2">
                    {sizes.map((size) => (
                      <div
                        key={size.variant_id}
                        className="flex items-center justify-between gap-3 rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-2"
                      >
                        <div>
                          <p className="text-sm font-medium">
                            {size.size
                              ? `Size ${size.size}`
                              : "Standard size"}
                          </p>

                          <p className="text-xs text-neutral-500">
                            {size.total_available_stock > 0
                              ? `${size.total_available_stock} in stock across branches`
                              : "Currently unavailable"}
                          </p>
                        </div>

                        <p className="text-sm font-semibold">
                          {money(size.effective_price)}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-4 border-t border-neutral-800 pt-3">
                  <p className="text-sm font-semibold">
                    Combined stock:{" "}
                    {product.total_available_stock ??
                      sizes.reduce(
                        (total, size) =>
                          total + size.total_available_stock,
                        0,
                      )}
                  </p>

                  <p className="mt-1 text-xs text-neutral-500">
                    Across the listed sizes and branches
                  </p>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
