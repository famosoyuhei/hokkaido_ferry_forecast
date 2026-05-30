---
name: ferry-cancellation-research
description: Use when researching, auditing, or improving ferry cancellation forecasting for the Wakkanai, Rishiri, and Rebun routes, including marine weather, route-specific risk factors, actual operation records, and model threshold updates.
---

# Ferry Cancellation Research

Use this skill when working on ferry cancellation prediction, marine weather research, route risk logic, forecast accuracy audits, or prompt generation for fixes in this repository.

## Workflow

1. Identify the target route, date range, and task type: forecast, actual weather, operation record, accuracy audit, or model improvement.
2. Read `references/memory.md` for route keys, port names, known weather patterns, and current model cautions.
3. Prefer official or primary sources when researching current facts:
   - Heartland Ferry for operation status and schedules.
   - JMA for warnings, forecasts, wave information, and meteorological context.
   - Open-Meteo only as a numeric API source or fallback, not as an official marine authority.
4. Separate facts from inferences. Mark estimated thresholds as estimates.
5. When proposing code changes, preserve JST handling, avoid committing DB files or secrets, and keep route/port keys consistent.

## Standard Checks

- Does the logic distinguish Wakkanai, Oshidomari, Kutsugata, and Kafuka?
- Does it evaluate by sailing time, not only by date?
- Does it avoid treating seasonal no-service days as weather cancellations?
- Does it give special attention to Rebun/Kafuka routes, winter months, and low-to-mid wind false negatives?
- Does it preserve data source timestamps and collection timestamps separately?

## Useful Repository Files

- `weather_forecast_collector.py`: forecast collection and cancellation risk generation.
- `actual_weather_collector.py`: actual/reanalysis weather collection for the 4 ports.
- `improved_ferry_collector.py`: Heartland Ferry operation scraping.
- `unified_accuracy_tracker.py`: route-level accuracy audits.
- `MARITIME_RESEARCH.md`: longer research notes.
- `docs/ai_employees/`: AI employee role and automation rules.

