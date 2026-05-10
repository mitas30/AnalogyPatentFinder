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

そこで本ツールでは、特許を **「抽象クラス」** と **「改善パラメータ」**（TRIZ）によって表現することで、分野を横断したアナロジー検索を可能にしています。

さらに、LLMによって生成された補足説明を組み合わせることで、技術転用の可能性を人間が評価しやすい文脈で提示します。

## クイックスタート

Docker がインストールされていれば、数ステップでローカル環境で試すことができます。

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
      "USE_GEMINI_MODEL": "gemini-1.5-pro"
    }
    ```

    APIキーは **Google AI Studio** から取得してください。意図しない課金を避けるため、課金設定は無効のままにしておくことをおすすめします。

3. **アプリケーションをビルドして起動する**

    ```bash
    docker-compose up --build
    ```

4. **ブラウザでアクセスする**

    **http://localhost:5173/** にアクセスしてください。

**注意:** このプロトタイプは約2,000件のアノテーション済み特許データセットを使用しているため、クエリによっては検索結果が0件になる場合があります。

## 使い方

1. 入力欄に、問題の**「対象」**（例：*battery*）と、**「改善したい観点」**（例：*safety, efficiency*）を自然言語で入力します。
2. 検索を実行すると、構造的に類似した特許の一覧が表示されます。
3. 各カードには、**問題**、**中核となる解決策**、**転用可能性のヒント**が要約されます。詳細をクリックすると、元の文書や関連情報にアクセスできます。

## 仕組み

本システムでは、対象となる特許文書を **抽象クラス** と **改善パラメータ(TRIZ)** という2つの軸で正規化します。次に、ユーザーのクエリも同様に抽象化し、対応する特許を検索します。

LLMは、説明文の生成や曖昧な表現の正規化に利用されます。これにより、可読性を高めるとともに、ユーザーが技術転用の可能性を判断しやすくしています。

実装はクライアント / サーバー構成になっており、Docker Compose によってアプリケーション、API、データベースをまとめて起動できます。

## Contribution Guide

Issue や Pull Request を歓迎します。まずは以下のラベルが付いたタスクから始めるのがおすすめです。

- `good first issue`: 最初に取り組みやすい改善。
- `enhancement`: 機能追加や UI / UX 改善。
- `data`: データの拡張やクリーニング。
- `docs`: ドキュメント改善（README、チュートリアル、スクリーンショット追加など）。

行動規範は、標準的なオープンソースのエチケットに従います。

## 引用

```bibtex
@software{AnalogyPatentFinder,
  author  = {Takuma Mitamura},
  title   = {AnalogyPatentFinder: An analogy-driven patent search engine},
  year    = {2024},
  url     = {https://github.com/mitas30/AnalogyPatentFinder},
  license = {MIT}
}
