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
