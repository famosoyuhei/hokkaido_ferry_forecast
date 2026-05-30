# Ferry Cancellation Research Memory

## Domain

The system forecasts cancellation risk for Heartland Ferry routes connecting Wakkanai, Rishiri Island, and Rebun Island. The practical users are island businesses that depend on ferry logistics.

## Ports

| Key | Japanese | Notes |
|---|---|---|
| `wakkanai` | 稚内 | Mainland departure hub |
| `oshidomari` | 鴛泊 | Rishiri east/northeast side |
| `kutsugata` | 沓形 | Rishiri west side; do not merge with Oshidomari |
| `kafuka` | 香深 | Rebun main port; often exposed to harsher conditions |

## Route Keys

- `wakkanai_oshidomari`
- `oshidomari_wakkanai`
- `wakkanai_kafuka`
- `kafuka_wakkanai`
- `wakkanai_kutsugata`
- `kutsugata_wakkanai`
- `oshidomari_kafuka`
- `kafuka_oshidomari`

## Official 2026 Sailing Timetable Memory

Source pages checked on 2026-05-26:

- Heartland Ferry timetable index / Wakkanai-Rishiri: https://heartlandferry.jp/timetable/
- Wakkanai-Rebun: https://heartlandferry.jp/timetable/time1/
- Rishiri-Rebun: https://heartlandferry.jp/timetable/time2/

The 2026 official timetable is expressed as date ranges. For day-by-day use, expand the matching range inclusively for the requested 2026 date. Timetable rows are planned sailings, not actual operation records. Weather cancellation audits must still compare against the operation status page and must not count non-scheduled sailings as cancellations.

### 2026 稚内-鴛泊 / 鴛泊-稚内

| Date range | `wakkanai_oshidomari` | `oshidomari_wakkanai` |
|---|---|---|
| 2026-01-01 to 2026-04-27 | 06:55-08:35; 14:00-15:40 | 09:05-10:45; 17:30-19:10 |
| 2026-04-28 to 2026-05-31 | 06:45-08:25; 10:10-11:50; 14:30-16:10 | 08:55-10:35; 14:35-16:15; 16:40-18:20 |
| 2026-06-01 to 2026-09-30 | 07:15-08:55; 11:15-12:55; 16:40-18:20 | 08:25-10:05; 12:05-13:45; 16:40-18:20 |
| 2026-10-01 to 2026-10-31 | 06:45-08:25; 10:10-11:50; 14:30-16:10 | 08:55-10:35; 14:35-16:15; 16:40-18:20 |
| 2026-11-01 to 2026-12-31 | 06:55-08:35; 14:00-15:40 | 09:05-10:45; 17:30-19:10 |

### 2026 稚内-香深 / 香深-稚内

Angle brackets on the official page indicate sailings via Rishiri/Oshidomari. Keep `via_oshidomari=true` for those sailings when building sailing-time weather assignments.

| Date range | `wakkanai_kafuka` | `kafuka_wakkanai` |
|---|---|---|
| 2026-01-01 to 2026-04-27 | 06:35-08:30; 14:10-16:05 | 09:00-10:55; 17:05-19:00 |
| 2026-04-28 to 2026-05-31 | 06:30-08:25; 10:10-13:00 via Oshidomari; 14:45-16:40 | 08:55-10:50; 13:25-16:15 via Oshidomari; 17:05-19:00 |
| 2026-06-01 to 2026-09-30 | 06:30-08:25; 10:30-12:25; 14:50-16:45 | 08:55-10:50; 14:20-16:15; 17:10-19:05 |
| 2026-10-01 to 2026-10-31 | 06:30-08:25; 10:10-13:00 via Oshidomari; 14:45-16:40 | 08:55-10:50; 13:25-16:15 via Oshidomari; 17:05-19:00 |
| 2026-11-01 to 2026-12-31 | 06:35-08:30; 14:10-16:05 | 09:00-10:55; 17:05-19:00 |

### 2026 利尻-礼文

| Date range | Route | Sailings |
|---|---|---|
| 2026-01-01 to 2026-04-27 | `oshidomari_kafuka` | 16:00-16:45 |
| 2026-01-01 to 2026-04-27 | `kafuka_oshidomari` | 16:25-17:10 |
| 2026-04-28 to 2026-05-31 | `oshidomari_kafuka` | 12:15-13:00 |
| 2026-04-28 to 2026-05-31 | `kafuka_oshidomari` | 13:25-14:10 |
| 2026-06-01 to 2026-09-30 | `oshidomari_kafuka` | 09:30-10:15; 13:15-14:00 |
| 2026-06-01 to 2026-09-30 | `kafuka_oshidomari` | 10:40-11:25; 15:30-16:15 |
| 2026-06-01 to 2026-09-30 | `kutsugata_kafuka` | 14:25-15:05 |
| 2026-06-01 to 2026-09-30 | `kafuka_kutsugata` | 12:50-13:30 |
| 2026-10-01 to 2026-10-31 | `oshidomari_kafuka` | 12:15-13:00 |
| 2026-10-01 to 2026-10-31 | `kafuka_oshidomari` | 13:25-14:10 |
| 2026-11-01 to 2026-12-31 | `oshidomari_kafuka` | 16:00-16:45 |
| 2026-11-01 to 2026-12-31 | `kafuka_oshidomari` | 16:25-17:10 |

Note: the 2026 Rishiri-Rebun timetable includes seasonal Kutsugata-Kafuka sailings from 2026-06-01 to 2026-09-30. Treat `kutsugata_kafuka` and `kafuka_kutsugata` as scheduled seasonal route keys for timetable/weather assignment even if older code only models Wakkanai-Kutsugata.

## Weather Variables

Core variables:

- wind speed
- wind direction
- wave height
- visibility
- season/month
- route and port exposure

Useful future variables:

- wave direction
- wave period
- crosswind component
- pressure tendency
- warnings/advisories
- blizzard/snow intensity

## Required Forecast and Actual Weather Numeric Fields

Forecast and actual/reanalysis datasets must be collected at hourly resolution and assigned to sailing windows. Daily averages are insufficient for cancellation forecasting.

Required for both forecast and actual/reanalysis:

| Field | Unit | Required? | Reason |
|---|---|---|---|
| wind_speed | m/s | yes | Primary cancellation driver |
| wind_direction | degrees or 16-point direction | yes | Route exposure, crosswind, fetch |
| wave_height | m, significant wave height | yes | Strongest cancellation driver |
| visibility | km | yes | Fog/blizzard navigation safety |
| precipitation_or_snowfall | mm/h | yes | Visibility degradation, winter context |
| temperature | C | yes | Icing, snow/blizzard context |
| pressure | hPa | yes | Low pressure and rapid worsening |
| valid_time | JST timestamp | yes | Sailing-time matching |
| source_time | timezone-aware timestamp | yes | Forecast freshness or observation availability |
| data_source | text | yes | Official forecast, API, archive, reanalysis, etc. |

Recommended when available:

| Field | Unit | Reason |
|---|---|---|
| wind_gust_or_max_wind | m/s | Docking and sudden danger |
| wave_direction | degrees or 16-point direction | Head/beam sea and island shadow |
| wave_period | sec | Swell and ride/safety |
| swell_height | m | High waves without local wind |
| swell_period | sec | Long-period swell |
| wind_wave_height | m | Locally generated sea |
| weather_code_or_text | code/text | Fog, snow, rain, blizzard explanation |
| warning_or_advisory | code/text | JMA danger signal |
| forecast_confidence | score/text | Longer-horizon uncertainty |

Normalization rules:

- Store wind speed in m/s, visibility in km, wave height in m, temperature in C, pressure in hPa.
- Store missing values as NULL, never as 0.
- Keep original text values from JMA when available, but also store normalized numeric values.
- Mark whether actual data is direct observation, archive, reanalysis, or fallback forecast API.
- For each sailing, preserve the departure-port, midpoint, destination-port, and via-port values used to compute the worst case.

## Sailing-Time Port Assignment Rules

- Scheduled sailings must be expanded from the 2026 official timetable before weather assignment.
- Normal sailings require 2 weather points: departure port and arrival port.
- Via sailings require 3 weather points: departure port, via port, and arrival port.
- For current 2026 timetable data, Wakkanai-Kafuka and Kafuka-Wakkanai sailings marked `via_oshidomari=true` use Oshidomari as the via port.
- Assign hourly weather records for each port role's relevant time window.
- Use `port_role=departure` for the departure port, `port_role=arrival` for the arrival port, and `port_role=via` for the via port.
- Departure reference time is departure time. Arrival reference time is arrival time.
- Wakkanai -> Oshidomari -> Kafuka: Wakkanai-Oshidomari sailing is 100 minutes, Oshidomari-Kafuka sailing is 45 minutes, total timetable duration is 170 minutes. Infer Oshidomari port call as departure+100 minutes through departure+125 minutes.
- Kafuka -> Oshidomari -> Wakkanai: Kafuka-Oshidomari sailing is 45 minutes, Oshidomari-Wakkanai sailing is 100 minutes, total timetable duration is 170 minutes. Infer Oshidomari port call as departure+45 minutes through departure+70 minutes.
- Via reference time is the midpoint of the inferred 25-minute port-call window.
- Store `window_start_time` and `window_end_time` for each assigned port role.
- Forecast assignments live in `sailing_weather_forecast`.
- Actual/reanalysis assignments live in `actual_sailing_weather`.

## Known Patterns

- Winter, especially December through March, has much higher cancellation risk at lower wind speeds than summer.
- Prior analysis found false negatives in the 8-25 m/s wind band during winter.
- Rebun/Kafuka routes can be harsher than Rishiri routes under similar broad-scale weather.
- Wakkanai west-side ferry routes are in the Japan Sea side environment, not the eastern Soya Strait.
- JMA warnings and wave forecasts should be treated as high-value context, while Open-Meteo/ERA5 values may miss port-scale and island-shadow effects.

## Cancellation and Safety Decision Signals

These are operational modeling rules, not confirmed Heartland Ferry internal criteria.

Cancellation-prone signals:

- Wave height is the strongest signal. Treat 3.0m+ as at least MEDIUM candidate, 4.0m+ as HIGH candidate, and 6.0m+ or wave-warning-equivalent conditions as extreme danger.
- Wind speed is a primary signal. Treat 20m/s+ as at least MEDIUM candidate, 25m/s+ as HIGH candidate, and 35m/s+ as extreme danger.
- Winter low-to-mid wind cases matter. In December-March, 8-15m/s wind plus 1.5-2.5m waves, snowfall/blizzard context, or northwest-west-northwest flow should not remain MINIMAL/LOW without review.
- Visibility below 1km is a serious navigation risk. Visibility near/below 0.5km is sea-fog-warning-equivalent and should be treated as a HIGH candidate.
- Kafuka/Rebun-related routes deserve a safety-side route factor under the same broad-scale weather because Rebun is more exposed.
- Wakkanai-only weather is insufficient for safety. Use departure port, destination port, route midpoint, and via port where applicable.

Safety-prone signals:

- Safety is a combination signal, not a single low value.
- A sailing can be treated as low risk only when the whole sailing window has low waves, weak wind, good visibility, no warning/advisory-equivalent signal, and no rapid worsening trend.
- If any high-confidence danger signal appears during departure, midpoint, arrival, or via-port timing, it should override otherwise safe-looking daily averages.

## Current Model Cautions

- Risk logic must not rely only on Wakkanai weather.
- Daily summaries are not enough; sailing-time alignment matters.
- Actual weather from Open-Meteo Archive is reanalysis, not direct port observation.
- Seasonal service gaps and maintenance periods must not be counted as weather cancellations.
- DB files and API keys must not be committed.
- Railway uses UTC internally; application logic should explicitly use JST.

## Improvement Hypotheses

- Add route-specific worst-case weather using departure port, destination port, and route midpoint.
- Add winter-specific low wind and moderate wave penalties.
- Add Kafuka/Rebun exposure factor.
- Add confidence penalties for missing wave or visibility data.
- Add official warning/advisory features before changing thresholds aggressively.
