import type {
  SupportEscalationChatBlock,
} from "@/lib/chat-types";


interface Props {
  block: SupportEscalationChatBlock;
}


export default function SupportEscalationBlock({
  block,
}: Props) {
  const statusLabel =
    block.status.replaceAll("_", " ");

  return (
    <section className="rounded-2xl border border-blue-900 bg-blue-950/20 p-5">
      <p className="text-xs uppercase tracking-wide text-blue-400">
        Customer support
      </p>

      <h3 className="mt-2 text-lg font-semibold text-neutral-100">
        Support request submitted
      </h3>

      <p className="mt-2 text-sm text-neutral-300">
        {block.message}
      </p>

      <div className="mt-4 space-y-2 rounded-xl border border-neutral-800 bg-neutral-950/40 p-4">
        <p className="text-sm text-neutral-300">
          <span className="text-neutral-500">
            Ticket ID:{" "}
          </span>
          <strong className="break-all text-neutral-100">
            {block.ticket_id}
          </strong>
        </p>

        <p className="text-sm text-neutral-300">
          <span className="text-neutral-500">
            Subject:{" "}
          </span>
          {block.subject}
        </p>

        <p className="text-sm text-neutral-300 capitalize">
          <span className="text-neutral-500">
            Status:{" "}
          </span>
          {statusLabel}
        </p>
      </div>

      <p className="mt-3 text-xs text-neutral-500">
        Keep your ticket ID for future reference.
      </p>
    </section>
  );
}
