import type {
  StockStatusBlock as StockStatusBlockData,
} from "@/lib/chat-types";


interface Props {
  block: StockStatusBlockData;
}


function statusLabel(
  status:
    | "available"
    | "low_stock"
    | "out_of_stock"
) {
  if (status === "available") {
    return "Available";
  }

  if (status === "low_stock") {
    return "Low stock";
  }

  return "Out of stock";
}


function statusClass(
  status:
    | "available"
    | "low_stock"
    | "out_of_stock"
) {
  if (status === "available") {
    return (
      "border-green-900 " +
      "bg-green-950/30 " +
      "text-green-300"
    );
  }

  if (status === "low_stock") {
    return (
      "border-amber-900 " +
      "bg-amber-950/30 " +
      "text-amber-300"
    );
  }

  return (
    "border-red-900 " +
    "bg-red-950/30 " +
    "text-red-300"
  );
}


export default function StockStatusBlock({
  block,
}: Props) {
  return (
    <section className="rounded-2xl border border-neutral-800 bg-neutral-900 p-5">
      <div>
        <p className="text-xs uppercase tracking-wide text-neutral-500">
          Stock availability
        </p>

        {block.product_name && (
          <h3 className="mt-2 text-lg font-semibold">
            {block.product_name}
          </h3>
        )}

        {block.sku && (
          <p className="mt-1 text-sm text-neutral-500">
            {block.sku}
          </p>
        )}

        {(block.color || block.size) && (
          <p className="mt-2 text-sm font-medium text-neutral-400">
            {[
              block.color
                ? `Color: ${block.color}`
                : null,
              block.size
                ? `Size: ${block.size}`
                : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        )}
      </div>

      {block.branches.length === 0 ? (
        <p className="mt-5 text-neutral-400">
          No branch stock is currently available
          for this selection.
        </p>
      ) : (
        <div className="mt-5 space-y-3">
          {block.branches.map(
            (branch) => (
              <article
                key={branch.branch_id}
                className="rounded-xl border border-neutral-800 bg-neutral-950 p-4"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h4 className="font-medium">
                      {branch.branch_name}
                    </h4>

                    {(branch.area ||
                      branch.city) && (
                      <p className="mt-1 text-sm text-neutral-500">
                        {branch.area}

                        {branch.area &&
                        branch.city
                          ? ", "
                          : ""}

                        {branch.city}
                      </p>
                    )}

                    {branch.address && (
                      <p className="mt-1 text-xs text-neutral-600">
                        {branch.address}
                      </p>
                    )}
                  </div>

                  <span
                    className={
                      "shrink-0 rounded-full " +
                      "border px-3 py-1 " +
                      "text-xs " +
                      statusClass(
                        branch.status
                      )
                    }
                  >
                    {statusLabel(
                      branch.status
                    )}
                  </span>
                </div>

                <p className="mt-3 text-sm text-neutral-300">
                  Available quantity:{" "}
                  <strong>
                    {
                      branch
                        .available_quantity
                    }
                  </strong>
                </p>
              </article>
            )
          )}
        </div>
      )}
    </section>
  );
}