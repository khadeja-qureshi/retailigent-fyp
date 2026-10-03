from typing import Any


class NotificationListBlock:
    """
    UI block for a list of notifications. Formatting only.
    """

    type = "notification_list"

    @staticmethod
    def build(
        notifications: list[dict[str, Any]],
        unread_count: int | None = None,
    ) -> dict[str, Any]:
        if unread_count is None:
            unread_count = sum(
                1 for n in notifications if not n.get("read_at")
            )

        return {
            "type": NotificationListBlock.type,
            "unread_count": unread_count,
            "notifications": notifications,
        }
