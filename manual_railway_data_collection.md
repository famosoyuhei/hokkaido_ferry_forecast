# Railway 本番環境のデータ収集（ローカルから実行）

## 問題
- Railway管理画面からコマンド実行ができない
- Cronジョブが見つからない/動いていない

## 解決策: ローカルから本番DBに直接データを投入

---

## 手順

### 1. 環境変数を設定

Railwayの本番環境と同じ設定にします:

**Windowsの場合**:
```cmd
set RAILWAY_VOLUME_MOUNT_PATH=.
```

**PowerShellの場合**:
```powershell
$env:RAILWAY_VOLUME_MOUNT_PATH = "."
```

---

### 2. データ収集スクリプトを実行

```bash
python weather_forecast_collector.py
```

実行後、以下のファイルが作成/更新されます:
- `ferry_weather_forecast.db` (ローカル)

---

### 3. データベースをRailwayにアップロード

**オプションA: Railway CLI使用**

```bash
# Railway CLIがインストール済みの場合
railway login
railway link
railway run python weather_forecast_collector.py
```

**オプションB: Git経由**

データベースファイルをGitにコミット（一時的に）:
```bash
git add ferry_weather_forecast.db
git commit -m "Update forecast data"
git push
```

⚠️ **注意**: この方法は非推奨（DBファイルをGitで管理すべきではない）

---

## より良い解決策: Railway CLIをインストール

### インストール方法

**Windows (PowerShell)**:
```powershell
iwr https://railway.app/install.ps1 | iex
```

**macOS/Linux**:
```bash
sh <(curl -sSL https://railway.app/install.sh)
```

### 使い方

1. **ログイン**:
   ```bash
   railway login
   ```

2. **プロジェクトをリンク**:
   ```bash
   railway link
   ```
   → プロジェクトID: `c93898e1-5fe6-4fd7-b81d-33cb31b8addf`

3. **コマンド実行**:
   ```bash
   railway run python weather_forecast_collector.py
   railway run python improved_ferry_collector.py
   ```

これで本番環境のDBに直接データが書き込まれます！

---

## Cronジョブを手動で追加する方法

もし`railway.json`のCron設定が反映されていない場合:

### Railway管理画面で

1. **左サイドバー → 「+」ボタン**

2. **「Add Cron Job」を選択**

3. **設定**:
   - **Name**: forecast_collection_morning
   - **Command**: `python weather_forecast_collector.py`
   - **Schedule**: `0 20 * * *` (UTC 20:00 = JST 05:00)

4. これを7個のジョブ全てについて繰り返す

---

## 推奨アクション

1. **まずRailway CLIをインストール** ← 最も簡単
2. `railway run`でデータ収集を実行
3. Cronジョブを手動で追加
4. 以降は自動で毎日実行される

---

**次のステップ**: Railway CLIインストールを試しますか？
