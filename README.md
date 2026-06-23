# GitHub Actions + Python + Telegram 金融市場自動通知

GitHub Actions で定期実行し、Python で市場データを取得して、Telegram に日本語通知を送る最小構成のサンプルです。

まずは次の 3 タスクを動かす前提で作っています。

- `7:00` 朝の全体マクロ経済チェック
- `9:30` 寄り後の日本株チェック
- `17:00` 日本市場 大引け後チェック

`12:00` `18:00` `20:30` の追加タスクは、設定ファイルとワークフローを先に用意してあり、`config/tasks.yaml` の `enabled` を `true` にすれば拡張しやすい構成です。

## できること

- GitHub Actions で自動実行
- Telegram へテキスト通知
- グラフ画像の生成
- 市場サマリーカード画像の生成
- 無料のニュース検索/RSSで材料ヘッドラインを確認
- `tasks.yaml` で通知の有効 / 無効を管理
- 無料版を前提に構築
- OpenAI API は後から追加できるように分離
- FRED API を入れると経済指標の未確認を減らせる

## 注意点

- 無料版では取得できない情報があります。その場合は `未確認` と表示します。
- 数字は推測で補完しません。
- 市場データ取得には `yfinance` を使っています。無料で始めやすい一方、取得失敗や遅延が起きる場合があります。
- ニュース材料は Google News RSS 検索を使います。取れない場合は `未確認` と表示し、数字は推測しません。
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

OpenAI / Gemini を後で使う場合だけ、必要になったタイミングで追加します。

- `OPENAI_API_KEY` 任意
- `GEMINI_API_KEY` 任意
- `FRED_API_KEY` 任意

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

Gemini / OpenAI を使う場合も、トークン消費を抑えるために通知用の重要材料だけを圧縮して送ります。

- `AI_SUMMARY_ENABLED`: `true` なら本番通知でAI要約を使います。止めたい場合は `false` にします。
- `AI_SUMMARY_ON_DRY_RUN`: `true` にすると `--dry-run` でもAI要約を試します。通常は `false` 推奨です。
- `AI_SUMMARY_MAX_INPUT_CHARS`: AIへ渡す入力文字数の上限です。初期値は `5200` です。
- `AI_SUMMARY_MAX_OUTPUT_TOKENS`: AIの出力上限です。初期値は `360` です。
- `AI_SUMMARY_TEMPERATURE`: 分析のブレを抑える設定です。初期値は `0.2` です。
- `AI_SUMMARY_DETAIL`: `true` にすると詳細根拠も多めに渡します。通常は `false` 推奨です。

`--dry-run` はテスト用なので、初期設定ではGemini/OpenAIを呼びません。これにより、動作確認だけでトークンを消費することを防ぎます。

## 10. ニュース検索・材料確認

`config/sources.yaml` の `research` で、タスクごとの検索キーワードを管理しています。

```yaml
research:
  default_queries:
    japan_market:
      - "日経平均 日本株 今日 材料"
```

通知時に無料の Google News RSS を検索し、取得できた見出しだけを材料として使います。検索に失敗した場合や十分な情報がない場合は、無理に補完せず `未確認` と表示します。

検索結果は次の基準で並べ替えます。

- 直近性: 新しい記事ほど優先します
- 関連度: `金利` `半導体` `決算` など、タスク別の重要語を含む記事を優先します
- 情報源: 日経、ロイター、Bloomberg、NHK、株探などを少し優先します
- ノイズ除去: 単なる株価ページ、PTS、ランキング系は減点します
- 材料分類: 金利・金融政策、為替、決算・業績、セクター材料などに分類します
- 分散選抜: 同じ媒体ばかりに偏らないようにし、材料カテゴリの広がりも見ます
- 信頼度表示: 材料数、媒体数、分類数、鮮度から `高/中/低` を表示します
- 検索カバレッジ: 検索本数、候補数、採用数、媒体分散、分類数、24時間以内の記事数を点検します
- 不足観点: たとえば日本株なら `為替` `決算・業績` `需給・レーティング` `セクター材料` の不足を表示します
- 追加検索: 不足観点が出た場合は、カテゴリ別の追加クエリで自動的に追跡検索します
- カテゴリ別根拠: 各カテゴリを `根拠あり` `候補のみ` `不足` に分け、分析で使える材料と未確認材料を区別します
- 根拠表示: ブラウザ版では `score`、採点理由、カテゴリ別根拠を表示します

## 11. よくある詰まりどころ

- Telegram に届かない
  - Bot を一度も開始していない可能性があります
  - `TELEGRAM_CHAT_ID` が違う可能性があります
- グラフが作れない
  - `pip install -r requirements.txt` が未実行の可能性があります
- GitHub Actions では動くがローカルで送れない
  - `.env` の設定が未入力の可能性があります

## データソース

- 世界株・為替・商品・海外指数: `yfinance`
- 通知送信: Telegram Bot API

詳細設定は次を参照してください。

- [config/tasks.yaml](/C:/Users/中田　洋介/Documents/Codex/2026-05-22/github-actions-python-telegram-chatgpt-1/config/tasks.yaml)
- [config/sources.yaml](/C:/Users/中田　洋介/Documents/Codex/2026-05-22/github-actions-python-telegram-chatgpt-1/config/sources.yaml)
- [config/rules.yaml](/C:/Users/中田　洋介/Documents/Codex/2026-05-22/github-actions-python-telegram-chatgpt-1/config/rules.yaml)
