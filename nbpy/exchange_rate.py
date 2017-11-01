"""Defines NBPCurrencyExchangeRate class."""

from nbpy.errors import UnknownCurrencyCode
from nbpy.currencies import currencies


__all__ = ['NBPExchangeRate']


class NBPExchangeRate(object):
    """Holds information about exchange rates for given currency and day."""

    def __init__(self, currency_code, date, source_id, mid, **kwargs):
        """Initialize for currency code, date and avg (mid) value."""
        self.currency_code = currency_code
        self.date = date
        self.source_id = source_id
        self.mid = mid

        if 'bid' in kwargs and 'ask' in kwargs:
            self.bid = kwargs.get('bid')
            self.ask = kwargs.get('ask')

    def __repr__(self):
        try:
            return "{cls_name}({code}, {date}, mid={mid}, bid={bid}, ask={ask})".format(
                cls_name=self.__class__.__name__,
                code=self.currency_code,
                date=self.date,
                mid=self.mid,
                bid=self.bid,
                ask=self.ask
            )
        except AttributeError:
            return "{cls_name}({code}, {date}, mid={mid})".format(
                cls_name=self.__class__.__name__,
                code=self.currency_code,
                date=self.date,
                mid=self.mid
            )

    @property
    def currency_code(self):
        """Currency code."""
        return self._currency_code

    @currency_code.setter
    def currency_code(self, code):
        code = code.upper()
        if code not in currencies:
            raise UnknownCurrencyCode(code)
        self._currency_code = code

    @property
    def currency_name(self):
        """Full currency name."""
        return currencies[self.currency_code]

    def __call__(self, amount_in_pln):
        """Convert amount in PLN to chosen currency."""
        try:
            return {
                'bid': self.bid * amount_in_pln,
                'ask': self.ask * amount_in_pln,
                'mid': self.mid * amount_in_pln,
            }
        except AttributeError:
            return {
                'mid': self.mid * amount_in_pln,
            }

    def __mul__(self, amount_in_pln):
        """Convert amount in PLN to chosen currency."""
        return self(amount_in_pln)

    def __rmul__(self, amount_in_pln):
        """Convert amount in PLN to chosen currency."""
        return self(amount_in_pln)