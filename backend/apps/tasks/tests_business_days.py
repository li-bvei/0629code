"""P6：結転の既定日（日本の営業日）。土日・祝日・振替休日・国民の休日を除く。手動で祝日を選ぶことはできる。"""
from datetime import date

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.tasks.business_days import SUPPORTED_YEARS, day_info, holiday_name, is_business_day, next_business_day
from apps.tasks.daily_plan import next_weekday
from apps.tasks.models import Task
from apps.tasks.tests_daily_plan import PlanFixture


class BusinessDayTests(SimpleTestCase):
    def test_rules(self):
        cases = [
            (date(2026, 10, 6), date(2026, 10, 7)),    # 普通の平日
            (date(2026, 10, 9), date(2026, 10, 13)),   # 金曜 → 月曜はスポーツの日（祝日）→ 火曜
            (date(2026, 11, 2), date(2026, 11, 4)),    # 祝日の前日（11/3 文化の日）
            (date(2026, 5, 1), date(2026, 5, 7)),      # 連休：5/2 土・3 日・4・5 祝・6 振替休日
            (date(2026, 9, 18), date(2026, 9, 24)),    # 9/21 敬老の日・22 国民の休日・23 秋分の日
            (date(2026, 12, 31), date(2027, 1, 4)),    # 年末：1/1 元日・2 土・3 日
            (date(2028, 2, 28), date(2028, 2, 29)),    # 閏年
        ]
        for start, expected in cases:
            with self.subTest(start=start):
                self.assertEqual(next_business_day(start), expected)
                self.assertEqual(next_weekday(start), expected)
        self.assertEqual(holiday_name(date(2026, 5, 6)), '憲法記念日 振替休日')
        self.assertEqual(holiday_name(date(2026, 9, 22)), '国民の休日')
        self.assertFalse(is_business_day(date(2026, 10, 12)))
        self.assertTrue(is_business_day(date(2026, 10, 13)))

    def test_day_info_and_supported_range(self):
        info = day_info(date(2026, 11, 3))
        self.assertEqual((info['holiday_name'], info['is_business_day'], info['next_business_day']), ('文化の日', False, '2026-11-04'))
        self.assertIn('祝日', info['notice'])
        outside = day_info(date(SUPPORTED_YEARS[1] + 1, 1, 1))  # 範囲外は土日だけで判定し、注意を出す
        self.assertFalse(outside['supported'])
        self.assertEqual(outside['holiday_name'], '')
        self.assertIn('判定できません', outside['notice'])


class CarryOverCalendarApiTests(PlanFixture, TestCase):
    def test_calendar_endpoint_and_manual_holiday_target(self):
        response = self.get(self.staff_a, '/api/tasks/calendar/', {'date': '2026-10-09'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['next_business_day'], '2026-10-13')
        self.assertEqual(self.get(self.staff_a, '/api/tasks/calendar/', {'date': 'x'}).status_code, 400)
        self.assertEqual(self.get(self.su_only, '/api/tasks/calendar/', {'date': '2026-10-09'}).status_code, 403)
        # 利用者が祝日を選んで結転することはできる（止めない）
        item = self.add(self.staff_a, '合成：祝日に回す作業')
        holiday = date(timezone.localdate().year + 1, 1, 1)
        response = self.post(self.staff_a, f'/api/tasks/{item["id"]}/carry-over/',
                             {'target_date': holiday.isoformat(), 'version': item['updated_at']})
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(Task.objects.filter(work_date=holiday, carried_from_id=item['id']).exists())
