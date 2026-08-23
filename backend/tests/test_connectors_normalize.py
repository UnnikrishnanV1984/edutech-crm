"""Pure normalize()/fetch_raw_leads() tests — no DB, no Redis. Each
connector's seed file is shaped like that platform's real payload
(SEED_CONNECTORS_PLAN.md step 6/7), so this proves normalize() actually
maps platform-specific fields into a RawLead, not a pass-through."""

from app.connectors.google import GoogleConnector
from app.connectors.meta import MetaConnector
from app.connectors.web import WebConnector
from app.connectors.whatsapp import WhatsAppConnector


def test_meta_connector_normalizes_field_data_array():
    leads = MetaConnector().fetch_raw_leads()
    assert len(leads) == 3
    first = leads[0]
    assert first.external_id == "120211000000001"
    assert first.full_name == "Priya Sharma"
    assert first.email == "priya.sharma@example.test"
    assert first.phone == "+91-9876543210"
    assert first.course_code == "MBA-FIN"
    assert first.occurred_at.year == 2026


def test_google_connector_normalizes_user_column_data():
    leads = GoogleConnector().fetch_raw_leads()
    assert len(leads) == 3
    first = leads[0]
    assert first.external_id == "gid-2026-000001"
    assert first.full_name == "Rahul Verma"
    assert first.email == "rahul.verma@example.test"
    assert first.course_code == "CS-101"


def test_web_connector_normalizes_form_submission():
    leads = WebConnector().fetch_raw_leads()
    assert len(leads) == 3
    first = leads[0]
    assert first.external_id == "web-sub-000001"
    assert first.full_name == "Neha Gupta"
    assert first.course_code == "DS-202"


def test_whatsapp_connector_has_no_email_and_e164_phone():
    leads = WhatsAppConnector().fetch_raw_leads()
    assert len(leads) == 3
    first = leads[0]
    assert first.external_id == "wamid.HBgMOTE5ODc2NTAwMDAxFQIAERgS"
    assert first.full_name == "Arjun Mehta"
    assert first.email is None
    assert first.phone == "+919876500001"
    assert first.course_code == "MBA-FIN"


def test_all_connectors_declare_a_valid_lead_source():
    for connector_cls in (MetaConnector, GoogleConnector, WebConnector, WhatsAppConnector):
        assert connector_cls().source in ("meta", "google", "web", "whatsapp")
