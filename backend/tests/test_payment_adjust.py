from datetime import date
import random

import pytest

from backend.modules.payment_adjust import (common_shock_sigma, draw_shock, invoice_features, keep_rate_shrunk,
    promise_adjusted_date, run_rate_sales, shrinkage_blend)


def test_shrinkage_uses_customer_weight():
    value = shrinkage_blend({'mean_delay': 10, 'std_delay': 2, 'on_time_rate': .8, 'n': 5}, {'mean_delay': 20, 'std_delay': 4, 'on_time_rate': .6, 'n': 5}, {'mean_delay': 30, 'std_delay': 6, 'on_time_rate': .4})
    assert value['shrinkage_weight'] == .5 and 10 < value['mean_delay'] < 30

def test_no_customer_history_uses_lower_level(): assert shrinkage_blend({}, {'mean_delay': 8, 'n': 10}, {'mean_delay': 20})['mean_delay'] < 20
def test_features_include_month_end_and_trend(): assert invoice_features({'amount': 999, 'issue_date': '2026-10-01', 'due_date': '2026-10-31', 'dispute': True}, [{'delay': x} for x in [1, 2, 3, 5, 6, 7]], '2026-10-25')['month_end']
def test_unestimable_common_shock_uses_default(): assert common_shock_sigma({'a': [1, 2]}) == .15
def test_estimable_common_shock_is_bounded(): assert .01 <= common_shock_sigma({'a': [1, 2, 3], 'b': [2, 4, 6]}) <= 1
def test_draw_shock_is_positive(): assert draw_shock(random.Random(1), .2) > 0
def test_kept_promise_is_near_date(): assert abs((date.fromisoformat(promise_adjusted_date(random.Random(1), '2026-11-10', 1, lambda: '2026-12-01')) - date(2026, 11, 10)).days) <= 3
def test_broken_promise_is_after_date(): assert promise_adjusted_date(random.Random(1), '2026-11-10', 0, lambda: '2026-10-01') == '2026-11-11'
def test_keep_rate_prior_and_validation():
    assert keep_rate_shrunk(0, 0) == .6
    with pytest.raises(ValueError): keep_rate_shrunk(2, 1)
def test_run_rate_trims_and_handles_short_history():
    invoices = [{'issue_date': f'2026-0{month}-10', 'amount': 100 * month} for month in range(4, 10)]
    assert run_rate_sales(invoices, '2026-10-25')['monthly_amount'] > 0
    assert run_rate_sales([], '2026-10-25')['monthly_amount'] is None
