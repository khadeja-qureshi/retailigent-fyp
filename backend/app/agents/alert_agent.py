from app.services.alert_service import (
    create_customer_alert,
    list_customer_alerts,
    pause_customer_alert,
    resume_customer_alert,
    cancel_customer_alert,
)


class AlertAgent:

    def create(
        self,
        customer_id: str,
        **kwargs,
    ):
        return create_customer_alert(
            customer_id=customer_id,
            **kwargs,
        )

    def list(self, customer_id: str):
        return list_customer_alerts(
            customer_id
        )

    def pause(
        self,
        customer_id: str,
        alert_id: str,
    ):
        return pause_customer_alert(
            customer_id,
            alert_id,
        )

    def resume(
        self,
        customer_id: str,
        alert_id: str,
    ):
        return resume_customer_alert(
            customer_id,
            alert_id,
        )

    def cancel(
        self,
        customer_id: str,
        alert_id: str,
    ):
        return cancel_customer_alert(
            customer_id,
            alert_id,
        )


alert_agent = AlertAgent()