from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app.api.v1.audit as audit_module

from app.core.auth import (
    get_current_user_roles,
)
from app.main import app
from app.services import audit_service
from app.services.audit_service import (
    AuditServiceError,
)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield

    app.dependency_overrides.clear()


def _as(
    roles: list[str],
):
    app.dependency_overrides[
        get_current_user_roles
    ] = lambda: roles


def _empty_result():
    return {
        "entries": [],
        "total": 0,
        "limit": 50,
        "offset": 0,
    }


# ============================================================================
# API authorization
# ============================================================================


def test_customer_role_is_forbidden(
    monkeypatch,
):
    _as(
        [
            "customer",
        ]
    )


    called = []


    monkeypatch.setattr(
        audit_module.audit_service,
        "list_audit_logs",
        (
            lambda **kw:
                called.append(
                    kw
                )
                or
                _empty_result()
        ),
    )


    with TestClient(
        app
    ) as client:
        response = client.get(
            "/api/v1/admin/audit-logs"
        )


    assert (
        response.status_code
        == 403
    )

    assert (
        called
        == []
    )


@pytest.mark.parametrize(
    "roles",
    [
        [
            "staff",
        ],
        [
            "manager",
        ],
        [
            "admin",
        ],
    ],
)
def test_privileged_roles_can_read_audit_logs(
    monkeypatch,
    roles,
):
    _as(
        roles
    )


    monkeypatch.setattr(
        audit_module.audit_service,
        "list_audit_logs",
        lambda **kw:
            _empty_result(),
    )


    with TestClient(
        app
    ) as client:
        response = client.get(
            "/api/v1/admin/audit-logs"
        )


    assert (
        response.status_code
        == 200
    )


def test_admin_can_read_and_filters_are_forwarded(
    monkeypatch,
):
    _as(
        [
            "admin",
        ]
    )


    captured = {}


    def fake(
        **kw,
    ):
        captured.update(
            kw
        )

        return {
            "entries": [
                {
                    "id":
                        "1",

                    "created_at":
                        (
                            "2026-10-26"
                            "T10:00:00+00:00"
                        ),

                    "actor_user_id":
                        None,

                    "actor_name":
                        None,

                    "actor_type":
                        "system",

                    "action":
                        "role_granted",

                    "entity_type":
                        "user_roles",

                    "entity_id":
                        None,

                    "before_data":
                        None,

                    "after_data": {
                        "role":
                            "customer",
                    },

                    "metadata":
                        {},
                }
            ],

            "total":
                1,

            "limit":
                10,

            "offset":
                20,
        }


    monkeypatch.setattr(
        audit_module.audit_service,
        "list_audit_logs",
        fake,
    )


    with TestClient(
        app
    ) as client:
        response = client.get(
            (
                "/api/v1/admin/audit-logs"
                "?action=role_"
                "&entity_type=user_roles"
                "&actor_type=system"
                "&limit=10"
                "&offset=20"
            )
        )


    assert (
        response.status_code
        == 200
    )


    body = (
        response.json()
    )


    assert (
        body[
            "total"
        ]
        == 1
    )


    assert (
        body[
            "entries"
        ][
            0
        ][
            "action"
        ]
        ==
        "role_granted"
    )


    assert (
        captured[
            "action"
        ]
        ==
        "role_"
    )


    assert (
        captured[
            "entity_type"
        ]
        ==
        "user_roles"
    )


    assert (
        captured[
            "actor_type"
        ]
        ==
        "system"
    )


    assert (
        captured[
            "limit"
        ]
        == 10
    )


    assert (
        captured[
            "offset"
        ]
        == 20
    )


def test_invalid_actor_type_is_rejected(
    monkeypatch,
):
    _as(
        [
            "admin",
        ]
    )


    monkeypatch.setattr(
        audit_module.audit_service,
        "list_audit_logs",
        (
            lambda **kw:
                _empty_result()
        ),
    )


    with TestClient(
        app
    ) as client:
        response = client.get(
            (
                "/api/v1/admin/audit-logs"
                "?actor_type=hacker"
            )
        )


    assert (
        response.status_code
        == 400
    )


def test_limit_above_maximum_is_rejected():
    _as(
        [
            "admin",
        ]
    )


    with TestClient(
        app
    ) as client:
        response = client.get(
            (
                "/api/v1/admin/audit-logs"
                "?limit=5000"
            )
        )


    assert (
        response.status_code
        == 422
    )


def test_service_failure_returns_500_without_leaking_details(
    monkeypatch,
):
    _as(
        [
            "admin",
        ]
    )


    def boom(
        **kw,
    ):
        raise AuditServiceError(
            (
                "Could not load "
                "the audit log."
            )
        )


    monkeypatch.setattr(
        audit_module.audit_service,
        "list_audit_logs",
        boom,
    )


    with TestClient(
        app
    ) as client:
        response = client.get(
            "/api/v1/admin/audit-logs"
        )


    assert (
        response.status_code
        == 500
    )


    assert (
        response.json()[
            "detail"
        ]
        ==
        "Could not load the audit log."
    )


def test_there_is_no_write_endpoint_for_audit_logs():
    _as(
        [
            "admin",
        ]
    )


    with TestClient(
        app
    ) as client:
        for method in (
            "post",
            "put",
            "patch",
            "delete",
        ):
            response = getattr(
                client,
                method,
            )(
                "/api/v1/admin/audit-logs"
            )


            assert (
                response.status_code
                == 405
            )


# ============================================================================
# Audit service
# ============================================================================


@pytest.fixture
def mocked_supabase(
    monkeypatch,
):
    query = (
        MagicMock()
    )


    for name in (
        "select",
        "eq",
        "ilike",
        "gte",
        "lte",
        "order",
        "range",
    ):
        getattr(
            query,
            name,
        ).return_value = query


    client = (
        MagicMock()
    )


    client.table.return_value = (
        query
    )


    monkeypatch.setattr(
        audit_service,
        "supabase_admin",
        client,
    )


    return {
        "client":
            client,

        "query":
            query,
    }


def test_service_applies_filters_and_caps_limit(
    mocked_supabase,
):
    q = (
        mocked_supabase[
            "query"
        ]
    )


    q.execute.return_value = (
        SimpleNamespace(
            data=[],
            count=0,
        )
    )


    audit_service.list_audit_logs(
        action=
            "role_",

        entity_type=
            "user_roles",

        actor_type=
            "staff",

        since=(
            "2026-10-01"
            "T00:00:00+00:00"
        ),

        limit=
            10_000,

        offset=
            -5,
    )


    (
        mocked_supabase[
            "client"
        ]
        .table
        .assert_called_once_with(
            "audit_logs"
        )
    )


    q.eq.assert_any_call(
        "entity_type",
        "user_roles",
    )


    q.eq.assert_any_call(
        "actor_type",
        "staff",
    )


    q.gte.assert_called_once_with(
        "created_at",
        (
            "2026-10-01"
            "T00:00:00+00:00"
        ),
    )


    q.range.assert_called_once_with(
        0,
        199,
    )


    q.order.assert_any_call(
        "created_at",
        desc=True,
    )


def test_service_escapes_like_wildcards_in_action(
    mocked_supabase,
):
    q = (
        mocked_supabase[
            "query"
        ]
    )


    q.execute.return_value = (
        SimpleNamespace(
            data=[],
            count=0,
        )
    )


    audit_service.list_audit_logs(
        action=
            "100%_off"
    )


    q.ilike.assert_called_once_with(
        "action",
        r"100\%\_off%",
    )


def test_service_flattens_actor_name(
    mocked_supabase,
):
    q = (
        mocked_supabase[
            "query"
        ]
    )


    q.execute.return_value = (
        SimpleNamespace(
            data=[
                {
                    "id":
                        "a1",

                    "created_at":
                        (
                            "2026-10-26"
                            "T10:00:00+00:00"
                        ),

                    "actor_user_id":
                        "u1",

                    "actor_type":
                        "staff",

                    "action":
                        "promotion_updated",

                    "entity_type":
                        "promotions",

                    "entity_id":
                        "p1",

                    "before_data": {
                        "discount_value":
                            10,
                    },

                    "after_data": {
                        "discount_value":
                            20,
                    },

                    "metadata":
                        None,

                    "actor": {
                        "full_name":
                            "Sara Staff",
                    },
                }
            ],

            count=
                41,
        )
    )


    result = (
        audit_service
        .list_audit_logs(
            limit=1
        )
    )


    assert (
        result[
            "total"
        ]
        == 41
    )


    entry = (
        result[
            "entries"
        ][
            0
        ]
    )


    assert (
        entry[
            "actor_name"
        ]
        ==
        "Sara Staff"
    )


    assert (
        entry[
            "metadata"
        ]
        == {}
    )


    assert (
        "actor"
        not in entry
    )


def test_service_wraps_database_errors(
    mocked_supabase,
):
    (
        mocked_supabase[
            "query"
        ]
        .execute
        .side_effect
    ) = RuntimeError(
        "db down: secret"
    )


    with pytest.raises(
        AuditServiceError
    ) as caught:
        (
            audit_service
            .list_audit_logs()
        )


    assert (
        "secret"
        not in str(
            caught.value
        )
    )