#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Mobile Web App for Ferry Forecast
"""

import json
import os
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request
from generate_forecast_data import ForecastDataGenerator

app = Flask(__name__)
app.secret_key = 'ferry_forecast_secret_key_2025'

@app.route('/')
def index():
    return render_template_string(INDEX_TEMPLATE)

@app.route('/api/7day_forecast')
def api_7day_forecast():
    """7日間予報API"""
    try:
        generator = ForecastDataGenerator()
        forecast_data = generator.generate_7day_forecast()
        
        return jsonify({
            'success': True,
            'generated_at': generator.generate_7day_forecast.__doc__ or 'Generated',
            'forecast_data': forecast_data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Simple HTML template without problematic Unicode characters
INDEX_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ferry Forecast System</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
    .risk-critical { border-left: 5px solid #dc3545; box-shadow: 0 0 10px rgba(220,53,69,0.3); }
    .risk-high { border-left: 5px solid #fd7e14; }
    .risk-medium { border-left: 5px solid #ffc107; }
    .risk-low { border-left: 5px solid #198754; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-primary">
        <div class="container">
            <span class="navbar-brand">Ferry Forecast System</span>
        </div>
    </nav>
    
    <div class="container mt-3">
        <div class="row">
            <div class="col-12">
                <h2>7-Day Ferry Operation Forecast</h2>
                <p class="text-muted">Real-time ferry operation predictions for Hokkaido routes</p>
            </div>
        </div>
        
        <!-- Summary Cards -->
        <div id="forecast-summary" class="row mb-4" style="display: none;">
            <div class="col-md-3">
                <div class="card bg-primary bg-opacity-10">
                    <div class="card-body text-center">
                        <h6 class="card-title">Total Services</h6>
                        <h4 id="total-services" class="text-primary">--</h4>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-success bg-opacity-10">
                    <div class="card-body text-center">
                        <h6 class="card-title">Normal Operation</h6>
                        <h4 id="normal-services" class="text-success">--</h4>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-warning bg-opacity-10">
                    <div class="card-body text-center">
                        <h6 class="card-title">Caution</h6>
                        <h4 id="warning-services" class="text-warning">--</h4>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-danger bg-opacity-10">
                    <div class="card-body text-center">
                        <h6 class="card-title">High Risk</h6>
                        <h4 id="high-risk-services" class="text-danger">--</h4>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Control buttons -->
        <div class="row mb-3">
            <div class="col">
                <button id="refresh-btn" class="btn btn-outline-primary" onclick="refreshForecast()">
                    Refresh Data
                </button>
                <small class="text-muted ms-3">Last update: <span id="last-update">--</span></small>
            </div>
        </div>
        
        <!-- Loading -->
        <div id="loading" class="text-center">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2">Loading 7-day forecast data...</p>
        </div>
        
        <!-- Forecast Container -->
        <div id="forecast-container">
            <div class="tab-content" id="date-content">
                <!-- Forecast data will be loaded here -->
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
    let forecastData = {};
    let currentDate = null;
    let autoRefreshInterval = null;

    function loadForecast() {
        document.getElementById('loading').style.display = 'block';
        document.getElementById('forecast-summary').style.display = 'none';
        document.getElementById('forecast-container').innerHTML = '';
        document.getElementById('refresh-btn').disabled = true;
        
        fetch('/api/7day_forecast')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    forecastData = data.forecast_data || {};
                    updateSummaryStats();
                    createDateTabs();
                    
                    const dates = Object.keys(forecastData).sort();
                    if (dates.length > 0) {
                        showDateForecast(dates[0]);
                        currentDate = dates[0];
                    }
                    
                    document.getElementById('loading').style.display = 'none';
                    document.getElementById('forecast-summary').style.display = 'flex';
                    document.getElementById('forecast-container').style.display = 'block';
                    updateLastUpdateTime();
                } else {
                    document.getElementById('loading').innerHTML = 
                        '<div class="alert alert-danger">Failed to load forecast data: ' + (data.error || 'Unknown error') + '</div>';
                }
            })
            .catch(error => {
                console.error('Error loading forecast:', error);
                document.getElementById('loading').innerHTML = 
                    '<div class="alert alert-danger">Network error occurred while loading forecast data</div>';
            })
            .finally(() => {
                document.getElementById('refresh-btn').disabled = false;
            });
    }

    function updateSummaryStats() {
        let totalServices = 0;
        let normalServices = 0;
        let warningServices = 0;
        let highRiskServices = 0;
        
        for (const date in forecastData) {
            const dayData = forecastData[date];
            totalServices += dayData.services.length;
            
            dayData.services.forEach(service => {
                const riskLevel = service.risk.risk_level;
                if (riskLevel === 'Critical') {
                    highRiskServices++;
                } else if (riskLevel === 'High') {
                    warningServices++;
                } else if (riskLevel === 'Medium') {
                    warningServices++;
                } else {
                    normalServices++;
                }
            });
        }
        
        document.getElementById('total-services').textContent = totalServices;
        document.getElementById('normal-services').textContent = normalServices;
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
                        <small class="text-muted">${dayData.weekday}day</small>
                    </button>
                </li>
            `;
        });
        
        tabsHtml += '</ul>';
        document.getElementById('forecast-container').innerHTML = tabsHtml + '<div id="date-content"></div>';
    }

    function showDateForecast(date) {
        currentDate = date;
        
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
            
            let cardClass = 'border-success risk-low';
            let badgeClass = 'bg-success';
            let riskIcon = 'OK';
            let alertBanner = '';
            
            if (risk.risk_level === 'Critical') {
                cardClass = 'border-danger risk-critical';
                badgeClass = 'bg-danger';
                riskIcon = 'CANCEL';
                alertBanner = `
                    <div class="alert alert-danger mb-2 py-2" role="alert">
                        <strong>CRITICAL CANCELLATION RISK (${riskScore}%)</strong>
                    </div>
                `;
            } else if (risk.risk_level === 'High') {
                cardClass = 'border-warning risk-high';
                badgeClass = 'bg-warning';
                riskIcon = 'HIGH';
                alertBanner = `
                    <div class="alert alert-warning mb-2 py-2" role="alert">
                        <strong>HIGH CANCELLATION RISK (${riskScore}%)</strong>
                    </div>
                `;
            } else if (risk.risk_level === 'Medium') {
                cardClass = 'border-info risk-medium';
                badgeClass = 'bg-info';
                riskIcon = 'CAUTION';
            }
            
            const riskFactorsText = risk.risk_factors.length > 0 
                ? risk.risk_factors.join(', ') 
                : 'Good conditions';
                
            servicesHtml += `
                <div class="col-md-6 col-lg-4">
                    <div class="card ${cardClass} h-100">
                        ${alertBanner}
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <strong>${service.route_name}</strong>
                            <span class="badge ${badgeClass}">${riskIcon}</span>
                        </div>
                        <div class="card-body">
                            <div class="row mb-2">
                                <div class="col-6">
                                    <small class="text-muted">Departure</small><br>
                                    <strong>${service.departure_time}</strong>
                                </div>
                                <div class="col-6">
                                    <small class="text-muted">Arrival</small><br>
                                    <strong>${service.arrival_time}</strong>
                                </div>
                            </div>
                            
                            <hr>
                            
                            <div class="small">
                                <div class="d-flex justify-content-between">
                                    <span>Cancel Risk:</span>
                                    <span class="fw-bold">${riskScore}%</span>
                                </div>
                                <div class="d-flex justify-content-between">
                                    <span>Wind:</span>
                                    <span>${weather.wind_speed}m/s</span>
                                </div>
                                <div class="d-flex justify-content-between">
                                    <span>Wave:</span>
                                    <span>${weather.wave_height}m</span>
                                </div>
                                <div class="d-flex justify-content-between">
                                    <span>Visibility:</span>
                                    <span>${weather.visibility}km</span>
                                </div>
                                <div class="d-flex justify-content-between">
                                    <span>Temperature:</span>
                                    <span>${weather.temperature}°C</span>
                                </div>
                                ${risk.risk_factors.length > 0 ? 
                                    `<div class="mt-2"><small class="text-warning">Risk: ${riskFactorsText}</small></div>` 
                                    : ''
                                }
                            </div>
                        </div>
                        <div class="card-footer small text-muted">
                            ${service.vessel} | Service #${service.service_no}
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
        const timeString = now.toLocaleTimeString();
        document.getElementById('last-update').textContent = timeString;
    }

    function setupAutoRefresh() {
        autoRefreshInterval = setInterval(() => {
            loadForecast();
        }, 5 * 60 * 1000); // 5 minutes
    }

    function stopAutoRefresh() {
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
            autoRefreshInterval = null;
        }
    }

    function refreshForecast() {
        loadForecast();
    }

    // Initialize on page load
    document.addEventListener('DOMContentLoaded', function() {
        loadForecast();
        setupAutoRefresh();
    });

    // Clean up on page unload
    window.addEventListener('beforeunload', function() {
        stopAutoRefresh();
    });
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    print("Ferry Forecast System - Simple Mobile Web App")
    print("Starting server on http://localhost:5000")
    print("Access from mobile: http://[YOUR_IP]:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=True)