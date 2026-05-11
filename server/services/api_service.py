from models.model import patentQuery,patentManager,abstractAdmin
from openai import OpenAI
from json import JSONDecodeError
import google.generativeai as genai
import json,requests
import os,logging,time,re
from bson import ObjectId

logger=logging.getLogger(__name__)

#* 一定リクエストまで無料の、Gemini APIを使うことにする。

class onlineGeminiClient: 
    """ユーザからの入力をもとに、Geminiで処理する関数のクラス。
    """
    def __init__(self):
        self.gemini_info = self._load_api_info()
        genai.configure(api_key=self.gemini_info["GEMINI_API_KEY"])
        self.client=genai.GenerativeModel(model_name=self.gemini_info["USE_GEMINI_MODEL"])

    def _load_api_info(self)->dict[str,str]:
        # JSON設定ファイルを開いて読み込む
        #ファイルのパスは、実行ファイルからの相対パス
        with open('config/config.json', 'r') as file:
            config = json.load(file)
        ret_dict={}
        ret_dict["GEMINI_API_KEY"]=config['GEMINI_API_KEY']
        ret_dict["USE_GEMINI_MODEL"]=config['USE_GEMINI_MODEL']
        if not ret_dict["USE_GEMINI_MODEL"]:
            raise ValueError("config/config.json の USE_GEMINI_MODEL を設定してください。")
        return ret_dict
    
    def guess_abstract_class(self,object:str)->dict[str,list]:
        """_summary_
        
        ユーザが入力したクエリから、そのクエリの対象が、どのような抽象機能を持つか推測する関数。

        Returns:
            _type_: _description_
        """
        current_relative_dir=os.path.dirname(os.path.abspath(__file__))
        file_path=os.path.join(current_relative_dir,"../llm_prompt/gemini/classify_user_query.json")
        with open(file_path, 'r',encoding='utf-8') as file:
            data=json.load(file)
        persona = data.get('persona')
        instruction = data.get('instruction')
        example = data.get('example')
        input_prefix = data.get('input_prefix')
        message = data.get('message')
        message=message.format(persona=persona, instruction=instruction,
                                 example=example, input_prefix=input_prefix, input=object)
        # gemini 1.5-proにはスキーマオブジェクトを渡せる。
        output_format = data.get('output_format')
        st=time.time()
        response=self.client.generate_content(message,generation_config=genai.GenerationConfig(
            temperature= 0.5,
            max_output_tokens= 8192,
            response_mime_type= "application/json",
            response_schema=output_format
            ))
        logger.log(logging.INFO,f"process_time:{time.time()-st:.2f}s metadata:{response.usage_metadata}") #output_token:{response.usage.completion_tokens} model:{response.model}")
        logger.info(response.text)
        return json.loads(response.text)
    
    def create_explanation_and_better_heading(self,heading:str,t_object:str,parameter:str,detail_info:str)->dict[str,str]:
        """_summary_
        
        特許の見出しに対して、より詳細な説明を生成する関数。
        また、見出しが不適切なときには、見出しを改善する処理も行う。

        Args:
            heading (str): _description_
            detail_solve_way (str): _description_

        Returns:
            dict[str,str]: _description_
        """
        current_relative_dir=os.path.dirname(os.path.abspath(__file__))
        file_path=os.path.join(current_relative_dir,"../llm_prompt/gemini/create_explain_and_better_heading.json")
        with open(file_path, 'r',encoding='utf-8') as file:
            data=json.load(file)
        persona = data.get('persona')
        output_format = data.get('output_format')
        instruction = data.get('instruction')
        example = data.get('example')
        input = data.get('input').format(heading=heading,object=t_object,parameter=parameter,detail_info=detail_info)
        message = data.get('message')
        message=message.format(persona=persona, output_format=output_format,instruction=instruction,
                                 example=example, input=input)
        logger.info(input)
        st=time.time()
        response=self.client.generate_content(message,generation_config=genai.GenerationConfig(
            temperature= 0.5,
            max_output_tokens= 8192,
            response_mime_type= "application/json",
            ))
        logger.log(logging.INFO,f"process_time:{time.time()-st:.2f}s metadata:{response.usage_metadata}") #output_token:{response.usage.completion_tokens} model:{response.model}")
        logger.debug(response.text)
        try:
            json_response=json.loads(response.text)
        except JSONDecodeError as e:
            logger.log(logging.ERROR,
                       msg=f"エラー:{e.msg}/n"+
                       f"ドキュメント:\n{e.doc}\n"+
                       f"位置:{e.pos}\n"+
                       f"{e.doc[e.pos-1:]}")  
            json_response={}   
        assert type(json_response) == dict
        return json_response
        
class patentInfoProvider:
    def __init__(self):
        self.online_Gemini_client = onlineGeminiClient()
        self.patent_finder = patentQuery("patents")
        self.pm=patentManager("patents")
        self.abstractadmin=abstractAdmin("abstracts")
        
    def _normalize_format(self,parameters:list)->list:
        """_summary_
        
        パラメータは、["1,2","3,4","5,6"]のような形式で入ってくることがあるので、これを["1","2","3","4","5","6"]のような形式に変換する関数。

        Args:
            parameters (list): _description_

        Returns:
            list: _description_
        """
        ret_list=[]
        for parameter in parameters:
            ret_list.extend(parameter.split(","))
        return ret_list
    
    def get_patent_by_id(self, id):
        return self.patent_model.find_by_id(id)

    def fetch_target_patents(self, object:str,parameters:list)->list[dict]:
        """_summary_

        ユーザのクエリに合致する特許を取得して返却する関数。
        
        Args:
            object (str): _description_
            parameters (list): _description_

        Returns:
            list[dict]: _description_
        """
        category = self.online_Gemini_client.guess_abstract_class(object)
        abstract_classes = category["abstract_class"]
        assert type(abstract_classes) == list
        parameters=self._normalize_format(parameters)
        object_patents=self.patent_finder.find_patents_by_query(abstract_classes,parameters)
        assert type(object_patents) == list
        for patent in object_patents:
            patent["_id"]=str(patent["_id"])
        logging.info(f"number of target_patents:{len(object_patents)}")
        return object_patents
    
    def create_and_store_explain(self,apply_number:str,heading:str,
                                 key_id:str,param_exp:str,t_object:str,parameter:str)->dict[str,str]:
        """_summary_
        
        見出しの詳しい解説を行う。
        
        asknature.orgを参考にしている。

        Args:
            apply_number (str): 出願番号。特許の詳しい解説を作成するためにDBにアクセスする必要がある。
            heading (str): 解説する内容の見出し

        Returns:
            dict : headingの説明。改善された見出しや、abstractSolution,Solutionが格納されることもある。
        """
        #step1 すでにその特許に対して、見出しの解説があるかどうかを確認する。
        is_created = self.inquire_explanation(apply_number,parameter)
        if(is_created==True):
            geminis_explanation=self.pm.get_explanation(apply_number,parameter)
        else:
            try:
                doc=self.pm.get_detail_info(apply_number)
                detail_problem=re.sub("\n","",doc["detail_problem"])
                detail_solve_way=re.sub("\n","",doc["detail_solve_way"]) 
                detail_info="【発明が解決しようとする課題】\n"+detail_problem+"\n【課題を解決するための手段】\n"+detail_solve_way
            except Exception as e:
                logger.warning(e)
            geminis_explanation=self.online_Gemini_client.create_explanation_and_better_heading(heading,t_object,param_exp,detail_info)
            if all(key in geminis_explanation for key in ["better_heading", "abstractSolution", "solution_summary"]):
                logging.info(f'1.{geminis_explanation["solution_summary"]["output"]}\n2.{geminis_explanation["better_heading"]["output"]}\n3.{geminis_explanation["abstractSolution"]["output"]}')
            logging.info(geminis_explanation["patent_explanation"]["output"])
            assert key_id is not None
            original_id=ObjectId(key_id)
            update_heading_cnt=0
            # 見出しの改善があった場合に、abstractに格納する
            if all(key in geminis_explanation for key in ["better_heading", "abstractSolution", "solution_summary"]):
                update_heading_cnt=self.abstractadmin.update_to_better_heading(original_id,parameter,geminis_explanation)
            update_data_cnt=self.abstractadmin.append_explanation(original_id,parameter,geminis_explanation["patent_explanation"]["output"])
            if(update_data_cnt==0):
                logger.warning("解説がDBに追加されていないようです。何らかのエラー")
            if(update_heading_cnt==0):
                logger.info("見出しの改善は行われませんでした。")
                geminis_explanation["is_heading_improved"]=False
            else:
                logger.info("見出しの改善が行われました。")
                geminis_explanation["is_heading_improved"]=True
        return geminis_explanation
                
        
    def inquire_explanation(self,apply_number:str,parameter:str)->bool:
        """_summary_
        
        特許の見出しに対する解説がすでに存在するかどうかを確認する関数。
        
        Args:
            apply_number (str): _description_

        Returns:
            bool: _description_
        """
        return self.pm.is_created(apply_number,parameter=parameter)
    
    def fetch_exist_explanation(self,apply_number:str,parameter:str)->dict[str,str]:
        """_summary_
        
        特許の詳細な解説を取得して返却する関数。

        Args:
            apply_number (str): _description_
            parameter (str): _description_

        Returns:
            dict[str,str]: _description_
        """
        explanation=self.pm.get_explanation(apply_number,parameter)
        struct_exp=self.structure_explanation(explanation["patent_explanation"]["output"])
        return struct_exp
    
    def structure_explanation(self,explanation:str)->dict[str,str]:
        """_summary_
        
        explanationを導入、戦略、応用に分割して、辞書に格納する関数。

        Args:
            explanation (str): _description_

        Raises:
            Exception: _description_
            Exception: _description_
            ValueError: _description_
            Exception: _description_

        Returns:
            dict[str,str]: _description_
        """
        ret_dict={}
        sep_list=explanation.rsplit("**応用**",1)
        ret_dict["application"]=sep_list[1]
        sep_list=sep_list[0].rsplit("**戦略**",1)
        ret_dict["strategy"]=sep_list[1]
        sep_list=sep_list[0].rsplit("**導入**",1)
        ret_dict["intro"]=sep_list[1]
        return ret_dict
        
class patentUrlFetcher:
    def __init__(self):
        self.token = None
        self.config = self._load_config()['patent_office']
        self.pm=patentManager("patents")
        self.token_expiry_time = None
        self.token_expiry_duration = 3000  # トークンの有効期限（秒）
        
    def _load_config(self):
        with open('config/config.json', 'r') as file:
            return json.load(file)
        
    def _update_full_url(self,apply_number:str,full_url:str)->None:
        """_summary_
        \nmongoDBの対応する特許ドキュメントに、特許公報のURLを追加する関数。
        """
        self.pm.update_full_url(apply_number,full_url)
        
    def get_url_to_full_page(self, apply_number: str) -> str:
        """_summary_
        \n特許庁の特許公報のページにリダイレクトするURLを取得する関数。
        \napply_numberに対応した特許公報のURLを取得する。
        \nその後、mongoDBのpatentsにURLを追加する。

        Args:
            apply_number (str): _description_

        Returns:
            str: _description_
        """
        token = self._get_valid_token()
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        api_url = f"https://ip-data.jpo.go.jp/api/patent/v1/jpp_fixed_address/{apply_number}"
        response = requests.get(api_url, headers=headers)
        
        if response.status_code == 200:
            data_dict = response.json()["result"]
            if int(data_dict["statusCode"]) == 100:
                remain_access=data_dict["remainAccessCount"]
                url=data_dict["data"]["URL"]
                self._update_full_url(apply_number,url)
                logger.log(logging.INFO,f"出願番号:{apply_number}\n取得したURL: {url} \n残りアクセス回数:{remain_access}")
                return url
            else:
                error_message = data_dict["errorMessage"]
                raise Exception(f"APIエラー: {error_message}")
        else:
            raise Exception(f"URLの取得に失敗しました: ステータスコード {response.status_code}")

    def _auth(self):
        username = self.config['username']
        password = self.config['password']
        
        if not username or not password:
            raise ValueError("PATENT_OFFICE_USERNAME または PATENT_OFFICE_PASS が設定されていません")

        data = {
            "grant_type": "password",
            "username": username,
            "password": password
        }

        token_url = "https://ip-data.jpo.go.jp/auth/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        response = requests.post(token_url, data=data, headers=headers)

        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.token_expiry_time = time.time() + self.token_expiry_duration
            logger.log(logging.INFO,"トークンの取得に成功しました")
        else:
            raise Exception(f"トークンの取得に失敗しました: ステータスコード {response.status_code}")

    def _get_valid_token(self):
        if self.token is None or time.time() >= self.token_expiry_time:
            self._auth()
        return self.token
