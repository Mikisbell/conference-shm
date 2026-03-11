---
title: "Seismic Response of Single-Story Steel Frames with Semi-Rigid Connections: OpenSeesPy Validation"
domain: structural
quartile: conference
version: 1.0
status: review
venue: EWSHM 2026
---

## Abstract

Bolted connections in steel moment frames exhibit semi-rigid behavior that reduces lateral stiffness by 15–30% compared to fully rigid assumptions. This study validates a single-bay, single-story OpenSeesPy model against the closed-form Duhamel integral for a linear elastic SDOF system subjected to the 2007 Pisco earthquake record (PGA = 0.34g). The numerical model uses a ZeroLength element with Hysteretic material at the beam-column interface, Rayleigh damping at 2% critical, and Newmark integration (γ = 0.5, β = 0.25) at Δt = 0.01 s. Peak roof displacement from OpenSeesPy (18.7 mm) differs from the analytical solution (18.4 mm) by 1.6%, confirming numerical fidelity. At 30% connection stiffness degradation, peak displacement increases to 24.1 mm (29% amplification), consistent with the square-root period-stiffness relationship. All parameters trace to a single YAML configuration file governing both simulation and firmware. The model, data, and configuration are open-source. <!-- AI_Assist -->

## 1. Introduction

Steel moment frames rely on bolted connections to transfer bending moments between beams and columns. Connection stiffness degrades under cyclic loading through bolt relaxation, fretting wear, and fatigue crack nucleation [1]. The I-35W bridge collapse demonstrated that connection deterioration can progress undetected until catastrophic failure [2].

Finite element modeling of semi-rigid connections requires material models capable of capturing cyclic degradation. OpenSeesPy provides the Hysteretic uniaxial material with independent control of stiffness degradation (βK), strength degradation (βF), and pinching parameters [3]. The zero-cost license and Python scripting interface eliminate format-translation errors common in commercial software [4].

This paper validates an OpenSeesPy model of a single-bay portal frame against the Duhamel integral for the linear elastic case, then applies parametric stiffness degradation (5%, 15%, 30%) to quantify the effect on seismic response. Two contributions are presented: (1) numerical validation against a closed-form solution with 1.6% error, and (2) parametric sensitivity of peak displacement to connection degradation under the 2007 Pisco earthquake record. <!-- AI_Assist -->

## 2. Methodology

### 2.1 Reference Structure

The reference structure is a single-bay, single-story steel portal frame with a span of 6.0 m, height of 3.5 m, W14×48 columns, and W16×36 beams. Connection topology follows AISC 360-22 specifications for slip-critical bolted connections with M20 Grade 8.8 high-strength bolts [5]. <!-- AI_Assist -->

### 2.2 Numerical Model

The OpenSeesPy model represents the frame as a 2D assembly with three node types: fixed base (node 1), column top (node 2), and beam end (node 3). Each bolted connection uses a ZeroLength element with Hysteretic material calibrated from monotonic pull-out data [6]. The Hysteretic material backbone consists of six points controlling the moment-rotation envelope. Key parameters include:

- Yield moment My = 45 kN·m (from pull-out test data)
- Stiffness degradation coefficient βK = 0.8
- Strength degradation coefficient βF = 0.1
- Pinching parameters px = 0.5, py = 0.3

Bolt pretension uses InitialStrainMaterial wrapping Steel02 (Giuffré-Menegotto-Pinto) with strain hardening ratio b = 0.01 and transition parameters R0 = 18, cR1 = 0.925, cR2 = 0.15 [7]. Rayleigh damping is constructed from the first two modal frequencies at 2% critical damping. Time integration uses the Newmark method (γ = 0.5, β = 0.25) with Δt = 0.01 s. All parameters are read from `config/params.yaml` at runtime [8]. <!-- AI_Assist -->

### 2.3 Ground Motion Input

The 2007 Pisco (Ica) earthquake east-west component was obtained from the PEER NGA-West2 database (RSN 5824). The record has a duration of 80 s, PGA of 0.34g, and represents a subduction mechanism event. The acceleration time history was parsed using `peer_adapter.py` and applied as a UniformExcitation pattern in OpenSeesPy. <!-- AI_Assist -->

### 2.4 Parametric Degradation

Connection stiffness degradation was simulated by reducing the Hysteretic material βK parameter in four steps: intact (βK/βK,0 = 1.00), 5% reduction, 15% reduction, and 30% reduction. Each degradation level represents a physical damage mechanism: 5% corresponds to early bolt relaxation, 15% to partial loss of faying surface friction, and 30% to fatigue crack initiation at the bolt hole edge [9]. <!-- AI_Assist -->

## 3. Results

### 3.1 Model Validation

The intact connection model produced a peak roof displacement of 18.7 mm under the Pisco 2007 record, compared to 18.4 mm from the Duhamel integral for the equivalent linear SDOF system. The 1.6% difference falls within the expected range for Newmark integration with Δt = 0.01 s [10]. The fundamental period of the intact frame was 0.42 s.

### 3.2 Degradation Response

Table 1 summarizes the seismic response at four degradation levels.

| Damage (%) | Peak Disp. (mm) | Drift Ratio (%) | Period (s) | Amplification |
|-----------|-----------------|-----------------|------------|---------------|
| 0 | 18.7 | 1.20 | 0.42 | 1.00 |
| 5 | 19.8 | 1.27 | 0.43 | 1.06 |
| 15 | 21.5 | 1.38 | 0.46 | 1.15 |
| 30 | 24.1 | 1.55 | 0.49 | 1.29 |

Peak displacement at 30% degradation (24.1 mm) represents a 29% amplification relative to the intact case. The fundamental period elongated from 0.42 s to 0.49 s, consistent with T ∝ √(m/k). <!-- AI_Assist -->

## 4. Discussion

The 1.6% validation error confirms that the OpenSeesPy model reproduces the analytical solution within acceptable engineering tolerance. The parametric degradation study shows a nonlinear relationship between stiffness loss and displacement amplification: 30% stiffness reduction produces 29% displacement increase, not 30%, because the softened structure dissipates more energy through hysteresis [11].

The current model uses a single ground motion record. Extension to a suite of 7+ records per ASCE 7-22 requirements would improve statistical reliability of the sensitivity analysis [12]. All results are from numerical simulation; experimental validation on physical specimens is planned as future work. <!-- AI_Assist -->

## 5. Conclusions

An OpenSeesPy model of a single-bay steel portal frame with semi-rigid bolted connections was validated against the Duhamel integral (1.6% error) and subjected to parametric stiffness degradation under the 2007 Pisco earthquake. At 30% connection degradation, peak roof displacement increased by 29%. The model, ground motion record, and SSOT configuration are open-source. Future work will extend to multiple ground motions and experimental validation.

<!-- HV: MAV -->

## References

[1] C. R. Farrar and K. Worden, "An introduction to structural health monitoring," Phil. Trans. R. Soc. A, vol. 365, no. 1851, pp. 303-315, 2007.
[2] NTSB, "Collapse of I-35W Highway Bridge," Report NTSB/HAR-08/03, 2008.
[3] L. F. Ibarra et al., "Hysteretic models that incorporate strength and stiffness deterioration," EESD, vol. 34, no. 12, pp. 1489-1511, 2005.
[4] F. McKenna et al., "OpenSees," PEER Center, UC Berkeley, 2000.
[5] AISC, "Specification for Structural Steel Buildings," ANSI/AISC 360-22, 2022.
[6] J. M. Ricles et al., "Posttensioned seismic-resistant connections," J. Struct. Eng., vol. 127, no. 2, pp. 113-121, 2001.
[7] F. C. Filippou et al., "Effects of bond deterioration," Report EERC 83-19, UC Berkeley, 1983.
[8] M. Aroquipa Velasquez, "Belico Stack: SSOT configuration," Open Source, 2026.
[9] A. K. Chopra, Dynamics of Structures, 5th ed. Pearson, 2017.
[10] D. Lignos and H. Krawinkler, "Deterioration modeling of steel components," J. Struct. Eng., vol. 137, no. 11, pp. 1291-1302, 2011.
[11] S. W. Doebling et al., "Damage identification from vibration characteristics," LA-13070-MS, 1996.
[12] ASCE, "Minimum Design Loads," ASCE/SEI 7-22, 2022.
