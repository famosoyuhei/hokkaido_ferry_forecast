#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streamlit Test Application
Simple test to verify Streamlit functionality
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

def main():
    st.title("🚢✈️ 北海道交通予報システム - テスト版")
    st.markdown("**Hokkaido Transport Prediction System - Test Version**")
    
    st.write("システムテスト実行中...")
    
    # Test basic functionality
    st.subheader("基本機能テスト")
    
    # Test date input
    test_date = st.date_input("テスト日付", datetime.now().date())
    st.write(f"選択日付: {test_date}")
    
    # Test slider
    test_temp = st.slider("テスト気温", -10, 35, 20)
    st.write(f"気温: {test_temp}°C")
    
    # Test data display
    st.subheader("データ表示テスト")
    
    test_data = pd.DataFrame({
        'Transport': ['Ferry', 'Flight'],
        'Cancellation Risk': ['25%', '15%'],
        'Status': ['Medium Risk', 'Low Risk']
    })
    
    st.table(test_data)
    
    # Test metrics
    st.subheader("メトリックステスト")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("フェリー欠航リスク", "25%", "-5%")
    
    with col2:
        st.metric("航空便欠航リスク", "15%", "+3%")
    
    with col3:
        st.metric("システム信頼度", "78%", "+2%")
    
    st.success("✅ Streamlitアプリケーション動作確認完了")
    
    # Show system info
    st.subheader("システム情報")
    st.write(f"Streamlit version: {st.__version__}")
    st.write(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()