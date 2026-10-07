"""日本の営業日（P6）：土日・国民の祝日（振替休日・国民の休日を含む）を休みとする。

祝日は jpholiday（MIT、ローカル計算、ネットワーク不要）で判定する。対応年は SUPPORTED_YEARS。
範囲外の日付は祝日を判定できないため土日だけを休みとし、画面に注意を出す（安全側：結転は自動で決めない）。
将来の祝日法の改正は jpholiday の更新で反映する（版は requirements.txt で固定）。
"""
from datetime import timedelta

import jpholiday

SUPPORTED_YEARS = (2000, 2050)
MAX_SEARCH_DAYS = 31


def is_supported(day):
    return SUPPORTED_YEARS[0] <= day.year <= SUPPORTED_YEARS[1]


def holiday_name(day):
    """祝日名（祝日でなければ空文字）。対応年の範囲外は判定しない（空文字）。"""
    if not is_supported(day):
        return ''
    return jpholiday.is_holiday_name(day) or ''


def is_business_day(day):
    return day.weekday() < 5 and not holiday_name(day)


def next_business_day(day):
    """day の翌日以降で最初の営業日。"""
    candidate = day + timedelta(days=1)
    for _ in range(MAX_SEARCH_DAYS):
        if is_business_day(candidate):
            return candidate
        candidate += timedelta(days=1)
    return candidate


def day_info(day):
    weekend = day.weekday() >= 5
    name = holiday_name(day)
    supported = is_supported(day)
    notice = ''
    if not supported:
        notice = f'{SUPPORTED_YEARS[0]}～{SUPPORTED_YEARS[1]} 年以外は祝日を判定できません（土日だけを休みとして扱います）。'
    elif name:
        notice = f'{day.month}月{day.day}日は祝日（{name}）です。'
    elif weekend:
        notice = f'{day.month}月{day.day}日は{"土" if day.weekday() == 5 else "日"}曜日です。'
    return {
        'date': day.isoformat(),
        'is_weekend': weekend,
        'holiday_name': name,
        'is_business_day': not weekend and not name,
        'next_business_day': next_business_day(day).isoformat(),
        'supported': supported,
        'supported_years': list(SUPPORTED_YEARS),
        'notice': notice,
    }
