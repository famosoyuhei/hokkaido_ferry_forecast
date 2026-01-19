# Markdown File Cleanup Plan - 2026-01-19

## ✅ Keep - Essential Documentation (8 files)

1. `README.md` - Project overview
2. `CLAUDE.md` - Main project documentation (THIS IS THE SOURCE OF TRUTH)
3. `ACCURACY_IMPROVEMENT_STRATEGY.md` - NEW: Phase 1-5 plan
4. `API_KEY_MANAGEMENT.md` - Security guide
5. `PWA_SMARTPHONE_APP_GUIDE.md` - User guide
6. `DATABASE_CLEANUP_SUMMARY.md` - Historical record
7. `GITHUB_ACTIONS_SETUP.md` - Setup guide (may be useful)
8. `RAILWAY_CRON_DEBUG.md` - Important findings about Railway Cron

**Keep: 8 files**

---

## 🗑️ Delete - Temporary/Obsolete Documentation

### Deployment Instructions (Obsolete - now in CLAUDE.md)
- `CLOUD_DEPLOYMENT.md`
- `DEPLOYMENT_CHECKLIST.md`
- `DEPLOYMENT_INSTRUCTIONS.md`
- `DEPLOYMENT_STATUS.md`
- `DEPLOYMENT_SUCCESS_CHECK.md`
- `FIND_RAILWAY_URL.md`
- `FIND_SERVICE_SETTINGS.md`
- `FIX_RAILWAY_REPOSITORY.md`
- `GENERATE_RAILWAY_DOMAIN.md`
- `INSTALL_RAILWAY_CLI.md`
- `RAILWAY_CLI_SETUP.md`
- `RAILWAY_OBSERVABILITY_INSTRUCTIONS.md`
- `manual_railway_data_collection.md`
- `RUN_COLLECTOR_ALTERNATIVE.md`
- `WAIT_FOR_AUTO_EXECUTION.md`

### Troubleshooting (Resolved - now in CLAUDE.md)
- `CHECK_CRON_STATUS.md`
- `DATA_ACCUMULATION_ISSUES.md`
- `DATA_ACCUMULATION_STATUS.md`
- `FIX_500_ERROR.md`
- `QUICK_CHECK.md`
- `SECURITY_URGENT_ACTION.md`

### Historical/Analysis (Archived info)
- `FORECAST_IMPLEMENTATION_COMPLETE.md`
- `IMPROVEMENTS_2025-10-22.md`
- `PREDICTION_ANALYSIS_2025-10-22.md`
- `PROJECT_CLEANUP_COMPLETE.md`
- `WEATHER_FORECAST_ANALYSIS.md`

### Cost/Impact Analysis (Already in CLAUDE.md)
- `billing_safety_report.md`
- `PC_UPTIME_IMPACT.md`
- `RAILWAY_COST_ANALYSIS.md`

### Future Projects (Not current focus)
- `aviation_historical_data_sources.md`
- `flightaware_api_signup_guide.md`
- `RISHIRI_AIRPORT_SYSTEM_DESIGN.md`

### Other
- `TASK_SCHEDULER_SETUP.md` - Obsolete (using GitHub Actions)
- `mobile_setup_guide.md` - Duplicate of PWA guide
- `file_cleanup_analysis.md` - This cleanup document (can delete after cleanup)

**Delete: 37 files**

---

## 📋 Action Plan

```bash
# Create docs/archive directory
mkdir -p docs/archive

# Move to archive (not delete, for safety)
mv CLOUD_DEPLOYMENT.md docs/archive/
mv DEPLOYMENT_*.md docs/archive/
mv FIND_*.md docs/archive/
mv FIX_*.md docs/archive/
mv GENERATE_*.md docs/archive/
mv INSTALL_*.md docs/archive/
mv RAILWAY_CLI_SETUP.md docs/archive/
mv RAILWAY_OBSERVABILITY_INSTRUCTIONS.md docs/archive/
mv manual_railway_data_collection.md docs/archive/
mv RUN_COLLECTOR_ALTERNATIVE.md docs/archive/
mv WAIT_FOR_AUTO_EXECUTION.md docs/archive/
mv CHECK_CRON_STATUS.md docs/archive/
mv DATA_ACCUMULATION_*.md docs/archive/
mv QUICK_CHECK.md docs/archive/
mv SECURITY_URGENT_ACTION.md docs/archive/
mv FORECAST_IMPLEMENTATION_COMPLETE.md docs/archive/
mv IMPROVEMENTS_*.md docs/archive/
mv PREDICTION_ANALYSIS_*.md docs/archive/
mv PROJECT_CLEANUP_COMPLETE.md docs/archive/
mv WEATHER_FORECAST_ANALYSIS.md docs/archive/
mv billing_safety_report.md docs/archive/
mv PC_UPTIME_IMPACT.md docs/archive/
mv RAILWAY_COST_ANALYSIS.md docs/archive/
mv aviation_historical_data_sources.md docs/archive/
mv flightaware_api_signup_guide.md docs/archive/
mv RISHIRI_AIRPORT_SYSTEM_DESIGN.md docs/archive/
mv TASK_SCHEDULER_SETUP.md docs/archive/
mv mobile_setup_guide.md docs/archive/
mv file_cleanup_analysis.md docs/archive/
mv markdown_cleanup_plan.md docs/archive/
```

---

## 📁 Final Structure

```
hokkaido_ferry_forecast/
├── README.md                             ← Project overview
├── CLAUDE.md                             ← Main documentation (SOURCE OF TRUTH)
├── ACCURACY_IMPROVEMENT_STRATEGY.md      ← Phase 1-5 plan
├── API_KEY_MANAGEMENT.md                 ← Security
├── PWA_SMARTPHONE_APP_GUIDE.md           ← User guide
├── DATABASE_CLEANUP_SUMMARY.md           ← Historical
├── GITHUB_ACTIONS_SETUP.md               ← Setup
└── RAILWAY_CRON_DEBUG.md                 ← Important findings

docs/archive/                             ← 37 archived files
```

**Total: 8 essential MD files (from 45)**

---

**Status**: Ready for execution
**Date**: 2026-01-19
