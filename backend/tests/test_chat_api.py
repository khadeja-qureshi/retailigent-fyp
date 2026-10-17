from fastapi.testclient import (
    TestClient,
)

import app.api.v1.chat as chat_module

from app.core.auth import (
    get_current_user_id,
    require_customer,
)
from app.main import app
from app.schemas.chat import (
    ChatTurnResponse,
    ProductCard,
    ProductCarouselBlock,
)


def _fake_customer_id():
    return "customer-1"


def _fake_customer_role():
    return "customer"


def _install_auth_overrides():
    app.dependency_overrides[
        get_current_user_id
    ] = _fake_customer_id

    app.dependency_overrides[
        require_customer
    ] = _fake_customer_role


def _clear_auth_overrides():
    app.dependency_overrides.clear()


def test_chat_streams_message_and_block(
    monkeypatch,
):
    _install_auth_overrides()

    called = {}

    def fake_process_turn(
        *,
        customer_id,
        message,
        conversation_id=None,
    ):
        called[
            "customer_id"
        ] = customer_id

        called[
            "message"
        ] = message

        called[
            "conversation_id"
        ] = conversation_id

        return ChatTurnResponse(
            conversation_id=(
                "conversation-123"
            ),
            message_id=(
                "message-123"
            ),
            content=(
                "I found one product."
            ),
            language="english",
            blocks=[
                ProductCarouselBlock(
                    products=[
                        ProductCard(
                            product_id=(
                                "product-1"
                            ),
                            variant_id=(
                                "variant-1"
                            ),
                            name=(
                                "Printed Lawn Kurta"
                            ),
                            sku=(
                                "SKU-1"
                            ),
                        )
                    ]
                )
            ],
        )

    monkeypatch.setattr(
        chat_module
        .orchestrator_agent,
        "process_turn",
        fake_process_turn,
    )

    try:
        client = TestClient(
            app
        )

        with client.stream(
            "POST",
            "/api/v1/chat",
            json={
                "message":
                    "Show me kurtas",
            },
        ) as response:
            body = "".join(
                response.iter_text()
            )

        assert (
            response.status_code
            == 200
        )

        assert (
            response.headers[
                "content-type"
            ].startswith(
                "text/event-stream"
            )
        )

        assert (
            called["customer_id"]
            == "customer-1"
        )

        assert (
            called["message"]
            == "Show me kurtas"
        )

        assert (
            "event: turn_started"
            in body
        )

        assert (
            "event: conversation"
            in body
        )

        assert (
            "conversation-123"
            in body
        )

        assert (
            "event: message_start"
            in body
        )

        assert (
            "event: message_delta"
            in body
        )

        assert (
            "I found one product."
            in body
        )

        assert (
            "event: block"
            in body
        )

        assert (
            "product_carousel"
            in body
        )

        assert (
            "event: done"
            in body
        )

    finally:
        _clear_auth_overrides()


def test_chat_passes_existing_conversation_id(
    monkeypatch,
):
    _install_auth_overrides()

    called = {}

    def fake_process_turn(
        *,
        customer_id,
        message,
        conversation_id=None,
    ):
        called[
            "conversation_id"
        ] = conversation_id

        return ChatTurnResponse(
            conversation_id=(
                conversation_id
                or "new-conversation"
            ),
            message_id="message-1",
            content="Done.",
            language="english",
            blocks=[],
        )

    monkeypatch.setattr(
        chat_module
        .orchestrator_agent,
        "process_turn",
        fake_process_turn,
    )

    try:
        client = TestClient(
            app
        )

        response = client.post(
            "/api/v1/chat",
            json={
                "message":
                    "Is it available?",
                "conversation_id":
                    "conversation-existing",
            },
        )

        assert (
            response.status_code
            == 200
        )

        assert (
            called[
                "conversation_id"
            ]
            ==
            "conversation-existing"
        )

        assert (
            "conversation-existing"
            in response.text
        )

    finally:
        _clear_auth_overrides()


def test_chat_streams_safe_error_event(
    monkeypatch,
):
    _install_auth_overrides()

    def fake_process_turn(
        **kwargs,
    ):
        raise RuntimeError(
            "secret internal database detail"
        )

    monkeypatch.setattr(
        chat_module
        .orchestrator_agent,
        "process_turn",
        fake_process_turn,
    )

    try:
        client = TestClient(
            app
        )

        response = client.post(
            "/api/v1/chat",
            json={
                "message":
                    "Show me kurtas",
            },
        )

        assert (
            response.status_code
            == 200
        )

        assert (
            "event: error"
            in response.text
        )

        assert (
            "I couldn't complete "
            "that request right now."
            in response.text
        )

        assert (
            "secret internal database detail"
            not in response.text
        )

    finally:
        _clear_auth_overrides()