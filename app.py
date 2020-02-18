import os, sys, logging
from logging import handlers
from configparser import ConfigParser
from requests import Session
from bs4 import BeautifulSoup
from selenium import webdriver

class App:
    def __init__(self, WD):
        self.WD = WD
        self._logger = App.initLogger(WD)
        self._conf = None
        self._items = None

        self._logger.info('Start MaskBot !!!')

    @staticmethod
    def initLogger(WD):
        log_dir = os.path.join(WD, 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        logger = logging.getLogger('MaskBot')
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter('[%(levelname)s|%(filename)s:%(lineno)s] %(asctime)s - %(message)s')
        f_handler = handlers.RotatingFileHandler(os.path.join(log_dir, 'coronachk.log'), 'a', 10 * 1024 * 1024, 5)
        f_handler.setFormatter(fmt)
        logger.addHandler(f_handler)
        return logger

    @staticmethod
    def _msg(item):
        pass

    # - 품절 체크
    @staticmethod
    def _isSoldOut(item):
        classList = list(map(lambda c: c['class'], item.find_all('li')))
        try:
            classList.index(['soldout'])
            return True
        except ValueError:
            return False

    # - 제품 정보 파싱(판매중인 경우만)
    @staticmethod
    def _parse(item):
        return {
            'link': item.find('div', class_='thumb').find('a')['href'],
            "img": item.find('div', class_='thumb').find('img')['src'],
            'dsc': item.find('ul', class_='info').find('li', class_='dsc').text,
            'price': item.find('ul', class_='info').find('li', class_='price').text
        }

    # - 페이지 내 제품 정보 추출
    @staticmethod
    def _extractItems(soup):
        return soup.find_all('div', class_='box')

    def _load_conf(self, file_name='app.conf'):
        file = os.path.join(self.WD, file_name)
        parser = ConfigParser()
        parser.read(file, encoding='utf-8-sig')
        self._conf = parser


    def _crawl(self):
        if not self._conf:
            self._load_conf()

        try:
            url = self._conf['default']['url']
            headers={
                "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.106 Safari/537.36"
            }

            session = Session().get(url, headers=headers)
            session.encoding = None # ISO-8859-1 (euc-kr)
            if session.status_code != 200:
                raise Exception("Wrong page.. Check your URL")

            html = session.text
            soup = BeautifulSoup(html, 'lxml')
            self._items = App._extractItems(soup)

        except Exception as e:
            self._logger.error(e)


    def run(self):
        # Crawling
        if not self._items:
            self._crawl()

        # Check soldout
        for item in self._items:
            if self._isSoldOut(item):
                continue
            else:
                result = self._parse(item)
                print(result)

if __name__ == '__main__':
    WD = os.path.dirname(os.path.realpath(__file__))
    app = App(WD)
    app.run()

# 1 페이지 내의 모든 아이템을 읽어서

# 2 품절인지 판단을 하고

# 3 품절이 아니면 notify로  알림을 보내주자.