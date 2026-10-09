"""Regression tests for fail-closed Stripe webhook verification."""
import os

# Importing the Flask app initializes its database schema. Keep tests isolated
# from any developer or production database and credentials.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("SESSION_SECRET", "cleanestimate-test-session-secret")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_only")

import pytest  # noqa: E402
import app as cleanestimate  # noqa: E402


@pytest.fixture()
def client():
    cleanestimate.app.config.update(TESTING=True)
    with cleanestimate.app.test_client() as test_client:
        yield test_client


def test_webhook_fails_closed_when_secret_is_unconfigured(client, monkeypatch):
    monkeypatch.setattr(cleanestimate, "STRIPE_WEBHOOK_SECRET", "")
    construct_event = pytest.MonkeyPatch()
    construct_event.setattr(
        cleanestimate.stripe.Webhook,
        "construct_event",
        staticmethod(lambda *args: pytest.fail("must not parse an unsigned event")),
    )
    try:
        response = client.post(
            "/stripe/webhook",
            data=b'{"type":"checkout.session.completed","data":{"object":{}}}',
            content_type="application/json",
        )
    finally:
        construct_event.undo()

    assert response.status_code == 503
    assert response.get_json()["error"] == "Webhook endpoint is not configured"


def test_webhook_rejects_missing_signature(client, monkeypatch):
    monkeypatch.setattr(cleanestimate, "STRIPE_WEBHOOK_SECRET", "whsec_test_only")
    monkeypatch.setattr(
        cleanestimate.stripe.Webhook,
        "construct_event",
        staticmethod(lambda *args: pytest.fail("must reject before verification")),
    )

    response = client.post(
        "/stripe/webhook",
        data=b'{"type":"checkout.session.completed","data":{"object":{}}}',
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Missing Stripe-Signature header"


def test_webhook_rejects_invalid_signature(client, monkeypatch):
    monkeypatch.setattr(cleanestimate, "STRIPE_WEBHOOK_SECRET", "whsec_test_only")

    def reject_signature(payload, signature, secret):
        raise cleanestimate.stripe.SignatureVerificationError(
            message="invalid signature", sig_header=signature
        )

    monkeypatch.setattr(
        cleanestimate.stripe.Webhook,
        "construct_event",
        staticmethod(reject_signature),
    )

    response = client.post(
        "/stripe/webhook",
        data=b'{"type":"checkout.session.completed","data":{"object":{}}}',
        headers={"Stripe-Signature": "t=1,v1=invalid"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid signature"


def test_verified_checkout_event_reaches_existing_handler(client, monkeypatch):
    secret = "whsec_test_only"
    raw_payload = b'{"type":"checkout.session.completed","data":{"object":{"id":"cs_test"}}}'
    signature = "t=1,v1=test-signature"
    event_data = {"id": "cs_test"}
    event = {
        "type": "checkout.session.completed",
        "data": {"object": event_data},
    }
    verification_calls = []
    handled = []

    def verify(payload, received_signature, received_secret):
        verification_calls.append((payload, received_signature, received_secret))
        return event

    monkeypatch.setattr(cleanestimate, "STRIPE_WEBHOOK_SECRET", secret)
    monkeypatch.setattr(
        cleanestimate.stripe.Webhook, "construct_event", staticmethod(verify)
    )
    monkeypatch.setattr(
        cleanestimate, "_handle_checkout_completed", lambda data: handled.append(data)
    )

    response = client.post(
        "/stripe/webhook",
        data=raw_payload,
        headers={"Stripe-Signature": signature},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert verification_calls == [(raw_payload, signature, secret)]
    assert handled == [event_data]
