from pydoc import TextRepr
import requests
from bs4 import BeautifulSoup, Tag, NavigableString, Comment
import pandas as pd
from tqdm import tqdm
import itertools

# ------------------------------------
# import
# ------------------------------------
import time
import re
import pandas as pd
import os
import datetime
from abc import ABC, abstractmethod


class Result(ABC):
    
    @abstractmethod
    def init(self):
        pass
        
    @abstractmethod
    def data(self):
        pass
    
class NKBResult(Result):
    
    def __init__(self, url, init=True) -> None:
        self.url = url
        self.soup = self.__get_soup(url)
        self._data = pd.DataFrame()
    #     if init:
    #         self.init()

    def init(self):
        pass
        # self._data = self.get_result()

    def data(self) -> pd.DataFrame:
      return self._data.reset_index()
        
    def __get_soup(self, url:str) -> BeautifulSoup:
      res = requests.get(url) 
      return BeautifulSoup(res.content, 'lxml') 

    def __get_tansho(self, tag:Tag):
        result = {'ticketType':'Tansho'}
        result['pattern'] = [x.text for x in tag.find('td',class_='Result').find_all('span') if x.text!='']
        result['payoff'] = [x.text for x in tag.find('td', class_='Payout').find_all('span') if x.text!='']
        return result
    
    def __get_fukusho(self, tag:Tag):
        result = {'ticketType':'fukusho'}
        result['pattern'] = [x.text for x in tag.find('td',class_='Result').find_all('span') if x.text!='']
        result['payoff'] = [x.text for x in tag.find('td', class_='Payout').find_all('span') if x.text!='']
        return result

    def __get_wide(self, tag:Tag):
        result = {'ticketType':'wide'}
        result['pattern'] = [[y.text for y in x.find_all('span')] for x in  tag.find_all('ul') if x.text !='']
        result['payoff'] = [x.text for x in tag.find('td', class_='Payout').find_all('span') if x.text!='']
        return result

    def get_result(self, soup:BeautifulSoup) -> pd.DataFrame:
        typesI = ['Tansho', 'Fukusho', 'Wide']
        tags=soup.find_all("tr",class_=typesI)
        rows = list()
        for tag in tags:
          rows.append(getattr(self,f'_NKBResult__get_{tag["class"][0].lower()}')(tag))
        return pd.DataFrame(rows)


    # def get_result(self) -> pd.DataFrame:
    #     tags = self.soup.find('tbody')
    #     rows = list()
    #     if isinstance(tags, Tag):
    #         tags = tags.find_all('tr')
    #     else:
    #         raise RuntimeError('cannot find result table')
    #     for tag in tags:
    #         rows.append({
    #             'horseNum':tag.find('td', class_='Num Txt_C').find('div').text,
    #             'rank':tag.find('div', class_='Rank').text,
    #             'rank1Odds':''})
    #     return pd.DataFrame(rows)
