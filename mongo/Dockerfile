# ベースイメージ
FROM mongo:latest

# エントリーポイントスクリプトのコピー
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# エントリーポイントの設定
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
