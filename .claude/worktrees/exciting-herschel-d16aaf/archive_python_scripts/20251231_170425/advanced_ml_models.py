#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Machine Learning Models for Transport Prediction
Ensemble learning with multiple algorithms for enhanced accuracy
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
import xgboost as xgb
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pickle
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AdvancedTransportPredictor:
    """Advanced ML-based transport prediction system"""
    
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.feature_importance = {}
        self.training_history = []
        
        # Initialize model components
        self._init_models()
        
    def _init_models(self):
        """Initialize ML models"""
        
        # Random Forest with optimized parameters
        self.rf_model = RandomForestClassifier(
            n_estimators=200,
            max_depth=15,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            class_weight='balanced'
        )
        
        # Gradient Boosting
        self.gb_model = GradientBoostingClassifier(
            n_estimators=150,
            learning_rate=0.1,
            max_depth=8,
            random_state=42
        )
        
        # XGBoost
        self.xgb_model = xgb.XGBClassifier(
            n_estimators=200,
            learning_rate=0.1,
            max_depth=8,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42
        )
        
        # Logistic Regression
        self.lr_model = LogisticRegression(
            random_state=42,
            class_weight='balanced',
            max_iter=1000
        )
        
        # Support Vector Machine
        self.svm_model = SVC(
            kernel='rbf',
            probability=True,
            random_state=42,
            class_weight='balanced'
        )
        
        # Ensemble voting classifier
        self.ensemble_model = VotingClassifier(
            estimators=[
                ('rf', self.rf_model),
                ('gb', self.gb_model),
                ('xgb', self.xgb_model),
                ('lr', self.lr_model)
            ],
            voting='soft'
        )
        
        # Store all models
        self.models = {
            'random_forest': self.rf_model,
            'gradient_boosting': self.gb_model,
            'xgboost': self.xgb_model,
            'logistic_regression': self.lr_model,
            'svm': self.svm_model,
            'ensemble': self.ensemble_model
        }
    
    def generate_synthetic_training_data(self, n_samples: int = 1000) -> Tuple[pd.DataFrame, pd.Series]:
        """Generate synthetic training data for initial model development"""
        
        logger.info(f"Generating {n_samples} synthetic training samples...")
        
        np.random.seed(42)
        
        # Generate weather features
        data = {
            # Basic weather
            'temperature': np.random.normal(15, 8, n_samples),
            'humidity': np.random.uniform(40, 100, n_samples),
            'wind_speed': np.random.exponential(8, n_samples),
            'wind_direction': np.random.uniform(0, 360, n_samples),
            'visibility': np.random.exponential(8000, n_samples),
            'pressure': np.random.normal(1015, 15, n_samples),
            'precipitation': np.random.exponential(1, n_samples),
            
            # Advanced features
            'pressure_tendency': np.random.normal(0, 2, n_samples),
            'temperature_change_24h': np.random.normal(0, 3, n_samples),
            'wind_gust': np.random.exponential(12, n_samples),
            'sea_temperature': np.random.normal(12, 6, n_samples),
            
            # Temporal features
            'hour': np.random.randint(0, 24, n_samples),
            'month': np.random.randint(1, 13, n_samples),
            'day_of_week': np.random.randint(0, 7, n_samples),
            'season': np.random.randint(1, 5, n_samples),  # 1=spring, 2=summer, 3=autumn, 4=winter
            
            # Location features
            'transport_type': np.random.choice(['ferry', 'flight'], n_samples),
            'route_type': np.random.choice(['short', 'medium', 'long'], n_samples),
            'departure_time_category': np.random.choice(['morning', 'afternoon', 'evening'], n_samples),
            
            # Terrain/geographic features
            'karman_vortex_risk': np.random.uniform(0, 1, n_samples),
            'sea_state': np.random.randint(1, 7, n_samples),  # Beaufort scale
            'terrain_shielding': np.random.uniform(0, 1, n_samples)
        }
        
        df = pd.DataFrame(data)
        
        # Generate cancellation labels based on realistic rules
        cancellation_prob = np.zeros(n_samples)
        
        # Weather-based cancellation rules
        cancellation_prob += np.where(df['wind_speed'] > 25, 0.6, 0)
        cancellation_prob += np.where(df['visibility'] < 1000, 0.7, 0)
        cancellation_prob += np.where(df['precipitation'] > 10, 0.4, 0)
        cancellation_prob += np.where(df['wind_gust'] > 35, 0.5, 0)
        
        # Fog conditions (high humidity + low wind + cool temp)
        fog_condition = (df['humidity'] > 90) & (df['wind_speed'] < 5) & (df['temperature'] < 10)
        cancellation_prob += np.where(fog_condition, 0.8, 0)
        
        # Pressure drop (frontal passage)
        cancellation_prob += np.where(df['pressure_tendency'] < -5, 0.3, 0)
        
        # Karman vortex effects for flights
        flight_mask = df['transport_type'] == 'flight'
        cancellation_prob += np.where(flight_mask & (df['karman_vortex_risk'] > 0.7), 0.4, 0)
        
        # Sea state effects for ferries
        ferry_mask = df['transport_type'] == 'ferry'
        cancellation_prob += np.where(ferry_mask & (df['sea_state'] > 5), 0.6, 0)
        
        # Seasonal adjustments
        winter_mask = df['month'].isin([12, 1, 2])
        cancellation_prob += np.where(winter_mask, 0.15, 0)
        
        summer_mask = df['month'].isin([6, 7, 8])
        cancellation_prob += np.where(summer_mask & (df['transport_type'] == 'flight'), -0.1, 0)
        
        # Time of day effects
        early_morning = df['hour'].isin([4, 5, 6, 7])
        cancellation_prob += np.where(early_morning & (df['humidity'] > 85), 0.3, 0)  # Morning fog
        
        # Cap probabilities
        cancellation_prob = np.clip(cancellation_prob, 0, 1)
        
        # Generate binary labels
        labels = np.random.binomial(1, cancellation_prob, n_samples)
        
        # Encode categorical variables
        le_transport = LabelEncoder()
        le_route = LabelEncoder()
        le_departure = LabelEncoder()
        
        df['transport_type'] = le_transport.fit_transform(df['transport_type'])
        df['route_type'] = le_route.fit_transform(df['route_type'])
        df['departure_time_category'] = le_departure.fit_transform(df['departure_time_category'])
        
        logger.info(f"Generated dataset with {labels.sum()} cancellations out of {n_samples} samples ({labels.mean():.1%} cancellation rate)")
        
        return df, pd.Series(labels)
    
    def train_models(self, X: pd.DataFrame, y: pd.Series, test_size: float = 0.2):
        """Train all ML models"""
        
        logger.info("Starting model training...")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )
        
        # Scale features
        self.scalers['standard'] = StandardScaler()
        X_train_scaled = self.scalers['standard'].fit_transform(X_train)
        X_test_scaled = self.scalers['standard'].transform(X_test)
        
        # Train each model
        results = {}
        
        for name, model in self.models.items():
            logger.info(f"Training {name}...")
            
            try:
                # Use scaled data for SVM and Logistic Regression
                if name in ['svm', 'logistic_regression']:
                    model.fit(X_train_scaled, y_train)
                    y_pred = model.predict(X_test_scaled)
                    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
                else:
                    model.fit(X_train, y_train)
                    y_pred = model.predict(X_test)
                    y_pred_proba = model.predict_proba(X_test)[:, 1]
                
                # Calculate metrics
                accuracy = model.score(X_test_scaled if name in ['svm', 'logistic_regression'] else X_test, y_test)
                auc_score = roc_auc_score(y_test, y_pred_proba)
                
                # Cross-validation
                cv_scores = cross_val_score(model, 
                                          X_train_scaled if name in ['svm', 'logistic_regression'] else X_train, 
                                          y_train, cv=5, scoring='roc_auc')
                
                results[name] = {
                    'accuracy': accuracy,
                    'auc_score': auc_score,
                    'cv_mean': cv_scores.mean(),
                    'cv_std': cv_scores.std(),
                    'predictions': y_pred,
                    'probabilities': y_pred_proba
                }
                
                logger.info(f"{name} - Accuracy: {accuracy:.3f}, AUC: {auc_score:.3f}, CV: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")
                
                # Feature importance for tree-based models
                if hasattr(model, 'feature_importances_'):
                    self.feature_importance[name] = {
                        'features': X.columns.tolist(),
                        'importance': model.feature_importances_.tolist()
                    }
                
            except Exception as e:
                logger.error(f"Error training {name}: {e}")
                results[name] = {'error': str(e)}
        
        # Store training results
        self.training_history.append({
            'timestamp': datetime.now(),
            'n_samples': len(X),
            'results': results,
            'test_accuracy': {name: r.get('accuracy', 0) for name, r in results.items()},
            'best_model': max(results.keys(), key=lambda k: results[k].get('auc_score', 0))
        })
        
        logger.info(f"Training complete. Best model: {self.training_history[-1]['best_model']}")
        
        return results, X_test, y_test
    
    def hyperparameter_optimization(self, X: pd.DataFrame, y: pd.Series):
        """Perform hyperparameter optimization for key models"""
        
        logger.info("Starting hyperparameter optimization...")
        
        # Random Forest optimization
        rf_param_grid = {
            'n_estimators': [100, 200, 300],
            'max_depth': [10, 15, 20, None],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4]
        }
        
        rf_grid_search = GridSearchCV(
            RandomForestClassifier(random_state=42),
            rf_param_grid,
            cv=5,
            scoring='roc_auc',
            n_jobs=-1,
            verbose=1
        )
        
        rf_grid_search.fit(X, y)
        
        logger.info(f"Best RF parameters: {rf_grid_search.best_params_}")
        logger.info(f"Best RF score: {rf_grid_search.best_score_:.3f}")
        
        # XGBoost optimization
        xgb_param_grid = {
            'n_estimators': [100, 200, 300],
            'learning_rate': [0.01, 0.1, 0.2],
            'max_depth': [6, 8, 10],
            'subsample': [0.8, 0.9, 1.0]
        }
        
        xgb_grid_search = GridSearchCV(
            xgb.XGBClassifier(random_state=42),
            xgb_param_grid,
            cv=5,
            scoring='roc_auc',
            n_jobs=-1,
            verbose=1
        )
        
        xgb_grid_search.fit(X, y)
        
        logger.info(f"Best XGB parameters: {xgb_grid_search.best_params_}")
        logger.info(f"Best XGB score: {xgb_grid_search.best_score_:.3f}")
        
        # Update models with best parameters
        self.models['random_forest'] = rf_grid_search.best_estimator_
        self.models['xgboost'] = xgb_grid_search.best_estimator_
        
        return {
            'random_forest': rf_grid_search,
            'xgboost': xgb_grid_search
        }
    
    def predict_transport_cancellation(self, features: Dict, model_name: str = 'ensemble') -> Dict:
        """Predict transport cancellation probability"""
        
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not found")
        
        model = self.models[model_name]
        
        # Convert features to DataFrame
        feature_df = pd.DataFrame([features])
        
        # Scale if necessary
        if model_name in ['svm', 'logistic_regression'] and 'standard' in self.scalers:
            feature_df_scaled = self.scalers['standard'].transform(feature_df)
            prediction = model.predict(feature_df_scaled)[0]
            probability = model.predict_proba(feature_df_scaled)[0, 1]
        else:
            prediction = model.predict(feature_df)[0]
            probability = model.predict_proba(feature_df)[0, 1]
        
        return {
            'prediction': bool(prediction),
            'cancellation_probability': float(probability),
            'model_used': model_name,
            'confidence': self._calculate_confidence(probability)
        }
    
    def _calculate_confidence(self, probability: float) -> float:
        """Calculate prediction confidence"""
        
        # Higher confidence for extreme predictions
        confidence = 2 * abs(probability - 0.5)
        return min(confidence, 0.95)
    
    def get_feature_importance_report(self) -> Dict:
        """Generate feature importance report"""
        
        report = {}
        
        for model_name, importance_data in self.feature_importance.items():
            features = importance_data['features']
            importance = importance_data['importance']
            
            # Sort by importance
            sorted_indices = np.argsort(importance)[::-1]
            
            report[model_name] = {
                'top_features': [features[i] for i in sorted_indices[:10]],
                'top_importance': [importance[i] for i in sorted_indices[:10]],
                'feature_ranking': {features[i]: importance[i] for i in range(len(features))}
            }
        
        return report
    
    def save_models(self, filepath: str):
        """Save trained models to disk"""
        
        model_data = {
            'models': self.models,
            'scalers': self.scalers,
            'feature_importance': self.feature_importance,
            'training_history': self.training_history,
            'timestamp': datetime.now()
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"Models saved to {filepath}")
    
    def load_models(self, filepath: str):
        """Load trained models from disk"""
        
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        self.models = model_data['models']
        self.scalers = model_data['scalers']
        self.feature_importance = model_data['feature_importance']
        self.training_history = model_data['training_history']
        
        logger.info(f"Models loaded from {filepath}")
    
    def generate_training_report(self) -> str:
        """Generate comprehensive training report"""
        
        if not self.training_history:
            return "No training history available."
        
        latest_training = self.training_history[-1]
        
        report = f"""
=== Advanced ML Models Training Report ===
Training Date: {latest_training['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}
Training Samples: {latest_training['n_samples']}
Best Model: {latest_training['best_model']}

Model Performance Summary:
"""
        
        for model_name, accuracy in latest_training['test_accuracy'].items():
            report += f"- {model_name.replace('_', ' ').title()}: {accuracy:.1%} accuracy\n"
        
        report += f"""
Feature Importance (Top 5 for Random Forest):
"""
        
        if 'random_forest' in self.feature_importance:
            rf_features = self.feature_importance['random_forest']
            sorted_indices = np.argsort(rf_features['importance'])[::-1]
            for i in range(min(5, len(sorted_indices))):
                idx = sorted_indices[i]
                feature = rf_features['features'][idx]
                importance = rf_features['importance'][idx]
                report += f"- {feature}: {importance:.3f}\n"
        
        return report

def main():
    """Main training and demonstration"""
    
    print("=== Advanced ML Transport Prediction Models ===")
    
    # Initialize predictor
    predictor = AdvancedTransportPredictor()
    
    # Generate synthetic training data
    X, y = predictor.generate_synthetic_training_data(n_samples=2000)
    
    # Train models
    results, X_test, y_test = predictor.train_models(X, y)
    
    # Generate report
    print(predictor.generate_training_report())
    
    # Feature importance
    importance_report = predictor.get_feature_importance_report()
    
    if 'random_forest' in importance_report:
        print("\n=== Top 5 Most Important Features ===")
        rf_report = importance_report['random_forest']
        for i, (feature, importance) in enumerate(zip(rf_report['top_features'][:5], rf_report['top_importance'][:5])):
            print(f"{i+1}. {feature}: {importance:.3f}")
    
    # Save models
    model_filepath = "advanced_transport_models.pkl"
    predictor.save_models(model_filepath)
    print(f"\nModels saved to {model_filepath}")
    
    # Demonstration prediction
    print("\n=== Sample Prediction ===")
    sample_features = {
        'temperature': 18.0,
        'humidity': 85.0,
        'wind_speed': 15.0,
        'wind_direction': 280.0,
        'visibility': 3000.0,
        'pressure': 1008.0,
        'precipitation': 2.0,
        'pressure_tendency': -3.0,
        'temperature_change_24h': -2.0,
        'wind_gust': 20.0,
        'sea_temperature': 14.0,
        'hour': 14,
        'month': 9,
        'day_of_week': 1,
        'season': 3,
        'transport_type': 1,  # flight
        'route_type': 1,
        'departure_time_category': 1,
        'karman_vortex_risk': 0.6,
        'sea_state': 3,
        'terrain_shielding': 0.3
    }
    
    prediction = predictor.predict_transport_cancellation(sample_features, 'ensemble')
    print(f"Cancellation Prediction: {prediction['prediction']}")
    print(f"Probability: {prediction['cancellation_probability']:.1%}")
    print(f"Confidence: {prediction['confidence']:.1%}")

if __name__ == "__main__":
    main()