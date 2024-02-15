import requests
import sys
import urllib.parse
import asyncio
from functools import partial
import re
import argparse
from bs4 import BeautifulSoup
import logging
from aqt import mw
from anki.hooks import addHook
import time 
from aqt.utils import showInfo, qconnect
from aqt.qt import *
from aqt.qt import QAction


logging.basicConfig(filename='anki_addon.log', filemode='w', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class Token:
    """
    https://www.52pojie.cn/thread-707169-1-1.html
    https://www.jianshu.com/p/af74f0719267
    """

    def __init__(self, tkk):
        self.tkk = tkk

    def calculate_token(self, text):
        if self.tkk == "":
            """
            422392.71207223
            406644.3293161072
            431767.4042228602
            440498.1287591069
            """
            self.tkk = "440498.1287591069"
        [first_seed, second_seed] = self.tkk.split(".")

        try:
            d = bytearray(text.encode('UTF-8'))
        except UnicodeDecodeError:
            d = bytearray(text)

        a = int(first_seed)
        for value in d:
            a += value
            a = self._work_token(a, "+-a^+6")
        a = self._work_token(a, "+-3^+b+-f")
        a ^= int(second_seed)
        if 0 > a:
            a = (a & 2147483647) + 2147483648
        a %= 1E6
        a = int(a)
        return str(a) + "." + str(a ^ int(first_seed))

    @staticmethod
    def _rshift(val, n):
        return val >> n if val >= 0 else (val + 0x100000000) >> n

    def _work_token(self, a, seed):
        for i in range(0, len(seed) - 2, 3):
            char = seed[i + 2]
            d = ord(char[0]) - 87 if char >= "a" else int(char)
            d = self._rshift(a, d) if seed[i + 1] == "+" else a << d
            a = a + d & 4294967295 if seed[i] == "+" else a ^ d
        return a


class GoogleTranslate(object):
    def __init__(self, args):
        self.http_host = args.host
        self.http_proxy = args.proxy
        self.synonyms_en = args.synonyms
        self.definitions_en = args.definitions
        self.examples_en = args.examples
        self.result_code = 'utf-8' if args.type == 'html' else sys.stdout.encoding
        sys.stdout.reconfigure(encoding=self.result_code) if args.type == 'html' else None
        self.alternative_language = args.alternative
        self.result_type = args.type
        self.target_language = ''
        self.query_string = ''
        self.result = ''

    def get_url(self, tl, qry, tk):
        url = f'https://{self.http_host}/translate_a/single?client=gtx&sl=en&tl={tl}&hl=en&dt=at&dt=bd&dt=ex&' \
              f'dt=ld&dt=md&dt=qca&dt=rw&dt=rm&dt=sos&dt=ss&dt=t&ssel=0&tsel=0&kc=1&tk={tk}&q={qry}'
        return url

    def get_synonym(self, resp):
        if resp[1]:
            #self.result += '\n'
            #self.result += f'\n'
            for x in resp[1]:
                self.result += f'# {x[0][0]}.\n'
                for y in x[2]:
                    self.result += f'{y[0]}: {", ".join(y[1])}\n'

    def get_result(self, resp):
        for x in resp[0]:
            self.result += x[0] if x[0] else ''
        self.result += '\n'

    def get_definitions(self, resp):
        self.result += '\n'
        self.result += f'0_0: Definitions of {self.query_string}\n'
        for x in resp[12]:
            self.result += f'# {x[0] if x[0] else ""}.\n'
            for y in x[1]:
                self.result += f'  - {y[0]}\n'
                self.result += f'    * {y[2]}\n' if len(y) >= 3 else ''

    def get_examples(self, resp):
        self.result += '\n'
        self.result += f'0_0: Examples of {self.query_string}\n'
        for x in resp[13][0]:
            self.result += f'  * {x[0]}\n'

    def get_synonyms_en(self, resp):
        self.result += '\n'
        self.result += f'0_0: Synonyms of {self.query_string}\n'
        for idx, x in enumerate(resp[11]):
            self.result += f'# {x[0]}.\n'
            for y in x[1]:
                self.result += ', '.join(y[0]) + '\n'

    def get_resp(self, url):
        proxies = {
            'http': f'http://{self.http_proxy.strip() if self.http_proxy.strip() else "127.0.0.1:1080"}',
            'https': f'http://{self.http_proxy.strip() if self.http_proxy.strip() else "127.0.0.1:1080"}'
        }
        base_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:96.0) Gecko/20100101 Firefox/96.0'}
        session = requests.Session()
        session.headers = base_headers
        resp = session.get(url, proxies=proxies if self.http_proxy.strip() else None, timeout=5).json()
        return resp

    def result_to_html(self):
        css_text = """\
        <style type="text/css">
        p {white-space: pre-wrap;}
        pos {color: #0000FF;}
        example {color: #008080;}
        gray {color: #606060;}
        </style>"""
        self.result = re.sub(r'(?m)^(#.*)', r'<pos><b>\1</b></pos>', self.result)
        self.result = re.sub(r'(?m)^([*].*)', r'<example>\1</example>', self.result)
        self.result = re.sub(r'(?m)^(0_0:.*?of)(.*)', r'<gray>\1</gray>\2', self.result)
        match = re.compile(rf"(?m)^({re.escape('^_^')}: Translate)(.*)(To)(.*)")
        self.result = match.sub(r'<gray>\1</gray>\2<gray>\3</gray>\4', self.result)
        self.result = f'<html>\n<head>\n{css_text}\n</head>\n<body>\n<p>{self.result}</p>\n</body>\n</html>'

    async def get_translation(self, target_language, query_string, tkk=''):
        self.result = ''
        self.target_language = target_language
        self.query_string = query_string
        tk = Token(tkk).calculate_token(self.query_string)
        if len(self.query_string) > 5000:
            return '(╯‵□′)╯︵┻━┻: Maximum characters exceeded...'
        parse_query = urllib.parse.quote_plus(self.query_string)
        url = self.get_url(self.target_language, parse_query, tk)
        url_alt = self.get_url(self.alternative_language, parse_query, tk)
        try:
            loop = asyncio.get_running_loop()
            resp = loop.run_in_executor(None, partial(self.get_resp, url))
            resp_alt = loop.run_in_executor(None, partial(self.get_resp, url_alt))
            [resp, resp_alt] = await asyncio.gather(resp, resp_alt)
            if resp[2] == self.target_language:
                self.result += f'{resp[2]} To {self.alternative_language}\n'
                self.get_result(resp)
                self.result += '---------\n'
                self.get_result(resp_alt)
                self.get_synonym(resp_alt)
            else:
                self.result += f'{self.query_string}\n---------\n'
                self.get_result(resp)
                self.get_synonym(resp)
            if self.synonyms_en and len(resp) >= 12 and resp[11]:
                self.get_synonyms_en(resp)
            if self.definitions_en and len(resp) >= 13 and resp[12]:
                self.get_definitions(resp)
            if self.examples_en and len(resp) >= 14 and resp[13]:
                self.get_examples(resp)
            if self.result_type == 'html':
                self.result_to_html()
            else:
                self.result = self.result.replace('<b>', '').replace('</b>', '')
            return self.result.encode(self.result_code, 'ignore').decode(self.result_code)
        except requests.exceptions.ReadTimeout:
            return '╰（‵□′）╯: ReadTimeout...'
        except requests.exceptions.ProxyError:
            return '(╯‵□′)╯︵┻━┻: ProxyError...'
        except Exception as e:
            return f'Errrrrrrrrror: {e}'



def translate_word(word):
    url = f"http://tahlilgaran.org/TDictionary/WebApp/?q={word}"
    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        translation_div = soup.find('div', class_='p-fa')
        if translation_div:
            return translation_div.get_text(strip=True)
        else:
            return "."
    else:
        return ".."




def get_args(target='fa', query='', host='translate.googleapis.com', proxy='', alternative='en', result_type='html', tkk='', synonyms=False, definitions=False, examples=False):
    args = argparse.Namespace()
    args.target = target
    args.query = query
    args.host = host
    args.proxy = proxy
    args.alternative = alternative
    args.type = result_type
    args.tkk = tkk
    args.synonyms = synonyms
    args.definitions = definitions
    args.examples = examples
    return args


async def translate_async(word, target_language='fa'):
    # Assuming GoogleTranslate and get_args are defined elsewhere
    args = get_args(query=word, target=target_language)
    g_trans = GoogleTranslate(args)
    trans = await g_trans.get_translation(target_language, word, tkk=args.tkk)
    return trans

async def translate_word_async(word):
    # Assuming translate_word is an existing synchronous function
    from_google_task = asyncio.create_task(translate_async(word))
    from_google = await from_google_task
    translation = translate_word(word)  # Synchronous translation function
    return f'\n{from_google}......\n{translation}'

def apply_translation_to_deck(deck_name, source_field, target_field):
    deck_id = mw.col.decks.id(deck_name)
    mw.col.decks.select(deck_id)
    
    for cid in mw.col.find_cards(f'"deck:{deck_name}"'):
        card = mw.col.get_card(cid)
        note = card.note()
        
        if source_field in note and target_field in note:
            source_text = note[source_field]
            
            if not '---------' in note[target_field]:
                # Execute asynchronous translation
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(translate_word_async(source_text))
                time.sleep(2)  # Consider removing or adjusting this based on actual requirements
                note[target_field] = f"{note[target_field]} {result}"  
                note.flush()
                #showInfo(f"source_text: {source_text}")
                
    showInfo(f"Processed deck: {deck_name}")

def test_function():
    card_count = mw.col.cardCount()
    showInfo(f"Card count: {card_count}")
    try:
        apply_translation_to_deck("1212 - 3rd edition TOEFL Vocab for Hardworkers", "Word", "Persian")
    except Exception as e:
        showInfo(f"Exception during translation: {e}")

# Add menu item to Anki
def add_menu_item():
    action = QAction("Persian Translate google+tahlilgaran", mw)
    qconnect(action.triggered, test_function)
    mw.form.menuTools.addAction(action)

add_menu_item()



