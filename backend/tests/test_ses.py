"""The SES backend, without touching the network.

boto3 is imported inside _send_ses(), so a fake module put in sys.modules is
enough to see exactly what would be sent to AWS. What matters here is the shape
of that call — the wrong key name fails at run time, on the one path that is
hardest to try out during development — and that a refusal from AWS survives in
mail_log with the provider's own words.
"""

from __future__ import annotations

import sys
import types

import pytest

from config import Config
from models import mail_log
from services import mailer


class FakeSES:
    """Stands in for the boto3 SES client."""

    def __init__(self, message_id="0100018f-aws-id", error=None):
        self.message_id = message_id
        self.error = error
        self.calls = []
        self.region = None

    def send_email(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"MessageId": self.message_id}


@pytest.fixture()
def ses(monkeypatch):
    """MAIL_BACKEND=ses, with a client that records instead of sending."""
    client = FakeSES()

    def make_client(service, region_name=None, **kwargs):
        assert service == "ses"
        client.region = region_name
        return client

    fake_boto3 = types.ModuleType("boto3")
    fake_boto3.client = make_client
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setattr(Config, "MAIL_BACKEND", "ses")
    monkeypatch.setattr(Config, "SYSTEM_FROM_EMAIL", "notifications@mail.sobreala.com")
    monkeypatch.setattr(Config, "SYSTEM_FROM_NAME", "Sobreala")
    monkeypatch.setattr(Config, "AWS_REGION", "us-east-1")
    monkeypatch.setattr(Config, "SES_TRANSACTIONAL_CONFIGURATION_SET", "")
    return client


def send_one(to="ana@ejemplo.com"):
    return mailer.send(to=to, subject="Tu código", html="<p>481920</p>",
                       text="481920", purpose=mail_log.CONFIRM)


def test_the_call_to_aws_has_the_shape_ses_expects(ses, database):
    identifier = send_one()

    assert identifier == "0100018f-aws-id"
    assert ses.region == "us-east-1"
    sent = ses.calls[0]
    assert sent["Source"] == "Sobreala <notifications@mail.sobreala.com>"
    assert sent["Destination"] == {"ToAddresses": ["ana@ejemplo.com"]}
    assert sent["Message"]["Subject"]["Data"] == "Tu código"
    # Both parts travel: the text one is what a client that refuses HTML shows.
    assert sent["Message"]["Body"]["Html"]["Data"] == "<p>481920</p>"
    assert sent["Message"]["Body"]["Text"]["Data"] == "481920"
    assert sent["Message"]["Subject"]["Charset"] == "UTF-8"


def test_the_configuration_set_only_travels_when_there_is_one(ses, database,
                                                              monkeypatch):
    send_one()
    assert "ConfigurationSetName" not in ses.calls[0]

    monkeypatch.setattr(Config, "SES_TRANSACTIONAL_CONFIGURATION_SET", "sobreala-system")
    send_one()
    assert ses.calls[1]["ConfigurationSetName"] == "sobreala-system"


def test_a_sent_message_is_recorded_with_the_aws_identifier(ses, database):
    send_one()

    row = database.mail_log.find_one({})
    assert row["backend"] == "ses"
    assert row["status"] == mail_log.SENT
    assert row["provider_id"] == "0100018f-aws-id"


def test_a_refusal_from_aws_survives_in_the_log(ses, database):
    # What SES answers while the account is still in the sandbox.
    ses.error = RuntimeError(
        "MessageRejected: Email address is not verified. The following "
        "identities failed the check in region US-EAST-1: ana@ejemplo.com")

    with pytest.raises(RuntimeError):
        send_one()

    row = database.mail_log.find_one({})
    assert row["status"] == mail_log.FAILED
    assert row["backend"] == "ses"
    assert "is not verified" in row["error"]
    assert row["provider_id"] is None
    # The body is kept, so what was going to be sent can still be read.
    assert "481920" in row["text"]


# ------------------------------------------------------------- configuration

def test_a_deploy_without_credentials_refuses_to_start(monkeypatch):
    monkeypatch.setattr(Config, "SECRET_KEY", "una-clave")
    monkeypatch.setattr(Config, "MAIL_BACKEND", "ses")
    monkeypatch.setattr(Config, "AWS_ACCESS_KEY_ID", "")
    monkeypatch.setattr(Config, "AWS_SECRET_ACCESS_KEY", "")

    with pytest.raises(RuntimeError) as refused:
        Config.check()
    # The message names what is missing, because that is what the person
    # reading the deploy log needs.
    assert "AWS_ACCESS_KEY_ID" in str(refused.value)
    assert "AWS_SECRET_ACCESS_KEY" in str(refused.value)


def test_with_credentials_it_starts(monkeypatch):
    monkeypatch.setattr(Config, "SECRET_KEY", "una-clave")
    monkeypatch.setattr(Config, "MAIL_BACKEND", "ses")
    monkeypatch.setattr(Config, "AWS_ACCESS_KEY_ID", "AKIA...")
    monkeypatch.setattr(Config, "AWS_SECRET_ACCESS_KEY", "secreta")
    monkeypatch.setattr(Config, "SYSTEM_FROM_EMAIL", "notifications@mail.sobreala.com")

    Config.check()  # no exception


def test_the_health_page_says_which_backend_is_live(client, database, monkeypatch):
    monkeypatch.setattr(Config, "MAIL_BACKEND", "ses")
    payload = client.get("/health").get_json()

    assert payload["mail"] == "ses"
    # And never anything that could be a credential.
    assert "AKIA" not in str(payload)
    assert "secret" not in str(payload).lower()
