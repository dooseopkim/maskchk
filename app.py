import os, sys, logging, io
from logging import handlers
from configparser import ConfigParser
from requests import Session
from bs4 import BeautifulSoup
from selenium import webdriver

class App:

    MSG_FORM = "\n지금 살 수 있다고 합니다~\n▶ {dsc}\n▶ 가격 : {price}\n▶ 바로가기 : {url}"

    def __init__(self, WD):
        self.WD = WD
        self._logger = self.initLogger()
        self._conf = None
        self._items = None

        self._logger.info('Start MaskBot !!!')




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

    # - 이미지 추출 함수
    @staticmethod
    def _getPhoto(url):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.106 Safari/537.36"
        }
        response = Session().get(url, headers=headers)
        if response.status_code != 200:
            raise Exception('Something Wrong your image..')

        return response.content
    # - 메세지 포매팅 후 반환
    @staticmethod
    def _msg(dsc=None, price=None, url=None):
        return App.MSG_FORM.format(dsc=dsc, price=price, url=url)



    # - 로거 초기화
    def initLogger(self):
        log_dir = os.path.join(self.WD, 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        logger = logging.getLogger('MaskBot')
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter('%(asctime)s - [%(levelname)s|%(filename)s:%(lineno)s] - %(message)s')
        st_handler = logging.StreamHandler()
        f_handler = handlers.RotatingFileHandler(os.path.join(log_dir, 'maskchk.log'), 'a', 10 * 1024 * 1024, 5)
        st_handler.setFormatter(fmt)
        f_handler.setFormatter(fmt)
        logger.addHandler(st_handler)
        logger.addHandler(f_handler)
        return logger

    # - 환경설정 파일 초기화
    def _initConf(self, file_name='app.conf'):
        file = os.path.join(self.WD, file_name)
        parser = ConfigParser()
        parser.read(file, encoding='utf-8-sig')
        self._conf = parser

    # - 짧은 URL로 변환
    def _shortURL(self, url):
        if not self._conf:
            self._initConf()

        NAVER = self._conf['naverAPI']
        response = Session().post(
            NAVER['URL'],
            headers={
                'X-Naver-Client-Id': NAVER['clientID'],
                'X-Naver-Client-Secret': NAVER['clientSecret']
            },
            data={
                'url': url.encode('utf-8')
            }
        )

        if response.json()['code'] != '200':
            self._logger.warning('Trans short url is fail..')
            return url

        return response.json()['result']['url']

    # - 라인 Notify 메세지 전송
    def _sendNotify(self, item):
        if not self._conf:
            self._initConf()

        url = self._conf['default']['HOST'] + item['link']  # original URL
        message = self._msg(item['dsc'], item['price'], self._shortURL(url))  # message

        img = self._conf['default']['HOST'] + item['img']  # image URL
        imageFile = io.BytesIO(self._getPhoto(img))

        TARGET_URL = self._conf['notify']['URL']
        TOKEN = self._conf['notify']['TOKEN']

        headers = {'Authorization': 'Bearer {TOKEN}'.format(TOKEN=TOKEN)}
        data = {'message': message}
        files = {'imageFile': imageFile}

        response = Session().post(TARGET_URL, headers=headers, data=data, files=files)




    # - 크롤링
    def _crawl(self):
        if not self._conf:
            self._initConf()

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
                selling = self._parse(item)
                self._sendNotify(selling)


if __name__ == '__main__':
    WD = os.path.dirname(os.path.realpath(__file__))
    app = App(WD)
    app.run()
    # print(app.shortURL('http://www.welkeepsmall.com/shop/shopbrand.html?type=X&xcode=007'))
# 1 페이지 내의 모든 아이템을 읽어서

# 2 품절인지 판단을 하고

# 3 품절이 아니면 notify로  알림을 보내주자.