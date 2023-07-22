import requests
from bs4 import BeautifulSoup, Tag, NavigableString, Comment
from requests_html import HTMLSession
import pandas as pd
import itertools

import numpy as np
import numbers
import re
import pandas as pd
from abc import ABC, abstractmethod

class Shutsuba(ABC):
    
    @abstractmethod
    def data(self):
      pass

    @abstractmethod
    def init(self):
      pass

# get data from NKB
# get odds from JRA
class NKBJRAShutsuba(Shutsuba):
    
    def data(self):
      return self._data.query('not isCanceled').drop('isCanceled', axis=1).reset_index()
    
    def __init__(self, 
                 nkburl:str, 
                 jraurl:str, init:bool = True) -> None:
      self._data:pd.DataFrame = pd.DataFrame()
      self.nkburl = nkburl
      self.jraurl = jraurl
      self.nkbsoup = self.__get_soup(nkburl)
      self.jrasoup = self.__get_soup(jraurl)

      if init:
        self.init()
    
    def init(self):
      horses = self.fetch_horse_info(self.nkbsoup)
      horses = pd.merge(horses, self.fetch_odds(self.jrasoup), on='horseNum')
      self._data = horses
    
    def __get_soup(self, url:str) -> BeautifulSoup:
      res = requests.get(url) 
      return BeautifulSoup(res.content, 'lxml') 

    def fetch_race_meta(self) -> pd.DataFrame:
        tag = self.nkbsoup.find('div', attrs={'class': 'RaceData01'})
        tag2 =  self.nkbsoup.find('div', attrs={'class': 'RaceData02'})
        if isinstance(tag, Tag) and isinstance(tag2, Tag):
            res=dict()
            def get_field_type(input, options):
                fields = []
                for ch in input:
                    if ch in options:
                        fields.append(ch)
                return '/'.join(fields)
            dir_options = ["左", "右", '内', '外']
            field_options = ["芝", "ダ"]
            vals = [x if isinstance(x, NavigableString) else x.contents for x in tag if not isinstance(x, Comment)]
            vals1 = [x if isinstance(x, NavigableString) else x.contents for x in tag2 if not isinstance(x, Comment)]
            vals = vals+vals1
            vals = [x if isinstance(x, str) else x[0] for x in vals if x and x!='\n']
            vals = [x for x in list(itertools.chain.from_iterable([x.split("\n") for x in vals])) if x]
            res['is_hindrance'] = int(False)
            res['direction'] = ''
            for val in vals:
                if isinstance(val, str):
                    if '馬場' in val:
                        res['ground_condition'] = val.split(":")[1]
                    if '天候' in val:
                        res['weather'] = val.split(":")[1]
                    if '頭' in val:
                        res['horse_count'] = re.findall(r'\d+', val)[0]
                    if any([x in val for x in dir_options]):
                        res['direction']= get_field_type(val,dir_options)
                    if any([x in val for x in field_options]):
                        res['field_type'] = get_field_type(val, field_options)
                        if len(re.findall(r'\d+', val)) == 1:
                            res['distance'] = re.findall(r'\d+', val)
                    if "障" in val:
                        res['distance'] = re.findall(r'\d+', val)[0]
                        res['is_hindrance'] = int(True)
            return pd.DataFrame(res, index=[0])
        else:
            raise RuntimeError("can not find the right tag")

  
    def __get_weight(self, row_tag:Tag) -> dict:
        tag = row_tag.find('td', class_='Weight')
        if isinstance(tag, Tag):
            weight = tag.get_text().lstrip().rstrip('\n')
            weightChange = int(weight[weight.find('(')+1:weight.find(')')].lstrip().rstrip('\n'))
            horseWeight = weight[:weight.find('(')]
            sign = -1 if '-' in horseWeight else 1
            horseWeight = sign* int(re.findall(r'\d+', horseWeight)[0].lstrip().rstrip('\n'))
            return {'weight': horseWeight,'weightChange':weightChange}
        else:
            return {'weight': np.nan, 'weightChange':np.nan}

    def __get_id_from_url(self, url:str) -> str:
        if url.endswith('/'):
            url = url[:-1]
        return url.split("/")[-1]

    def __get_age_sex(self, rowTag:Tag) -> dict:
        tag = rowTag.find('td', class_='Barei Txt_C')
        if isinstance(tag, Tag):
          agesex = tag.get_text().lstrip().rstrip('\n')
          return {'age':int(re.findall(r'\d+', agesex)[0]), 'sex':re.findall(r'[^\d]', agesex)[0]}
        else:
            return {'age': np.nan, 'sex':''}

    def fetch_horse_info(self, soup) -> pd.DataFrame:
        tags = soup.find_all('tr', class_='HorseList')
        rows = list()
        for tag in tags:
          info = dict()
          info['horseNum'] = int(tag.select('td[class*="Umaban"]')[0].text.lstrip().rstrip('\n'))
          info['lane'] = int(tag.select('td[class*="Waku"]')[0].find('span').text.lstrip().rstrip('\n'))
          info['horseName'] = tag.find('span', 'HorseName').get_text().lstrip().rstrip('\n')
          info['horseId'] = self.__get_id_from_url(tag.find('span', 'HorseName').find("a").get('href').lstrip().rstrip('\n'))
          info['trainerName'] = tag.find('td', 'Trainer').find("a").text.lstrip().rstrip('\n')
          info['affiliations'] = tag.find('td', 'Trainer').find('span').text.lstrip().rstrip('\n')
          info['trainId'] = self.__get_id_from_url(tag.find('td', 'Trainer').find("a").get('href').lstrip().rstrip('\n'))
          info['isCanceled'] = True if tag.find('td', class_='Cancel_Txt') else False
          info = info|self.__get_weight(tag)
          info = info|self.__get_age_sex(tag)
          info['load'] = float(tag.select('td[class="Txt_C"]')[0].text) if tag.select('td[class="Txt_C"]') else np.nan
          rows.append(info)
        print(len(rows))
        return pd.DataFrame(rows)

    def fetch_odds(self, soup) -> pd.DataFrame:
        tags = soup.find('tbody').find_all('tr')
        rows = list()
        for tag in tags:
            info = dict()
            horse_num = tag.find('td', class_='num').text.split('\n')[0]
            odds = tag.find('div', class_='odds').find('span', class_='num').text
            info['horseNum'] = int(horse_num) if horse_num.isnumeric() else np.nan
            info['odds']= float(odds) if odds.replace('.', '').isnumeric() else np.nan
            rows.append(info)
        return pd.DataFrame(rows).pipe(
                  lambda x: x.assign(popularity = x['odds'].rank().astype(int, errors = 'ignore')))
            
