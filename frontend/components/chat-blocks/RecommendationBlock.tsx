"use client";

import Image from "next/image";
import type { RecommendationChatBlock } from "@/lib/chat-types";

export default function RecommendationBlock({
  block,
}: {
  block: RecommendationChatBlock;
}) {
  return (
    <section className="rounded-2xl border border-[#d8d2dd] bg-[#f7f4f8] p-4 text-[#332e34]">
      <h3 className="text-base font-semibold text-[#332e34]">
        {block.title}
      </h3>

      {block.products.length === 0 ? (
        <p className="mt-3 text-sm text-[#716a73]">
          No matching recommendations were found. Try changing your filters.
        </p>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {block.products.map((product) => (
            <article
              key={product.variant_id}
              className="overflow-hidden rounded-xl border border-[#ded8e2] bg-white shadow-sm"
            >
              {product.image_url && (
                <div className="relative aspect-[4/3] overflow-hidden bg-[#f3f0f4]">
                  <Image
                    src={product.image_url}
                    alt={product.name}
                    fill
                    sizes="(max-width: 640px) 100vw, 50vw"
                    className="object-cover"
                  />
                </div>
              )}

              <div className="p-3">
                <h4 className="font-semibold text-[#332e34]">
                  {product.name}
                </h4>

                {product.brand && (
                  <p className="mt-1 text-xs text-[#716a73]">
                    {product.brand}
                  </p>
                )}

                <div className="mt-2 flex flex-wrap gap-x-2 gap-y-1 text-xs text-[#716a73]">
                  {product.color && (
                    <span>Color: {product.color}</span>
                  )}

                  {product.size && (
                    <span>Size: {product.size}</span>
                  )}

                  {product.material && (
                    <span>{product.material}</span>
                  )}
                </div>

                {product.effective_price != null && (
                  <p className="mt-3 font-semibold text-[#332e34]">
                    Rs. {product.effective_price.toLocaleString()}
                  </p>
                )}

                {product.max_available_at_one_branch != null && (
                  <p className="mt-1 text-xs text-[#716a73]">
                    Up to {product.max_available_at_one_branch} available at one branch
                  </p>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}