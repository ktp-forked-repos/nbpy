"""Tests for NBPClient (with mock responses)."""

import pytest
import math
import random
import responses
from datetime import datetime, timedelta
from decimal import Decimal
from collections import Sequence
from nbpy import BASE_URI


# Test currency codes
test_currency_codes = ('EUR', 'HRK', 'GYD')

# Kwargs for NBPClient
converter_kwargs = [
    {
        'currency_code': currency_code,
        'as_float': as_float,
        'suppress_errors': suppress_errors
    }
    for currency_code in test_currency_codes
    for as_float in (False, True)
    for suppress_errors in (False, True)
]

def _converter(**kwargs):
    from nbpy import NBPClient
    return NBPClient(**kwargs)

@pytest.mark.parametrize('kwargs', converter_kwargs)
def test_converter_basic(kwargs):
    converter = _converter(**kwargs)

    assert converter.currency_code == kwargs['currency_code']
    assert converter.as_float == kwargs['as_float']
    assert converter.suppress_errors == kwargs['suppress_errors']

@pytest.fixture(params=converter_kwargs)
def converter(request):
    """NBPClient object."""
    return _converter(**request.param)


class MockJSONData(object):
    """Helper class for creating mock JSON data."""

    def __init__(self, table, currency_obj, tail):
        self.table = table.upper()
        self.currency = currency_obj
        self.uri = BASE_URI + '/exchangerates/rates/{}/{}/{}'.format(
            self.table.lower(), self.currency.code.lower(), tail
        )

    def source_id(self, date):
        return "{count}/{table}/NBP/{year}".format(
            count=random.randint(1, 365),
            table=self.table,
            year=date.year
        )

    def rate_value(self):
        return round(random.uniform(0.0, 5.0), 5)

    def rate(self, date):
        rate = {
            "no": self.source_id(date),
            "effectiveDate": date.strftime("%Y-%m-%d"),
        }

        if self.table == 'C':
            rate = dict(rate, **{
                "bid": self.rate_value(),
                "ask": self.rate_value(),
            })
        else:
            rate = dict(rate, **{
                "mid": self.rate_value(),
            })

        return rate

    @staticmethod
    def _date_range(date, end_date):
        while date <= end_date:
            yield date
            date += timedelta(days=1)

    def data(self, start_date, end_date=None):
        if not end_date:
            end_date = start_date
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')

        rates = [
            self.rate(date)
            for date in self._date_range(start_date, end_date)
        ]

        return {
            'table': self.table,
            'currency': self.currency.name,
            'code': self.currency.code,
            'rates': rates
        }


def _prepare_responses(**kwargs):
    """
    Prepare responses for given currency, date and resource.

    Returns generated currency rates (for future comparison).
    """
    currency = kwargs.get('currency')
    date = kwargs.get('date')
    resource = kwargs.get('resource')
    as_float = kwargs.get('as_float', False)
    status_code = kwargs.get('status_code', 200)

    # Clear existing responses
    responses.reset()

    for table in currency.tables:
        # Create mock data
        mock = MockJSONData(table, currency, resource)

        if status_code == 200:
            responses.add(
                responses.Response(
                    method='GET', url=mock.uri,
                    json=mock.data(date), status=status_code,
                    content_type='application/json'
                )
            )
        else:
            responses.add(
                responses.Response(
                    method='GET', url=mock.uri,
                    status=status_code,
                    content_type='application/json'
                )
            )

def _test_exchange_rate_single(exchange_rate, **kwargs):
    """Perform checks for NBPExchangeRate object."""
    from nbpy.exchange_rate import NBPExchangeRate

    currency = kwargs.get('currency')
    date = kwargs.get('date')
    bid_ask = kwargs.get('bid_ask', False)
    as_float = kwargs.get('as_float', False)

    # Basic checks
    assert isinstance(exchange_rate, NBPExchangeRate)
    assert exchange_rate.currency_code == currency.code
    assert exchange_rate.currency_name == currency.name
    assert exchange_rate.date == datetime.strptime(date, '%Y-%m-%d')

    # Check mid, bid and ask
    if as_float:
        rates_cls = float
    else:
        rates_cls = Decimal

    if bid_ask and 'C' in currency.tables:
        assert isinstance(exchange_rate.bid, rates_cls)
        assert isinstance(exchange_rate.ask, rates_cls)
    else:
        assert isinstance(exchange_rate.mid, rates_cls)

def _test_exchange_rate(exchange_rate, **kwargs):
    """Perform checks for NBPExchangeRate object or their sequence."""
    if isinstance(exchange_rate, Sequence):
        for er in exchange_rate:
            _test_exchange_rate_single(er, **kwargs)
    else:
        _test_exchange_rate_single(exchange_rate, **kwargs)

@pytest.mark.parametrize("bid_ask,status_code",
                         [(bid_ask, status_code)
                          for bid_ask in (False, True)   
                          for status_code in (200, 400, 404)])
@responses.activate
def test_calls(converter, bid_ask, status_code):
    from nbpy.currencies import currencies
    from nbpy.errors import BidAskUnavailable, APIError

    # Setup
    kwargs = {
        'currency': currencies[converter.currency_code],
        'date': datetime.today().strftime('%Y-%m-%d'),
        'bid_ask': bid_ask,
        'as_float': converter.as_float,
        'status_code': status_code,
    }

    calls_to_test = (
        {
            'name': 'current',
            'resource': '',
            'args': ()
        },
        {
            'name': 'today',
            'resource': 'today',
            'args': ()
        },
        {
            'name': '__call__',
            'resource': '',
            'args': ()
        },
        {
            'name': 'date',
            'resource': kwargs['date'],
            'args': (kwargs['date'],)
        },
    )

    bid_ask_should_fail = (bid_ask and 'C' not in kwargs['currency'].tables)

    for call in calls_to_test:
        test_call = getattr(converter, call['name'])
        kwargs['resource'] = call['resource']

        _prepare_responses(**kwargs)

        # Error subtest
        def _test_converter_error(exception_cls):
            if converter.suppress_errors:
                # Exceptions suppressed
                assert test_call(*call['args'], bid_ask=bid_ask) is None
            else:
                with pytest.raises(exception_cls):
                    test_call(*call['args'], bid_ask=bid_ask)

        if status_code != 200:
            # HTTP Errors
            if bid_ask_should_fail:
                exception_cls = BidAskUnavailable
            else:
                exception_cls = APIError

            _test_converter_error(exception_cls)

        elif bid_ask_should_fail:
            # HTTP OK, but bid/ask call should fail for currency
            _test_converter_error(BidAskUnavailable)

        else:
            # All should be fine
            exchange_rate = test_call(*call['args'], bid_ask=bid_ask)
            _test_exchange_rate(exchange_rate, **kwargs)
