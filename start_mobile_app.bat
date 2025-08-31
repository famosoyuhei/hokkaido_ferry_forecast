@echo off
echo 📱 北海道フェリー予測システム - モバイルWebアプリ
echo.
echo 🚀 Webサーバーを起動しています...
echo.

REM 必要なパッケージをインストール
echo 📦 必要なパッケージをインストール中...
pip install flask

REM IPアドレス取得・表示
echo 🌐 ネットワーク情報:
ipconfig | findstr "IPv4"
echo.

echo 📱 スマホでアクセス方法:
echo    1. パソコンとスマホを同じWiFiに接続
echo    2. 上記のIPアドレスを確認
echo    3. スマホブラウザで http://[IPアドレス]:5000 にアクセス
echo    例: http://192.168.1.100:5000
echo.
echo 💻 パソコンでアクセス: http://localhost:5000
echo.
echo ⌨️  Ctrl+C で終了
echo.

REM Pythonアプリ起動
python mobile_web_app.py

pause