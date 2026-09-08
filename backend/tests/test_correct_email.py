"""Fixing an address that was typed wrong, before the account is confirmed.

The situation these exist for: someone registers as ana@gmial.com by mistake.
The account is created under that address, the code goes to a mailbox that is
not theirs, and asking for another code with the right address finds nothing —
rule 7 keeps the screen from saying so. Without a way to correct it, the only
way out is registering again from scratch, and nothing says that either.
"""

from __future__ import annotations

from conftest import code_from_outbox, confirm, register

from models import account as accounts
from models import auth_event as events
from models import token as tokens

WRONG = "ana@gmial.com"
RIGHT = "ana@gmail.com"


def correct(client, email):
    client.get("/confirmar/corregir")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    return client.post("/confirmar/corregir",
                       data={"csrf_token": csrf, "email": email})


def pending(client):
    with client.session_transaction() as sess:
        return sess.get("pending_account_id")


# ----------------------------------------------------------------- the case

def test_correcting_the_address_and_finishing(client, database, outbox):
    """The whole thing, end to end: the case as it was asked about."""
    register(client, email=WRONG)
    assert accounts.by_email(database, WRONG) is not None

    corrected = correct(client, RIGHT)
    assert corrected.status_code == 302
    assert corrected.headers["Location"].endswith("/confirmar")

    # The new code went to the right address, and it is the one that works.
    last = sorted(outbox.glob("*.txt"))[-1].read_text(encoding="utf-8")
    assert RIGHT in last
    assert confirm(client, code_from_outbox(outbox)).headers["Location"].endswith("/panel")

    # One account, under the right address, confirmed.
    assert database.accounts.count_documents({}) == 1
    account = accounts.by_email(database, RIGHT)
    assert account is not None and account["email_confirmed_at"]
    assert accounts.by_email(database, WRONG) is None


def test_the_code_sent_to_the_wrong_address_stops_working(client, database, outbox):
    register(client, email=WRONG)
    old = code_from_outbox(outbox)

    correct(client, RIGHT)

    assert "no es correcto" in confirm(client, old).get_data(as_text=True)
    assert accounts.by_email(database, RIGHT)["email_confirmed_at"] is None
    # And there is exactly one code alive, the new one.
    assert database.account_tokens.count_documents(
        {"purpose": tokens.EMAIL_CONFIRMATION}) == 1


# --------------------------------------------------------------- the guards

def test_correcting_to_an_address_that_is_taken(client, database, outbox):
    register(client, email="beto@ejemplo.com")
    fresh = client.application.test_client()
    register(fresh, email=WRONG)

    refused = correct(fresh, "beto@ejemplo.com")

    assert refused.status_code == 200
    assert "Ya existe una cuenta con ese correo" in refused.get_data(as_text=True)
    # Nothing moved: the address with the mistake is still the one on file.
    assert accounts.by_email(database, WRONG) is not None


def test_correcting_to_the_same_address_just_sends_another_code(client, database,
                                                                outbox):
    register(client, email=WRONG)
    before = code_from_outbox(outbox)

    assert correct(client, WRONG).status_code == 302
    assert code_from_outbox(outbox) != before


def test_the_screen_needs_a_pending_unconfirmed_account(client, database, outbox):
    # Nobody waiting for anything: there is nothing to correct.
    assert client.get("/confirmar/corregir").headers["Location"].endswith("/confirmar")

    # And once the address is confirmed, this is not the door to change it.
    register(client)
    confirm(client, code_from_outbox(outbox))
    assert client.get("/confirmar/corregir").headers["Location"].endswith("/confirmar")


def test_it_cannot_be_used_to_fill_a_stranger_inbox(client, database, outbox):
    """It sends mail to an address typed by hand, like the registration form.

    So it shares the same budget per address: correcting it over and over to the
    same victim stops sending well before it becomes a nuisance, and the screen
    does not change because of it.
    """
    register(client, email=WRONG)
    answers = [correct(client, RIGHT) for _ in range(8)]

    sent = [p for p in outbox.glob("*.txt")
            if RIGHT in p.read_text(encoding="utf-8")]
    assert len(sent) == 5                      # REGISTER_PER_EMAIL
    assert {r.status_code for r in answers} == {302}
    assert len({r.headers["Location"] for r in answers}) == 1


def test_every_correction_is_recorded(client, database, outbox):
    register(client, email=WRONG)
    correct(client, RIGHT)
    correct(client, "beto@ejemplo.com")        # free, so it goes through too

    assert [d["outcome"] for d in
            database.auth_events.find({"kind": events.CORRECT_EMAIL}).sort("created_at", 1)] == [
        events.OK, events.OK]


# ------------------------------------------------ the pointer left behind

def test_a_resend_for_an_unknown_address_drops_the_pending_account(client,
                                                                   database,
                                                                   outbox):
    """The session stops waiting for an account nobody asked about.

    It changes nothing on screen —the three answers of the resend form look the
    same, which is what rule 7 asks— but the session no longer holds the account
    with the mistake in it.
    """
    register(client, email=WRONG)
    assert pending(client) is not None

    client.get("/reenviar-confirmacion")
    with client.session_transaction() as sess:
        csrf = sess["_csrf"]
    answer = client.post("/reenviar-confirmacion",
                         data={"csrf_token": csrf, "email": RIGHT})

    assert answer.headers["Location"].endswith("/confirmar")
    assert pending(client) is None
