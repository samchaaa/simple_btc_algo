import time
from datetime import datetime, timedelta
import numpy as np

from cbpro import *

api_key = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
passphrase = 'xxxxxxxxxxxxx'
secret = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

import logging
logging.basicConfig(filename='./btc_algo.log', format='%(name)s - %(message)s')
logging.warning('{} logging started'.format(datetime.now().strftime("%x %X")))

class History():

    """ Gets data and returns signal. """

    def __init__(self):
        self.pc = PublicClient()
        self.avg1 = 50
        self.avg2 = 100

    def signal(self):
        self.startdate = (datetime.now() - timedelta(seconds=60*60*200)).strftime("%Y-%m-%dT%H:%M")
        self.enddate = datetime.now().strftime("%Y-%m-%dT%H:%M")

        self.data = self.pc.get_product_historic_rates(
            'BTC-USD', 
            start=self.startdate, 
            end=self.enddate, 
            granularity=3600
        )
        
        self.data.sort(key=lambda x: x[0])
        
        if np.mean([x[4] for x in self.data[-self.avg1:]]) > np.mean([x[4] for x in self.data[-self.avg2:]]):
            return True
        else:
            return False

class Account():

    """ Authenticates, checks balances, places orders. """
    
    def __init__(self):
        self.auth_client = AuthenticatedClient(api_key, secret, passphrase)
        self.size = 0.001
        
    def is_balanceUSD(self):
        self.account = self.auth_client.get_accounts()
        if float([x for x in self.account if x['currency'] == 'USD'][0]['available']):
            return True
        else:
            return False
        
    def is_balanceBTC(self):
        self.account = self.auth_client.get_accounts()
        if float([x for x in self.account if x['currency'] == 'BTC'][0]['available']):
            return True
        else:
            return False
        
    def buy(self):
        return self.auth_client.place_market_order(
            'BTC-USD', 
            'buy', 
            size=self.size
        )
        
    def sell(self):
        return self.auth_client.place_market_order(
            'BTC-USD', 
            'sell', 
            size=self.size
        )
        
def run():
    
    print('initiating run()')
    
    auth_client = Account()
    
    # Checks if top of the hour, if so returns signals.
    while True:
        if datetime.now().minute == 0:
            if History().signal:
                if auth_client.is_balanceUSD():
                    buy = auth_client.buy()
                    logging.warning('{} - {}'.format(datetime.now(), buy)) 
            else:
                if auth_client.is_balanceBTC():
                    sell = auth_client.sell()
                    logging.warning('{} - {}'.format(datetime.now(), sell))
            time.sleep((60*60) - datetime.now().minute*60 - (datetime.now().microsecond/1000000))
        else:
            time.sleep((60*60) - datetime.now().minute*60 - (datetime.now().microsecond/1000000))
        
if __name__ == '__main__':
    run()