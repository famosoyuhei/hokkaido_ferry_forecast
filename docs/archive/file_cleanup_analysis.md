# File Cleanup Analysis - 2026-01-19

## 🎯 Active Production Files (Keep)

### Core Services (7 files)
1. ✅ `forecast_dashboard.py` - Flask web application (Railway)
2. ✅ `weather_forecast_collector.py` - Weather data collection (GitHub Actions)
3. ✅ `improved_ferry_collector.py` - Ferry operations collection (GitHub Actions)
4. ✅ `sailing_forecast_system.py` - Sailing forecast generation
5. ✅ `notification_service.py` - Notification system (future)
6. ✅ `push_notification_service.py` - Push notifications (future)
7. ✅ `unified_accuracy_tracker.py` - NEW: Unified accuracy tracking (GitHub Actions)

### Utility (1 file)
8. ✅ `generate_pwa_icons.py` - PWA icon generator (utility)

**Total Active: 8 files**

---

## ⚠️ Legacy/Duplicate Accuracy Files (Delete)

### Old Accuracy Trackers (6 files)
1. ❌ `accuracy_tracker.py` - OLD: Uses ferry_actual_operations.db (wrong DB)
2. ❌ `accuracy_dashboard.py` - OLD: Separate dashboard (not integrated)
3. ❌ `dual_accuracy_tracker.py` - OLD: Duplicate functionality
4. ❌ `operation_accuracy_calculator.py` - OLD: Duplicate functionality
5. ❌ `prediction_accuracy_system.py` - OLD: Duplicate functionality
6. ❌ `test_accuracy_system.py` - OLD: Test/development file

**Reason**: Replaced by `unified_accuracy_tracker.py` which properly integrates both databases.

### ML/Optimization (2 files - Keep for now, may activate in Phase 3)
- ⚠️ `ml_threshold_optimizer.py` - Future: Phase 3 (Machine Learning)
- ⚠️ `auto_threshold_adjuster.py` - Future: Phase 3 (Automatic adjustment)

**Decision**: Keep but document as "Phase 3 - Not Active"

### Test/Development Files (5 files)
7. ❌ `check_accuracy_db.py` - Development: DB checking
8. ❌ `check_accuracy_tables.py` - Development: Table checking
9. ❌ `check_data_status.py` - Development: Status checking (just created today)
10. ❌ `generate_test_predictions.py` - Development: Test data
11. ❌ `quick_test.py` - Development: Quick tests
12. ❌ `automated_improvement_runner.py` - Development: Old automation

---

## 📊 Summary

| Category | Count | Action |
|----------|-------|--------|
| **Active Production** | 8 | Keep |
| **Legacy Accuracy** | 6 | Delete |
| **Future ML** | 2 | Keep (inactive) |
| **Test/Dev** | 6 | Delete |
| **Total to Delete** | 12 | |

---

## 🗂️ Recommended Actions

### Delete Now (12 files)
```bash
# Legacy accuracy trackers
rm accuracy_tracker.py
rm accuracy_dashboard.py
rm dual_accuracy_tracker.py
rm operation_accuracy_calculator.py
rm prediction_accuracy_system.py
rm test_accuracy_system.py

# Test/development files
rm check_accuracy_db.py
rm check_accuracy_tables.py
rm check_data_status.py
rm generate_test_predictions.py
rm quick_test.py
rm automated_improvement_runner.py
```

### Keep but Mark as Future (2 files)
- `ml_threshold_optimizer.py` - Add comment: "Phase 3 - Not Active"
- `auto_threshold_adjuster.py` - Add comment: "Phase 3 - Not Active"

---

## 📁 Final Active File List

After cleanup, only these 8 files remain active:

```
hokkaido_ferry_forecast/
├── forecast_dashboard.py              # Flask web app
├── weather_forecast_collector.py      # Data collection (weather)
├── improved_ferry_collector.py        # Data collection (ferry)
├── sailing_forecast_system.py         # Forecast generation
├── unified_accuracy_tracker.py        # Accuracy tracking (NEW)
├── notification_service.py            # Notifications (future)
├── push_notification_service.py       # Push notifications (future)
└── generate_pwa_icons.py              # Utility

Future (Phase 3):
├── ml_threshold_optimizer.py          # ML optimization (inactive)
└── auto_threshold_adjuster.py         # Auto adjustment (inactive)
```

---

## ✅ Benefits of Cleanup

1. **Clarity**: Only production files visible
2. **No Confusion**: Single source of truth for accuracy tracking
3. **Easier Maintenance**: Fewer files to manage
4. **GitHub Actions Simplicity**: Clear which scripts are active

---

**Created**: 2026-01-19 21:00 JST
**Status**: Ready for execution
