import requests, time, json
import hmac
import hashlib
import base64
from requests.auth import AuthBase

"""

From https://github.com/danpaquin/coinbasepro-python/

Modifications:
- outdated versions of buy() and sell() commented out (under AuthenticatedClient)
- param 'stop_price' added to place_stop_order (under AuthenticatedClient)

"""


class CBProAuth(AuthBase):
    # Provided by CBPro: https://docs.pro.coinbase.com/#signing-a-message
    def __init__(self, api_key, secret_key, passphrase):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase

    def __call__(self, request):
        timestamp = str(time.time())
        message = ''.join([timestamp, request.method,
                           request.path_url, (request.body or '')])
        request.headers.update(get_auth_headers(timestamp, message,
                                                self.api_key,
                                                self.secret_key,
                                                self.passphrase))
        return request


def get_auth_headers(timestamp, message, api_key, secret_key, passphrase):
    message = message.encode('ascii')
    hmac_key = base64.b64decode(secret_key)
    signature = hmac.new(hmac_key, message, hashlib.sha256)
    signature_b64 = base64.b64encode(signature.digest()).decode('utf-8')
    return {
        'Content-Type': 'Application/JSON',
        'CB-ACCESS-SIGN': signature_b64,
        'CB-ACCESS-TIMESTAMP': timestamp,
        'CB-ACCESS-KEY': api_key,
        'CB-ACCESS-PASSPHRASE': passphrase
    }
    
class PublicClient(object):
    """cbpro public client API.
    All requests default to the `product_id` specified at object
    creation if not otherwise specified.
    Attributes:
        url (Optional[str]): API URL. Defaults to cbpro API.
    """

    def __init__(self, api_url='https://api.pro.coinbase.com', timeout=30):
        """Create cbpro API public client.
        Args:
            api_url (Optional[str]): API URL. Defaults to cbpro API.
        """
        self.url = api_url.rstrip('/')
        self.auth = None
        self.session = requests.Session()

    def get_products(self):
        """Get a list of available currency pairs for trading.
        Returns:
            list: Info about all currency pairs. Example::
                [
                    {
                        "id": "BTC-USD",
                        "display_name": "BTC/USD",
                        "base_currency": "BTC",
                        "quote_currency": "USD",
                        "base_min_size": "0.01",
                        "base_max_size": "10000.00",
                        "quote_increment": "0.01"
                    }
                ]
        """
        return self._send_message('get', '/products')

    def get_product_order_book(self, product_id, level=1):
        """Get a list of open orders for a product.
        The amount of detail shown can be customized with the `level`
        parameter:
        * 1: Only the best bid and ask
        * 2: Top 50 bids and asks (aggregated)
        * 3: Full order book (non aggregated)
        Level 1 and Level 2 are recommended for polling. For the most
        up-to-date data, consider using the websocket stream.
        **Caution**: Level 3 is only recommended for users wishing to
        maintain a full real-time order book using the websocket
        stream. Abuse of Level 3 via polling will cause your access to
        be limited or blocked.
        Args:
            product_id (str): Product
            level (Optional[int]): Order book level (1, 2, or 3).
                Default is 1.
        Returns:
            dict: Order book. Example for level 1::
                {
                    "sequence": "3",
                    "bids": [
                        [ price, size, num-orders ],
                    ],
                    "asks": [
                        [ price, size, num-orders ],
                    ]
                }
        """
        params = {'level': level}
        return self._send_message('get',
                                  '/products/{}/book'.format(product_id),
                                  params=params)

    def get_product_ticker(self, product_id):
        """Snapshot about the last trade (tick), best bid/ask and 24h volume.
        **Caution**: Polling is discouraged in favor of connecting via
        the websocket stream and listening for match messages.
        Args:
            product_id (str): Product
        Returns:
            dict: Ticker info. Example::
                {
                  "trade_id": 4729088,
                  "price": "333.99",
                  "size": "0.193",
                  "bid": "333.98",
                  "ask": "333.99",
                  "volume": "5957.11914015",
                  "time": "2015-11-14T20:46:03.511254Z"
                }
        """
        return self._send_message('get',
                                  '/products/{}/ticker'.format(product_id))

    def get_product_trades(self, product_id, before='', after='', limit=None, result=None):
        """List the latest trades for a product.
        This method returns a generator which may make multiple HTTP requests
        while iterating through it.
        Args:
             product_id (str): Product
             before (Optional[str]): start time in ISO 8601
             after (Optional[str]): end time in ISO 8601
             limit (Optional[int]): the desired number of trades (can be more than 100,
                          automatically paginated)
             results (Optional[list]): list of results that is used for the pagination
        Returns:
             list: Latest trades. Example::
                 [{
                     "time": "2014-11-07T22:19:28.578544Z",
                     "trade_id": 74,
                     "price": "10.00000000",
                     "size": "0.01000000",
                     "side": "buy"
                 }, {
                     "time": "2014-11-07T01:08:43.642366Z",
                     "trade_id": 73,
                     "price": "100.00000000",
                     "size": "0.01000000",
                     "side": "sell"
         }]
        """
        return self._send_paginated_message('/products/{}/trades'
                                            .format(product_id))

    def get_product_historic_rates(self, product_id, start=None, end=None,
                                   granularity=None):
        """Historic rates for a product.
        Rates are returned in grouped buckets based on requested
        `granularity`. If start, end, and granularity aren't provided,
        the exchange will assume some (currently unknown) default values.
        Historical rate data may be incomplete. No data is published for
        intervals where there are no ticks.
        **Caution**: Historical rates should not be polled frequently.
        If you need real-time information, use the trade and book
        endpoints along with the websocket feed.
        The maximum number of data points for a single request is 200
        candles. If your selection of start/end time and granularity
        will result in more than 200 data points, your request will be
        rejected. If you wish to retrieve fine granularity data over a
        larger time range, you will need to make multiple requests with
        new start/end ranges.
        Args:
            product_id (str): Product
            start (Optional[str]): Start time in ISO 8601
            end (Optional[str]): End time in ISO 8601
            granularity (Optional[int]): Desired time slice in seconds
        Returns:
            list: Historic candle data. Example:
                [
                    [ time, low, high, open, close, volume ],
                    [ 1415398768, 0.32, 4.2, 0.35, 4.2, 12.3 ],
                    ...
                ]
        """
        params = {}
        if start is not None:
            params['start'] = start
        if end is not None:
            params['end'] = end
        if granularity is not None:
            acceptedGrans = [60, 300, 900, 3600, 21600, 86400]
            if granularity not in acceptedGrans:
                raise ValueError( 'Specified granularity is {}, must be in approved values: {}'.format(
                        granularity, acceptedGrans) )

            params['granularity'] = granularity
        return self._send_message('get',
                                  '/products/{}/candles'.format(product_id),
                                  params=params)

    def get_product_24hr_stats(self, product_id):
        """Get 24 hr stats for the product.
        Args:
            product_id (str): Product
        Returns:
            dict: 24 hour stats. Volume is in base currency units.
                Open, high, low are in quote currency units. Example::
                    {
                        "open": "34.19000000",
                        "high": "95.70000000",
                        "low": "7.06000000",
                        "volume": "2.41000000"
                    }
        """
        return self._send_message('get',
                                  '/products/{}/stats'.format(product_id))

    def get_currencies(self):
        """List known currencies.
        Returns:
            list: List of currencies. Example::
                [{
                    "id": "BTC",
                    "name": "Bitcoin",
                    "min_size": "0.00000001"
                }, {
                    "id": "USD",
                    "name": "United States Dollar",
                    "min_size": "0.01000000"
                }]
        """
        return self._send_message('get', '/currencies')

    def get_time(self):
        """Get the API server time.
        Returns:
            dict: Server time in ISO and epoch format (decimal seconds
                since Unix epoch). Example::
                    {
                        "iso": "2015-01-07T23:47:25.201Z",
                        "epoch": 1420674445.201
                    }
        """
        return self._send_message('get', '/time')

    def _send_message(self, method, endpoint, params=None, data=None):
        """Send API request.
        Args:
            method (str): HTTP method (get, post, delete, etc.)
            endpoint (str): Endpoint (to be added to base URL)
            params (Optional[dict]): HTTP request parameters
            data (Optional[str]): JSON-encoded string payload for POST
        Returns:
            dict/list: JSON response
        """
        url = self.url + endpoint
        r = self.session.request(method, url, params=params, data=data,
                                 auth=self.auth, timeout=30)
        return r.json()

    def _send_paginated_message(self, endpoint, params=None):
        """ Send API message that results in a paginated response.
        The paginated responses are abstracted away by making API requests on
        demand as the response is iterated over.
        Paginated API messages support 3 additional parameters: `before`,
        `after`, and `limit`. `before` and `after` are mutually exclusive. To
        use them, supply an index value for that endpoint (the field used for
        indexing varies by endpoint - get_fills() uses 'trade_id', for example).
            `before`: Only get data that occurs more recently than index
            `after`: Only get data that occurs further in the past than index
            `limit`: Set amount of data per HTTP response. Default (and
                maximum) of 100.
        Args:
            endpoint (str): Endpoint (to be added to base URL)
            params (Optional[dict]): HTTP request parameters
        Yields:
            dict: API response objects
        """
        if params is None:
            params = dict()
        url = self.url + endpoint
        while True:
            r = self.session.get(url, params=params, auth=self.auth, timeout=30)
            results = r.json()
            for result in results:
                yield result
            # If there are no more pages, we're done. Otherwise update `after`
            # param to get next page.
            # If this request included `before` don't get any more pages - the
            # cbpro API doesn't support multiple pages in that case.
            if not r.headers.get('cb-after') or \
                    params.get('before') is not None:
                break
            else:
                params['after'] = r.headers['cb-after']
                
class AuthenticatedClient(PublicClient):
    """ Provides access to Private Endpoints on the cbpro API.
    All requests default to the live `api_url`: 'https://api.pro.coinbase.com'.
    To test your application using the sandbox modify the `api_url`.
    Attributes:
        url (str): The api url for this client instance to use.
        auth (CBProAuth): Custom authentication handler for each request.
        session (requests.Session): Persistent HTTP connection object.
    """
    def __init__(self, key, b64secret, passphrase,
                 api_url="https://api.pro.coinbase.com"):
        """ Create an instance of the AuthenticatedClient class.
        Args:
            key (str): Your API key.
            b64secret (str): The secret key matching your API key.
            passphrase (str): Passphrase chosen when setting up key.
            api_url (Optional[str]): API URL. Defaults to cbpro API.
        """
        super(AuthenticatedClient, self).__init__(api_url)
        self.auth = CBProAuth(key, b64secret, passphrase)
        self.session = requests.Session()

    def get_account(self, account_id):
        """ Get information for a single account.
        Use this endpoint when you know the account_id.
        Args:
            account_id (str): Account id for account you want to get.
        Returns:
            dict: Account information. Example::
                {
                    "id": "a1b2c3d4",
                    "balance": "1.100",
                    "holds": "0.100",
                    "available": "1.00",
                    "currency": "USD"
                }
        """
        return self._send_message('get', '/accounts/' + account_id)

    def get_accounts(self):
        """ Get a list of trading all accounts.
        When you place an order, the funds for the order are placed on
        hold. They cannot be used for other orders or withdrawn. Funds
        will remain on hold until the order is filled or canceled. The
        funds on hold for each account will be specified.
        Returns:
            list: Info about all accounts. Example::
                [
                    {
                        "id": "71452118-efc7-4cc4-8780-a5e22d4baa53",
                        "currency": "BTC",
                        "balance": "0.0000000000000000",
                        "available": "0.0000000000000000",
                        "hold": "0.0000000000000000",
                        "profile_id": "75da88c5-05bf-4f54-bc85-5c775bd68254"
                    },
                    {
                        ...
                    }
                ]
        * Additional info included in response for margin accounts.
        """
        return self.get_account('')

    def get_account_history(self, account_id, **kwargs):
        """ List account activity. Account activity either increases or
        decreases your account balance.
        Entry type indicates the reason for the account change.
        * transfer:	Funds moved to/from Coinbase to cbpro
        * match:	Funds moved as a result of a trade
        * fee:	    Fee as a result of a trade
        * rebate:   Fee rebate as per our fee schedule
        If an entry is the result of a trade (match, fee), the details
        field will contain additional information about the trade.
        Args:
            account_id (str): Account id to get history of.
            kwargs (dict): Additional HTTP request parameters.
        Returns:
            list: History information for the account. Example::
                [
                    {
                        "id": "100",
                        "created_at": "2014-11-07T08:19:27.028459Z",
                        "amount": "0.001",
                        "balance": "239.669",
                        "type": "fee",
                        "details": {
                            "order_id": "d50ec984-77a8-460a-b958-66f114b0de9b",
                            "trade_id": "74",
                            "product_id": "BTC-USD"
                        }
                    },
                    {
                        ...
                    }
                ]
        """
        endpoint = '/accounts/{}/ledger'.format(account_id)
        return self._send_paginated_message(endpoint, params=kwargs)

    def get_account_holds(self, account_id, **kwargs):
        """ Get holds on an account.
        This method returns a generator which may make multiple HTTP requests
        while iterating through it.
        Holds are placed on an account for active orders or
        pending withdraw requests.
        As an order is filled, the hold amount is updated. If an order
        is canceled, any remaining hold is removed. For a withdraw, once
        it is completed, the hold is removed.
        The `type` field will indicate why the hold exists. The hold
        type is 'order' for holds related to open orders and 'transfer'
        for holds related to a withdraw.
        The `ref` field contains the id of the order or transfer which
        created the hold.
        Args:
            account_id (str): Account id to get holds of.
            kwargs (dict): Additional HTTP request parameters.
        Returns:
            generator(list): Hold information for the account. Example::
                [
                    {
                        "id": "82dcd140-c3c7-4507-8de4-2c529cd1a28f",
                        "account_id": "e0b3f39a-183d-453e-b754-0c13e5bab0b3",
                        "created_at": "2014-11-06T10:34:47.123456Z",
                        "updated_at": "2014-11-06T10:40:47.123456Z",
                        "amount": "4.23",
                        "type": "order",
                        "ref": "0a205de4-dd35-4370-a285-fe8fc375a273",
                    },
                    {
                    ...
                    }
                ]
        """
        endpoint = '/accounts/{}/holds'.format(account_id)
        return self._send_paginated_message(endpoint, params=kwargs)

    def place_order(self, product_id, side, order_type, **kwargs):
        """ Place an order.
        The three order types (limit, market, and stop) can be placed using this
        method. Specific methods are provided for each order type, but if a
        more generic interface is desired this method is available.
        Args:
            product_id (str): Product to order (eg. 'BTC-USD')
            side (str): Order side ('buy' or 'sell)
            order_type (str): Order type ('limit', 'market', or 'stop')
            **client_oid (str): Order ID selected by you to identify your order.
                This should be a UUID, which will be broadcast in the public
                feed for `received` messages.
            **stp (str): Self-trade prevention flag. cbpro doesn't allow self-
                trading. This behavior can be modified with this flag.
                Options:
                'dc'	Decrease and Cancel (default)
                'co'	Cancel oldest
                'cn'	Cancel newest
                'cb'	Cancel both
            **overdraft_enabled (Optional[bool]): If true funding above and
                beyond the account balance will be provided by margin, as
                necessary.
            **funding_amount (Optional[Decimal]): Amount of margin funding to be
                provided for the order. Mutually exclusive with
                `overdraft_enabled`.
            **kwargs: Additional arguments can be specified for different order
                types. See the limit/market/stop order methods for details.
        Returns:
            dict: Order details. Example::
            {
                "id": "d0c5340b-6d6c-49d9-b567-48c4bfca13d2",
                "price": "0.10000000",
                "size": "0.01000000",
                "product_id": "BTC-USD",
                "side": "buy",
                "stp": "dc",
                "type": "limit",
                "time_in_force": "GTC",
                "post_only": false,
                "created_at": "2016-12-08T20:02:28.53864Z",
                "fill_fees": "0.0000000000000000",
                "filled_size": "0.00000000",
                "executed_value": "0.0000000000000000",
                "status": "pending",
                "settled": false
            }
        """
        # Margin parameter checks
        if kwargs.get('overdraft_enabled') is not None and \
                kwargs.get('funding_amount') is not None:
            raise ValueError('Margin funding must be specified through use of '
                             'overdraft or by setting a funding amount, but not'
                             ' both')

        # Limit order checks
        if order_type == 'limit':
            if kwargs.get('cancel_after') is not None and \
                    kwargs.get('time_in_force') != 'GTT':
                raise ValueError('May only specify a cancel period when time '
                                 'in_force is `GTT`')
            if kwargs.get('post_only') is not None and kwargs.get('time_in_force') in \
                    ['IOC', 'FOK']:
                raise ValueError('post_only is invalid when time in force is '
                                 '`IOC` or `FOK`')

        # Market and stop order checks
        if order_type == 'market' or order_type == 'stop':
            if not (kwargs.get('size') is None) ^ (kwargs.get('funds') is None):
                raise ValueError('Either `size` or `funds` must be specified '
                                 'for market/stop orders (but not both).')

        # Build params dict
        params = {'product_id': product_id,
                  'side': side,
                  'type': order_type}
        params.update(kwargs)
        return self._send_message('post', '/orders', data=json.dumps(params))

    # def buy(self, product_id, order_type, **kwargs):
        # """Place a buy order.
        # This is included to maintain backwards compatibility with older versions
        # of cbpro-Python. For maximum support from docstrings and function
        # signatures see the order type-specific functions place_limit_order,
        # place_market_order, and place_stop_order.
        # Args:
            # product_id (str): Product to order (eg. 'BTC-USD')
            # order_type (str): Order type ('limit', 'market', or 'stop')
            # **kwargs: Additional arguments can be specified for different order
                # types.
        # Returns:
            # dict: Order details. See `place_order` for example.
        # """
        # return self.place_order(product_id, 'buy', order_type, **kwargs)

    # def sell(self, product_id, order_type, **kwargs):
        # """Place a sell order.
        # This is included to maintain backwards compatibility with older versions
        # of cbpro-Python. For maximum support from docstrings and function
        # signatures see the order type-specific functions place_limit_order,
        # place_market_order, and place_stop_order.
        # Args:
            # product_id (str): Product to order (eg. 'BTC-USD')
            # order_type (str): Order type ('limit', 'market', or 'stop')
            # **kwargs: Additional arguments can be specified for different order
                # types.
        # Returns:
            # dict: Order details. See `place_order` for example.
        # """
        # return self.place_order(product_id, 'sell', order_type, **kwargs)

    def place_limit_order(self, product_id, side, price, size,
                          client_oid=None,
                          stp=None,
                          time_in_force=None,
                          cancel_after=None,
                          post_only=None,
                          overdraft_enabled=None,
                          funding_amount=None):
        """Place a limit order.
        Args:
            product_id (str): Product to order (eg. 'BTC-USD')
            side (str): Order side ('buy' or 'sell)
            price (Decimal): Price per cryptocurrency
            size (Decimal): Amount of cryptocurrency to buy or sell
            client_oid (Optional[str]): User-specified Order ID
            stp (Optional[str]): Self-trade prevention flag. See `place_order`
                for details.
            time_in_force (Optional[str]): Time in force. Options:
                'GTC'   Good till canceled
                'GTT'   Good till time (set by `cancel_after`)
                'IOC'   Immediate or cancel
                'FOK'   Fill or kill
            cancel_after (Optional[str]): Cancel after this period for 'GTT'
                orders. Options are 'min', 'hour', or 'day'.
            post_only (Optional[bool]): Indicates that the order should only
                make liquidity. If any part of the order results in taking
                liquidity, the order will be rejected and no part of it will
                execute.
            overdraft_enabled (Optional[bool]): If true funding above and
                beyond the account balance will be provided by margin, as
                necessary.
            funding_amount (Optional[Decimal]): Amount of margin funding to be
                provided for the order. Mutually exclusive with
                `overdraft_enabled`.
        Returns:
            dict: Order details. See `place_order` for example.
        """
        params = {'product_id': product_id,
                  'side': side,
                  'order_type': 'limit',
                  'price': price,
                  'size': size,
                  'client_oid': client_oid,
                  'stp': stp,
                  'time_in_force': time_in_force,
                  'cancel_after': cancel_after,
                  'post_only': post_only,
                  'overdraft_enabled': overdraft_enabled,
                  'funding_amount': funding_amount}
        params = dict((k, v) for k, v in params.items() if v is not None)

        return self.place_order(**params)

    def place_market_order(self, product_id, side, size=None, funds=None,
                           client_oid=None,
                           stp=None,
                           overdraft_enabled=None,
                           funding_amount=None):
        """ Place market order.
        Args:
            product_id (str): Product to order (eg. 'BTC-USD')
            side (str): Order side ('buy' or 'sell)
            size (Optional[Decimal]): Desired amount in crypto. Specify this or
                `funds`.
            funds (Optional[Decimal]): Desired amount of quote currency to use.
                Specify this or `size`.
            client_oid (Optional[str]): User-specified Order ID
            stp (Optional[str]): Self-trade prevention flag. See `place_order`
                for details.
            overdraft_enabled (Optional[bool]): If true funding above and
                beyond the account balance will be provided by margin, as
                necessary.
            funding_amount (Optional[Decimal]): Amount of margin funding to be
                provided for the order. Mutually exclusive with
                `overdraft_enabled`.
        Returns:
            dict: Order details. See `place_order` for example.
        """
        params = {'product_id': product_id,
                  'side': side,
                  'order_type': 'market',
                  'size': size,
                  'funds': funds,
                  'client_oid': client_oid,
                  'stp': stp,
                  'overdraft_enabled': overdraft_enabled,
                  'funding_amount': funding_amount}
        params = dict((k, v) for k, v in params.items() if v is not None)

        return self.place_order(**params)

    def place_stop_order(self, product_id, side, price, stop, stop_price,
                         size=None, funds=None,
                         client_oid=None,
                         stp=None,
                         overdraft_enabled=None,
                         funding_amount=None):
        """ Place stop order.
        Args:
            product_id (str): Product to order (eg. 'BTC-USD')
            side (str): Order side ('buy' or 'sell)
            price (Decimal): Desired price at which the stop order triggers.
            size (Optional[Decimal]): Desired amount in crypto. Specify this or
                `funds`.
            funds (Optional[Decimal]): Desired amount of quote currency to use.
                Specify this or `size`.
            client_oid (Optional[str]): User-specified Order ID
            stp (Optional[str]): Self-trade prevention flag. See `place_order`
                for details.
            overdraft_enabled (Optional[bool]): If true funding above and
                beyond the account balance will be provided by margin, as
                necessary.
            funding_amount (Optional[Decimal]): Amount of margin funding to be
                provided for the order. Mutually exclusive with
                `overdraft_enabled`.
        Returns:
            dict: Order details. See `place_order` for example.
        """
        params = {'product_id': product_id,
                  'side': side,
                  'price': price,
                   # 'order_type': 'stop',
                  'size': size,
                  'funds': funds,
                  'client_oid': client_oid,
                  'stop': stop,
                  'stop_price': stop_price,
                  'stp': stp,
                  'overdraft_enabled': overdraft_enabled,
                  'funding_amount': funding_amount}
        params = dict((k, v) for k, v in params.items() if v is not None)

        return self.place_order(**params)

    def cancel_order(self, order_id):
        """ Cancel a previously placed order.
        If the order had no matches during its lifetime its record may
        be purged. This means the order details will not be available
        with get_order(order_id). If the order could not be canceled
        (already filled or previously canceled, etc), then an error
        response will indicate the reason in the message field.
        **Caution**: The order id is the server-assigned order id and
        not the optional client_oid.
        Args:
            order_id (str): The order_id of the order you want to cancel
        Returns:
            list: Containing the order_id of cancelled order. Example::
                [ "c5ab5eae-76be-480e-8961-00792dc7e138" ]
        """
        return self._send_message('delete', '/orders/' + order_id)

    def cancel_all(self, product_id=None):
        """ With best effort, cancel all open orders.
        Args:
            product_id (Optional[str]): Only cancel orders for this
                product_id
        Returns:
            list: A list of ids of the canceled orders. Example::
                [
                    "144c6f8e-713f-4682-8435-5280fbe8b2b4",
                    "debe4907-95dc-442f-af3b-cec12f42ebda",
                    "cf7aceee-7b08-4227-a76c-3858144323ab",
                    "dfc5ae27-cadb-4c0c-beef-8994936fde8a",
                    "34fecfbf-de33-4273-b2c6-baf8e8948be4"
                ]
        """
        if product_id is not None:
            params = {'product_id': product_id}
        else:
            params = None
        return self._send_message('delete', '/orders', params=params)

    def get_order(self, order_id):
        """ Get a single order by order id.
        If the order is canceled the response may have status code 404
        if the order had no matches.
        **Caution**: Open orders may change state between the request
        and the response depending on market conditions.
        Args:
            order_id (str): The order to get information of.
        Returns:
            dict: Containing information on order. Example::
                {
                    "created_at": "2017-06-18T00:27:42.920136Z",
                    "executed_value": "0.0000000000000000",
                    "fill_fees": "0.0000000000000000",
                    "filled_size": "0.00000000",
                    "id": "9456f388-67a9-4316-bad1-330c5353804f",
                    "post_only": true,
                    "price": "1.00000000",
                    "product_id": "BTC-USD",
                    "settled": false,
                    "side": "buy",
                    "size": "1.00000000",
                    "status": "pending",
                    "stp": "dc",
                    "time_in_force": "GTC",
                    "type": "limit"
                }
        """
        return self._send_message('get', '/orders/' + order_id)

    def get_orders(self, product_id=None, status=None, **kwargs):
        """ List your current open orders.
        This method returns a generator which may make multiple HTTP requests
        while iterating through it.
        Only open or un-settled orders are returned. As soon as an
        order is no longer open and settled, it will no longer appear
        in the default request.
        Orders which are no longer resting on the order book, will be
        marked with the 'done' status. There is a small window between
        an order being 'done' and 'settled'. An order is 'settled' when
        all of the fills have settled and the remaining holds (if any)
        have been removed.
        For high-volume trading it is strongly recommended that you
        maintain your own list of open orders and use one of the
        streaming market data feeds to keep it updated. You should poll
        the open orders endpoint once when you start trading to obtain
        the current state of any open orders.
        Args:
            product_id (Optional[str]): Only list orders for this
                product
            status (Optional[list/str]): Limit list of orders to
                this status or statuses. Passing 'all' returns orders
                of all statuses.
                ** Options: 'open', 'pending', 'active', 'done',
                    'settled'
                ** default: ['open', 'pending', 'active']
        Returns:
            list: Containing information on orders. Example::
                [
                    {
                        "id": "d0c5340b-6d6c-49d9-b567-48c4bfca13d2",
                        "price": "0.10000000",
                        "size": "0.01000000",
                        "product_id": "BTC-USD",
                        "side": "buy",
                        "stp": "dc",
                        "type": "limit",
                        "time_in_force": "GTC",
                        "post_only": false,
                        "created_at": "2016-12-08T20:02:28.53864Z",
                        "fill_fees": "0.0000000000000000",
                        "filled_size": "0.00000000",
                        "executed_value": "0.0000000000000000",
                        "status": "open",
                        "settled": false
                    },
                    {
                        ...
                    }
                ]
        """
        params = kwargs
        if product_id is not None:
            params['product_id'] = product_id
        if status is not None:
            params['status'] = status
        return self._send_paginated_message('/orders', params=params)

    def get_fills(self, product_id=None, order_id=None, **kwargs):
        """ Get a list of recent fills.
        As of 8/23/18 - Requests without either order_id or product_id
        will be rejected
        This method returns a generator which may make multiple HTTP requests
        while iterating through it.
        Fees are recorded in two stages. Immediately after the matching
        engine completes a match, the fill is inserted into our
        datastore. Once the fill is recorded, a settlement process will
        settle the fill and credit both trading counterparties.
        The 'fee' field indicates the fees charged for this fill.
        The 'liquidity' field indicates if the fill was the result of a
        liquidity provider or liquidity taker. M indicates Maker and T
        indicates Taker.
        Args:
            product_id (str): Limit list to this product_id
            order_id (str): Limit list to this order_id
            kwargs (dict): Additional HTTP request parameters.
        Returns:
            list: Containing information on fills. Example::
                [
                    {
                        "trade_id": 74,
                        "product_id": "BTC-USD",
                        "price": "10.00",
                        "size": "0.01",
                        "order_id": "d50ec984-77a8-460a-b958-66f114b0de9b",
                        "created_at": "2014-11-07T22:19:28.578544Z",
                        "liquidity": "T",
                        "fee": "0.00025",
                        "settled": true,
                        "side": "buy"
                    },
                    {
                        ...
                    }
                ]
        """
        if (product_id is None) and (order_id is None):
            raise ValueError('Either product_id or order_id must be specified.')

        params = {}
        if product_id:
            params['product_id'] = product_id
        if order_id:
            params['order_id'] = order_id
        params.update(kwargs)

        return self._send_paginated_message('/fills', params=params)

    def get_fundings(self, status=None, **kwargs):
        """ Every order placed with a margin profile that draws funding
        will create a funding record.
        This method returns a generator which may make multiple HTTP requests
        while iterating through it.
        Args:
            status (list/str): Limit funding records to these statuses.
                ** Options: 'outstanding', 'settled', 'rejected'
            kwargs (dict): Additional HTTP request parameters.
        Returns:
            list: Containing information on margin funding. Example::
                [
                    {
                        "id": "b93d26cd-7193-4c8d-bfcc-446b2fe18f71",
                        "order_id": "b93d26cd-7193-4c8d-bfcc-446b2fe18f71",
                        "profile_id": "d881e5a6-58eb-47cd-b8e2-8d9f2e3ec6f6",
                        "amount": "1057.6519956381537500",
                        "status": "settled",
                        "created_at": "2017-03-17T23:46:16.663397Z",
                        "currency": "USD",
                        "repaid_amount": "1057.6519956381537500",
                        "default_amount": "0",
                        "repaid_default": false
                    },
                    {
                        ...
                    }
                ]
        """
        params = {}
        if status is not None:
            params['status'] = status
        params.update(kwargs)
        return self._send_paginated_message('/funding', params=params)

    def repay_funding(self, amount, currency):
        """ Repay funding. Repays the older funding records first.
        Args:
            amount (int): Amount of currency to repay
            currency (str): The currency, example USD
        Returns:
            Not specified by cbpro.
        """
        params = {
            'amount': amount,
            'currency': currency  # example: USD
            }
        return self._send_message('post', '/funding/repay',
                                  data=json.dumps(params))

    def margin_transfer(self, margin_profile_id, transfer_type, currency,
                        amount):
        """ Transfer funds between your standard profile and a margin profile.
        Args:
            margin_profile_id (str): Margin profile ID to withdraw or deposit
                from.
            transfer_type (str): 'deposit' or 'withdraw'
            currency (str): Currency to transfer (eg. 'USD')
            amount (Decimal): Amount to transfer
        Returns:
            dict: Transfer details. Example::
                {
                  "created_at": "2017-01-25T19:06:23.415126Z",
                  "id": "80bc6b74-8b1f-4c60-a089-c61f9810d4ab",
                  "user_id": "521c20b3d4ab09621f000011",
                  "profile_id": "cda95996-ac59-45a3-a42e-30daeb061867",
                  "margin_profile_id": "45fa9e3b-00ba-4631-b907-8a98cbdf21be",
                  "type": "deposit",
                  "amount": "2",
                  "currency": "USD",
                  "account_id": "23035fc7-0707-4b59-b0d2-95d0c035f8f5",
                  "margin_account_id": "e1d9862c-a259-4e83-96cd-376352a9d24d",
                  "margin_product_id": "BTC-USD",
                  "status": "completed",
                  "nonce": 25
                }
        """
        params = {'margin_profile_id': margin_profile_id,
                  'type': transfer_type,
                  'currency': currency,  # example: USD
                  'amount': amount}
        return self._send_message('post', '/profiles/margin-transfer',
                                  data=json.dumps(params))

    def get_position(self):
        """ Get An overview of your margin profile.
        Returns:
            dict: Details about funding, accounts, and margin call.
        """
        return self._send_message('get', '/position')

    def close_position(self, repay_only):
        """ Close position.
        Args:
            repay_only (bool): Undocumented by cbpro.
        Returns:
            Undocumented
        """
        params = {'repay_only': repay_only}
        return self._send_message('post', '/position/close',
                                  data=json.dumps(params))