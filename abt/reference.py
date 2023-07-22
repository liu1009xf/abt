from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import urljoin
import requests
import re
import datetime as dt
import re

from enum import Enum
from abc import ABC, abstractmethod

from .const import RaceLocation

class GroundCondition(ABC):
    @abstractmethod
    def to_df(self):
      pass

    @abstractmethod
    def init(self):
      pass

# initiate with location Example: 
# To get 
class JRAGroundCondition(GroundCondition):
    def __init__(self,
                location: RaceLocation|str, 
                init:bool = True, 
                url:str = 'https://www.jra.go.jp/keiba/baba/'):
        self.url = url
        self.location = location.name if isinstance(location, RaceLocation) else location
        self.weather = ''
        self.shiba_condition = ''
        self.dart_condition = ''
        self.date = None
        if init:
          self.init()
    
    def to_df(self):
        return pd.DataFrame({
            'date': [self.date],
            'location':[self.location], 
            'weather':[self.weather], 
            'shibaCondition': [self.shiba_condition], 
            'dartCondition': [self.dart_condition]})

    def __parse_date(self, date):
        date = re.sub(r'\（.*?\）', '',date.text[1:-1])
        day = re.findall(r'(?<=月).+?(?=日)', date)[0]
        month = re.findall(r'(?<=年).+?(?=月)', date)[0]
        year = date[:date.find('年')]
        self.date = dt.datetime(int(year), int(month), int(day)).date()
        return date
    
    # Get Race meta info including datetime, weather and ground condition
    def init(self):
        res = requests.get(self.url)
        soup = BeautifulSoup(res.content, 'lxml')

        date = [x for x in soup.find_all('span', attrs={'class': 'date'}) if x.get('class')[0]=='date']
        if 1<len(date):
            raise RuntimeError ('Unexpectedly get more than 1 date')
        self.__parse_date(date[0])

        # 天候の情報を取得する
        class_cell_txt = soup.find('div', attrs={'class': 'cell txt'})
        if class_cell_txt is not None:
            self.weather = class_cell_txt.text.replace('天候：', '')
        else:
            raise RuntimeError(f'No Weather Info for {self.location}')

        # レース開催予定の馬場と情報が掲載されているURLを取得する
        location_list = []
        location_url = []
        class_nav_tab = soup.find_all('div', attrs={'class': 'nav tab'})
        tag_a = class_nav_tab[0].find_all('a')

        for i in tag_a:
            location_list.append(i.text)
            url = urljoin(self.url, i.get('href'))
            location_url.append(url)

        location_list = [s.replace('競馬場', '') for s in location_list]

        index_num = location_list.index(self.location)
        url = location_url[index_num]

        res = requests.get(url)
        soup = BeautifulSoup(res.content, 'lxml')

        class_data_list_unit = soup.find_all('div', attrs={'class': 'data_list_unit'})
        for i in class_data_list_unit:
            tag_h4 = i.find_all('h4')

            # skip if no h4 tag
            if len(tag_h4) == 0:
                continue

            if tag_h4[0].text == '芝':
                tag_p = i.find_all('p')
                self.shiba_condition = tag_p[0].text

            if tag_h4[0].text == 'ダート':
                tag_p = i.find_all('p')
                self.dart_condition = tag_p[0].text

