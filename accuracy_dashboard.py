#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Accuracy Improvement Dashboard
Web-based dashboard to visualize prediction accuracy trends
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from flask import Flask, render_template, jsonify
import sqlite3
import pandas as pd
import json
from datetime import datetime, timedelta
from pathlib import Path
import os

app = Flask(__name__)

# Database paths
data_dir = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '.')
accuracy_db = os.path.join(data_dir, "prediction_accuracy.db")

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('accuracy_dashboard.html')

@app.route('/api/performance/current')
def get_current_performance():
    """Get current performance metrics"""

    try:
        conn = sqlite3.connect(accuracy_db)
        query = '''
            SELECT * FROM model_performance
            ORDER BY evaluation_date DESC LIMIT 1
        '''
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            return jsonify({'error': 'No performance data available'})

        perf = df.iloc[0]

        return jsonify({
            'accuracy': float(perf['accuracy_rate']),
            'precision': float(perf['precision_score']),
            'recall': float(perf['recall_score']),
            'f1_score': float(perf['f1_score']),
            'mae': float(perf['mean_absolute_error']),
            'rmse': float(perf['root_mean_squared_error']),
            'calibration': float(perf['calibration_score']),
            'total_predictions': int(perf['total_predictions']),
            'correct_predictions': int(perf['correct_predictions']),
            'evaluation_date': perf['evaluation_date']
        })

    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/performance/trend')
def get_performance_trend():
    """Get performance trend over time"""

    try:
        conn = sqlite3.connect(accuracy_db)
        query = '''
            SELECT
                evaluation_date,
                accuracy_rate,
                precision_score,
                recall_score,
                f1_score
            FROM model_performance
            ORDER BY evaluation_date ASC
        '''
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            return jsonify({'error': 'No trend data available'})

        return jsonify({
            'dates': df['evaluation_date'].tolist(),
            'accuracy': df['accuracy_rate'].tolist(),
            'precision': df['precision_score'].tolist(),
            'recall': df['recall_score'].tolist(),
            'f1_score': df['f1_score'].tolist()
        })

    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/matches/recent')
def get_recent_matches():
    """Get recent prediction matches"""

    try:
        conn = sqlite3.connect(accuracy_db)
        query = '''
            SELECT
                match_date,
                route,
                predicted_risk_level,
                predicted_risk_score,
                actual_status,
                prediction_correct,
                false_positive,
                false_negative
            FROM prediction_matches
            ORDER BY match_date DESC
            LIMIT 50
        '''
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            return jsonify({'error': 'No match data available'})

        return jsonify({
            'matches': df.to_dict(orient='records')
        })

    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/thresholds/current')
def get_current_thresholds():
    """Get current risk thresholds"""

    # Default thresholds
    thresholds = {
        'wind_speed': 15.0,
        'wave_height': 3.0,
        'visibility': 1.0,
        'temperature': -10.0
    }

    try:
        conn = sqlite3.connect(accuracy_db)

        # Get most recent adjustments for each parameter
        for param in thresholds.keys():
            query = f'''
                SELECT new_value FROM threshold_adjustments
                WHERE parameter_name = ?
                ORDER BY adjustment_date DESC LIMIT 1
            '''
            cursor = conn.cursor()
            cursor.execute(query, (param,))
            row = cursor.fetchone()

            if row:
                thresholds[param] = float(row[0])

        conn.close()

        return jsonify(thresholds)

    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/thresholds/history')
def get_threshold_history():
    """Get threshold adjustment history"""

    try:
        conn = sqlite3.connect(accuracy_db)
        query = '''
            SELECT
                adjustment_date,
                parameter_name,
                old_value,
                new_value,
                reason
            FROM threshold_adjustments
            ORDER BY adjustment_date DESC
            LIMIT 20
        '''
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            return jsonify({'adjustments': []})

        return jsonify({
            'adjustments': df.to_dict(orient='records')
        })

    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/confusion_matrix')
def get_confusion_matrix():
    """Get confusion matrix data"""

    try:
        conn = sqlite3.connect(accuracy_db)
        query = '''
            SELECT
                SUM(CASE WHEN actual_cancellation = 1 AND predicted_cancellation = 1 THEN 1 ELSE 0 END) as tp,
                SUM(CASE WHEN actual_cancellation = 0 AND predicted_cancellation = 0 THEN 1 ELSE 0 END) as tn,
                SUM(CASE WHEN false_positive = 1 THEN 1 ELSE 0 END) as fp,
                SUM(CASE WHEN false_negative = 1 THEN 1 ELSE 0 END) as fn
            FROM prediction_matches
        '''
        cursor = conn.cursor()
        cursor.execute(query)
        row = cursor.fetchone()
        conn.close()

        return jsonify({
            'true_positive': int(row[0]) if row[0] else 0,
            'true_negative': int(row[1]) if row[1] else 0,
            'false_positive': int(row[2]) if row[2] else 0,
            'false_negative': int(row[3]) if row[3] else 0
        })

    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/route_performance')
def get_route_performance():
    """Get performance breakdown by route"""

    try:
        conn = sqlite3.connect(accuracy_db)
        query = '''
            SELECT
                route,
                COUNT(*) as total,
                SUM(CASE WHEN prediction_correct = 1 THEN 1 ELSE 0 END) as correct,
                AVG(prediction_error) as avg_error
            FROM prediction_matches
            GROUP BY route
        '''
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            return jsonify({'routes': []})

        df['accuracy'] = df['correct'] / df['total']

        return jsonify({
            'routes': df.to_dict(orient='records')
        })

    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    templates_dir = Path('templates')
    templates_dir.mkdir(exist_ok=True)

    # Create HTML template
    html_template = '''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>予測精度ダッシュボード - フェリー運航予報</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Hiragino Sans', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: #333;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        header {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 20px;
        }
        h1 { color: #667eea; font-size: 2em; margin-bottom: 10px; }
        .subtitle { color: #666; font-size: 1.1em; }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .metric-card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            text-align: center;
        }
        .metric-value {
            font-size: 3em;
            font-weight: bold;
            color: #667eea;
            margin: 10px 0;
        }
        .metric-label {
            color: #666;
            font-size: 1.1em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .chart-container {
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .chart-title {
            font-size: 1.5em;
            color: #667eea;
            margin-bottom: 20px;
            text-align: center;
        }
        .status-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: bold;
        }
        .status-excellent { background: #10b981; color: white; }
        .status-good { background: #3b82f6; color: white; }
        .status-fair { background: #f59e0b; color: white; }
        .status-poor { background: #ef4444; color: white; }
        .refresh-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1em;
            margin: 20px 0;
        }
        .refresh-btn:hover { background: #5568d3; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: #f3f4f6;
            font-weight: bold;
            color: #667eea;
        }
        .correct { color: #10b981; font-weight: bold; }
        .incorrect { color: #ef4444; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 予測精度改善ダッシュボード</h1>
            <p class="subtitle">フェリー運航予報の精度をリアルタイムで監視・改善</p>
            <button class="refresh-btn" onclick="loadAllData()">🔄 データ更新</button>
        </header>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">精度</div>
                <div class="metric-value" id="accuracy">--%</div>
                <div id="accuracy-status"></div>
            </div>
            <div class="metric-card">
                <div class="metric-label">適合率</div>
                <div class="metric-value" id="precision">--%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">再現率</div>
                <div class="metric-value" id="recall">--%</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">F1スコア</div>
                <div class="metric-value" id="f1score">--</div>
            </div>
        </div>

        <div class="chart-container">
            <h2 class="chart-title">📈 精度トレンド (時系列)</h2>
            <canvas id="trendChart"></canvas>
        </div>

        <div class="chart-container">
            <h2 class="chart-title">🎯 混同行列</h2>
            <canvas id="confusionChart"></canvas>
        </div>

        <div class="chart-container">
            <h2 class="chart-title">🛳️ 航路別パフォーマンス</h2>
            <canvas id="routeChart"></canvas>
        </div>

        <div class="chart-container">
            <h2 class="chart-title">📋 最近の予測マッチング</h2>
            <div id="recentMatches"></div>
        </div>

        <div class="chart-container">
            <h2 class="chart-title">⚙️ 閾値調整履歴</h2>
            <div id="thresholdHistory"></div>
        </div>
    </div>

    <script>
        let trendChart, confusionChart, routeChart;

        async function loadCurrentPerformance() {
            try {
                const response = await fetch('/api/performance/current');
                const data = await response.json();

                if (data.error) {
                    console.error(data.error);
                    return;
                }

                document.getElementById('accuracy').textContent = (data.accuracy * 100).toFixed(1) + '%';
                document.getElementById('precision').textContent = (data.precision * 100).toFixed(1) + '%';
                document.getElementById('recall').textContent = (data.recall * 100).toFixed(1) + '%';
                document.getElementById('f1score').textContent = data.f1_score.toFixed(3);

                // Status badge
                const accuracy = data.accuracy;
                let statusHtml = '';
                if (accuracy >= 0.85) {
                    statusHtml = '<span class="status-badge status-excellent">優秀</span>';
                } else if (accuracy >= 0.75) {
                    statusHtml = '<span class="status-badge status-good">良好</span>';
                } else if (accuracy >= 0.60) {
                    statusHtml = '<span class="status-badge status-fair">要改善</span>';
                } else {
                    statusHtml = '<span class="status-badge status-poor">改善必要</span>';
                }
                document.getElementById('accuracy-status').innerHTML = statusHtml;

            } catch (error) {
                console.error('Error loading performance:', error);
            }
        }

        async function loadTrendChart() {
            try {
                const response = await fetch('/api/performance/trend');
                const data = await response.json();

                if (data.error) return;

                const ctx = document.getElementById('trendChart').getContext('2d');

                if (trendChart) trendChart.destroy();

                trendChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: data.dates,
                        datasets: [{
                            label: '精度',
                            data: data.accuracy.map(v => v * 100),
                            borderColor: '#667eea',
                            backgroundColor: 'rgba(102, 126, 234, 0.1)',
                            tension: 0.4
                        }, {
                            label: '適合率',
                            data: data.precision.map(v => v * 100),
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            tension: 0.4
                        }, {
                            label: '再現率',
                            data: data.recall.map(v => v * 100),
                            borderColor: '#f59e0b',
                            backgroundColor: 'rgba(245, 158, 11, 0.1)',
                            tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: 'top' }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 100,
                                ticks: { callback: value => value + '%' }
                            }
                        }
                    }
                });

            } catch (error) {
                console.error('Error loading trend chart:', error);
            }
        }

        async function loadConfusionMatrix() {
            try {
                const response = await fetch('/api/confusion_matrix');
                const data = await response.json();

                if (data.error) return;

                const ctx = document.getElementById('confusionChart').getContext('2d');

                if (confusionChart) confusionChart.destroy();

                confusionChart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: ['真陽性', '真陰性', '偽陽性', '偽陰性'],
                        datasets: [{
                            label: '予測結果',
                            data: [data.true_positive, data.true_negative, data.false_positive, data.false_negative],
                            backgroundColor: ['#10b981', '#3b82f6', '#f59e0b', '#ef4444']
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { display: false }
                        }
                    }
                });

            } catch (error) {
                console.error('Error loading confusion matrix:', error);
            }
        }

        async function loadRoutePerformance() {
            try {
                const response = await fetch('/api/route_performance');
                const data = await response.json();

                if (data.error || !data.routes.length) return;

                const ctx = document.getElementById('routeChart').getContext('2d');

                if (routeChart) routeChart.destroy();

                routeChart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: data.routes.map(r => r.route),
                        datasets: [{
                            label: '精度',
                            data: data.routes.map(r => r.accuracy * 100),
                            backgroundColor: '#667eea'
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 100,
                                ticks: { callback: value => value + '%' }
                            }
                        }
                    }
                });

            } catch (error) {
                console.error('Error loading route performance:', error);
            }
        }

        async function loadRecentMatches() {
            try {
                const response = await fetch('/api/matches/recent');
                const data = await response.json();

                if (data.error) return;

                let html = '<table><thead><tr><th>日付</th><th>航路</th><th>予測</th><th>実績</th><th>結果</th></tr></thead><tbody>';

                data.matches.slice(0, 20).forEach(match => {
                    const resultClass = match.prediction_correct ? 'correct' : 'incorrect';
                    const resultText = match.prediction_correct ? '✓ 正解' : '✗ 不正解';

                    html += `<tr>
                        <td>${match.match_date}</td>
                        <td>${match.route}</td>
                        <td>${match.predicted_risk_level} (${match.predicted_risk_score.toFixed(0)}%)</td>
                        <td>${match.actual_status}</td>
                        <td class="${resultClass}">${resultText}</td>
                    </tr>`;
                });

                html += '</tbody></table>';
                document.getElementById('recentMatches').innerHTML = html;

            } catch (error) {
                console.error('Error loading recent matches:', error);
            }
        }

        async function loadThresholdHistory() {
            try {
                const response = await fetch('/api/thresholds/history');
                const data = await response.json();

                if (!data.adjustments || !data.adjustments.length) {
                    document.getElementById('thresholdHistory').innerHTML = '<p>閾値調整履歴はまだありません</p>';
                    return;
                }

                let html = '<table><thead><tr><th>日付</th><th>パラメータ</th><th>変更前</th><th>変更後</th><th>理由</th></tr></thead><tbody>';

                data.adjustments.forEach(adj => {
                    html += `<tr>
                        <td>${adj.adjustment_date}</td>
                        <td>${adj.parameter_name}</td>
                        <td>${adj.old_value.toFixed(2)}</td>
                        <td>${adj.new_value.toFixed(2)}</td>
                        <td>${adj.reason}</td>
                    </tr>`;
                });

                html += '</tbody></table>';
                document.getElementById('thresholdHistory').innerHTML = html;

            } catch (error) {
                console.error('Error loading threshold history:', error);
            }
        }

        function loadAllData() {
            loadCurrentPerformance();
            loadTrendChart();
            loadConfusionMatrix();
            loadRoutePerformance();
            loadRecentMatches();
            loadThresholdHistory();
        }

        // Initial load
        window.addEventListener('load', loadAllData);

        // Auto-refresh every 60 seconds
        setInterval(loadAllData, 60000);
    </script>
</body>
</html>'''

    template_file = templates_dir / 'accuracy_dashboard.html'
    template_file.write_text(html_template, encoding='utf-8')

    print("="*80)
    print("ACCURACY DASHBOARD SERVER")
    print("="*80)
    print("\n✓ Dashboard starting...")
    print("\nAccess the dashboard at:")
    print("  http://localhost:5001")
    print("\nPress Ctrl+C to stop the server")
    print("="*80 + "\n")

    app.run(host='0.0.0.0', port=5001, debug=True)
