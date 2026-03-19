---
type: cover_letter
journal: "SPIE Smart Structures and NDE 2027"
paper_title: "Wave-Equation Constrained PINN for Acoustic Emission Source Localization in Bolted Connections: A Cyber-Physical Digital Twin Framework with ifcJSON Middleware"
date: "March 17, 2026"
status: draft
---

March 17, 2026

Dear Program Committee, SPIE SS&NDE 2027,

We are pleased to submit our manuscript entitled **"Wave-Equation Constrained PINN for Acoustic Emission Source Localization in Bolted Connections: A Cyber-Physical Digital Twin Framework with ifcJSON Middleware"** for consideration
for publication in *SPIE Smart Structures and NDE 2027*.

## Summary

This paper presents a wave-equation constrained physics-informed neural network (PINN) for passive acoustic emission (AE) source localization in bolted steel plates, trained exclusively on synthetic data generated via OpenSeesPy across four torque-loss scenarios (0–100%), and coupled to a cyber-physical digital twin through an ifcJSON middleware layer. The framework closes a gap in existing interoperability standards by embedding an inverse localization solver upstream of the ORNL ifcJSON serialization pipeline, enabling the digital twin to autonomously update its damage-state representation from passive AE observations generated during operational loading. A complete open-source toolchain — from synthetic data generation through PINN inference to BIM-compatible ifcJSON export — is provided as a reproducible baseline for subsequent experimental validation.

## Key Highlights

1. Novel integration of a wave-equation constrained PINN inverse solver with ifcJSON digital twin middleware, achieving a global localization MAE of **8.33 mm** (< 2.8% of the 300 mm plate dimension) with a physically consistent monotonic damage gradient from 4.94 mm (intact) to 12.83 mm (full loose, 100% torque loss) for the unconstrained baseline (λ = 0); the physics constraint selectively improves the highest-noise scenario, reducing full-loose MAE from 12.83 mm to 12.47 mm.
2. Ablation study confirming that the wave-equation physics regularization (λ = 0.1) acts noise-adaptively: it reduces full-loose localization error by −0.36 mm (12.83 → 12.47 mm) relative to the unconstrained baseline (λ = 0), while the global MAE shifts from 8.33 mm to 8.74 mm (+0.41 mm), consistent with the theoretical role of PDE collocation as a scenario-selective manifold prior — improving the highest-noise case at the cost of a marginal global penalty.
3. End-to-end reproducible pipeline (OpenSeesPy synthetic generation → PINN training → ifcJSON export) implemented as an open-source toolchain; data and model artifacts are available at https://github.com/Mikisbell/pinn-bolted-reproducibility.

## Novelty Statement

This work is novel because it combines two capabilities that, to our knowledge, have not been jointly demonstrated in the SHM digital twin literature: a physics-informed inverse localization solver and standards-compliant ifcJSON middleware integration. The ORNL ifcJSON reference implementation (Barbosa et al., 2023) established rigorous data transport from structural sensors to BIM environments but did not address the inverse localization step — mapping raw AE arrival-time observations to spatial damage coordinates. Prior PINN-based AE localization frameworks (e.g., the MFC-PINN of Henkes et al., 2022) demonstrated generalization improvements over unconstrained baselines under noise but used analytically defined domains with damage-independent noise models and reported no connection to standardized digital twin middleware. The present work provides both: a physics-constrained inverse solver calibrated to scenario-specific bolt-loosening noise behavior, and a serialization layer that adheres to the ORNL ifcJSON schema for direct BIM integration — enabling a bidirectional cyber-physical feedback loop without requiring pre-processed localization inputs from an external solver.

## Relevance to SPIE Smart Structures and NDE 2027

This manuscript aligns with the scope of *SPIE Smart Structures and NDE 2027* on multiple tracks. The core technical content addresses passive acoustic emission monitoring and source localization — canonical NDE topics within the Smart Structures and NDE symposium. The use of low-cost Arduino Nano 33 BLE Sense Rev2 hardware as the target acquisition platform directly engages the conference's interest in field-deployable, embedded sensing solutions. The ifcJSON digital twin integration connects to the growing SPIE track on cyber-physical systems and structural digital twins for infrastructure resilience. Finally, the physics-informed machine learning methodology — embedding PDE residuals as training constraints — represents a methodologically current contribution at the intersection of ML and structural mechanics, a topic of increasing prominence in SPIE SS&NDE proceedings. The combination of NDE sensing, PINN-based inverse solvers, low-cost hardware, and BIM-compatible middleware makes this manuscript relevant to multiple SPIE audience segments simultaneously.

## Declarations

- This manuscript has not been published previously and is not under consideration
  by another journal.
- All authors have approved the manuscript and agree with its submission.
- This research received no external funding.
- The authors declare no conflict of interest.
- Data and code availability: https://github.com/Mikisbell/pinn-bolted-reproducibility

## Suggested Reviewers

1. **Tribikram Kundu**, University of Arizona (Department of Civil and Architectural Engineering and Mechanics) — expertise in acoustic emission source localization and ultrasonic NDE; editor of *Acoustic Source Localization* (Wiley, 2014), directly cited as ref [1] in this manuscript. Contact via University of Arizona faculty directory.

2. **Alexander Henkes**, Technische Universität Braunschweig (Institute of Applied Mechanics) — expertise in physics-informed neural networks for elastic wave and AE inverse problems; lead author of the MFC-PINN paper (Henkes, Wessels & Mahnken, *Comput. Methods Appl. Mech. Eng.* 2022, 396, 114990), cited as ref [28] in this manuscript. Contact: a.henkes@tu-braunschweig.de (verify current affiliation before submission).

3. **Victor Giurgiutiu**, University of South Carolina (Department of Mechanical Engineering) — expertise in piezoelectric wafer active sensors, guided-wave SHM, and structural NDE with embedded sensor networks; author of *Structural Health Monitoring with Piezoelectric Wafer Active Sensors* (Academic Press, 2014), cited as ref [24] in this manuscript. Contact via University of South Carolina faculty directory.

We believe this work makes a significant contribution to the field and look
forward to hearing from you.

Sincerely,



