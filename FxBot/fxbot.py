import logging
import numpy as np
import time
import traceback
import pandas as pd

from pymongo import MongoClient
import requests
from .xAPIConnector import *



#logging.getLogger('xAPIConnector').setLevel(logging.ERROR)
logging.getLogger('pymongo').setLevel(logging.ERROR)
logging.getLogger('requests').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)

#connection to MongoDB
client = MongoClient('localhost')

db = client.Bot

FxData = db.FxData
FxData10 = db.FxData10


HEADER ={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.75 Safari/537.36'}

def get_info_about_trades():
    '''
    returns: <dict>, profitable trades and unprofitable with sum profits and losses as dict
    '''
    return FxData.aggregate([{'$facet':{'loss':[{ '$match': { 'order': { '$exists': True }, 'profit' :{'$lt':12} }},{'$count': "No"}], 
                                        'profitable':[{ '$match': { 'order': { '$exists': True }, 'profit' :{'$gt':12} }},{'$count': "No"}], 
                                        'PL':[{ '$match': { 'order': { '$exists': True } }},{ '$group': { '_id' : None, 'sum' : { '$sum': "$profit" }}}]}
                             }]).next()

def get_trades():
    '''
    function which retuns list of dictionaries with data about closed trades
    returns: <list>, list of dictionaries with data about closed trades
    '''
    return list(FxData.aggregate([{ '$match': { 'order': { '$exists': True }}}]))

def get_structured_data(time = 100, limit = 0):
    '''
    Function to get structured data from MongoDB, please it can take time ...
    returns: <tuple>, tuple: <numpy.array>, <numpy.array> or if you want: features, labels
        
    args:
        time: <int>, how long features ( in this case timeserie) will be long in seconds
        limit: <int>, positive integer to limit number of trades if necessary
    '''
    trades = get_trades()
    if limit != 0 and limit > 0:
        trades = trades[:limit]
    #generate labels
    profits = [item.get('profit') for item in trades]
    logger.debug('Gets {} trades'.format(len(profits)))
    #convert list profits and losses to binary
    labels = np.array([[(0 if item < 0 else 1)] for item in profits]).astype(np.uint8)
    # features
    times = [item.get('Time') for item in trades]
    features = []
    logger.debug('Labels done. Working on features')
    # fetching data for features and structuring them
    for ind, item in enumerate(times):
        # lower or equal time that in item, only price to get, reversed it by sorting, limit size of data and reversed it again 
        x = list(FxData.find({'Time':{'$lte':item}},{"Price":1, '_id':0}).sort('Time', pymongo.DESCENDING).limit(time))[::-1]
        features.append([item.get('Price') for item in x])
        if ind % 10 == 0:
            logger.debug('Done structuring {} trades'.format(ind))
    features = np.array(features).astype(np.float32)
    logger.debug('Your data are prepared')
    return features, labels

class Trader():

    def __init__(self, userid= 11111, password='password', demo=True, setbet=0 , stop_loss = 0.0010, take_profit = 0.0065, model = False):
        #model must be restored before 
        self.model = False
        if model:
            self.model = model
        server = 'xapi.xtb.com'
        port = 5124
        streaming_port = 5125
        logging.basicConfig(level=logging.DEBUG, format = '%(asctime)s %(levelname)s %(message)s')
        self.logger = logging.getLogger(__name__)
        self.server = server
        self.port = port
        self.streaming_port = streaming_port
        if demo == False:
            self.port = 5112
            self.streaming_port = 5113
        self.userid = userid  
        self.password = password
        self.prices = []
        self.demo = demo
        self.setbet = setbet
        self.stop_loss = stop_loss
        self.take_profit = take_profit

    def get_day(self):
        '''
        returns  day as Mon, ... Sun, Fri ... UTC ZONE
        '''
        return time.strftime( "%a" , time.gmtime() )

    def get_hour(self):
        '''
        returnshour + minutes for 13 15 returns 1315 as integer UTC ZONE
        '''
        return int(time.strftime("%H%M", time.gmtime()))

    def get_price(self):
        '''
        returns price for EURUSD
        '''
        url = "http://webrates.truefx.com/rates/connect.html?f=html&c=EUR/USD"
        data  = requests.get(url, headers = HEADER).text.replace('<table>','').replace('<tr>','').replace('<td>','').replace('</td>','')
        return float( data [ data.index('.') - 1 : data.index('.') + 6 ] )

    def trade(self, value = 0, volume = 1, customComment = ''):
        '''
        opens trade if value = 0 buy if 1 sell, also returns response from XTB api
        '''
        apiClient = APIClient(address = self.server, port = self.port, encrypt = True)
        loginCmd = loginCommand(self.userid, self.password)
        # execute login command
        loginResponse = apiClient.execute(loginCmd)
        symbol = baseCommand('getSymbol',{"symbol": "EURUSD"})
        tick = apiClient.execute(symbol)
        # get price for opening trade
        price = tick['returnData']['ask']
        # set take profit and stop loss
        tp, sl = 0,0
        tp = tick['returnData']['bid']- self.take_profit if value == 1 else tick['returnData']['ask'] + self.take_profit
        sl = tick['returnData']['bid'] + self.stop_loss if value == 1 else tick['returnData']['ask'] - self.stop_loss
        trade = baseCommand('tradeTransaction',{"tradeTransInfo": {"cmd": value,"customComment": customComment,"expiration": 0,"order": 0,"price": price,"sl": sl,"tp": tp,"symbol": "EURUSD","type": 0,"volume": volume}})
        tradeResponse = apiClient.execute(trade)
        del self.prices[:]
        apiClient.disconnect()
        return tradeResponse

    def buy(self, volume = 1, customComment = ''):
        '''
        opens trade if value = 0 buy if 1 sell, also returns response from XTB api
        '''
        apiClient = APIClient(address = self.server, port = self.port, encrypt = True)
        loginCmd = loginCommand(self.userid, self.password)
        # execute login command
        loginResponse = apiClient.execute(loginCmd)
        symbol = baseCommand('getSymbol',{"symbol": "EURUSD"})
        tick = apiClient.execute(symbol)
        # get price for opening trade
        price = tick['returnData']['ask']
        # set take profit and stop loss
        trade = baseCommand('tradeTransaction',{"tradeTransInfo": {"cmd": 0,"customComment": customComment,"expiration": 0,"order": 0,"price": round(price,5),"sl": round(price - self.stop_loss,5),
                                                                   "tp": round(price + self.take_profit,5),"symbol": "EURUSD","type": 0,"volume": volume}})
        tradeResponse = apiClient.execute(trade)
        del self.prices[:]
        apiClient.disconnect()
        return tradeResponse

    def sell(self, volume = 1, customComment = ''):
        '''
        opens trade if value = 0 buy if 1 sell, also returns response from XTB api
        '''
        apiClient = APIClient(address = self.server, port = self.port, encrypt = True)
        loginCmd = loginCommand(self.userid, self.password)
        # execute login command
        loginResponse = apiClient.execute(loginCmd)
        symbol = baseCommand('getSymbol',{"symbol": "EURUSD"})
        tick = apiClient.execute(symbol)
        # get price for opening trade
        price = tick['returnData']['bid']
        # set take profit and stop loss
        trade = baseCommand('tradeTransaction',{"tradeTransInfo": {"cmd": 1,"customComment": customComment,"expiration": 0,"order": 0,"price": round(price,5),"sl": round(price + self.stop_loss,5),
                                                                   "tp": round(price - self.take_profit,5),"symbol": "EURUSD","type": 0,"volume": volume}})
        tradeResponse = apiClient.execute(trade)
        del self.prices[:]
        apiClient.disconnect()
        return tradeResponse


    def delete_trades(self, residue=0):
        '''
        returns opened trades also you can set up that numbers of last trades which will stay
        '''
        apiClient = APIClient(address=self.server, port=self.port, encrypt=True)
        loginCmd = loginCommand(self.userid, self.password)
        # execute login command
        loginResponse = apiClient.execute(loginCmd)
        openTrades = apiClient.execute(baseCommand('getTrades',{"openedOnly": True}))['returnData']
        if openTrades:
            for i in range(len(openTrades)-1,residue - 1,-1):
                trade = baseCommand('tradeTransaction',{"tradeTransInfo": {"cmd": list_open[i]['cmd'],"customComment": openTrades[i]["customComment"],"expiration":0,"order": openTrades[i]['order'],"price": openTrades[i]['close_price'],"sl": openTrades[i]['sl'],"tp": openTrades[i]['tp'],"symbol": "EURUSD","type": 2,"volume": openTrades[i]['volume']}})
                traderesponse = apiClient.execute(trade)
        apiClient.disconnect()

    def get_trades(self):
        '''
        returns historical trades
        '''
        apiClient = APIClient(address=self.server, port=self.port, encrypt=True)
        loginCmd = loginCommand(self.userid, self.password)
        # execute login command
        loginResponse = apiClient.execute(loginCmd)
        trades = apiClient.execute(baseCommand('getTradesHistory',{"end": 0,"start":0}))
        return trades

    def update_info_trades(self):
        '''
        add info about orders to mongodb by using customComment
        '''
        trades = self.get_trades()['returnData']
        for item in trades:
            try:
                Time = int(item['customComment'])
                result = {}
                for element in ['order','cmd','profit','close_time']:
                    result[element] = item[element]
                FxData.update({'Time':Time},{'$set':result})
            except:
                logger.debug('Order not found ...')
            logger.debug('Done')

    def set_bet(self):
        '''
        returns volume which will be used to open trade
        '''
        apiClient = APIClient(address=self.server, port=self.port, encrypt=True)
        loginCmd = loginCommand(self.userid, self.password)
        #execute login command
        loginResponse = apiClient.execute(loginCmd)
        balanceResponse = apiClient.execute(baseCommand('getMarginLevel',dict()))
        balance = balanceResponse["returnData"]['balance']
        volume = balance//400
        volume = 1 if volume == 0 else volume
        volume = round(volume*0.01,2)
        volume = 50 if volume > 50 else volume
        apiClient.disconnect()
        return  volume

    def check(self):
        '''
        checks data if there is a signal
        '''
        if len(self.prices) > 3601:
            delta = self.prices[-1]-self.prices[-1200]
            '''
            here will be good to implement control by linear regression
            hmm it will be interesting if it is really possible to get 40 percent of profitable trades
            '''
            response = {1:'buy',-2:'sell'}
            result = response.get(delta//0.0010)
            if result and self.model:
                logger.debug('Making prediction')
                #scale and reshape input prices
                prices = np.array(self.prices[-3600:]).reshape(1,-1)
                #make prediction
                prediction = self.model.predict(prices)
                if np.round(prediction) == True:
                    del self.prices[:-2400]
                    logger.debug('Prediction True')
                    #store info about that
                    db['Filtering'].insert({'Prediction':True, 'Timestamp':time.ctime(), 'Userid': self.userid, 'Type':result})
                    return result
                else:
                    #delete prices anyway 
                    logger.debug('Prediction False')
                    del self.prices[:-2400]
                    db['Filtering'].insert({'Prediction':False, 'Timestamp':time.ctime(), 'Userid': self.userid, 'Type':result})
                    return None
            if result:
                return result
            else:
                return None

    def scan_fx(self):
        '''
        scans every second if there is signal to trade
        '''
        while True:
            hourmin = self.get_hour()
            day =  self.get_day()
            if day == 'Fri' and 1944 < hourmin <2000:
                self.update_info_trades()
                time.sleep(172750)
            try:
                price = self.get_price()
                self.prices.append(price)
                response = self.check()
                result = {}
                result['Time'] = int(time.time())
                result['Price'] = price
                if response:
                    logger.error(response)
                    #normally setted by set_bet()
                    bet = self.set_bet()
                    if response == 'buy':
                        tradeResponse = self.buy(volume = bet, customComment =  str(result['Time']))
                    if response == 'sell':
                        tradeResponse = self.sell(volume = bet, customComment =  str(result['Time']))
                    if tradeResponse['status']:
                        result['Order'] = tradeResponse['returnData']['order']
                        self.logger.debug(result)
                #FxData.insert(result)
                #self.logger.error('One loop done')
                time.sleep(0.8)
                if len(self.prices)>7200:
                    del self.prices[:3600]
            except Exception as e:
                self.logger.debug('Error : {} Traceback : {}'.format(e, traceback.print_exc()))
                time.sleep(0.75)
                
def run():
    #change to your account, if real account add demo = False
    tr = Trader(userid = 11111111, password = 'blablabla')
    tr.scan_fx()
    
def run10():
    #change to your account, if real account add demo = False
    # trying to harvest data with different take profit
    tr = Trader(userid = 11111111, password = 'blablabla', setbet = 0.01 , stop_loss = 0.0010, take_profit = 0.0010, collection = FxData10)
    tr.scan_fx()

if __name__ == "__main__":
    tr = Trader(userid = 11111111)
    tr.scan_fx()
