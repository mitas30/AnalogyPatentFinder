import re,os
import logging
from logging.handlers import RotatingFileHandler

class AnsiColorCodes:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class ColorFormatter(logging.Formatter):
    """カスタムログフォーマットを定義するクラス。ログレベルによって色を変える。"""
    def __init__(self, fmt):
        super().__init__(fmt)

    def format(self, record):
        color = ''
        if record.levelno == logging.ERROR:
            color = AnsiColorCodes.FAIL
        elif record.levelno == logging.WARNING:
            color = AnsiColorCodes.WARNING
        elif record.levelno == logging.INFO:
            color = AnsiColorCodes.OKGREEN
        elif record.levelno == logging.DEBUG:
            color = AnsiColorCodes.OKBLUE
        record.msg = f"{color}{record.msg}{AnsiColorCodes.ENDC}"
        return super().format(record)
    
class CleanFormatter(logging.Formatter):
    """ログからANSIカラーコードを除去するフォーマッタ。"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def format(self, record):
        original = super().format(record)
        return self.ansi_escape.sub('', original)

def setup_logging():
    """__summary__
    
    アプリケーションのログ設定を行う関数。
    
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  

    # コンソール出力用のハンドラー設定
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColorFormatter('%(levelname)s: %(message)s'))
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # ファイル出力用のハンドラー設定 
    log_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),'../log/app.log')
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    file_handler = RotatingFileHandler(log_path, maxBytes=1048576, backupCount=3,encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(CleanFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
