# Skill: Environmental Domain — Ecology / Environmental Engineering Papers
# Loaded lazily by subagents when project.domain = "environmental"

## Domain Identity
- **Solver**: scipy + statsmodels (data-driven, no FEM solver)
- **Data sources**: Remote sensing (GEE, Copernicus), air quality (OpenAQ),
  biodiversity (GBIF), climate (ERA5 ECMWF)
- **Emulator**: NONE — field sensors connect via APIs or CSV exports
- **Status**: PLANNED (compute pipeline scaffold ready — implement per paper)

## SSOT Namespaces (config/params.yaml)
When activating this domain, add to params.yaml:
```yaml
# ─── Environmental domain params ─────────────────────────────────
project:
  domain: "environmental"

environmental:
  study_area:
    bbox: [-77.15, -12.15, -76.95, -11.95]  # [lon_min, lat_min, lon_max, lat_max]
    crs: "EPSG:4326"
    resolution_m: 10          # spatial resolution in meters
  time_series:
    start_date: "2020-01-01"
    end_date: "2023-12-31"
    temporal_resolution: "monthly"   # daily | weekly | monthly | yearly
  targets:
    ndvi_threshold: 0.4       # vegetation health threshold (dimensionless)
    aqi_limit_pm25: 35        # EPA NAAQS PM2.5 24h standard (µg/m³)
    species_min_count: 5      # minimum occurrences for species inclusion
  model:
    regression_type: "OLS"    # OLS | GLS | spatial_lag | spatial_error
    spatial_autocorrelation_test: "moran_i"
    significance_level: 0.05
```

## Compute Pipeline
```
C0: python3 -c "import scipy, numpy, pandas; print('ENV deps OK')"
C1: TODO — tools/fetch_environmental_data.py --verify
C2: domains/environmental.py → EnvironmentalBackend.run_compute()
C3: SKIP (no hardware emulator)
C4: TODO — tools/generate_env_synthetic.py
C5: python3 tools/generate_compute_manifest.py
Stats: python3 tools/compute_statistics.py --quartile q3  (Q1/Q2 only)
```

## Typical Data Workflows
### Urban Forestry / NDVI
```python
# 1. Download Sentinel-2 imagery via Google Earth Engine
# 2. Compute NDVI = (NIR - Red) / (NIR + Red)
# 3. Classify urban green cover change over time
# 4. Statistical test: Mann-Kendall trend, Moran's I spatial autocorrelation
# 5. Save: data/processed/ndvi_timeseries.csv, data/processed/green_cover_map.tif
```

### Air Quality Monitoring
```python
# 1. Download PM2.5/PM10/NO2 from OpenAQ API
# 2. Compute AQI categories, exceedance frequency
# 3. Spatial interpolation (kriging / IDW)
# 4. Regression: AQI ~ traffic + land_use + temperature + wind
# 5. Save: data/processed/aqi_stations.csv, data/processed/aqi_spatial.csv
```

### Biodiversity / Species Distribution
```python
# 1. Download occurrence records from GBIF
# 2. MaxEnt or GLM for species distribution modeling
# 3. Richness maps, diversity indices (Shannon, Simpson)
# 4. Save: data/processed/species_richness.csv, data/processed/sdm_rasters/
```

## Available Python Libraries (install when needed)
```bash
pip install geopandas rasterio geemap pysal netCDF4 xarray statsmodels scikit-learn
# For GDAL on WSL2: sudo apt install gdal-bin libgdal-dev python3-gdal
```

## APIs and Keys
| API | Env var | Purpose | Free? |
|-----|---------|---------|-------|
| OpenAQ | (none required) | Air quality station data | Yes |
| GBIF | (none required) | Species occurrence records | Yes |
| Google Earth Engine | `GEE_SERVICE_ACCOUNT_KEY` | Satellite imagery | Yes (academic) |
| ECMWF CDS | `CDS_API_KEY` | ERA5 climate reanalysis | Yes |

Add to `.env`:
```
GEE_SERVICE_ACCOUNT_KEY=path/to/service_account.json
CDS_API_KEY=your-cds-api-key-here
```

## Normative Codes / Standards
- EPA NAAQS (US air quality standards)
- EU Air Quality Directive 2008/50/EC
- IPBES frameworks (biodiversity assessment)
- ISO 14064 (GHG accounting and verification)
- FAO land use classification (LULC)

## Paper Quartile Requirements
| Quartile | Data requirement |
|----------|-----------------|
| Conference | Synthetic spatial data OK; published dataset reanalysis |
| Q4 | Published datasets + novel analysis |
| Q3 | Field campaign OR remote sensing time series (≥ 3 years) |
| Q2 | Field data + remote sensing validation |
| Q1 | Multi-site field + remote sensing + mechanistic model |

## Figures Produced (when plot_figures.py is extended)
When `domain="environmental"` is implemented in plot_figures.py:
- Fig 1: Study area map (spatial extent, stations, land cover)
- Fig 2: Time series (NDVI / AQI / species count over time period)
- Fig 3: Spatial distribution map (interpolated surface)
- Fig 4: Statistical model results (regression coefficients, CI)
- Fig 5: Benchmark comparison (model vs field observations)

## Implementation Roadmap for First Environmental Paper
1. Choose topic: Urban heat island OR deforestation monitoring OR air quality
2. Download public dataset (no fieldwork needed for Conference/Q4)
3. Implement `tools/fetch_environmental_data.py` (download + validate)
4. Wire `EnvironmentalBackend.run_compute()` in `domains/environmental.py`
5. Add `DOMAIN_SECTIONS["environmental"]` to `articles/scientific_narrator.py`
6. Add `domain="environmental"` figure set to `tools/plot_figures.py`
7. Add `environmental.*` section to `config/params.yaml`
8. Run `python3 tools/generate_params.py` to propagate SSOT

## Subagent Instructions
When activated for an environmental paper:
1. Read `config/params.yaml` → `environmental.*` section
2. Verify chosen public dataset is accessible (API test or local CSV)
3. Confirm `data/processed/COMPUTE_MANIFEST.json` exists before IMPLEMENT
4. Use narrator flag: `python3 articles/scientific_narrator.py --domain environmental`
5. Cite normative standards (EPA NAAQS, EU Directive, IPBES) in Methods
6. For Q1/Q2: include Moran's I or Mann-Kendall tests in Results
