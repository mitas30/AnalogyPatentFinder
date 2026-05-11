# 概要

AnalogyPatentFinder は、**あなたが抱えている具体的な問題**を解決するために、異なる分野だが構造的に類似した解決策を発見する「アナロジー駆動」の特許検索ツールです。  
特許の中核的なアイデアを抽象化することで、一見関係のない分野の発明から発想のヒントを得ることが目的です

## できること

このツールでは、あなたが解決したい問題の**対象**と、改善したい**指標**を入力すると、特許の基本的なアイデアを抽象化・比較し、構造的に類似した特許を提示します。

検索結果を表示する際には、**問題**、**解決アイデア**、**応用可能性**について自然言語による補足説明を付けることで、専門家でなくても理解しやすい形で発想のヒントを提供します。

このリポジトリでは、特許を「抽象クラス」と「改善パラメータ」によって再整理し、検索できるようにしています。

## デモ

![Analogy Patent Finder Demo](./demo.gif)

https://github.com/user-attachments/assets/57123fa9-611a-4b85-8982-6007a24e1810

## 背景とアイデア

既存の特許検索はキーワード一致に優れていますが、異なる分野に存在する **「構造的に類似した解決策」** を見つけることは得意ではありません。

そこで本ツールでは、特許を **抽象クラス** と **改善パラメータ**によって表現することで、分野を横断したアナロジー検索を可能にしています。

さらに、LLMによって生成された補足説明を組み合わせることで、技術転用の可能性を人間が評価しやすい文脈で提示します。

## クイックスタート

Docker がインストールされていれば、数ステップでローカル環境で試すことができます。

**追記 260512:** 日本の特許公報 / 特許文書はデータの再配布が不可能なため、現在データを用意できていません。 英語の特許データを同梱するまでお待ちください

1. **リポジトリをクローンする**

    ```bash
    git clone https://github.com/mitas30/AnalogyPatentFinder.git
    cd AnalogyPatentFinder
    ```

2. **設定ファイルを準備する**

    `server/config/config_example.json` を `config.json` にリネームし、必要な値を設定してください。

    ```bash
    mv server/config/config_example.json server/config/config.json
    ```

    `server/config/config.json` の例（一部）：

    ```json
    {
      "GEMINI_API_KEY": "YOUR_GEMINI_API_KEY_HERE",
      "USE_GEMINI_MODEL": "gemini-3-flash-preview"
    }
    ```

    APIキーは [Google AI Studio](https://aistudio.google.com/) から取得してください。意図しない課金を避けるため、課金設定は無効のままにしておくことをおすすめします。

3. **アプリケーションをビルドして起動する**

    ```bash
    docker-compose up --build
    ```

4. **ブラウザでアクセスする**

    **http://localhost:5173/** にアクセスしてください。

**注意:** アノテーション済み特許データセットは同梱していません。初回起動時のMongoDBは空の状態です。

ローカルで手元の初期データを使う場合は、`mongo/initial-data.json` を置いてから起動してください。存在する場合のみ、初回起動時に `patents` コレクションへ投入されます。`mongo/initial-data2.json` と `mongo/initial-data3.json` も存在すれば、それぞれ `abstracts` と `parameters` に投入されます。初期データを入れ直す場合は、`docker-compose down -v` で MongoDB の名前付きボリュームを削除してから再起動してください。

## 使い方

1. 入力欄に、問題の **対象**（例：*battery*）と、**改善したい観点**（例：*安全性, 効率性*）を入力します。
2. 検索を実行すると、構造的に類似した特許の一覧が表示されます。
3. 各カードには、**問題**、**特許が提示した解決策**、**転用可能性のヒント**が表示されます

## 仕組み

本システムでは、対象となる特許文書を 抽象クラス [1] と 改善パラメータ[2] の2つの軸で正規化します。次に、ユーザーのクエリも同様に抽象化し、対応する特許を検索します。

LLMは、説明文の生成や曖昧な表現の正規化に利用されます。これにより、可読性を高めるとともに、ユーザーが技術転用の可能性を判断しやすくしています。

# 参考文献
[1] J. Hirtz, R. B. Stone, D. A. McAdams, S. Szykman, and K. L. Wood, “A functional basis for engineering design: Reconciling and evolving previous efforts,” Res Eng Design, vol. 13, no. 2, pp. 65–82, Mar. 2002, doi: 10.1007/s00163-001-0008-3.  
[2] “Appendix I: 39 Parameters of the Contradiction Matrix,” in TRIZ for Engineers: Enabling Inventive Problem Solving, John Wiley & Sons, Ltd, 2011, pp. 468–470. doi: 10.1002/9780470684320.app1.
[3] L. Liu, Y. Li, Y. Xiong, and D. Cavallucci, “A new function-based patent knowledge retrieval tool for conceptual design of innovative products,” vol. 115, Nov. 2019, doi: 10.1016/j.compind.2019.103154.
[4] H. B. Kang, X. Qian, T. Hope, D. Shahaf, J. Chan, and A. Kittur, “Augmenting Scientific Creativity with an Analogical Search Engine,” vol. 29, no. 6, p. 1, Nov. 2022, doi: 10.1145/3530013.
[5] K. Gilon, J. Chan, F. Y. Ng, H. Liifshitz-Assaf, A. Kittur, and D. Shahaf, “Analogy Mining for Specific Design Needs,” Apr. 2018, doi: 10.1145/3173574.3173695.
[6] H. B. Kang et al., “BIOSPARK: An End-to-End Generative System for Biological-Analogical Inspirations and Ideation.”
[7] T. Hope, J. Chan, A. Kittur, and D. Shahaf, “Accelerating Innovation Through Analogy Mining,” Aug. 2017, doi: 10.1145/3097983.3098038.
[8] L. Yu, R. E. Kraut, and A. Kittur, “Distributed Analogical Idea Generation with Multiple Constraints,” Feb. 2016, doi: 10.1145/2818048.2835201.
[9] J. Savelka, K. D. Ashley, M. A. Gray, H. Westermann, and H. Xu, “Can GPT-4 Support Analysis of Textual Data in Tasks Requiring Highly Specialized Domain Expertise?”
[10] L. Yu, A. Kittur, and R. E. Kraut, “Searching for analogical ideas with crowds,” Apr. 2014, doi: 10.1145/2556288.2557378.
[11] L. Yu, A. Kittur, and R. E. Kraut, “Distributed analogical idea generation,” Apr. 2014, doi: 10.1145/2556288.2557371.
