
import datetime
import pandas as pd
import requests
import re

from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin

from enum import Enum
from abc import ABC, abstractmethod

from abt.const import RaceLocation

class Schedule(ABC):
    
    @abstractmethod
    def data(self):
      pass

    @abstractmethod
    def init(self):
      pass

class JRASchedule(Schedule):
    
    def data(self):
        return self._data.reset_index()
    
    def __init__(self, init:bool = True) -> None:
        self._data:pd.DataFrame = pd.DataFrame()
        if init:
          self.init()

    def init(self):
      basesoup = self.__access_entries()
      self._data = self.get_location_url(basesoup)
      self._data = pd.concat(
          self._data["url"].apply(
            lambda x: self.fetch_race_url_from_round_url(x)).to_list()) # type: ignore
      self._data['netkeibaURL'] = self.get_netkeiba_shutsuba_url(self._data)
      self._data['resultURL'] = self.get_netkeiba_result_url(self._data)

        # redirect to the page where each race url can be found
    def __access_entries(self) -> BeautifulSoup:
      # chromeを起動する
      option = webdriver.ChromeOptions()
      option.add_argument('--headless')

      try:
          browser = webdriver.Chrome(ChromeDriverManager().install(), options=option)
      except:
          service = webdriver.ChromeService(executable_path = ChromeDriverManager().install())
          browser = webdriver.Chrome(service=service, options=option)

      # open jra page
      browser.get('https://www.jra.go.jp/')
      browser.implicitly_wait(10)  # 指定した要素が見つかるまでの待ち時間を10秒と設定する

      # 出馬表をクリック
      xpath = '//*[@id="quick_menu"]/div/ul/li[2]/a'
      elem_search = browser.find_element(By.XPATH, value=xpath)
      elem_search.click()

      # 「今週の出馬表」の左端の開催をクリック
      xpath = '//*[@id="main"]/div[2]/div/div/div[1]/a'
      elem_search = browser.find_element(By.XPATH, value=xpath)
      elem_search.click()

      # ラウンドをクリック
      xpath = '//*[@id="race_list"]/tbody/tr[1]/th'
      elem_search = browser.find_element(By.XPATH, value=xpath)
      elem_search.click()

      # 表示しているページのURLを取得する
      cur_url = browser.current_url
      res = requests.get(cur_url)  # 指定したURLからデータを取得する
      soup = BeautifulSoup(res.content, 'lxml')  # content形式で取得したデータをhtml形式で分割する

      return soup
    
    def __parseLocationRoundKai(self, text:str|None):
        if text is None: raise  RuntimeError('No date text')
        day = re.findall(r"(\d+)日", text)
        kai = re.findall(r"(\d+)回", text)
        place = re.findall(r'(?<={}回).*?(?={}日)'.format(kai, day), text)
        if any([1!=len(x) for x in [day, kai, place]]):
            raise RuntimeError("number of count of day, kai or place is not 1")
        return {'location':place[0], 'round':kai[0], 'day':day[0]}
    
    # 開催場所のURLを取得する
    # 「5回東京5日」「5回阪神5日」などのURLを取得する
    # arg: soup
    # return: dataFrame of location, round, day, url
    # example -> for 5回東京1日 location:東京, round:5, day:1, url: https//www.abc.def
    def get_location_url(self, soup:BeautifulSoup):
        locations_info = soup.find_all('div', attrs={'class': 'link_list multi div3 center mid narrow'})

        # 開催場所のURLを保存するリストを用意
        location_url = []

        # 取得したdivタグから追加でaタグを取得し、aタグからhrefを抽出する
        # 'https://www.jra.go.jp'と抽出したhrefを結合してlocation_urlに保存する
        url_dfs = []
        for locations in locations_info:
            for location in locations.find_all('a'):
                res = self.__parseLocationRoundKai(location.text)
                url = urljoin('https://www.jra.go.jp', location.get('href'))
                url_dfs.append(res|{'url':url})
                location_url.append(url)

        return pd.DataFrame(url_dfs)

    def fetch_race_url_from_round_url(self, url:str) -> pd.DataFrame:
        res = requests.get(url)
        soup = BeautifulSoup(res.content, 'html5lib')
        return self.get_round_url(soup)
  
    def __parseDate(self, text:str|None) -> dict:
        if text is None: raise  RuntimeError('No date text')
        year = re.findall(r"(\d+)年", text)
        month = re.findall(r"(\d+)月", text)
        day = re.findall(r"(\d+)日", text)
        if any([1<len(x) for x in [year, month, day]]):
            raise RuntimeError("more than one year, month or day found in string")
        return {'date':datetime.date(int(year[0]), int(month[0]), int(day[0]))}
    
    def __parseTime(self, text:str|None) -> dict:
        if text is None: raise  RuntimeError('No date text')
        hour = re.findall(r"(\d+)時", text)
        minute = re.findall(r"(\d+)分", text)
        if any([1<len(x) for x in [hour, minute]]):
            raise RuntimeError("more than one year, month or day found in string")
        return {'startHour':int(hour[0]), 'startMinute':int(minute[0])}
    
    def getTime(self, url:str) -> dict:
      res = requests.get(url)
      soup = BeautifulSoup(res.content, 'html5lib')
      round_meta = soup.find('div', attrs={'id': 'syutsuba'})
      if not isinstance(round_meta, Tag):
          raise RuntimeError('No Round info found, please check code')
      meta_text = round_meta.find('div', attrs={'class':'cell date'})
      time_text = round_meta.find('div', attrs={'class':'cell time'})
      time_text = time_text.find('strong') if time_text is not None else None
      time_text = time_text.text if isinstance(time_text, Tag) else None
      return self.__parseTime(time_text)
    

    def get_round_url(self, soup:BeautifulSoup) -> pd.DataFrame:
      rounds_info = soup.find('ul', attrs={'class': 'nav race-num mt15'})
      round_meta = soup.find('div', attrs={'id': 'syutsuba'})
      if not isinstance(round_meta, Tag):
          raise RuntimeError('No Round info found, please check code')
      meta_text = round_meta.find('div', attrs={'class':'cell date'})
      round_text = meta_text.text.split(' ')[-1] if meta_text is not None else None
      date_text = meta_text.text.split(' ')[0] if meta_text is not None else None
      round_data = self.__parseLocationRoundKai(round_text)
      date = self.__parseDate(date_text)
      # ラウンドのURLを保存するリストを用意
      round_url = []

      if not isinstance(rounds_info, Tag):
        raise RuntimeError('No Round info found, please check code')
      # リンクページのURLを作成する
      for round in rounds_info.find_all('a'): 
          url = urljoin('https://www.jra.go.jp', round.get('href'))
          race = int(re.findall(r"\d+", round.find('img', alt=True)['alt'])[0])
          time = self.getTime(url)
          round_url.append(date|time|round_data|{'race':race, 'url':url})
      return pd.DataFrame(round_url)

    def __build_netkeiba_raceId(self, location, date, round, day, race):
      locationId=f"{RaceLocation[location].value:02d}"
      year = str(date.year)
      return "".join([year, locationId]+[f'{int(x):02d}' for x in [round, day, race]])

    def __build_netkeiba_url(self, meta, mode='shutuba'):
      prefix = f'https://race.netkeiba.com/race/{mode}.html?race_id='
      return f'{prefix}{self.__build_netkeiba_raceId(**meta)}'
    
    def get_netkeiba_shutsuba_url(self, data:pd.DataFrame) -> pd.Series:
        meta_cols = ['date', 'location', 'round','day', 'race']
        return data[meta_cols].apply(lambda x: self.__build_netkeiba_url(x), axis=1)
    
    def get_netkeiba_result_url(self, data:pd.DataFrame) -> pd.Series: 
        meta_cols = ['date', 'location', 'round','day', 'race']
        return data[meta_cols].apply(lambda x: self.__build_netkeiba_url(x, mode='result'), axis=1)


