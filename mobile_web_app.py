#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
北海道フェリー予測システム - モバイルWebアプリ
Hokkaido Ferry Prediction System - Mobile Web App

スマホ対応のWebインターフェース
"""

from flask import Flask, render_template, jsonify, request, send_from_directory
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
import logging

# 既存システムのインポート
from ferry_forecast_ui import FerryForecastUI
from data_collection_manager import DataCollectionManager
from adaptive_prediction_system import AdaptivePredictionSystem

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ferry_forecast_secret_key_2025'

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# システム初期化
base_dir = Path(__file__).parent
data_dir = base_dir / "data"
ui_system = FerryForecastUI()
data_manager = DataCollectionManager(data_dir)
adaptive_system = AdaptivePredictionSystem(data_dir)

@app.route('/')
def index():
    """メインページ"""
    return render_template('index.html')

@app.route('/api/forecast')
def get_forecast():
    """7日間予報データAPI"""
    try:
        # 7日間予報データを生成
        from generate_forecast_data import ForecastDataGenerator
        generator = ForecastDataGenerator()
        forecast_data = generator.generate_7day_forecast()
        
        return jsonify({
            "success": True,
            "forecast_data": forecast_data,
            "generated_at": datetime.now().isoformat(),
            "total_days": len(forecast_data)
        })
        
    except Exception as e:
        logger.error(f"予報API エラー: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/forecast/<date>')
def get_forecast_by_date(date):
    """指定日の予報データAPI"""
    try:
        from generate_forecast_data import ForecastDataGenerator
        generator = ForecastDataGenerator()
        forecast_data = generator.generate_7day_forecast()
        
        if date in forecast_data:
            return jsonify({
                "success": True,
                "date_data": forecast_data[date],
                "generated_at": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "success": False,
                "error": f"Date {date} not found in forecast data"
            }), 404
            
    except Exception as e:
        logger.error(f"日別予報API エラー: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/status')
def get_system_status():
    """システム状況API"""
    try:
        # データ収集状況
        data_status = data_manager.get_current_status()
        
        # 予測パラメータ
        prediction_params = adaptive_system.get_current_prediction_parameters()
        
        # 適応レポート
        adaptation_report = adaptive_system.generate_adaptation_report()
        
        return jsonify({
            "success": True,
            "data_status": data_status,
            "prediction_params": prediction_params,
            "adaptation_report": adaptation_report,
            "updated_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"ステータスAPI エラー: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/routes')
def get_routes():
    """航路情報API"""
    try:
        routes_data = []
        for route_id, route_info in ui_system.schedules.items():
            route_data = {
                "id": route_id,
                "name": route_info.get("route_name", route_id),
                "schedules": route_info.get("schedules", {})
            }
            routes_data.append(route_data)
        
        return jsonify({
            "success": True,
            "routes": routes_data
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/forecast')
def forecast_page():
    """予報ページ"""
    return render_template('forecast.html')

@app.route('/status')
def status_page():
    """システム状況ページ"""
    return render_template('status.html')

@app.route('/about')
def about_page():
    """システム情報ページ"""
    return render_template('about.html')

# 静的ファイル配信（開発用）
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('templates/static', filename)

def create_templates():
    """HTMLテンプレート作成"""
    templates_dir = base_dir / "templates"
    static_dir = templates_dir / "static"
    templates_dir.mkdir(exist_ok=True)
    static_dir.mkdir(exist_ok=True)
    
    # ベーステンプレート
    base_template = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}北海道フェリー予測システム{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="manifest" href="{{ url_for('static_files', filename='manifest.json') }}">
    <meta name="theme-color" content="#007bff">
    <style>
        body { padding-top: 56px; }
        .risk-low { color: #28a745; }
        .risk-medium { color: #ffc107; }
        .risk-high { color: #fd7e14; }
        .risk-critical { color: #dc3545; }
        .weather-info { font-size: 0.9em; color: #6c757d; }
        .route-card { margin-bottom: 1rem; }
        .forecast-card { border-left: 4px solid #dee2e6; }
        .forecast-card.risk-low { border-left-color: #28a745; }
        .forecast-card.risk-medium { border-left-color: #ffc107; }
        .forecast-card.risk-high { border-left-color: #fd7e14; }
        .forecast-card.risk-critical { border-left-color: #dc3545; }
    </style>
</head>
<body>
    <!-- ナビゲーション -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary fixed-top">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('index') }}">フェリー予報</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('index') }}">ホーム</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('forecast_page') }}">予報</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('status_page') }}">システム状況</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('about_page') }}">について</a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>

    <!-- メインコンテンツ -->
    <div class="container mt-4">
        {% block content %}{% endblock %}
    </div>

    <!-- フッター -->
    <footer class="bg-light text-center py-3 mt-5">
        <div class="container">
            <small>&copy; 2025 北海道フェリー予測システム</small>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>"""
    
    with open(templates_dir / "base.html", "w", encoding="utf-8") as f:
        f.write(base_template)
    
    # インデックスページ
    index_template = """{% extends "base.html" %}
{% block content %}
<div class="row">
    <div class="col-12">
        <div class="jumbotron bg-primary text-white p-4 rounded mb-4">
            <h1 class="display-4">北海道フェリー予測システム</h1>
            <p class="lead">稚内⇔利尻島・礼文島の運航予報をお届けします</p>
            <hr class="my-4">
            <p>気象条件を分析し、7日間の運航予報を提供。データ蓄積により予測精度が向上します。</p>
        </div>
    </div>
</div>

<div class="row">
    <div class="col-md-6 mb-4">
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">📅 7日間予報</h5>
                <p class="card-text">各航路・各便の詳細な運航予報を確認できます。</p>
                <a href="{{ url_for('forecast_page') }}" class="btn btn-primary">予報を見る</a>
            </div>
        </div>
    </div>
    
    <div class="col-md-6 mb-4">
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">システム状況</h5>
                <p class="card-text">データ蓄積状況と予測精度を確認できます。</p>
                <a href="{{ url_for('status_page') }}" class="btn btn-success">状況を見る</a>
            </div>
        </div>
    </div>
</div>

<div class="row">
    <div class="col-12">
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0">🚀 システム特徴</h5>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-4 mb-3">
                        <h6>⚡ 段階的精度向上</h6>
                        <small class="text-muted">データ蓄積に応じて自動的に予測精度が向上</small>
                    </div>
                    <div class="col-md-4 mb-3">
                        <h6>適応的学習</h6>
                        <small class="text-muted">実績データから自動的に予測基準を調整</small>
                    </div>
                    <div class="col-md-4 mb-3">
                        <h6>冬季特化</h6>
                        <small class="text-muted">流氷・降雪・低温など冬季条件に特化</small>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<div id="system-status" class="mt-4">
    <!-- システム状況がここに読み込まれます -->
</div>

<script>
// システム状況を取得して表示
fetch('/api/status')
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const statusHtml = `
                <div class="alert alert-info">
                    <h6>現在のシステム状況</h6>
                    <p><strong>予測段階:</strong> ${data.prediction_params.stage}</p>
                    <p><strong>データ数:</strong> ${data.data_status.current_count}件</p>
                    <p><strong>信頼度:</strong> ${Math.round(data.prediction_params.confidence_base * 100)}%</p>
                </div>
            `;
            document.getElementById('system-status').innerHTML = statusHtml;
        }
    })
    .catch(error => console.error('Error:', error));
</script>
{% endblock %}"""
    
    with open(templates_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(index_template)
    
    # 予報ページ（日付タブ付き、便ごと表示、欠航目立つ表示）
    forecast_template = """{% extends "base.html" %}
{% block title %}7日間運航予報 - 北海道フェリー予測システム{% endblock %}
{% block content %}
<div class="row">
    <div class="col-12">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <div>
                <h2>7日間運航予報</h2>
                <p class="text-muted mb-0">ハートランドフェリー 利尻・礼文航路 (毎日18便)</p>
            </div>
            <div>
                <button class="btn btn-success" onclick="loadForecast()" id="refresh-btn">
                    <i class="bi bi-arrow-clockwise"></i> 更新
                </button>
                <small class="text-muted d-block mt-1" id="last-update">最終更新: --:--</small>
            </div>
        </div>
    </div>
</div>

<!-- 日付タブ -->
<div class="row mb-4">
    <div class="col-12">
        <nav>
            <div class="nav nav-tabs" id="date-tabs" role="tablist">
                <!-- 日付タブがここに動的生成される -->
            </div>
        </nav>
    </div>
</div>

<!-- 予報概要 -->
<div id="forecast-summary" class="row mb-3" style="display:none;">
    <div class="col-md-3">
        <div class="card bg-light">
            <div class="card-body text-center">
                <h6 class="card-title">総便数</h6>
                <h4 id="total-services" class="text-primary">--</h4>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card bg-success bg-opacity-10">
            <div class="card-body text-center">
                <h6 class="card-title">正常運航予定</h6>
                <h4 id="normal-services" class="text-success">--</h4>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card bg-warning bg-opacity-10">
            <div class="card-body text-center">
                <h6 class="card-title">要注意便</h6>
                <h4 id="warning-services" class="text-warning">--</h4>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card bg-danger bg-opacity-10">
            <div class="card-body text-center">
                <h6 class="card-title">欠航リスク</h6>
                <h4 id="high-risk-services" class="text-danger">--</h4>
            </div>
        </div>
    </div>
</div>

<div id="loading" class="text-center">
    <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">読み込み中...</span>
    </div>
    <p class="mt-2">7日間の運航予報データを取得中...</p>
</div>

<div id="forecast-container">
    <div class="tab-content" id="date-content">
        <!-- 各日の予報データがここに読み込まれます -->
    </div>
</div>

<script>
let forecastData = {};
let currentDate = null;
let autoRefreshInterval = null;

function loadForecast() {
    // ローディング表示
    document.getElementById('loading').style.display = 'block';
    document.getElementById('forecast-summary').style.display = 'none';
    document.getElementById('forecast-container').innerHTML = '';
    
    // 更新ボタン無効化
    document.getElementById('refresh-btn').disabled = true;
    
    fetch('/api/7day_forecast')
        .then(response => response.json())
        .then(data => {
            forecastData = data.forecast_data || {};
            
            // 統計情報表示
            updateSummaryStats();
            
            // 日付タブ作成
            createDateTabs();
            
            // 最初の日を表示
            const dates = Object.keys(forecastData).sort();
            if (dates.length > 0) {
                showDateForecast(dates[0]);
                currentDate = dates[0];
            }
            
            // ローディング終了
            document.getElementById('loading').style.display = 'none';
            document.getElementById('forecast-summary').style.display = 'block';
            document.getElementById('forecast-container').style.display = 'block';
            
            // 更新時刻表示
            updateLastUpdateTime();
        })
        .catch(error => {
            console.error('Error loading forecast:', error);
            document.getElementById('loading').innerHTML = 
                '<div class="alert alert-danger">予報データの読み込みに失敗しました</div>';
        })
        .finally(() => {
            document.getElementById('refresh-btn').disabled = false;
        });
}

function updateSummaryStats() {
    let totalServices = 0;
    let warningServices = 0;
    let highRiskServices = 0;
    
    for (const date in forecastData) {
        const dayData = forecastData[date];
        totalServices += dayData.services.length;
        
        dayData.services.forEach(service => {
            const riskLevel = service.risk.risk_level;
            if (riskLevel === 'High' || riskLevel === 'Critical') {
                highRiskServices++;
            } else if (riskLevel === 'Medium') {
                warningServices++;
            }
        });
    }
    
    document.getElementById('total-services').textContent = totalServices;
    document.getElementById('warning-services').textContent = warningServices;
    document.getElementById('high-risk-services').textContent = highRiskServices;
}

function createDateTabs() {
    const dates = Object.keys(forecastData).sort();
    let tabsHtml = '<ul class="nav nav-tabs mb-3" id="date-tabs">';
    
    dates.forEach((date, index) => {
        const dayData = forecastData[date];
        const activeClass = index === 0 ? 'active' : '';
        
        tabsHtml += `
            <li class="nav-item">
                <button class="nav-link ${activeClass}" onclick="showDateForecast('${date}')" 
                        data-date="${date}">
                    ${dayData.date_display}
                    <br>
                    <small class="text-muted">${dayData.weekday}曜日</small>
                </button>
            </li>
        `;
    });
    
    tabsHtml += '</ul>';
    document.getElementById('forecast-container').innerHTML = tabsHtml + '<div id="date-content"></div>';
}

function showDateForecast(date) {
    currentDate = date;
    
    // タブのアクティブ状態更新
    document.querySelectorAll('#date-tabs .nav-link').forEach(tab => {
        tab.classList.remove('active');
        if (tab.dataset.date === date) {
            tab.classList.add('active');
        }
    });
    
    const dayData = forecastData[date];
    if (!dayData) return;
    
    let servicesHtml = '<div class="row g-3">';
    
    dayData.services.forEach(service => {
        const risk = service.risk;
        const weather = service.weather;
        const riskScore = Math.round(risk.risk_score);
        
        let cardClass = 'border-success';
        let badgeClass = 'bg-success';
        let riskIcon = '✓';
        let alertBanner = '';
        
        if (risk.risk_level === 'Critical') {
            cardClass = 'border-danger';
            badgeClass = 'bg-danger';
            riskIcon = '🚫';
            alertBanner = `
                <div class="alert alert-danger mb-2 py-2" role="alert">
                    <strong>欠航リスク極高 (${riskScore}%)</strong>
                </div>
            `;
        } else if (risk.risk_level === 'High') {
            cardClass = 'border-warning';
            badgeClass = 'bg-warning';
            riskIcon = '!';
            alertBanner = `
                <div class="alert alert-warning mb-2 py-2" role="alert">
                    <strong>欠航リスク高 (${riskScore}%)</strong>
                </div>
            `;
        } else if (risk.risk_level === 'Medium') {
            cardClass = 'border-info';
            badgeClass = 'bg-info';
            riskIcon = '⚡';
        }
        
        const riskFactorsText = risk.risk_factors.length > 0 
            ? risk.risk_factors.join(', ') 
            : '良好';
            
        servicesHtml += `
            <div class="col-md-6 col-lg-4">
                <div class="card ${cardClass} h-100">
                    ${alertBanner}
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <strong>${service.route_name}</strong>
                        <span class="badge ${badgeClass}">${riskIcon} ${risk.risk_level}</span>
                    </div>
                    <div class="card-body">
                        <div class="row mb-2">
                            <div class="col-6">
                                <small class="text-muted">出航</small><br>
                                <strong>${service.departure_time}</strong>
                            </div>
                            <div class="col-6">
                                <small class="text-muted">到着</small><br>
                                <strong>${service.arrival_time}</strong>
                            </div>
                        </div>
                        
                        <hr>
                        
                        <div class="small">
                            <div class="d-flex justify-content-between">
                                <span>欠航リスク:</span>
                                <span class="fw-bold">${riskScore}%</span>
                            </div>
                            <div class="d-flex justify-content-between">
                                <span>風速:</span>
                                <span>${weather.wind_speed}m/s</span>
                            </div>
                            <div class="d-flex justify-content-between">
                                <span>波高:</span>
                                <span>${weather.wave_height}m</span>
                            </div>
                            <div class="d-flex justify-content-between">
                                <span>視界:</span>
                                <span>${weather.visibility}km</span>
                            </div>
                            <div class="d-flex justify-content-between">
                                <span>気温:</span>
                                <span>${weather.temperature}°C</span>
                            </div>
                            ${risk.risk_factors.length > 0 ? 
                                `<div class="mt-2"><small class="text-warning">${riskFactorsText}</small></div>` 
                                : ''
                            }
                        </div>
                    </div>
                    <div class="card-footer small text-muted">
                        ${service.vessel} | 便${service.service_no}
                    </div>
                </div>
            </div>
        `;
    });
    
    servicesHtml += '</div>';
    document.getElementById('date-content').innerHTML = servicesHtml;
}

function updateLastUpdateTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('ja-JP', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    document.getElementById('last-update').textContent = timeString;
}

// 自動更新設定
function setupAutoRefresh() {
    // 5分間隔で自動更新
    autoRefreshInterval = setInterval(() => {
        loadForecast();
    }, 5 * 60 * 1000);
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

// 手動更新
function refreshForecast() {
    loadForecast();
}

// ページ読み込み時の初期化
document.addEventListener('DOMContentLoaded', function() {
    loadForecast();
    setupAutoRefresh();
});

// ページを離れる時の処理
window.addEventListener('beforeunload', function() {
    stopAutoRefresh();
});
</script>
</body>
</html>
'''
    
    with open(templates_dir / "forecast.html", "w", encoding="utf-8") as f:
        f.write(forecast_template)
    
    # システム状況ページ
    status_template = """{% extends "base.html" %}
{% block title %}システム状況 - 北海道フェリー予測システム{% endblock %}
{% block content %}
<div class="row">
    <div class="col-12">
        <h2>システム状況</h2>
        <p class="text-muted">データ蓄積状況と予測精度の確認</p>
    </div>
</div>

<div id="loading" class="text-center">
    <div class="spinner-border" role="status">
        <span class="visually-hidden">読み込み中...</span>
    </div>
    <p>システム状況を取得中...</p>
</div>

<div id="status-container">
    <!-- システム状況がここに読み込まれます -->
</div>

<script>
function loadStatus() {
    document.getElementById('loading').style.display = 'block';
    
    fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            document.getElementById('loading').style.display = 'none';
            
            if (data.success) {
                displayStatus(data);
            } else {
                document.getElementById('status-container').innerHTML = 
                    '<div class="alert alert-danger">システム状況の取得に失敗しました</div>';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            document.getElementById('loading').style.display = 'none';
            document.getElementById('status-container').innerHTML = 
                '<div class="alert alert-danger">ネットワークエラーが発生しました</div>';
        });
}

function displayStatus(data) {
    const container = document.getElementById('status-container');
    
    const progress = (data.data_status.current_count / data.data_status.max_count) * 100;
    
    let html = `
        <!-- データ収集状況 -->
        <div class="card mb-4">
            <div class="card-header">
                <h5 class="mb-0">データ収集状況</h5>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-6">
                        <p><strong>収集データ数:</strong> ${data.data_status.current_count}件 / ${data.data_status.max_count}件</p>
                        <div class="progress mb-3">
                            <div class="progress-bar" style="width: ${progress}%">${progress.toFixed(1)}%</div>
                        </div>
                        <p><strong>状態:</strong> <span class="badge bg-${getStatusBadgeColor(data.data_status.status)}">${data.data_status.message}</span></p>
                    </div>
                    <div class="col-md-6">
                        <p><strong>最終更新:</strong> ${new Date(data.data_status.last_updated).toLocaleString('ja-JP')}</p>
                        <p><strong>自動停止:</strong> ${data.data_status.auto_stop_enabled ? '✅ 有効' : '❌ 無効'}</p>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 予測システム状況 -->
        <div class="card mb-4">
            <div class="card-header">
                <h5 class="mb-0">予測システム状況</h5>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-6">
                        <p><strong>予測段階:</strong> ${data.prediction_params.stage}</p>
                        <p><strong>予測手法:</strong> ${data.prediction_params.prediction_method}</p>
                        <p><strong>信頼度:</strong> ${Math.round(data.prediction_params.confidence_base * 100)}%</p>
                    </div>
                    <div class="col-md-6">
                        <p><strong>段階進捗:</strong> ${Math.round(data.prediction_params.progress * 100)}%</p>
                        <p><strong>適応調整回数:</strong> ${data.prediction_params.adaptation_count}回</p>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // 適応レポート
    if (data.adaptation_report && !data.adaptation_report.error) {
        html += `
            <div class="card mb-4">
                <div class="card-header">
                    <h5 class="mb-0">適応システムレポート</h5>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <p><strong>システム成熟度:</strong> ${data.adaptation_report.system_maturity}</p>
                            <p><strong>信頼度レベル:</strong> ${data.adaptation_report.confidence_level}</p>
                        </div>
                        <div class="col-md-6">
                            <p><strong>段階進捗:</strong> ${data.adaptation_report.stage_progress}</p>
                        </div>
                    </div>
                    
                    ${data.adaptation_report.recommendations ? `
                    <h6>推奨事項</h6>
                    <ul>
                        ${data.adaptation_report.recommendations.map(rec => `<li>${rec}</li>`).join('')}
                    </ul>
                    ` : ''}
                    
                    ${data.adaptation_report.threshold_changes && data.adaptation_report.threshold_changes.length > 0 ? `
                    <h6>閾値調整履歴</h6>
                    <div class="table-responsive">
                        <table class="table table-sm">
                            <thead>
                                <tr>
                                    <th>条件</th>
                                    <th>レベル</th>
                                    <th>変更率</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${data.adaptation_report.threshold_changes.slice(0, 5).map(change => `
                                <tr>
                                    <td>${change.condition}</td>
                                    <td>${change.level}</td>
                                    <td>${change.change_percent > 0 ? '+' : ''}${change.change_percent.toFixed(1)}%</td>
                                </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;
    }
    
    container.innerHTML = html;
}

function getStatusBadgeColor(status) {
    const colors = {
        'COMPLETED': 'success',
        'NEAR_COMPLETION': 'warning',
        'LEARNING_ACTIVE': 'info',
        'COLLECTING': 'primary',
        'NOT_STARTED': 'secondary'
    };
    return colors[status] || 'secondary';
}

// 初回読み込み
loadStatus();

// 30秒ごとに自動更新
setInterval(loadStatus, 30000);
</script>
{% endblock %}"""
    
    with open(templates_dir / "status.html", "w", encoding="utf-8") as f:
        f.write(status_template)
    
    # システム情報ページ
    about_template = """{% extends "base.html" %}
{% block title %}システム情報 - 北海道フェリー予測システム{% endblock %}
{% block content %}
<div class="row">
    <div class="col-12">
        <h2>システム情報</h2>
        <p class="text-muted">北海道フェリー予測システムについて</p>
    </div>
</div>

<div class="card mb-4">
    <div class="card-header">
        <h5 class="mb-0">システム概要</h5>
    </div>
    <div class="card-body">
        <p>北海道フェリー予測システムは、稚内⇔利尻島・礼文島間のフェリー運航状況を予測するシステムです。</p>
        <ul>
            <li>気象条件を分析して運航リスクを評価</li>
            <li>データ蓄積により予測精度が段階的に向上</li>
            <li>冬季の厳しい条件（流氷・降雪・低温）に特化</li>
        </ul>
    </div>
</div>

<div class="card mb-4">
    <div class="card-header">
        <h5 class="mb-0">対象航路</h5>
    </div>
    <div class="card-body">
        <div class="row">
            <div class="col-md-4">
                <h6>稚内 ⇔ 鴛泊</h6>
                <small class="text-muted">利尻島（鴛泊港）</small>
            </div>
            <div class="col-md-4">
                <h6>稚内 ⇔ 沓形</h6>
                <small class="text-muted">利尻島（沓形港）</small>
            </div>
            <div class="col-md-4">
                <h6>稚内 ⇔ 香深</h6>
                <small class="text-muted">礼文島（香深港）</small>
            </div>
        </div>
    </div>
</div>

<div class="card mb-4">
    <div class="card-header">
        <h5 class="mb-0">⚡ 予測精度の進化</h5>
    </div>
    <div class="card-body">
        <div class="row">
            <div class="col-md-3">
                <div class="text-center">
                    <h6 class="text-muted">初期段階</h6>
                    <p class="h4">0-49件</p>
                    <small>気象条件ルールベース</small>
                </div>
            </div>
            <div class="col-md-3">
                <div class="text-center">
                    <h6 class="text-primary">学習段階</h6>
                    <p class="h4">50-199件</p>
                    <small>ルール + 基本機械学習</small>
                </div>
            </div>
            <div class="col-md-3">
                <div class="text-center">
                    <h6 class="text-success">成熟段階</h6>
                    <p class="h4">200-499件</p>
                    <small>ハイブリッド予測</small>
                </div>
            </div>
            <div class="col-md-3">
                <div class="text-center">
                    <h6 class="text-warning">完成段階</h6>
                    <p class="h4">500件+</p>
                    <small>高精度機械学習</small>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="card mb-4">
    <div class="card-header">
        <h5 class="mb-0">分析要素</h5>
    </div>
    <div class="card-body">
        <div class="row">
            <div class="col-md-6">
                <h6>基本気象要素</h6>
                <ul>
                    <li>💨 風速・風向</li>
                    <li>🌊 波高予報</li>
                    <li>視界（霧・降雪）</li>
                    <li>気温</li>
                </ul>
            </div>
            <div class="col-md-6">
                <h6>冬季特化要素</h6>
                <ul>
                    <li>流氷情報</li>
                    <li>降雪・吹雪</li>
                    <li>🧊 船体凍結リスク</li>
                    <li>⛄ 港湾設備凍結</li>
                </ul>
            </div>
        </div>
    </div>
</div>

<div class="card">
    <div class="card-header">
        <h5 class="mb-0">モバイル対応</h5>
    </div>
    <div class="card-body">
        <p>このWebアプリはスマートフォン・タブレットに最適化されています。</p>
        <ul>
            <li>レスポンシブデザイン</li>
            <li>⚡ 軽量・高速読み込み</li>
            <li>リアルタイム更新</li>
            <li>📶 オフライン対応（予定）</li>
        </ul>
        <p><small class="text-muted">ホーム画面に追加してアプリのように使用できます。</small></p>
    </div>
</div>
{% endblock %}"""
    
    with open(templates_dir / "about.html", "w", encoding="utf-8") as f:
        f.write(about_template)
    
    # PWA Manifest
    manifest = {
        "name": "北海道フェリー予測システム",
        "short_name": "フェリー予報",
        "description": "稚内⇔利尻島・礼文島の運航予報",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#007bff",
        "icons": [
            {
                "src": "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTkyIiBoZWlnaHQ9IjE5MiIgdmlld0JveD0iMCAwIDEyOCAxMjgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIxMjgiIGhlaWdodD0iMTI4IiBmaWxsPSIjMDA3YmZmIi8+Cjx0ZXh0IHg9IjY0IiB5PSI4MCIgZm9udC1zaXplPSI2NCIgdGV4dC1hbmNob3I9Im1pZGRsZSI+8J+agzwvdGV4dD4KPHN2Zz4K",
                "sizes": "192x192",
                "type": "image/svg+xml"
            }
        ]
    }
    
    with open(static_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    print("HTML templates created successfully")

def main():
    """メイン実行"""
    print("Hokkaido Ferry Forecast System - Mobile Web App")
    
    # テンプレート作成
    create_templates()
    
    # サーバー起動
    print("\nStarting Web Server...")
    print("Mobile Access:")
    print("   - Same WiFi: http://[PC_IP_ADDRESS]:5000")
    print("   - Local: http://localhost:5000")
    print("\nTo test on mobile:")
    print("   1. Connect PC and phone to same WiFi")
    print("   2. Check PC IP address (ipconfig)")
    print("   3. Access http://IP_ADDRESS:5000 on phone browser")
    print("\nPress Ctrl+C to stop")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        print("\nWeb server stopped")

if __name__ == "__main__":
    main()