import os
import sys
import requests
import logging, logging.handlers

from bs4 import BeautifulSoup
from configparser import ConfigParser


class App:


    def __init__(self, WD, TYPE):
        self.WD = WD
        self.TYPE = TYPE
        self._logger = None
        self._conf = None
        self._items = None


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
            'dsc': item.find('ul', class_='info').find('li', class_='dsc').text,
            'price': item.find('ul', class_='info').find('li', class_='price').text
        }

    # - 페이지 내 제품 정보 추출
    @staticmethod
    def _extractItems(soup):
        divs = soup.find_all('div', class_='box')
        if len(divs) == 0:
            raise Exception("Website is down..")
        return divs

    # - 이미지 추출 함수
    @staticmethod
    def _getPhoto(url):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.106 Safari/537.36"
        }
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception(response.text)

        return response.content

    # - 메세지 포매팅 후 반환
    @staticmethod
    def _msg(dsc=None, price=None, url=None):
        return "▶ {dsc}\n▶ 가격 : {price}\n▶ 바로가기\n{url}".format(dsc=dsc, price=price, url=url)


    # - 로거 초기화
    def _initLogger(self):
        log_dir = os.path.join(self.WD, 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        logger = logging.getLogger('MaskBot')
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter('%(asctime)s - [%(levelname)s|%(filename)s:%(lineno)s] - %(message)s')

        st_handler = logging.StreamHandler()
        f_handler = logging.handlers.RotatingFileHandler(os.path.join(log_dir, 'maskchk.log'), 'a', 10 * 1024 * 1024, 5)

        st_handler.setFormatter(fmt)
        f_handler.setFormatter(fmt)

        logger.addHandler(st_handler)
        logger.addHandler(f_handler)

        self._logger = logger

    # - 환경설정 파일 초기화
    def _initConf(self, file_name='app.conf'):
        file = os.path.join(self.WD, file_name)
        parser = ConfigParser()
        parser.read(file, encoding='utf-8-sig')
        self._conf = parser

    # - 짧은 URL로 변환
    def _shortURL(self, url):
        origin_url = self._conf['default']['HOST'] + url
        try:
            self._logger.info('Call API Naver shortURL')

            NAVER = self._conf['naverAPI']
            response = requests.post(
                NAVER['URL'],
                headers={
                    'X-Naver-Client-Id': NAVER['clientID'],
                    'X-Naver-Client-Secret': NAVER['clientSecret']
                },
                data={
                    'url': origin_url.encode('utf-8')
                }
            )

            if response.json()['code'] != '200':
                raise Exception(response.json()['message'])

            return response.json()['result']['url']

        except Exception as e:
            self._logger.warning(e)
            return origin_url


    # - 라인 Notify 메세지 전송
    def _sendNotify(self, messages):
        try:
            self._logger.info('Send Line notification')
            TARGET_URL = self._conf['notify']['URL']
            TOKEN = self._conf['notify']['TOKEN']

            message = '\n==========================\n'.join(messages)

            headers = {'Authorization': 'Bearer {TOKEN}'.format(TOKEN=TOKEN)}
            data = {'message': message}

            response = requests.post(TARGET_URL, headers=headers, data=data)

            if response.status_code != 200:
                raise Exception(response.text)
        except Exception as e:
            self._logger.error(e)

    # - 크롤링
    def _crawl(self):
        try:
            TARGET_URL = self._conf['default']['BBS']
            headers={
                "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.106 Safari/537.36"
            }

            if self.TYPE == 'cool':
                # 쿨패치
                xcode = '007'
            elif self.TYPE == 'hot':
                # 핫팩
                xcode = '002'
            else:
                # 마스크
                xcode = '023'
            params = {'type': 'x', 'xcode': xcode}

            response = requests.get(TARGET_URL, headers=headers, params=params)
            response.encoding = None # ISO-8859-1 (euc-kr)

            self._logger.info('Crawling... {}'.format(response.url))

            if response.status_code != 200:
                raise Exception("Wrong page.. Check your URL")

            html = response.text
            soup = BeautifulSoup(html, 'lxml')

            # Extract divs of item
            self._items = App._extractItems(soup)

        except Exception as e:
            self._logger.error(e)


    def run(self):
        try:
            # List of message for send notification
            messages = ['\n==========================\n\n현재 구입 가능한 상품\n']

            # Initialize
            self._initLogger()
            self._initConf('_app.conf')

            self._logger.info('Start process')

            # Crawling
            self._crawl()

            # Check Soldout
            selling_items = [item for item in self._items if not self._isSoldOut(item)]
            self._logger.info('Check available for purchase : {} items.'.format(len(selling_items)))

            # If no item, sys exit
            if len(selling_items) == 0:
                sys.exit()

            for item in selling_items:
                item_ = self._parse(item)

                dsc_ = item_.get('dsc')
                price_ = item_.get('price')
                link_ = self._shortURL(item_.get('link'))
                message = self._msg(dsc_, price_, link_)
                messages.append(message)

            # - Send notification
            self._sendNotify(messages)

        except Exception as e:
            _, _, tb = sys.exc_info()
            self._logger.error('line : {} - {}'.format(tb.tb_lineno, e))
        finally:
            self._logger.info('End Process')


def main():
    WD = os.path.dirname(os.path.realpath(__file__))
    if len(sys.argv) >= 2:
        TYPE = sys.argv[1]
    else:
        TYPE = 'mask'
    app = App(WD, TYPE)
    app.run()


if __name__ == '__main__':
    main()
