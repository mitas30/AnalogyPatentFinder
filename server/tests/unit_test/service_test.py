import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tools.operations import pdfDataProcessor,fineTuning,expOperator,patentProcessor
from tools import operations as service

logger = logging.getLogger(__name__)
    
def test_format_one_patent():
    # 相対パスをテストスクリプトのディレクトリからの相対パスに変換
    test_file_dir = os.path.dirname(__file__)
    test_file_path = os.path.join(test_file_dir,'../../data/test_data','2023168635.pdf') 
    pdf_processor=pdfDataProcessor(test_file_path)
    pdf_processor.extract_one_patent(is_test=True)
    
def test_format_patent_datas():
    """_summary_ 
    \nテスト特許データをDBに書き込む。
    """
    # 相対パスをテストスクリプトのディレクトリからの相対パスに変換
    current_dir = os.path.dirname(__file__)
    test_folder_path = os.path.join(current_dir,'../../data/test_data/P_A1') 
    pdf_processor=pdfDataProcessor(test_folder_path)
    pdf_processor.batch_extract_patent_datas(is_test=True)  

def check_duplicate_patent():
    service.remove_all_documents_with_same_invent_name_and_problem()
    
def aggregate_function_classes():
    """ _summary_ 
    \n抽象的な機能ごとの特許数を集計する
    """
    operator =service.expOperator()
    logger.log(logging.INFO, "[抽象的な機能:一致特許数]")
    operator.aggr_classified_function_classes()
    
def test_uncategorized_function_classes(max_doc: int = 10):
    """未分類のfunction_classesをDBから取得し、処理する
    function_classesの機能が正しく動作しているかを確認するためのテスト
    """
    pp = patentProcessor()
    logger.log(logging.INFO, f"未分類のfunction_classesを持つ特許を{max_doc}件取得")
    pp.categorize_functions(max_doc, is_process=False)
    logger.log(logging.INFO, "\n")
    
def test_check_poffice_api(max_doc:int=1):
    """_summary_ 特許庁APIと正常に通信しているか確認 毎回やってもいいテスト

    Args:
        max_doc (int, optional): _description_. Defaults to 1.
    """
    logger.log(logging.INFO,"[特許庁APIと正常に通信しているか確認]")
    service.update_documents_with_full_url(max_doc=max_doc,is_write=True)
    
def show_not_headding(max_doc:int=10):
    """_summary_ 未分類の特許を表示する
    """
    pp=patentProcessor()
    logger.log(logging.INFO, f"headdingの無い特許を{max_doc}件取得")
    pp.add_heading(max_doc,is_process=False)
    logger.log(logging.INFO, "\n") 
