# db/ — Data Governance for Digital Twin Papers

Every number in your paper traces back to a file in this folder.

This directory holds (or points to) every external dataset your paper needs:
ground motion records, benchmark datasets, calibration data, and field
measurements. Nothing here is invented — it all comes from published sources
or your own instruments.

**This folder is gitignored by design.** Binary data files (`.AT2`, `.csv`,
`.mat`, `.hdf5`) are too large to version. Each project clone downloads its
own data following the steps below. Only `manifest.yaml`, `README.md`, and
`.gitkeep` files are tracked.

## 1. Quick Start

```bash
# 1. Fill out manifest.yaml with your paper's data requirements
#    (domain, quartile, excitation source, benchmark names)

# 2. Download excitation records (see Section 2)

# 3. Download benchmark datasets (see Section 5)

# 4. Run verification
python3 tools/fetch_benchmark.py --verify

# 5. validate_submission.py will check manifest.yaml automatically
python3 tools/validate_submission.py
```

## 2. Excitation Records — PEER NGA-West2

The NGA-West2 database contains ~21,000 processed ground motion records
from shallow crustal earthquakes worldwide. This is the primary source for
structural engineering papers.

### Step-by-step

1. **Create an account** at https://ngawest2.berkeley.edu/ (free, requires
   academic or professional email).

2. **Define your selection criteria** in `manifest.yaml` under
   `excitation.selection_criteria`. If you have `tools/select_ground_motions.py`,
   run it to get a list of RSN (Record Sequence Numbers):
   ```bash
   python3 tools/select_ground_motions.py \
     --Mw 6.0 8.5 \
     --Rjb 0 200 \
     --Vs30 180 760 \
     --target-spectrum CMS \
     --n-records 11
   ```
   This outputs RSN numbers and updates `manifest.yaml`.

3. **Search on PEER website:**
   - Go to "Search" → "NGA-West2 Ground Motions"
   - Enter your RSN numbers (comma-separated) or filter by Mw, Rjb, Vs30
   - Click "Search"

4. **Download:**
   - Select the records you need → "Add to Cart"
   - Go to Cart → "Download" → choose format (usually "Uncorrected" or
     "Processed accelerograms")
   - Download the ZIP file

5. **Unzip into the records folder:**
   ```bash
   unzip NGA-West2_records.zip -d db/excitation/records/
   ```

6. **Verify:**
   ```bash
   python3 tools/fetch_benchmark.py --verify
   ```
   This checks that all RSNs listed in `manifest.yaml` have corresponding
   `.AT2` files in `db/excitation/records/`.

### Flatfile (optional but recommended)

The NGA-West2 flatfile (~50 MB CSV) contains metadata for all 21,000+
records. Download it from the PEER website under "Flatfile" and place it in:
```
db/excitation/flatfiles/Updated_NGA_West2_Flatfile_RotD50_d050_public_version.csv
```

This enables programmatic record selection without the web interface.

## 3. Subduction Records — NGA-Sub

For subduction zone earthquakes (Peru, Chile, Japan, Cascadia), use the
NGA-Subduction database instead of NGA-West2.

1. Go to https://www.risksciences.ucla.edu/nhr3/nga-subduction/gmportal
2. Create an account (free).
3. Search by event name (e.g., "Maule 2010", "Tohoku 2011", "Pisco 2007")
   or by magnitude/distance/mechanism filters.
4. Download records and place in `db/excitation/records/`.
5. Update `manifest.yaml`: set `excitation.source: "NGA-Sub"` and
   `selection_criteria.mechanism: "subduction"`.

### Peru-specific: CISMID

For Peruvian records not in NGA-Sub:

1. Go to https://www.cismid.uni.edu.pe/
2. Navigate to "Red Acelerografica Nacional" → "Registros"
3. Request access (may require institutional affiliation).
4. Available events include Pisco 2007, Arequipa 2001, Nazca 1996.
5. Place records in `db/excitation/records/` and note the source in
   `manifest.yaml`.

## 4. Other Excitation Sources

| Source | URL | Coverage |
|--------|-----|----------|
| CESMD | https://www.strongmotioncenter.org/ | California + US |
| K-NET / KiK-net | https://www.kyoshin.bosai.go.jp/ | Japan |
| ESM | https://esm-db.eu/ | Europe + Mediterranean |
| GeoNet | https://www.geonet.org.nz/ | New Zealand |

For wind and wave excitation (domains `air` and `water`), place time
histories in `db/excitation/records/` with appropriate naming and update
`manifest.yaml` accordingly.

## 5. Benchmark Datasets

These are published datasets used to validate your method against known
results. Required for Q3 and above.

### LANL 3-Story Frame

A well-known SHM benchmark with labeled damage states.

- **Source:** Los Alamos National Laboratory
- **URL:** https://www.lanl.gov/projects/national-security-education-center/engineering/ei-software-download.shtml
- **Format:** `.mat` (MATLAB) or `.csv`
- **Place in:** `db/benchmarks/lanl/`
- **Use case:** Validate damage detection algorithms, compare classification
  accuracy against published results.

### IASC-ASCE SHM Benchmark

Phase I (simulated) and Phase II (experimental) benchmark problems for
structural health monitoring.

- **Reference:** Johnson et al. (2004), "Phase I IASC-ASCE Structural Health
  Monitoring Benchmark Problem Using Simulated Data"
- **Data:** Available through ASCE or upon request from authors
- **Place in:** `db/benchmarks/iasc_asce/`
- **Use case:** Modal identification, damage detection under varying
  environmental conditions.

### Z24 Bridge

Continuous monitoring data from the Z24 bridge in Switzerland before its
demolition, including progressive damage introduction.

- **Reference:** Maeck & De Roeck (2003)
- **Data:** Contact KU Leuven Structural Mechanics division
- **Place in:** `db/benchmarks/z24_bridge/`
- **Use case:** Environmental variability effects on modal parameters,
  damage detection under real-world conditions.

### NHERI DesignSafe

The NHERI DesignSafe cyberinfrastructure hosts experimental and simulation
datasets from natural hazards research.

- **URL:** https://www.designsafe-ci.org/
- **Account:** Free (requires registration)
- **Place in:** `db/benchmarks/nheri_designsafe/`
- **Use case:** Shake table tests, centrifuge experiments, full-scale field
  tests. Search by keyword or DOI.

## 6. Calibration & Validation Data

### Calibration (`db/calibration/`)

Site-specific data used to tune model parameters. Required for Q2 and above.

| Subfolder | What goes here | Typical source |
|-----------|---------------|----------------|
| `material_tests/` | Steel coupon tests (fy, fu, elongation), concrete cylinder tests (f'c), rebar mill certs | Lab reports per ASTM A370, ASTM C39 |
| `soil_profile/` | Vs30 measurements, SPT/CPT logs, site classification | CISMID, USGS, local geotechnical reports |
| `as_built/` | As-built drawings, rebar schedules, member dimensions | Building owner, municipality records |

### Validation (`db/validation/`)

Independent measurements that prove the model works. Required for Q2 and above.

| Subfolder | What goes here | Typical source |
|-----------|---------------|----------------|
| `field_campaigns/` | Ambient vibration recordings, forced vibration tests | Your own instruments (see `articles/field_data_campaign.md`) |
| `shake_table/` | Shake table test results from published experiments | NHERI, E-Defense, LNEC, university labs |

**Field campaign protocol:** Follow `articles/field_data_campaign.md` for
hardware setup, minimum recording duration (30 min ambient), sensor
placement, and data format requirements.

## 7. manifest.yaml — How to Fill It

The manifest is the bridge between your data and your paper. Here is what
to fill at each stage:

### During EXPLORE

```yaml
paper_id: "your-paper-short-id"
domain: structural          # or water, air
quartile: conference        # or Q4, Q3, Q2, Q1
excitation:
  source: "NGA-West2"
  selection_criteria:
    magnitude_Mw: [6.5, 7.5]
    distance_Rjb_km: [10, 100]
    Vs30_ms: [250, 500]
    mechanism: "reverse"
    target_spectrum: "CMS"
  status: pending
```

### During IMPLEMENT

After downloading records and running analyses:

```yaml
excitation:
  flatfile: "excitation/flatfiles/nga_west2_flatfile.csv"
  records_needed: [766, 953, 1111, 1489, 1633]
  records_present: [766, 953, 1111, 1489, 1633]
  status: complete

traceability:
  - claim: "Maximum drift ratio was 1.2% under RSN766"
    figure: "Fig. 3"
    data_file: "data/processed/drift_results.csv"
    source: "OpenSeesPy NRHA with RSN766 (Chi-Chi 1999)"
    excitation_rsn: 766
```

### How validate_submission.py uses it

The validation script reads `db/manifest.yaml` and checks:

- **All quartiles:** `excitation.status` must be `complete`
- **Q3+:** At least one benchmark with `status: complete`
- **Q2+:** At least one calibration and one validation entry with
  `status: complete`
- **Q1:** All of the above plus `traceability` must have at least one entry
  per figure in the paper

If any required field is `pending`, the submission is blocked with a clear
message explaining what data is missing.
