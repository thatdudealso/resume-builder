from apps.web.config import Settings


def test_payments_disabled_when_no_keys():
    s = Settings(stripe_secret_key="", nowpayments_api_key="")
    assert s.payments_enabled is False


def test_payments_enabled_when_stripe_key_present():
    s = Settings(stripe_secret_key="sk_live_x", nowpayments_api_key="")
    assert s.payments_enabled is True


def test_explicit_override_wins():
    s = Settings(stripe_secret_key="sk_live_x", payments_enabled_override="false")
    assert s.payments_enabled is False
    s2 = Settings(stripe_secret_key="", payments_enabled_override="true")
    assert s2.payments_enabled is True


def test_support_url_defaults_empty():
    assert Settings().support_url == ""
