from __future__ import annotations

from tools._bootstrap import activate_server_context

activate_server_context()

import json,logging,os,shutil,re,datetime,time
from bson.objectid import ObjectId
from typing import Any,Literal,Tuple
from models.model import patentManager,patentQuery,patentBulkUpdater,patentCleaner,abstractAdmin

Document = Any

logger = logging.getLogger(__name__)

class SplitError(Exception):
    """特定の分割操作で期待される条件を満たさない場合に発生する例外"""
    pass

class pdfDataProcessor:
    """
    PDFデータを抽出、加工するクラス。\n
    DBとのインタラクションも含む。
    """

    # *与えられるフォルダパスは、絶対パスであることが期待される
    def __init__(self, fetch_folder_path:str, processed_folder_path:str=None):
        # フォルダが存在しない場合に作成
        if not os.path.exists(fetch_folder_path):
            os.makedirs(fetch_folder_path)
        if processed_folder_path!=None and not os.path.exists(processed_folder_path):
            os.makedirs(processed_folder_path)

        self.fetch_folder_path = fetch_folder_path
        self.processed_folder_path = processed_folder_path
        self.patentmanip = patentManager(collection_name="patents")
        self.SUCCESS = 0
        self.ERROR_IN_ABSTRACT = -1
        self.ERROR_IN_DETAIL = -2
        self.ERROR_IN_OTHER = -3
        
    def getFolderPath(self, result_code):
        """
        処理結果コードに基づき、対応するフォルダのパスを返す。

        Parameters:
        result_code (int): 処理結果を表すコード。成功の場合は0、エラーの場合はエラーコード。

        Returns:
        str: 対応するフォルダのパス。
        """
        if result_code == 0:
            folder_name = "Processed"
        elif result_code == self.ERROR_IN_ABSTRACT:
            folder_name = "AboutAbstract"
        elif result_code == self.ERROR_IN_DETAIL:
            folder_name = "AboutDetail"
        else:
            folder_name = "Others"

        target_folder = os.path.join(self.processed_folder_path, folder_name)
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
        return target_folder
    
    def batch_extract_patent_datas(self, keep_processed_files: bool=True, is_test: bool = False):
        """
        指定されたフォルダ(self.fetch_folder_path)内に存在する全てのPDFファイルから特許データを抽出し、データベースに格納するバッチ処理を行う。
        抽出やデータベース格納に失敗した場合、ファイルは例外フォルダに移動される。

        Parameters:
        keep_processed_files (bool): 処理したPDFを残すかどうかを指定するフラグ。
        """
        if keep_processed_files==True and is_test==False and self.processed_folder_path==None:
            logger.log(logging.ERROR, "keep_processed_filesがTrueの場合、processed_folder_pathを指定してください")
            return
        if is_test==False:
            logger.log(logging.INFO, "Batch[データベースへの格納] start")
        self._make_flat(self.fetch_folder_path)
        error_count = 0
        count = 0

        for filename in os.listdir(self.fetch_folder_path):
            file_path = os.path.join(self.fetch_folder_path, filename)
            if os.path.isfile(file_path):
                res_code = self.extract_one_patent(file_path,is_test=is_test)
                if is_test:
                    continue
                if res_code == self.SUCCESS:
                    if keep_processed_files:
                        success_folder = self.getFolderPath(result_code=res_code)
                        shutil.move(file_path, os.path.join(success_folder, filename))
                    else:
                        os.remove(file_path)
                    count += 1
                else:
                    logger.log(logging.ERROR, f"正常でないpdfファイル: {file_path}")
                    error_folder = self.getFolderPath(result_code=res_code)
                    shutil.move(file_path, os.path.join(error_folder, filename))
                    error_count += 1
            if count%100==0 and is_test==False:
                logger.log(logging.INFO, f"Batch[データベースへの格納] is in progress. count={count}, error_count={error_count}")

        if is_test==False:
            logger.log(logging.INFO, f"Batch[データベースへの格納] complete count={count}, error_count={error_count}")

    #TODO 現在はSplitErrorのみを返すが、どこが原因なのかを返すようにする
    def extract_one_patent(self,file_path:str,is_test:bool=False)->int:
        """ 1つのPDFから情報を取り出す関数。
            結果に応じたコードを返す
        """
        # 相対パスを絶対パスに変換
        file_path = os.path.abspath(file_path)
        
        try:
            extract_data=self._extract_needed_data(file_path)
            if extract_data=={}:
                return self.ERROR_IN_ABSTRACT
            if is_test:
                '''
                for key, value in extract_data.items():
                    if isinstance(value, str):
                        logger.log(logging.INFO,f"{key}: {value[:30]}")
                    else:
                        logger.log(logging.INFO,f"{key}: {value}")
                '''
                return self.SUCCESS
            else:
                result=self.patentmanip.add_patent_data(extract_data)
                if result==0:
                    return self.SUCCESS
        except SplitError as e:
            logger.log(logging.WARNING,f"{e}")
            return self.ERROR_IN_ABSTRACT

    def _slice_patent_section(self,pdf_document:Document,pattern:str,sub_pattern:str)->str:
        """
        [pattern]より上の部分を切り出して、stringで返す。
        ただし、これが無いものは例外として扱う
        また、patternはraw文字列であることが期待される
        """
        #step1 patternのあるページまで切り出す
        target_page=""
        ret_str=""
        is_find=False
        for page in pdf_document:
            target_page+=page.get_text("text")
            areas = page.search_for(pattern)
            if areas !=[]:
                is_find=True
                break
        #特許請求の範囲がない場合
        if is_find==False:
            is_find=True
            target_page=""
            is_find=False
            for page in pdf_document:
                target_page+=page.get_text("text")
                areas = page.search_for(sub_pattern)
                if areas !=[]:
                    is_find=True
                    break
            if is_find==False:
                raise SplitError(f"特許文書に{pattern}も{sub_pattern}も存在しない")
            else:
                ret_str=re.split(sub_pattern,target_page)[0]
        #step2 patternより上の、最初の連続部分文字列を返す
        else:
            ret_str=re.split(pattern,target_page)[0]
        return ret_str
    
    def _extract_needed_data(self,file_path:str)->dict:
        """
        1つの公開特許広報から特定の情報を抽出する。
        公表特許公報(グローバルな出願)は、フォーマットが異なるため、使えない。
        Parameters:
        file_path (str): 抽出するファイルのpath

        成功した場合は、抽出データのmapを返す。
        どこかで失敗した場合は、SplitErrorを返す
        """
        try:
            import fitz
        except ModuleNotFoundError as e:
            raise RuntimeError("PyMuPDF is required for patent PDF import. Install server/requirements.txt.") from e
        pdf_doc=fitz.open(file_path)
        doc_description=self._slice_patent_section(pdf_doc,r"【発明の効果】",r"【図面の簡単な説明】")
        overview_or_detail=re.split(r"【\s*発明の詳細な説明\s*】.*\n",doc_description)
        if len(overview_or_detail)!=2:
            raise SplitError("【発明の詳細な説明】という項目が存在しない")
        overview=re.split(r"【\s*選択図\s*】.*\n",overview_or_detail[0])[0]
        overview_info=self._split_overview(overview,file_path)
        detail_info=self._split_detail(overview_or_detail[1])
        return overview_info |detail_info

    def _split_overview(self,overview:str,file_path:str)->map:
        info_dict={}
        basicinfo_or_abstract=re.split(r"【\s*要\s*約\s*】.*\n",overview)
        if len(basicinfo_or_abstract)!=2:
            raise SplitError("【要約】が存在しない")
        basic_info=basicinfo_or_abstract[0]
        abstract=re.sub(r"\n","",basicinfo_or_abstract[1])
        #*【選択図】があるが、要約から離れた位置に存在している場合、または[化*]が存在するときlen(m)!=2
        #* ただし、これらの例外は13/3050
        #* 【が2つのときも、[効果]や[構成]のようなときがあるが、この例外も7/3050
        #* 問題を分解する教師あり分類器の都合上、課題と解決手段が存在している特許だけを受け付ける
        #2-2 要約を課題と手段に分ける 
        split_list=re.split(r"【\w*課題】|【\w*手段】",abstract)
        if(len(split_list)!=3):
            raise SplitError(f"要約が課題と手段に分かれていない split_len={str(len(split_list))}")
        info_dict['problem']=split_list[1]
        info_dict['solve_way']=split_list[2]
        #step3 step1のstringから基本的な特許情報を抽出する
        basic_info_list=re.split("【発明の名称】|Int\.Cl.+\n",basic_info)
        if(len(basic_info_list)!=3):
            logger.log(logging.DEBUG,f"{str(len(split_list))}\nfile_path={file_path}")
        info_dict['invent_name']=re.match(".+",basic_info_list[2]).group()
        #3-1 出願番号を取得する
        if extracted_number:=re.search(r'特願(\d{4})-(\d+)',basic_info_list[1]):
            year = extracted_number.group(1)
            number = int(extracted_number.group(2))
            info_dict['apply_number'] = f"{year}{number:06}"
        else:
            raise SplitError("出願番号が存在しない") 
        #3-2 IPC class_listを取得する
        ipc_class_str=re.split("\nＦＩ",basic_info_list[1])[0]
        info_dict['ipc_class_code_list']=self._convertClassStrToList(ipc_class_str)
        #3-3 出願日を取得する(Date型で格納する)
        if date_list:=re.search(r"\(22\)[^\(]+\((\d+)\.(\d+)\.(\d+)\)\n",basic_info_list[1]):
            info_dict['apply_date']=datetime.datetime(int(date_list.group(1)),int(date_list.group(2)),int(date_list.group(3)))
        else:
            raise SplitError("出願日が存在しない") 
        return info_dict
    
    def _split_detail(self,detail:str)->map:
        """_summary_ 特許の詳細な説明から、課題と解決手段の詳細を取り出す

        Args:
            detail (str): _description_

        Raises:
            SplitError: _description_

        Returns:
            map: _description_
        """
        info_dict={}
        exception_f=False
        tmp_list=re.split(r"\s*【発明が解決しようとする課題】\s*",detail)
        if len(tmp_list)!=2:
            tmp_list=re.split(r"\s*【発明の概要】\s*",detail)
            m=re.search(r"\s*【課題を解決するための手段】\s*",detail)
            if len(tmp_list)!=2 or m==None:
                raise SplitError("【発明が解決しようとする課題】も【課題を解決するための手段】も存在しない")
            else:
                exception_f=True
        detail=tmp_list[1]
        detail,cnt1=re.subn(r"【\d+】\n","",detail)
        detail,cnt2=re.subn(r"10\n20\n30\n40\n50\n","",detail)
        detail,cnt3=re.subn(r"\(\d+\)\n.+\n","",detail)
        detail_list=re.split(r"\s*【課題を解決するための手段】\s*",detail)
        #logger.log(logging.INFO,f"cnt1:{cnt1} cnt2:{cnt2} cnt3:{cnt3}")
        if len(detail_list)!=2:
            raise SplitError("【課題を解決するための手段】が存在しない")
        info_dict['detail_problem']=detail_list[0]
        info_dict['detail_solve_way']=detail_list[1]
        if exception_f==True:
            info_dict['detail_problem']=""
        return info_dict

    def _convertClassStrToList(self,ipc_class_str)->list[str]:
        """class_strから、単一のキーワードのリストに変換する"""
        class_list=[]
        raw_class_list=re.split("\n",ipc_class_str)
        for raw_keycode in raw_class_list:
            keycode=re.sub("\s+\(.+\)","",raw_keycode)
            class_list.append(keycode)
        return class_list
    
    def _make_flat(self, folder_path: str):
        """
        指定されたフォルダ内のすべてのファイルをフォルダのトップレベルに移動し、
        空になったサブディレクトリを削除する。

        この関数は、指定されたディレクトリ内のファイルをフラットに整理することで、
        ディレクトリ構造を単純化します。同名のファイルが存在する場合、上書きされるリスクがあるため、
        事前に適切なファイル名の管理が必要です。

        Parameters:
            folder_path (str): ファイルをフラットに整理するディレクトリのパス。
        """
        # 指定されたフォルダパス内を再帰的に探索（ボトムアップ）
        for dirpath, dirnames, filenames in os.walk(folder_path, topdown=False):
            for filename in filenames:
                source_path = os.path.join(dirpath, filename)
                destination_path = os.path.join(folder_path, filename)
                # ファイル名の衝突をチェック
                if os.path.exists(destination_path):
                    continue  # 同名ファイルが存在する場合はスキップ
                # ファイルを移動
                shutil.move(source_path, destination_path)
                
            # ディレクトリが空になっているかチェックし、空であれば削除
            if not os.listdir(dirpath) and dirpath != folder_path:
                os.rmdir(dirpath)

#TODO 明確な役割によるクラスの再構成
class gptClient:
    '''
    GPTを使ったメソッド集合のクラス。このクラスには、GPTを使う小さな部分関数のみを記述すること。
    '''
    def __init__(self):
        from openai import OpenAI

        self.openai_api_key = self._load_api_key()
        self.client=OpenAI(api_key=self.openai_api_key)
        self.current_model="gpt-4o"
        
    def _load_api_key(self)->str:
        # JSON設定ファイルを開いて読み込む
        #ファイルのパスは、実行ファイルからの相対パス
        with open('config/config.json', 'r') as file:
            config = json.load(file)
        return config['OPENAI_API_KEY']
    
    #TODO jsonl_filenameがfileの相対パスを指すように、fine-tuningでも変更する
    def upload_file(self,jsonl_filename:str,purpose:str)->str:
        """_summary_  batch処理用のファイルjsonl_filename.jsonlをopenaiにアップロードする

        Args:
            jsonl_fileplace (str): batch処理用のjsonlファイルの名前 場所は必要ない
            例えば、jsonl_fileplace="input"の場合、../data/openai_batch/input/input.jsonlをアップロードする
            purpose: batch処理の目的を指定する(openAI側の引数) batch or fine-tune

        Returns:
            str: file_id(各処理で指定することになるファイルのid)
        """
        file_path="../data"
        if purpose=="batch":
            file_path=jsonl_filename
        elif purpose=="fine-tune":
            file_path+="/fine-tuning/"+jsonl_filename+".jsonl"
        else:
            logger.log(logging.ERROR,"purposeが不正です")
            return ""
        response = self.client.files.create(
        file=open(file_path, "rb"),
        purpose=purpose
        )
        batchfile_id=response.id
        logger.log(logging.INFO,f"id:{batchfile_id} filesize:{response.bytes}Byte ")
        return batchfile_id
    
    #TODO 抽象化関数の形式に合わせる
    #TODO すべて同じ関数として扱うことができる(行うかは不明)
    #* divide_problems関数は現在使われていない
    def divide_problems(self,problem_list:list[dict],is_collect:bool)->dict[list[str]]:
        ''' summary:\n
            problem_list(10の特許がlistにされている)のproblemは、複数の目的(問題)を述べている可能性がある。\n
            したがって、これを単一のspanに分解する。\n
            is_collectがtrueになっている場合は、会話データを収集する
        '''
        with open('llm_prompt/dismantle.json', 'r', encoding='utf-8') as file:
            #.jsonでは、1つのobjectしか定義できない
            # loadによって、jsonファイルをpythonのデータに変更できる
            data = json.load(file)
        # 特定のキーに対応するデータを取得
        system_message = data.get('system_message')
        user_message = data.get('user')
        example_message = data.get('example')
        model=""
        if is_collect==True:
            model=self.current_model
        else:
            model="ft:gpt-3.5-turbo-0125:personal::9LrSN0B4"
        messages=[
            {"role": "system","content":system_message},
            {"role": "user","content":f"{user_message}\n{example_message}\n<problem>\n{problem_list}"}
        ]
        st=time.time()
        response=self.client.chat.completions.create(model=model,response_format={ "type": "json_object" },messages=messages)
        return_message=json.loads(response.choices[0].message.content)
        logger.log(logging.INFO,f"process_time:{time.time()-st:.2f}s input_token:{response.usage.prompt_tokens} output_token:{response.usage.completion_tokens} model:{response.model}")
        if is_collect==True:
            #jsonl形式に沿うように変換する
            with open('../data/fine-tuning/function1.jsonl',"a",encoding='utf_8') as f:
                insert_json_object={}
                system_obj={"role":"system","content":system_message}
                user_obj={"role":"user","content":f"{user_message}\n{example_message}\n<problem>\n{problem_list}"}
                assistant_obj={"role":"assistant","content":str(return_message)}
                insert_json_object["messages"]=system_obj,user_obj,assistant_obj                
                f.write(json.dumps(insert_json_object,ensure_ascii=False)+'\n')
        return return_message
    
    def annotate_improvement_parameters_from_patent(self, patent_data:list[dict],is_collect:bool)->dict:
        """_summary_
        \n特許データから、向上するパラメータとその対象を抽出する。
        \n1回で15個の特許データを処理する。

        Args:
            patent_data (_type_): _description_

        Returns:
            _type_: _description_
        """
        with open('llm_prompt/extract_parameter.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            
        system_message_template = data.get('system_message_template')
        persona = data.get('persona')
        instruction = data.get('instruction')
        output_format = data.get('output_format')
        user_message_template = data.get('user_message_template')
        example = data.get('example')
        input_prefix = data.get('input_prefix')
        input_details = "\n".join([f"{i+1}\n{d['invent_name']}\n{d['problem']}" for i, d in enumerate(patent_data)])
        system_message = system_message_template.format(persona=persona, instruction=instruction, output_format=output_format)
        user_message = user_message_template.format(example=example, input_prefix=input_prefix, input=input_details)
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        logger.log(logging.INFO,user_message)
        st=time.time()
        response=self.client.chat.completions.create(model=self.current_model,response_format={ "type": "json_object" },messages=messages)
        logger.log(logging.INFO,f"process_time:{time.time()-st:.2f}s input_token:{response.usage.prompt_tokens} output_token:{response.usage.completion_tokens} model:{response.model}")
        return_message=json.loads(response.choices[0].message.content)
        if is_collect==True:
            timestamp=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(f'../data/fine-tuning/annotate_{timestamp}.jsonl', "a", encoding='utf_8') as f:
                insert_json_object = {}
                system_obj = {"role": "system", "content": system_message}
                user_obj = {"role": "user", "content": user_message}
                assistant_obj = {"role": "assistant", "content": str(return_message)}
                insert_json_object["messages"] = system_obj, user_obj, assistant_obj
                f.write(json.dumps(insert_json_object, ensure_ascii=False) + '\n')
        return return_message
    
    def categorize_functions(self, concrete_functions:list[dict],is_collect:bool)->dict[str,list[dict[str,str]]]:
        """_summary_\n
        機能データを抽象化して45のクラスのいずれかに分類する。\n
        1回で50個の機能データを処理する。

        Args:
            patent_data (_type_): _description_

        Returns:
            _type_: _description_
        """
        with open('llm_prompt/categorize_functions.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
            
        system_message_template = data.get('system_message_template')
        persona = data.get('persona')
        instruction = data.get('instruction')
        output_format = data.get('output_format')
        user_message_template = data.get('user_message_template')
        example = data.get('example')
        input_prefix = data.get('input_prefix')
        input_details = "\n".join([f"{i+1}.{function['object']}" for i, function in enumerate(concrete_functions)])
        system_message = system_message_template.format(persona=persona, instruction=instruction, output_format=output_format)
        user_message = user_message_template.format(example=example, input_prefix=input_prefix, input=input_details)
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        logger.log(logging.INFO,user_message)
        st=time.time()
        response=self.client.chat.completions.create(model=self.current_model,response_format={ "type": "json_object" },messages=messages)
        logger.log(logging.INFO,f"process_time:{time.time()-st:.2f}s input_token:{response.usage.prompt_tokens} output_token:{response.usage.completion_tokens} model:{response.model}")
        return_message=json.loads(response.choices[0].message.content)
        if is_collect==True:
            timestamp=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(f'../data/fine-tuning/annotate_{timestamp}.jsonl', "a", encoding='utf_8') as f:
                insert_json_object = {}
                system_obj = {"role": "system", "content": system_message}
                user_obj = {"role": "user", "content": user_message}
                assistant_obj = {"role": "assistant", "content": str(return_message)}
                insert_json_object["messages"] = system_obj, user_obj, assistant_obj
                f.write(json.dumps(insert_json_object, ensure_ascii=False) + '\n')
        return return_message

    def add_heading(self, patent_data: list[dict], is_collect: bool) -> dict[str, list[dict[str, str]]]:
        """_summary_
        \n特許がパラメータAを向上させた方法について、解決方法を抜き出し、わかりやすい言葉に変換する。
        1回で15個の特許データを処理する。ただし、パラメータ1つごとに1つの特許データとして扱う。

        Args:
            patent_data (list[dict]): 加工に使用する特許データ
            is_collect (bool): fine-tuningのデータとして収集するかどうか

        Returns:
            dict[str, list[dict[str, str]]]: _description_
        """
        with open('llm_prompt/add_heading.json', 'r', encoding='utf-8') as file:
            data = json.load(file)

        system_message_template = data.get('system_message_template')
        persona = data.get('persona')
        instruction = data.get('instruction')
        output_format = data.get('output_format')
        user_message_template = data.get('user_message_template')
        example = data.get('example')
        input_prefix = data.get('input_prefix')
        input_details = "\n".join([f"{i+1}.\napply_num:{d['apply_num']}\nobject:{d['object']}\nparameter:{d['parameter']}\nparam_explanation:{d['param_explanation']}\nsolve_way:{d['solve_way']}" for i, d in enumerate(patent_data)])
        system_message = system_message_template.format(persona=persona, instruction=instruction, output_format=output_format)
        user_message = user_message_template.format(example=example, input_prefix=input_prefix, input=input_details)
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        logging.debug(system_message)
        logging.debug(user_message)
        st = time.time()
        response = self.client.chat.completions.create(model=self.current_model, response_format={"type": "json_object"}, messages=messages)
        logger.log(logging.INFO, f"process_time:{time.time() - st:.2f}s input_token:{response.usage.prompt_tokens} output_token:{response.usage.completion_tokens} model:{response.model}")
        return_message = json.loads(response.choices[0].message.content)
        if is_collect:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(f'../data/fine-tuning/heading_{timestamp}.jsonl', "a", encoding='utf_8') as f:
                insert_json_object = {}
                system_obj = {"role": "system", "content": system_message}
                user_obj = {"role": "user", "content": user_message}
                assistant_obj = {"role": "assistant", "content": str(return_message)}
                insert_json_object["messages"] = system_obj, user_obj, assistant_obj
                f.write(json.dumps(insert_json_object, ensure_ascii=False) + '\n')
        return return_message

class patentProcessor:
    def __init__(self):
        self.db_query = patentQuery(collection_name="patents")
        self.db_updater = patentBulkUpdater(collection_name="patents")
        self.gpt_client = None
        self.config = self._load_process_config()
        
    def _load_process_config(self):
        config_file_path = 'config/process_config.json'
        with open(config_file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
        
    def make_span_problems_list(self,max_doc=None,is_write=True,is_collect=False,is_process=True):
        self._process_documents("dismantle_problem", max_doc,is_write,is_collect,is_process)

    def create_and_store_improvement_parameters(self,max_doc=None,is_write=True,is_collect=False,is_process=True):
        self._process_documents("annotate_improvement_parameters", max_doc, is_write,is_collect,is_process)
        
    def categorize_functions(self,max_doc=None,is_write=True,is_collect=False,is_process=True):
        self._process_documents("categorize_functions", max_doc, is_write,is_collect,is_process)
                
    def add_heading(self,max_doc=None,is_write=True,is_collect=False,is_process=True):
        self._process_documents("add_heading", max_doc, is_write,is_collect,is_process)
                
    # ?これなんで必要なんだっけ?
    def _prepare_data(self, part_doc_list, config):
        """_summary_ 
        \n各プロセス固有のデータを準備する。
        \nバッチ処理におけるgptBatch._process_documents()に相当する。

        Args:
            part_doc_list (_type_): _description_
            config (_type_): _description_

        Returns:
            _type_: _description_
        """
        # 各プロセス固有のデータ準備
        if config['prefix'] == 'dismantle':
            return [{"problem":d["problem"]} for d in part_doc_list]
        elif config['prefix'] == 'annotate':
            return [{"invent_name":d["invent_name"], "problem":d["problem"]} for d in part_doc_list]
        elif config['prefix'] == 'categorize':
            return [{"object":d["object"]} for d in part_doc_list]
        elif config['prefix'] == 'add_heading':
            return [{"apply_num":d["apply_number"],"object":d["object"],"parameter":d["parameter"],"param_explanation":d["param_explanation"],"solve_way":d["solve_way"]} for d in part_doc_list]

    def _process_documents(self, process_type, max_doc=100,is_write=True,is_collect=False,is_process=False):
        """ GPTのAPIを呼び出す形で、mongoDBのデータを加工する

        Args:
            process_type (_type_): annotate_improvement_parameters or dismantle_problem or categorize_functions
            max_doc (_type_, optional): 加工する文書の最大数. Defaults to None.
            is_write (bool, optional): データをDBに書き込むかどうか. Defaults to True.
            is_collect (bool, optional): fine-tuning用のデータを作成するかどうか. Defaults to False.
        """
        config = self.config[process_type]

        # ドキュメントの取得
        fetch_function = getattr(self.db_query, config['get_documents_func'])
        doc_list = fetch_function(max_doc)
        doc_num = len(doc_list)
        chunk_size = config['chunk_size']

        for i in range((doc_num + chunk_size - 1) // chunk_size):
            part_doc_list = doc_list[chunk_size * i: min(chunk_size * (i + 1), doc_num)]
            id_list = [d["id"] for d in part_doc_list]
            processing_data = self._prepare_data(part_doc_list, config)

            if is_process:
                if self.gpt_client is None:
                    self.gpt_client = gptClient()
                # GPTによる処理
                gpt_function = getattr(self.gpt_client, config['gpt_function'])
                output_data = gpt_function(processing_data, is_collect)
            else:
                for idx, data in enumerate(processing_data):
                    info=f"{idx+1}."
                    for k,v in data.items():
                        info+=f"\n{k}:{v}"
                    logger.log(logging.INFO,info)
                continue
            
            logger.log(logging.DEBUG, f"[{process_type}:{i+1}回目の出力]\n{output_data}")
            if is_write:
                w_cnt=self._write_to_db(id_list, output_data, config)
                logger.log(logging.INFO, f"{process_type}: Updated {w_cnt} documents")
        
    def _write_to_db(self, id_list, output_data, config)->int:
        # DBに書き込み
        update_function = getattr(self.db_updater, config['update_function'])
        w_cnt=update_function(id_list, output_data)
        return w_cnt

class gptBatch:
    '''
    GPTを使ったbatch処理のクラス
    主に、OpenAIにbatch処理を依頼する関数と、batch処理の結果を取得して、加工、DBに挿入する処理などを担当する
    '''
    def __init__(self):
        from openai import OpenAI

        self.openai_api_key = self._load_api_key()
        self.using_model=self._load_using_model()
        self.client=OpenAI(api_key=self.openai_api_key)
        self.db_query=patentQuery(collection_name="patents")
        self.db_updater=patentBulkUpdater(collection_name="patents")
        self.gpt_manip = gptClient()
        self.fine_tuner = fineTuning()
        
    def _load_api_key(self)->str:
        # JSON設定ファイルを開いて読み込む
        #ファイルのパスは、実行ファイルからの相対パス
        with open('config/config.json', 'r') as file:
            config = json.load(file)
        return config['OPENAI_API_KEY']
    
    def _load_using_model(self)->str:
        with open('config/config.json', 'r') as file:
            config = json.load(file)
            return config['USE_GPT_MODEL']    

    def _load_prompt(self, filepath)->dict:
        """
        プロンプトファイルを読み込む

        Args:
            filepath: プロンプトファイルのパス

        Returns:
            プロンプトデータの辞書
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                logger.log(logging.INFO,f"Loading prompt file from {filepath}")
                return json.load(file)
        except Exception as e:
            logger.log(logging.ERROR,f"Error loading prompt file {filepath}: {e}")
            raise
    
    #* バッチ処理を追加するごとに、この関数を少し変更する必要がある
    def batch_process(self, process_type: Literal['annotate_improvement_parameters','categorize_functions','add_heading'], 
                      max_doc=None, finetuning_model=None):
        """
        _summary_
        \n一般的なバッチ処理関数(外から呼び出すのはこの関数)
        \nバッチ処理のリクエストまで行ってくれる。
        \nバッチ処理が完了したら、ask_batch_resultで結果を取得すること。

        Args:
            \nprocess_type (str): バッチ処理のタイプ。次のいずれかを指定します。 #* バッチ処理を追加するごとに、Literalを追加しよう
                \n- 'dismantle_problem' #! 廃止
                \n- 'annotate_improvement_parameters'
                \n- 'categorize_functions'
                \n- 'add_heading'
            \nmax_doc (option): 処理する文書の最大数。Noneの場合は全ての文書を処理する。
            \nfinetuning_model (option): fine-tuningモデルを使用したい場合。Noneの場合はデフォルトのモデルを使用する。
        """
        try:
            config = self._get_process_config(process_type)
            fetch_funtion=getattr(self.db_query,config['get_documents_func'],None)
            if fetch_funtion is None:
                raise ValueError(f"Unknown fetch_function: {config['get_documents_func']}")            
            doc_list = fetch_funtion(max_doc)
            prompt_data = self._load_prompt(config['prompt_filepath'])

            chunks, id_memo = self._process_input(doc_list, config['chunk_size'],process_type)
            jsonl_data = self._create_jsonl_data(prompt_data, chunks, finetuning_model)
            jsonl_filepath = self._save_batch_files(config['prefix'], id_memo, jsonl_data, chunks  if config['save_additional_data'] else None)

            batchfile_id = self.gpt_manip.upload_file(jsonl_filepath, "batch")
            self._make_batch_request(batchfile_id)
            logger.log(logging.INFO, f"Batch processing for {process_type} submitted.")
        except Exception as e:
            logger.log(logging.ERROR, f"Error in batch processing for {process_type}: {e}")
            raise

    def ask_batch_result(self,batch_id:str)->bool:
        """_summary_  batch_idを使って、batch処理の結果を取得する。 
        \nbatchが完了している場合は、output.jsonlに結果が書き込まれる。
        \nDBに結果を挿入したい場合には、write_batch_result_to_databaseを呼び出すこと。

        Args:
             (str): get_batch_output_file_idで取得したoutput_file_id

        Returns:
            bool: batch処理が完了したかどうか
        """
        status=self._check_batch_status(batch_id)
        if status=="completed":
            output_file_id=self._fetch_batch_output_file_id(batch_id)
            self._fetch_batch_result(output_file_id)
            return True
        else:
            logger.log(logging.INFO,f"status:{status}")
            return False

    def write_batch_result_to_database(self, id_memo_fileplace: str, output_fileplace: str,
                                       process_type:Literal['annotate_improvement_parameters','categorize_functions','add_heading'], 
                                       is_write:bool=True,is_collect: bool = False, problems_fileplace: str = ""):
        """_summary_
        \nバッチ処理結果をデータベースに書き込み、必要に応じてファインチューニング用データを生成する
        
        Args:
            \nid_memo_fileplace : batchで処理したデータのobjectIDを保管するjsonファイル名 ファイル名だけでいい
            \noutput_fileplace : batchで処理したoutputを保管するjsonlファイル名 ファイル名だけでいい
            \nprocess_type: バッチ処理のタイプ。
            \nis_write(bool): データベースを更新するかどうか
            \nis_collect (bool): fine-tuning(または、検証)用のデータを作成するかどうか
            \nproblems_fileplace: batchで処理したinputを保管するjsonファイル名。
            fine-tuning用のデータを作成する場合に使用するが、これもファイル名だけでいい
        """        
        if is_collect:
            input = self._read_jsonl("../data/openai_batch/memo/" + problems_fileplace + ".json")
            fine_tuning_data_list = []
    
        id_memo = self._read_jsonl("../data/openai_batch/memo/" + id_memo_fileplace + ".jsonl")
        output = self._read_jsonl("../data/openai_batch/res/" + output_fileplace + ".jsonl")
        batch_config=self._get_batch_config(process_type)
    
        id_memo_dict = {list(chunk.keys())[0]: list(chunk.values())[0] for chunk in id_memo}
        output_dict = {item['custom_id']: item['response'] for item in output}
            
        for request_id, str_id_list in id_memo_dict.items():
            content_str = output_dict[request_id]['body']['choices'][0]['message']['content']
            try:
                result = json.loads(content_str)  # JSON形式の文字列をPythonの辞書に変換
            except json.JSONDecodeError as e:
                logger.log(logging.ERROR, f"JSON decoding error: {e}")
                continue
            
            id_list = [ObjectId(str_id) for str_id in str_id_list]
            
            logger.log(logging.INFO, f"request_id : {request_id}")
            for info_dict in result[batch_config['object_key']]:
                logger.log(logging.DEBUG, info_dict)
            
            #* dbの更新
            update_function = getattr(self.db_updater, batch_config['update_function'],None)
            if update_function is None:
                raise ValueError(f"Unknown fetch_function: {batch_config['update_function']}")
            if is_write:
                # 実際に使用するのはresultの方
                w_cnt=update_function(id_list, result)
                logging.info(f"update count of {request_id} : {w_cnt}")

            if is_collect:
                input_chunk = input[0][int(request_id.split('-')[1])]
                #process_typeとconfig、promptなどすべてに統一した名前を使おう
                with open(f'llm_prompt/{process_type}.json', 'r', encoding='utf-8') as file:
                    data = json.load(file)
                system_message = data.get('system_message')
                user_message = data.get('user')
                example_message = data.get('example')
                info_list = [{batch_config['data_structure'][key]: obj[key] for key in batch_config['data_structure']} for obj in result]
                # ファインチューニング用のデータをリストに追加
                fine_tuning_data_list.append(
                    self.fine_tuner.create_fine_tuning_data(system_message, user_message, example_message, input_chunk, info_list, '')
                )
    
        # ファインチューニング用のデータを一度に書き込む
        #! fine-tuningは廃止する(gpt-4oが強い)
        if is_collect:
            self.fine_tuner.write_fine_tuning_data(fine_tuning_data_list, f'../data/fine-tuning/{process_type}_.jsonl') 

    #* バッチ処理を追加するごとに、この関数を変更する必要がある
    def _process_input(self, doc_list:list[dict], chunk_size:int, 
                           process_type:Literal['annotate_improvement_parameters','categorize_functions','add_heading'])->tuple[list[str],list[dict[str,list[str]]]]:
        """_summary_
        \nfetch_functionで取得した文書のリストを処理単位に分割し、IDメモとchunks(input)を作成する。
        これは、GPTのinput部分にあたるので、作成したexampleと形式を揃える必要がある。
        \nオンライン処理におけるpatentProcessor._prepare_data()関数に相当する。

        Args:
            doc_list: 文書のリスト
            chunk_size: チャンクのサイズ
            process_type: バッチ処理のタイプ

        Returns:
            チャンクリストとIDメモのリスト
        """
        doc_num = len(doc_list)
        chunks = []
        id_memo = []

        for i in range(0, doc_num, chunk_size):
            part_doc_list = doc_list[i:i + chunk_size]
            id_list = [str(doc["id"]) for doc in part_doc_list]
            id_memo.append({f"request-{i // chunk_size:05}": id_list})

            chunk = ""
            for j, doc in enumerate(part_doc_list):
                if process_type == 'dismantle_problem':
                    chunk += f"{j + 1}\n{doc['problem']}\n"
                elif process_type == 'annotate_improvement_parameters':
                    chunk += f"{j + 1}\n{doc['invent_name']}\n{doc['problem']}\n"
                elif process_type == 'categorize_functions':
                    chunk += f"{j + 1}. {doc['object']}\n"
                elif process_type == 'add_heading':
                    chunk += f"{j+1}.\napply_num:{doc['apply_number']}\nobject:{doc['object']}\nparameter:{doc['parameter']}\nparam_explanation:{doc['param_explanation']}\nsolve_way:{doc['solve_way']}\n"
                else:
                    raise ValueError(f"Unknown process type: {process_type}")
            chunk = chunk.strip()
            chunks.append(chunk)

        logger.log(logging.INFO, f"Processed {doc_num} documents into {len(chunks)} chunks")
        return chunks, id_memo
    
    #! 見やすいけど、異なるdictに対応できないので廃止する
    def _log_output(self, request_id:str,id_list:list,result:dict[str,list[dict]],batch_config)->bool:
        output_data=result[batch_config['object_key']]
        #* 出力の確認用にわざわざ作る
        info_list = [{batch_config['data_structure'][key]: obj[key] for key in batch_config['data_structure']} 
                     for obj in output_data]
        
        #* 出力の検証
        logger.log(logging.INFO, f"\nrequest_id : {request_id}")
        for info_dict in info_list:
            logger.log(logging.INFO, info_dict)

        if len(info_list) != len(id_list):
            logger.error(f"ERROR\n 戻り値の数:{len(info_list)} request_id:{request_id}\n")
            return False
        else:
            logger.log(logging.INFO, f"{request_id} is proper.") 
            return True             

    def _write_jsonl_file(self, filepath, data_list,mode:str):
        """
        JSONLファイルにデータリストを書き込む

        Args:
            filepath: 出力ファイルのパス
            data_list: 書き込むデータのリスト
            mode: id_list or input_data
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as file:
                for item in data_list:
                    file.write(json.dumps(item, ensure_ascii=False) + '\n')
            logger.log(logging.INFO,f"Successfully wrote JSONL file of {mode}. \n{filepath}")
        except Exception as e:
            logger.log(logging.ERROR,f"Error writing JSONL file {filepath}: {e}")
            raise
        
    def _create_jsonl_data(self, prompt_data:dict, chunks:list, finetuning_model=None):
        """
        バッチ処理用のJSONLデータを作成する

        Args:
            prompt_data: プロンプトデータの辞書
            chunks: batch処理するデータのリスト user_messageに含める
            finetuning_model: 使用するファインチューニングモデル（オプション）

        Returns:
            JSONLデータのリスト
        """
        system_message_template = prompt_data.get('system_message_template')
        user_message_template = prompt_data.get('user_message_template')
        persona = prompt_data.get('persona')
        instruction = prompt_data.get('instruction')
        output_format = prompt_data.get('output_format')
        example = prompt_data.get('example')
        input_prefix = prompt_data.get('input_prefix')

        jsonl_data = []
        for idx, chunk in enumerate(chunks):
            system_message = system_message_template.format(persona=persona, instruction=instruction, output_format=output_format)
            user_message = user_message_template.format(example=example, input_prefix=input_prefix, input=chunk)

            model = finetuning_model if finetuning_model else self.using_model

            request = {
                "custom_id": f"request-{idx:05}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": model,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ]
                }
            }
            jsonl_data.append(request)
        logger.log(logging.INFO, "Created JSONL data for batch processing")
        return jsonl_data

    def _save_batch_files(self, prefix, id_memo, jsonl_data, additional_data=None):
        """
        バッチ処理用のファイルを保存する

        Args:
            prefix: ファイル名のプレフィックス
            id_memo: IDメモのリスト
            jsonl_data: JSONLデータのリスト
            additional_data: 追加データ（オプション）例えば、fine-tuning用に使うデータ

        Returns:
            入力ファイルのパス
        """
        try:
            timestamp = re.sub(r'\.', '_', str(time.time()))
            memo_path = f"../data/openai_batch/memo/{prefix}_oid_{timestamp[:10]}.jsonl"
            self._write_jsonl_file(memo_path, id_memo,"id_list")

            input_path = f"../data/openai_batch/input/{prefix}_batchI_{timestamp[:10]}.jsonl"
            self._write_jsonl_file(input_path, jsonl_data,"input_data")

            if additional_data:
                additional_data_path = f"../data/openai_batch/memo/{prefix}_additional_{timestamp}.json"
                with open(additional_data_path, 'w', encoding='utf-8') as file:
                    file.write(json.dumps(additional_data, ensure_ascii=False))
            logger.log(logging.INFO,f"Saved batch files with prefix {prefix}")

            return input_path
        except Exception as e:
            logger.log(logging.ERROR,f"Error saving batch files with prefix {prefix}: {e}")
            raise
        
    def _get_process_config(self, process_type):
        """
        指定されたプロセスタイプに対する設定を返す。
        \nこれは、batchファイルの作成時に使用される設定で、オンライン処理の設定と共通のものである。

        Args:
            process_type: バッチ処理のタイプ

        Returns:
            プロセスの設定を含む辞書
        """
        config_file_path = 'config/process_config.json'
        with open(config_file_path, 'r', encoding='utf-8') as file:
            configs = json.load(file)
        
        if process_type not in configs:
            raise ValueError(f"Process type {process_type} is not defined in the configuration file.")
        
        return configs[process_type]
    
    def _get_batch_config(self,process_type:str)->dict:
        """
        _summary_  process_typeに対応するbatch処理の設定を取得する。
        \nこれは、batch処理を受け取ってからDBに格納するまでに使用される設定である。
        """
        
        with open('config/batch_config.json', 'r') as file:
            config = json.load(file)
            return config[process_type]
        
    def _make_batch_request(self,batchfile_id:str)->str:
        """_summary_  batchfile_idを使って、batch処理をopenaiに依頼する

        Args:
            batchfile_id (str): upload_file関数で取得したbatchfile_id
            
        Returns: batch_id: batch処理を識別するためのid
        """
        response = self.client.batches.create(
        completion_window="24h",
        endpoint="/v1/chat/completions",
        input_file_id=batchfile_id
        )
        batch_id=response.id 
        logger.log(logging.INFO,f"batch_id:{batch_id}")
        return batch_id
    
    def _check_batch_status(self,batch_id:str)->str:
        """_summary_  batch_idを使って、batch処理のstatusを確認する

        Args:
            batch_id (str): make_batch_requestで取得したbatch_id

        Returns:
            str: batch処理のstatus
        """
        response = self.client.batches.retrieve(batch_id)
        logger.log(logging.INFO,f"status:{response.status}")
        return response.status
    
    def _fetch_batch_output_file_id(self,batch_id:str)->str:
        """_summary_ 
        \nbatch_idから、batch処理の結果であるjsonlファイルのidを取得して返す。
        \nここで返されるのは、batch処理の結果ではなく、ファイルのidであることに注意

        Args:
            batch_id (str): make_batch_requestで作成したbatch_id

        Returns:
            str: batch処理の結果が書かれたjsonlファイルのid
        """
        response = self.client.batches.retrieve(batch_id)
        return response.output_file_id
        
    def _fetch_batch_result(self,output_file_id:str)->None:
        """_summary_  batch処理の結果を取得して、ローカルに保存する
        """
        jsonl_content = self.client.files.content(output_file_id).text
        file_path="../data/openai_batch/res/batch_"+output_file_id[-5:]+".jsonl"
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(jsonl_content)
            logger.info(f"outout_file: batch_"+{output_file_id[-5:]})
    
    # JSONオブジェクトを読み込むための関数
    def _read_jsonl(self,file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return [json.loads(line) for line in file]

#NOTE 現在のところ、このクラスは使用していない                     
class fineTuning:
    def __init__(self):
        from openai import OpenAI

        self.openai_api_key = self._load_api_key()
        self.client=OpenAI(api_key=self.openai_api_key)
    
    def _load_api_key(self)->str:
        # JSON設定ファイルを開いて読み込む
        #ファイルのパスは、実行ファイルからの相対パス
        with open('config/config.json', 'r') as file:
            config = json.load(file)
        return config['OPENAI_API_KEY']
    
    def create_fine_tuning_data(self, system_message: str, user_message: str, example_message: str, input_chunk: str, info_list: list, output_filename: str) -> None:
        """
        ファインチューニング用のデータを作成し、jsonlファイルに保存する

        Args:
            system_message (str): システムメッセージ
            user_message (str): ユーザーメッセージ
            example_message (str): 例示メッセージ
            input_chunk (str): 入力チャンク
            info_list (list): 出力情報のリスト
            output_filename (str): 出力ファイル名
        """
        with open(output_filename, "a", encoding='utf_8') as f:
            insert_json_object = {
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": f"{user_message}\n{example_message}\n<problem>\n{input_chunk}"},
                    {"role": "assistant", "content": str(info_list)}
                ]
            }
            f.write(json.dumps(insert_json_object, ensure_ascii=False) + '\n')
    
    def make_fine_tuning_request(self,training_file:str)->str:
        """_summary_ fine-tuningのリクエストをopenaiに送信する

        Args:
            training_file (str): fine-tuningのためのjsonlファイルに対応するid

        Returns:
            str: 各fine-tuningに割り当てられたid
        """
        response=self.client.fine_tuning.jobs.create(
            training_file=training_file,
            model="gpt-3.5-turbo",
        )
        response_id=response.id
        return response_id
        
    def do_fine_tuning(self,jsonl_filename:str)->str:
        """_summary_ fine-tuningのリクエストをopenaiに送信する

        Args:
            jsonl_filename (str): fine-tuningのためのjsonlファイルの名前
        
        Returns: fine_tune_id: fine-tuningのid
        """
        gpt_manip=gptClient()
        filename=gpt_manip.upload_file(jsonl_filename,"fine-tune")
        fine_tune_id=self.make_fine_tuning_request(filename)
        logger.log(logging.INFO,f"fine_tune_id:{fine_tune_id}")
        return fine_tune_id
        
    def analyze_fine_tuning_model(self,finetune_id:str)->None:
        """_summary_ fine-tuningの結果を分析する step,train_loss,validation_lossを表示する
        また、検証データを追加していた場合は、その結果(valid_loss,valid_mean_token_accuracy)も表示する

        Args:
            finetune_id (str): 各fine-tuningに割り当てられたid
        """
        job=self.client.fine_tuning.jobs.retrieve(finetune_id)
        result_file_id=job.result_files[0]
        content=self.client.files.content(result_file_id).text
        logger.log(logging.INFO,content)
        
    def evaluate_fine_tuning_model(self,finetune_model_id:str)->None:
        """_summary_ fine-tuningの結果を評価する

        Args:
            finetune_model_id (str): 
        """

class expOperator:
    """_summary_  実験や検証に関する操作を行うクラス
    
    """
    def __init__(self):
        pass
    
    def aggr_clasified_impr_params(self)->Tuple[list,list]:
        """_summary_ 分類された改善パラメータの数を集計して、logに出力する
        
        """
        import matplotlib.pyplot as plt
        import numpy as np
        import seaborn as sns

        db_query=patentQuery(collection_name="patents")
        res_list=db_query.get_parameter_counts()
        class_list=[]
        num_list=[]
        for res in res_list:
            class_list.append(res[0])
            num_list.append(res[1])
        class_data=np.array(class_list)
        num_data=np.array(num_list)
        fig,ax1=plt.subplots(1, 1, figsize=(12, 10))
        #sns.~plotでグラフを作成する
        sns.barplot(x=class_data,y=num_data,ax=ax1,color='skyblue')
        ax1.set_title('frequency_by_improve_params')
        ax1.set_xlabel('parameter_class')
        ax1.set_ylabel('Flequency')
        # グラフの表示
        plt.tight_layout()
        plt.show()
            
    def aggr_classified_function_classes(self):
        """_summary_ 分類されたfunction_classesの数を集計して、logに出力する
        
        """
        import matplotlib.pyplot as plt
        import numpy as np
        import seaborn as sns

        db_query = patentQuery(collection_name="patents")
        res_list = db_query.get_function_class_counts()
        class_list=[]
        num_list=[]
        for res in res_list:
            class_list.append(res[0])
            num_list.append(res[1])            
        class_data=np.array(class_list)
        num_data=np.array(num_list)
        fig,ax1=plt.subplots(1, 1, figsize=(12, 10))
        #sns.~plotでグラフを作成する
        sns.barplot(x=class_data,y=num_data,ax=ax1,color='forestgreen')
        ax1.set_title('frequency_by_functional_class')
        ax1.set_xlabel('function_class')
        ax1.set_ylabel('Flequency')
        # グラフの表示
        plt.tight_layout()
        plt.show()        

#! 以下の関数は、現在は使用していない            
def update_documents_with_full_url(max_doc: int = None,
                                   batch_size: int = 50,is_write=True):
    """
    full_urlを持たないdocumentを更新するメソッド。apply_numberを使ってURLを取得し、ドキュメントを更新する。
    \n現在は、ユーザが特許の完全な情報をみたいときにオンラインで個別のURLを取得するため、この関数は使わない。
    引数:
        max_doc (int): 更新するdocumentの最大数 (デフォルトはNone)
    """
    from services.api_service import patentUrlFetcher

    patent_office_connector = patentUrlFetcher()
    db_reader = patentQuery(collection_name="patents")
    db_updater = patentBulkUpdater(collection_name="patents")
    documents = db_reader.get_documents_without_full_url(max_doc)
    id_list = []
    url_list = []
    for doc in documents:
        doc_id=doc['id']
        apply_number = doc['apply_number']
        try:
            full_url = patent_office_connector.get_url_to_full_page(apply_number)
            id_list.append(doc_id)
            url_list.append({'full_url': full_url})
            if len(id_list) >= batch_size and is_write:
                db_updater.bulk_update_full_url(id_list, url_list)
                logger.log(logging.INFO, f"Updated {len(id_list)} documents")
                id_list.clear()
                url_list.clear()
        except Exception as e:
            logger.log(logging.WARNING,f"Failed to update document {doc['id']} with apply_number {apply_number}: {e}")
    # 残りのドキュメントをバルク更新
    if id_list and is_write:
        db_updater.bulk_update_full_url(id_list, url_list)
        logger.log(logging.INFO, f"Updated {len(id_list)} documents")
        
def search_patents(query:str):
    dammy=patentManager("patents")
    result=dammy.tmp_func(query)
    return result

def make_new_abstracts():
    """_summary_ 
    \ncollection{patent}から、collection{abstract}のデータを作成する。
    \nただし、既にabstractに存在するデータは作成しない。
    """
    dammy=abstractAdmin(collection_name="patents")
    doc_num=dammy.transfer_parameters()
    logger.log(logging.INFO,f"abstractへの転送を完了。{doc_num}個のドキュメントを処理。")

#* バッチ処理を行うときについでに実行する関数
def remove_all_documents_with_same_invent_name_and_problem():
    """
    特定のコレクションの全ドキュメントから同じinvent_nameとproblemを持つ
    ドキュメントをすべて削除する関数。
    """
    # patentCleanerクラスのインスタンスを作成
    cleaner = patentCleaner("patents")

    # 重複ドキュメントのIDを取得
    duplicate_ids = cleaner.get_duplicate_ids()
    
    for id in duplicate_ids:
        logger.log(logging.INFO, f"Deleting document with ID {id}")

    # 重複ドキュメントの削除
    cleaner.delete_documents_by_ids(duplicate_ids)
