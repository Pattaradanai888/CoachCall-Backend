# src/analytics/utils.py
from datetime import date, timedelta
from typing import Any


def format_trend_data(daily_counts_dict: dict[date, int]) -> list[dict[str, Any]]:
    six_days_ago = date.today() - timedelta(days=6)
    dates = [six_days_ago + timedelta(days=i) for i in range(7)]
    trend_data = []
    for d in dates:
        count = daily_counts_dict.get(d, 0)
        trend_data.append(
            {
                "date": d.isoformat(),
                "day_name": d.strftime("%a"),
                "formatted_date": d.strftime("%m/%d"),
                "count": count,
            }
        )
    return trend_data


def calculate_weekly_insights(
    week_count: int, prev_week_count: int, trend_data: list[dict[str, Any]]
) -> tuple[float | None, str | None, float, bool | None]:
    week_change = None
    is_growing = None
    if prev_week_count is not None and prev_week_count > 0:
        week_change = round(((week_count - prev_week_count) / prev_week_count) * 100, 1)
        is_growing = week_change > 0
    elif prev_week_count == 0 and week_count > 0:
        is_growing = True
        week_change = 100.0

    peak_day = None
    max_count = 0
    for item in trend_data:
        if item["count"] > max_count:
            max_count = item["count"]
            peak_day = item["day_name"]
    if max_count == 0:
        peak_day = None

    avg_daily = round(week_count / 7, 1) if week_count > 0 else 0.0

    return week_change, peak_day, avg_daily, is_growing
