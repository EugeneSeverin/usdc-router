from datetime import timedelta

from app.bot.alerts import evaluate
from app.models import TgSubscriber, utcnow


def sub(th=1.0):
    return TgSubscriber(chat_id=1, spread_threshold=th, active=True)


def test_needs_30_minutes_above_threshold():
    s, t0 = sub(), utcnow()
    assert not evaluate(s, 2.0, t0)
    assert not evaluate(s, 2.0, t0 + timedelta(minutes=29))
    assert evaluate(s, 2.0, t0 + timedelta(minutes=30))


def test_dip_below_threshold_resets_timer():
    s, t0 = sub(), utcnow()
    evaluate(s, 2.0, t0)
    assert not evaluate(s, 0.5, t0 + timedelta(minutes=20))
    assert not evaluate(s, 2.0, t0 + timedelta(minutes=35))  # таймер начался заново
    assert evaluate(s, 2.0, t0 + timedelta(minutes=65))


def test_cooldown_six_hours():
    s, t0 = sub(), utcnow()
    evaluate(s, 2.0, t0)
    assert evaluate(s, 2.0, t0 + timedelta(minutes=30))
    assert not evaluate(s, 2.0, t0 + timedelta(hours=5))
    assert evaluate(s, 2.0, t0 + timedelta(hours=6, minutes=31))


def test_no_data_never_alerts():
    assert not evaluate(sub(), None, utcnow())
