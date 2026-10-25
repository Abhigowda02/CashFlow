"""Shared monthly schedules for forecasts and the expenses dashboard."""
import calendar
from datetime import date, timedelta


def monthly_occurrences(obligations, as_of, horizon_days=90):
    start = date.fromisoformat(as_of)
    rows = []
    for offset in range(horizon_days):
        day = start + timedelta(days=offset)
        for obligation in obligations:
            scheduled_day = min(int(obligation.get('day_of_month', 1)), calendar.monthrange(day.year, day.month)[1])
            if day.day == scheduled_day:
                rows.append(dict(id=obligation['id'], name=obligation.get('name', 'Obligation'),
                    amount=int(obligation.get('amount', 0)), date=day.isoformat(),
                    category=obligation.get('category', 'other'), kind='recurring',
                    requested_day=int(obligation.get('day_of_month', 1)), days_until=offset))
    return rows
