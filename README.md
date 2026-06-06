# GitHub Actions + Python + Telegram 金融市場自動通知

GitHub Actions で定期実行し、Python で市場データを取得して、Telegram に日本語通知を送る最小構成のサンプルです。

まずは次の 3 タスクを動かす前提で作っています。

- `7:00` 朝の為替・FXチェック
- `8:00` 朝の日本株チェック
- `17:00` 日本市場 大引け後チェック

`12:00` `18:00` `20:30` の追加タスクは、設定ファイルとワークフローを先に用意してあり、`config/tasks.yaml` の `enabled` を `true` にすれば拡張しやすい構成です。

## できること

- GitHub Actions で自動実行
- Telegram へテキスト通知
- グラフ画像の生成
- 市場サマリーカード画像の生成
- `tasks.yaml` で通知の有効 / 無効を管理
- 無料版を前提に構築
- OpenAI API は後から追加できるように分離

## 注意点

- 無料版では取得できない情報があります。その場合は `未確認` と表示します。
- 数字は推測で補完しません。
- 市場データ取得には `yfinance` を使っています。無料で始めやすい一方、取得失敗や遅延が起きる場合があります。
- GitHub Actions の定期実行は GitHub 側の都合で数分ずれることがあります。

## フォルダ構成

```text
.github/workflows/
config/
src/
```

## 必要なもの

- GitHub アカウント
- Telegram アカウント
- Telegram Bot
- Bot を送りたいチャットの `chat_id`

## 1. Telegram Bot を作る

1. Telegram で `@BotFather` を開く
2. `/newbot` を実行する
3. 表示された Bot Token を控える

## 2. Chat ID を確認する

Bot に一度メッセージを送ってから、次の URL をブラウザで開きます。

```text
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
```

返ってきた JSON の中にある `chat.id` を `TELEGRAM_CHAT_ID` として使います。

## 3. GitHub にアップロードする

このプロジェクトを GitHub リポジトリに置きます。

## 4. GitHub Secrets を設定する

GitHub リポジトリで次を設定してください。

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

OpenAI を後で使う場合だけ、必要になったタイミングで追加します。

- `OPENAI_API_KEY` 任意

## 5. ローカルで試す

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python src/main.py --task fx_morning
python src/main.py --task japan_morning
python src/main.py --task japan_close
```

`.env` に Telegram の値を入れていない場合、送信はスキップされ、内容だけログに出ます。

## 6. tasks.yaml の使い方

通知ごとの有効 / 無効は `config/tasks.yaml` で管理します。

```yaml
fx_morning:
  enabled: true
```

`enabled: false` のタスクは、ワークフローが動いても送信しません。

## 7. 追加タスクを有効化する方法

次のタスクは初期状態で `enabled: false` です。

- `japan_midday`
- `earnings_close`
- `fx_evening`

有効化するには `config/tasks.yaml` の該当タスクを `true` に変更します。

```yaml
japan_midday:
  enabled: true
```

## 8. GitHub Actions の動作

ワークフローはそれぞれ分かれています。

- `fx_morning.yml`
- `japan_morning.yml`
- `japan_midday.yml`
- `japan_close.yml`
- `earnings.yml`
- `fx_evening.yml`

手動実行もできるよう `workflow_dispatch` を入れています。

## 9. OpenAI を後から追加する

`src/openai_summary.py` を差し替えるか拡張すると、通知文の要約や補足コメントを OpenAI API に任せられます。

現時点では未設定でも動くようにしてあり、API キーがない場合は自動で通常ルールベースにフォールバックします。

## 10. よくある詰まりどころ

- Telegram に届かない
  - Bot を一度も開始していない可能性があります
  - `TELEGRAM_CHAT_ID` が違う可能性があります
- グラフが作れない
  - `pip install -r requirements.txt` が未実行の可能性があります
- GitHub Actions では動くがローカルで送れない
  - `.env` の設定が未入力の可能性があります

## データソース

- 為替・株価・海外指数: `yfinance`
- 通知送信: Telegram Bot API

詳細設定は次を参照してください。

- [config/tasks.yaml](/C:/Users/中田　洋介/Documents/Codex/2026-05-22/github-actions-python-telegram-chatgpt-1/config/tasks.yaml)
- [config/sources.yaml](/C:/Users/中田　洋介/Documents/Codex/2026-05-22/github-actions-python-telegram-chatgpt-1/config/sources.yaml)
- [config/rules.yaml](/C:/Users/中田　洋介/Documents/Codex/2026-05-22/github-actions-python-telegram-chatgpt-1/config/rules.yaml)
