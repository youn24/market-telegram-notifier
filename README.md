# GitHub Actions + Python + Telegram 金融市場自動通知

GitHub Actions で定期実行し、Python で市場データを取得して、Telegram に日本語通知を送る最小構成のサンプルです。

まずは次の 3 タスクを動かす前提で作っています。

- `7:00` 朝の全体マクロ経済チェック
- `9:30` 寄り後の日本株チェック
- `17:00` 日本市場 大引け後チェック

`12:00` `18:00` `20:30` の追加タスクは、設定ファイルと手動実行用ワークフローを用意してあります。追加するときは `config/tasks.yaml` の `enabled` を `true` にし、対応ワークフローへ定期実行の `schedule` を追加します。

## できること

- GitHub Actions で自動実行
- Telegram へ短いテキスト通知を1通だけ送信
- グラフ画像の生成
- 市場サマリーカード画像の生成
- 無料のニュース検索/RSSで材料ヘッドラインを確認
- `tasks.yaml` で通知の有効 / 無効を管理
- 無料版を前提に構築
- OpenAI API は後から追加できるように分離
- FRED API を入れると経済指標の未確認を減らせる
- Canva / Adobe 用のデザイン指示書を自動生成
- 9:30・17:00通知でテーマ株の広がりと主導銘柄を確認
- 株式・VIX・金・為替・テーマ株から価格で確認できる資金方向を整理

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
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python src/main.py --task fx_morning
python src/main.py --task japan_morning
python src/main.py --task japan_close
```

`.env` に Telegram の値を入れていない場合、送信はスキップされ、内容だけログに出ます。

Telegram通知は、初期設定では1回につき「タイトル・イラスト入り画像1枚」と短いキャプションだけです。細かいチャート、グラフ、分析、根拠は通知内の `詳細はこちら` リンクからブラウザ版レポートで確認します。

画像を付けたくない場合は、`.env` または GitHub Variables 側で `TELEGRAM_ATTACH_IMAGE=false` にしてください。複数画像は送らず、最大1枚だけ送ります。

## 6. tasks.yaml の使い方

通知ごとの有効 / 無効は `config/tasks.yaml` で管理します。

```yaml
fx_morning:
  enabled: true
```

`enabled: false` のタスクは送信しません。初期状態で無効な3タスクは定期実行の `schedule` 自体も外してあり、不要なGitHub Actions実行を防ぎます。

## データ品質の安全基準

- Yahoo Finance系の価格は調整後終値を使い、株式分割や分配による見かけ上の急変を抑えます。
- 各データに基準日・取得元・経過日数を付け、古いデータや未来日付は分析へ採用しません。
- 通常では考えにくい変動率を検出した場合は、数値を断定せず `未確認` にします。
- 株価・為替・商品と、金利・スプレッドは同じ騰落率ランキングへ混ぜません。
- 通知画像とブラウザ版に `確認済 x/y` と最新基準日を表示します。

## テーマ株の確認

9:30と17:00の日本株通知では、半導体、AI・データセンター、防衛、銀行、ロボット・FA、建設・インフラを確認します。

- 各テーマは代表4銘柄を等ウェイトで集計します。
- 最低3銘柄を取得できた場合だけ判定します。
- 平均騰落率が±1.5%以上、かつ75%以上の銘柄が同方向の場合に `一斉高` または `一斉安` とします。
- 確認度75点以上だけを高信頼テーマシグナルとして扱います。
- 1銘柄だけの急騰・急落ではテーマ認定しません。
- 取得できない銘柄や取得不足のテーマは、推測せず `未確認` と表示します。
- Telegramには最重要テーマを短く表示し、全テーマと主導3銘柄は詳細レポートで確認できます。

構成銘柄と判定値は `config/sources.yaml` の `theme_stocks` で変更できます。テーマ株の数値はYahoo Finance経由の取得値であり、売買推奨や勝率を示すものではありません。

## 足元のお金の流れ

通知では、取得済み価格の相対強弱から次の方向を整理します。

- 世界株が広く上昇・下落しているか
- 日経225とTOPIXが同方向か
- NASDAQとRussell 2000のどちらが優位か
- VIXと金が警戒・逃避の価格反応を示しているか
- USD/JPYが円安・円高のどちらへ動いているか
- 複数銘柄で確認できた主導テーマは何か

これは「価格から見た資金方向」であり、実際の資金流入額ではありません。投資主体別売買、ETF純流入額、先物建玉の実額を取得できない場合は `未確認` と表示し、価格上昇だけを資金流入額として断定しません。

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
- `STRICT_FACTS_ONLY`: `true` の場合、AIが入力データにない数字や断定表現を出したら、そのAI要約は通知に採用しません。初期値は `true` です。

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

## 11. Canva / Adobe でデザインを強化する

通知を実行すると、GitHub Pages 側に `design-brief.md` が作られます。

このファイルには、Canva・Adobe Express・Illustrator・画像生成AIへ渡せるデザイン指示が入っています。

使い方は次の通りです。

1. ブラウザ版レポートを開く
2. `デザイン方針` の `Canva / Adobe 用デザイン指示書` を開く
3. `Canva Prompt` を Canva に貼る
4. `Adobe Prompt` を Adobe Express や Illustrator の制作メモに貼る
5. 生成されたデザインを参考に、通知画像のレイアウト改善へ使う

通常Canva候補と高品質Canva候補は、タスク種別と相場トーンに合わせて毎回自動選定されます。7:00の全体マクロ、9:30の寄り後、17:00の大引け後、強気/警戒の相場では高品質候補を優先します。

Adobeは現在この環境から直接デザイン生成するツールがないため、`Adobe候補` として Adobe Express / Illustrator / Firefly へ貼る制作指示を出します。

数字は必ずこのシステムで取得した実データを使います。Canva や Adobe 側で数字を作らないでください。取得できない情報は `未確認` として扱います。

ブラウザ版レポートには、文字だけではなく次の視覚要素も表示します。

- `視覚ダッシュボード`: 地合いスコア、リスク、実戦方針をカード形式で表示
- `騰落ヒートマップ`: 取得できた指数・為替・金利・商品を上昇/下落の色で整理
- `画像生成AI用プロンプト`: 背景、アイコン、ガネーシャ先生/カワウソ君のアクセント素材用に分けて出力

画像生成AIやデザインツールを使う場合も、相場の数字や騰落率はこのシステムで取得した値だけを使い、デザイン側で新しい数字を作らないでください。

## 12. よくある詰まりどころ

- Telegram に届かない
  - Bot を一度も開始していない可能性があります
  - `TELEGRAM_CHAT_ID` が違う可能性があります
- グラフが作れない
  - `pip install -r requirements.txt` が未実行の可能性があります
- GitHub Actions では動くがローカルで送れない
  - `.env` の設定が未入力の可能性があります
- PowerShell で日本語が文字化けして見える
  - 実行前に `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` を設定してください
  - ファイルは UTF-8 前提です。エディタ側も UTF-8 で開いてください

## データソース

- 世界株・為替・商品・海外指数: `yfinance`
- nikkei225jp.com: 公開ページで確認できる世界株価、日経225先物/CFD、ADR、米国主要指数、SOX、VIX、為替、金利、商品、経済スケジュールなどの参照リンクと確認観点を詳細レポートに表示します。リアルタイム数値は取得済みデータで確認できたものだけ使い、確認できない値は `未確認` とします。
- 通知送信: Telegram Bot API

詳細設定は次を参照してください。

- [config/tasks.yaml](/C:/Users/中田　洋介/Documents/Codex/2026-05-22/github-actions-python-telegram-chatgpt-1/config/tasks.yaml)
- [config/sources.yaml](/C:/Users/中田　洋介/Documents/Codex/2026-05-22/github-actions-python-telegram-chatgpt-1/config/sources.yaml)
- [config/rules.yaml](/C:/Users/中田　洋介/Documents/Codex/2026-05-22/github-actions-python-telegram-chatgpt-1/config/rules.yaml)

## GitHub Actionsの開始遅延対策

GitHub Actionsの予約実行は、GitHub側の混雑により予定時刻より遅れて開始する場合があります。このプロジェクトでは次の対策を行います。

- 予定時刻より前に複数の予備起動を登録します。
- `src/schedule_guard.py` が日本時間を確認し、予定時刻より前は通知しません。
- 通知できる時間帯を過ぎた古い実行は通知しません。
- GitHub Actionsのキャッシュへ当日の送信済み記録を保存し、同じ通知は1日1回だけ送ります。
- 手動実行は確認作業のため、時刻ガードと当日1回制限の対象外です。

現在の自動通知時間帯は次のとおりです。

- 7:00 全体マクロ: 07:00から08:30まで
- 9:30 寄り後日本株: 09:30から11:00まで
- 17:00 日本市場大引け後: 17:00から18:30まで
- 時間外急変: 17:30から翌08:30まで30分ごとに確認（高確認度の急変時だけ通知）

### 時間外の急変通知

- 先物・VIX・USD/JPY・金・原油・日本株ADRを確認します。
- 指数・先物は原則±1%、為替は±0.5%、商品は±2%、ADRは±3%を急変の入口条件にします。
- 入口条件だけでは送りません。データ鮮度、直近観測の継続、関連市場の方向一致を点数化し、確認度75/100以上の場合だけ送ります。
- 確認度は売買の勝率ではありません。数字を取得できない場合や関連市場が一致しない場合は通知せず、未確認として扱います。
- 条件未達時はAI要約・画像生成・Telegram送信を省略します。同じ時間外セッションの通知は最初の1回だけです。

この方法は無料版GitHub Actionsで開始遅延の影響を小さくする対策です。GitHub側の実行時刻を完全に保証するものではありません。
