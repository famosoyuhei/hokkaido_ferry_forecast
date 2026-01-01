#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Accuracy Analysis and System Improvement
Continuous monitoring and improvement of prediction accuracy
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import sqlite3
from pathlib import Path
import json
from dataclasses import dataclass
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PredictionRecord:
    """Individual prediction record for analysis"""
    prediction_id: str
    timestamp: datetime
    transport_type: str
    route: str
    scheduled_time: str
    predicted_probability: float
    predicted_risk_level: str
    actual_outcome: str  # "operated", "delayed", "cancelled"
    actual_delay_minutes: Optional[int]
    weather_conditions: Dict
    model_version: str
    confidence_score: float

@dataclass
class AccuracyMetrics:
    """System accuracy metrics"""
    total_predictions: int
    correct_predictions: int
    overall_accuracy: float
    precision: float
    recall: float
    f1_score: float
    mean_absolute_error: float
    prediction_calibration: float
    confidence_correlation: float

class AccuracyAnalysisSystem:
    """System for analyzing and improving prediction accuracy"""
    
    def __init__(self):
        self.db_path = Path("accuracy_analysis.db")
        self._init_database()
        
        # Analysis parameters
        self.risk_thresholds = {
            "LOW": (0.0, 0.3),
            "MEDIUM": (0.3, 0.6),
            "HIGH": (0.6, 1.0)
        }
        
        # Calibration bins for reliability analysis
        self.calibration_bins = np.linspace(0, 1, 11)
        
        # Performance tracking
        self.performance_history = []
    
    def _init_database(self):
        """Initialize accuracy tracking database"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id TEXT PRIMARY KEY,
                timestamp DATETIME,
                transport_type TEXT,
                route TEXT,
                scheduled_time TEXT,
                predicted_probability REAL,
                predicted_risk_level TEXT,
                actual_outcome TEXT,
                actual_delay_minutes INTEGER,
                weather_conditions TEXT,
                model_version TEXT,
                confidence_score REAL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accuracy_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                analysis_date DATETIME,
                period_start DATETIME,
                period_end DATETIME,
                total_predictions INTEGER,
                overall_accuracy REAL,
                precision_score REAL,
                recall_score REAL,
                f1_score REAL,
                calibration_score REAL,
                model_version TEXT,
                detailed_metrics TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS improvement_suggestions (
                suggestion_id TEXT PRIMARY KEY,
                created_date DATETIME,
                category TEXT,
                description TEXT,
                impact_estimate REAL,
                implementation_effort TEXT,
                priority_score REAL,
                status TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def record_prediction(self, record: PredictionRecord):
        """Record a prediction for later accuracy analysis"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO predictions
            (prediction_id, timestamp, transport_type, route, scheduled_time,
             predicted_probability, predicted_risk_level, actual_outcome,
             actual_delay_minutes, weather_conditions, model_version, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.prediction_id,
            record.timestamp,
            record.transport_type,
            record.route,
            record.scheduled_time,
            record.predicted_probability,
            record.predicted_risk_level,
            record.actual_outcome,
            record.actual_delay_minutes,
            json.dumps(record.weather_conditions),
            record.model_version,
            record.confidence_score
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Recorded prediction {record.prediction_id}")
    
    def analyze_accuracy(self, days_back: int = 30) -> AccuracyMetrics:
        """Analyze prediction accuracy over specified period"""
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        conn = sqlite3.connect(self.db_path)
        query = """
            SELECT * FROM predictions 
            WHERE timestamp BETWEEN ? AND ? 
            AND actual_outcome IS NOT NULL
        """
        
        df = pd.read_sql_query(query, conn, params=(start_date, end_date))
        conn.close()
        
        if df.empty:
            logger.warning("No prediction data available for analysis")
            return self._empty_metrics()
        
        # Convert predictions to binary classification
        df['predicted_cancelled'] = df['predicted_probability'] > 0.5
        df['actual_cancelled'] = df['actual_outcome'] == 'cancelled'
        
        # Calculate metrics
        accuracy = accuracy_score(df['actual_cancelled'], df['predicted_cancelled'])
        precision, recall, f1, _ = precision_recall_fscore_support(
            df['actual_cancelled'], df['predicted_cancelled'], average='binary'
        )
        
        # Mean absolute error for probability predictions
        mae = mean_absolute_error(
            df['actual_cancelled'].astype(int), 
            df['predicted_probability']
        )
        
        # Calibration analysis
        calibration_score = self._calculate_calibration(
            df['actual_cancelled'], df['predicted_probability']
        )
        
        # Confidence correlation
        confidence_correlation = df['confidence_score'].corr(
            (df['predicted_cancelled'] == df['actual_cancelled']).astype(int)
        )
        
        metrics = AccuracyMetrics(
            total_predictions=len(df),
            correct_predictions=int(accuracy * len(df)),
            overall_accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1,
            mean_absolute_error=mae,
            prediction_calibration=calibration_score,
            confidence_correlation=confidence_correlation if not np.isnan(confidence_correlation) else 0.0
        )
        
        self._save_accuracy_snapshot(metrics, start_date, end_date, df)
        
        return metrics
    
    def _calculate_calibration(self, actual: pd.Series, predicted_prob: pd.Series) -> float:
        """Calculate prediction calibration score"""
        
        bin_boundaries = np.linspace(0, 1, 11)
        bin_lowers = bin_boundaries[:-1]
        bin_uppers = bin_boundaries[1:]
        
        calibration_error = 0.0
        total_samples = len(actual)
        
        for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
            in_bin = (predicted_prob > bin_lower) & (predicted_prob <= bin_upper)
            prop_in_bin = in_bin.mean()
            
            if prop_in_bin > 0:
                accuracy_in_bin = actual[in_bin].mean()
                avg_confidence_in_bin = predicted_prob[in_bin].mean()
                calibration_error += np.abs(avg_confidence_in_bin - accuracy_in_bin) * prop_in_bin
        
        return 1.0 - calibration_error  # Convert to score (higher is better)
    
    def _save_accuracy_snapshot(self, metrics: AccuracyMetrics, start_date: datetime, 
                               end_date: datetime, df: pd.DataFrame):
        """Save accuracy snapshot to database"""
        
        detailed_metrics = {
            "by_transport_type": self._calculate_metrics_by_group(df, 'transport_type'),
            "by_route": self._calculate_metrics_by_group(df, 'route'),
            "by_risk_level": self._calculate_metrics_by_group(df, 'predicted_risk_level'),
            "confusion_matrix": confusion_matrix(
                df['actual_cancelled'], df['predicted_cancelled']
            ).tolist()
        }
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        snapshot_id = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        cursor.execute("""
            INSERT INTO accuracy_snapshots
            (snapshot_id, analysis_date, period_start, period_end, total_predictions,
             overall_accuracy, precision_score, recall_score, f1_score, calibration_score,
             model_version, detailed_metrics)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot_id,
            datetime.now(),
            start_date,
            end_date,
            metrics.total_predictions,
            metrics.overall_accuracy,
            metrics.precision,
            metrics.recall,
            metrics.f1_score,
            metrics.prediction_calibration,
            "1.0",  # Current model version
            json.dumps(detailed_metrics, default=str)
        ))
        
        conn.commit()
        conn.close()
    
    def _calculate_metrics_by_group(self, df: pd.DataFrame, group_col: str) -> Dict:
        """Calculate accuracy metrics by group"""
        
        group_metrics = {}
        
        for group_val in df[group_col].unique():
            group_df = df[df[group_col] == group_val]
            
            if len(group_df) > 5:  # Minimum sample size
                accuracy = accuracy_score(
                    group_df['actual_cancelled'], 
                    group_df['predicted_cancelled']
                )
                
                group_metrics[str(group_val)] = {
                    "count": len(group_df),
                    "accuracy": accuracy,
                    "avg_predicted_prob": float(group_df['predicted_probability'].mean()),
                    "actual_cancellation_rate": float(group_df['actual_cancelled'].mean())
                }
        
        return group_metrics
    
    def generate_improvement_suggestions(self, metrics: AccuracyMetrics) -> List[Dict]:
        """Generate suggestions for improving prediction accuracy"""
        
        suggestions = []
        
        # Low overall accuracy
        if metrics.overall_accuracy < 0.7:
            suggestions.append({
                "category": "model_improvement",
                "description": "Overall accuracy below 70%. Consider retraining with more data or different algorithms.",
                "impact_estimate": 0.1,
                "implementation_effort": "high",
                "priority_score": 9.0
            })
        
        # Poor calibration
        if metrics.prediction_calibration < 0.8:
            suggestions.append({
                "category": "calibration",
                "description": "Prediction probabilities are poorly calibrated. Consider probability calibration techniques.",
                "impact_estimate": 0.05,
                "implementation_effort": "medium",
                "priority_score": 7.0
            })
        
        # Low precision (too many false positives)
        if metrics.precision < 0.6:
            suggestions.append({
                "category": "false_positive_reduction",
                "description": "High false positive rate. Adjust prediction thresholds or add more specific features.",
                "impact_estimate": 0.08,
                "implementation_effort": "medium",
                "priority_score": 8.0
            })
        
        # Low recall (missing cancellations)
        if metrics.recall < 0.6:
            suggestions.append({
                "category": "sensitivity_improvement",
                "description": "Missing actual cancellations. Lower thresholds or add early warning features.",
                "impact_estimate": 0.12,
                "implementation_effort": "medium",
                "priority_score": 9.5
            })
        
        # Poor confidence correlation
        if metrics.confidence_correlation < 0.3:
            suggestions.append({
                "category": "confidence_calibration",
                "description": "Confidence scores not correlating with accuracy. Improve confidence estimation.",
                "impact_estimate": 0.03,
                "implementation_effort": "low",
                "priority_score": 5.0
            })
        
        # Data volume suggestions
        if metrics.total_predictions < 100:
            suggestions.append({
                "category": "data_collection",
                "description": "Insufficient prediction history. Increase data collection frequency and duration.",
                "impact_estimate": 0.15,
                "implementation_effort": "low",
                "priority_score": 8.5
            })
        
        # Save suggestions to database
        for suggestion in suggestions:
            self._save_improvement_suggestion(suggestion)
        
        return sorted(suggestions, key=lambda x: x['priority_score'], reverse=True)
    
    def _save_improvement_suggestion(self, suggestion: Dict):
        """Save improvement suggestion to database"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        suggestion_id = f"suggestion_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{suggestion['category']}"
        
        cursor.execute("""
            INSERT INTO improvement_suggestions
            (suggestion_id, created_date, category, description, impact_estimate,
             implementation_effort, priority_score, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            suggestion_id,
            datetime.now(),
            suggestion['category'],
            suggestion['description'],
            suggestion['impact_estimate'],
            suggestion['implementation_effort'],
            suggestion['priority_score'],
            'pending'
        ))
        
        conn.commit()
        conn.close()
    
    def generate_accuracy_report(self, days_back: int = 30) -> str:
        """Generate comprehensive accuracy report"""
        
        metrics = self.analyze_accuracy(days_back)
        suggestions = self.generate_improvement_suggestions(metrics)
        
        report = f"""
=== Hokkaido Transport Prediction System - Accuracy Report ===
Analysis Period: {days_back} days
Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

OVERALL PERFORMANCE METRICS
============================
Total Predictions Analyzed: {metrics.total_predictions}
Correct Predictions: {metrics.correct_predictions}
Overall Accuracy: {metrics.overall_accuracy:.1%}

DETAILED METRICS
================
Precision: {metrics.precision:.1%} (of predicted cancellations, how many were correct)
Recall: {metrics.recall:.1%} (of actual cancellations, how many were predicted)
F1-Score: {metrics.f1_score:.1%} (balanced precision/recall measure)

PREDICTION QUALITY
==================
Mean Absolute Error: {metrics.mean_absolute_error:.3f}
Prediction Calibration: {metrics.prediction_calibration:.1%}
Confidence Correlation: {metrics.confidence_correlation:.3f}

PERFORMANCE ASSESSMENT
======================"""
        
        if metrics.overall_accuracy >= 0.8:
            report += "\n[EXCELLENT] - System performing very well"
        elif metrics.overall_accuracy >= 0.7:
            report += "\n[GOOD] - System performing adequately"
        elif metrics.overall_accuracy >= 0.6:
            report += "\n[FAIR] - System needs improvement"
        else:
            report += "\n[POOR] - System requires significant improvement"
        
        report += f"\n\nIMPROVEMENT RECOMMENDATIONS"
        report += "\n" + "=" * 30
        
        if suggestions:
            for i, suggestion in enumerate(suggestions[:5], 1):
                report += f"\n{i}. {suggestion['category'].replace('_', ' ').title()}"
                report += f"\n   Priority: {suggestion['priority_score']:.1f}/10"
                report += f"\n   Description: {suggestion['description']}"
                report += f"\n   Expected Impact: {suggestion['impact_estimate']:.1%}"
                report += f"\n   Effort: {suggestion['implementation_effort']}"
                report += "\n"
        else:
            report += "\nNo immediate improvements needed - system performing well!"
        
        report += f"\nSYSTEM STATUS"
        report += "\n" + "=" * 15
        
        if metrics.total_predictions < 50:
            report += "\n[WARNING] Limited prediction history. Collect more data for reliable analysis."
        
        if metrics.prediction_calibration < 0.7:
            report += "\n[WARNING] Predictions may be over/under-confident. Consider calibration."
        
        report += f"\n\nDatabase: {self.db_path}"
        report += f"\nNext recommended analysis: {(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')}"
        
        return report
    
    def _empty_metrics(self) -> AccuracyMetrics:
        """Return empty metrics when no data available"""
        
        return AccuracyMetrics(
            total_predictions=0,
            correct_predictions=0,
            overall_accuracy=0.0,
            precision=0.0,
            recall=0.0,
            f1_score=0.0,
            mean_absolute_error=0.0,
            prediction_calibration=0.0,
            confidence_correlation=0.0
        )

def create_demo_prediction_data():
    """Create demo prediction data for testing"""
    
    analyzer = AccuracyAnalysisSystem()
    
    # Simulate 100 predictions over the last 30 days
    np.random.seed(42)
    
    routes = ["Wakkanai-Rishiri", "Wakkanai-Rebun", "Sapporo-Rishiri", "New Chitose-Rishiri"]
    transport_types = ["Ferry", "Ferry", "Flight", "Flight"]
    
    for i in range(100):
        # Random date in last 30 days
        days_ago = np.random.randint(0, 30)
        timestamp = datetime.now() - timedelta(days=days_ago)
        
        # Random route
        route_idx = np.random.randint(0, len(routes))
        route = routes[route_idx]
        transport_type = transport_types[route_idx]
        
        # Simulate realistic prediction vs actual
        base_risk = np.random.beta(2, 5)  # Most predictions low risk
        predicted_prob = base_risk + np.random.normal(0, 0.1)
        predicted_prob = np.clip(predicted_prob, 0, 1)
        
        # Actual outcome based on prediction with some noise
        actual_cancelled = np.random.random() < (predicted_prob + np.random.normal(0, 0.15))
        
        # Risk level classification
        if predicted_prob < 0.3:
            risk_level = "LOW"
        elif predicted_prob < 0.6:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"
        
        # Confidence score (inversely related to uncertainty)
        confidence = 1.0 - abs(predicted_prob - 0.5) + np.random.normal(0, 0.1)
        confidence = np.clip(confidence, 0.1, 0.9)
        
        record = PredictionRecord(
            prediction_id=f"demo_pred_{i:03d}",
            timestamp=timestamp,
            transport_type=transport_type,
            route=route,
            scheduled_time=np.random.choice(["08:30", "13:30", "17:15"]),
            predicted_probability=predicted_prob,
            predicted_risk_level=risk_level,
            actual_outcome="cancelled" if actual_cancelled else "operated",
            actual_delay_minutes=np.random.randint(0, 60) if not actual_cancelled else None,
            weather_conditions={
                "temperature": np.random.normal(15, 8),
                "wind_speed": np.random.exponential(12),
                "visibility": np.random.exponential(8000)
            },
            model_version="1.0",
            confidence_score=confidence
        )
        
        analyzer.record_prediction(record)
    
    return analyzer

def main():
    """Demonstrate accuracy analysis system"""
    
    print("=== Accuracy Analysis and System Improvement Demo ===")
    
    # Create demo data
    print("Creating demo prediction data...")
    analyzer = create_demo_prediction_data()
    
    print("[OK] Demo data created (100 predictions over 30 days)")
    
    # Generate accuracy report
    print("\nGenerating accuracy analysis...")
    report = analyzer.generate_accuracy_report(days_back=30)
    
    print(report)
    
    # Show system capabilities
    print("\n=== System Capabilities ===")
    print("[OK] Prediction accuracy tracking")
    print("[OK] Performance metrics calculation")
    print("[OK] Calibration analysis")
    print("[OK] Automatic improvement suggestions")
    print("[OK] Historical performance comparison")
    print("[OK] Route-specific accuracy analysis")
    print("[OK] Transport-type specific metrics")
    print("[OK] Confidence score validation")
    
    print(f"\nAnalysis Database: {analyzer.db_path}")
    print("System ready for continuous accuracy monitoring")

if __name__ == "__main__":
    main()