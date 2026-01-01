#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フェリー監視システムセットアップスクリプト
Ferry Monitoring System Setup Script
"""

import subprocess
import sys
from pathlib import Path

def install_requirements():
    """必要なパッケージをインストール"""
    additional_packages = [
        'beautifulsoup4>=4.9.0',
        'schedule>=1.1.0',
        'lxml>=4.6.0'
    ]
    
    print("追加パッケージをインストールしています...")
    for package in additional_packages:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"✓ {package} インストール完了")
        except subprocess.CalledProcessError as e:
            print(f"✗ {package} インストール失敗: {e}")

def create_directories():
    """必要なディレクトリを作成"""
    base_dir = Path(__file__).parent
    directories = [
        base_dir / "data",
        base_dir / "logs"
    ]
    
    for directory in directories:
        directory.mkdir(exist_ok=True)
        print(f"✓ ディレクトリ作成: {directory}")

def main():
    print("=== フェリー監視システムセットアップ ===")
    
    # ディレクトリ作成
    create_directories()
    
    # パッケージインストール
    install_requirements()
    
    print("\n=== セットアップ完了 ===")
    print("使用方法:")
    print("  python ferry_monitoring_system.py")
    
if __name__ == "__main__":
    main()