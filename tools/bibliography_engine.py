"""
tools/bibliography_engine.py — Dynamic Citation Engine for the EIU
===================================================================
Injects academic references into the final Markdown article based on
the methodological bases consumed during the Research Director campaign.

Categories:
  - SHM & Structural Engineering
  - Recycled Concrete / Alternative Materials
  - Seismic Engineering & Ground Motion
  - Edge Computing & IoT
  - Machine Learning & Deep Learning for SHM
  - Signal Processing & Kalman Filtering
  - Cryptography & Data Integrity
  - Digital Twins
  - Codes & Standards
"""

from pathlib import Path

# Master Citation Database (Q1-Conference Knowledge Vault)
CITATION_VAULT = {

    # ═══════════════════════════════════════════════════════════════
    # SHM & STRUCTURAL ENGINEERING
    # ═══════════════════════════════════════════════════════════════
    "shm_wsn": (
        "Lynch, J. P., & Loh, K. J. (2006). "
        "'A summary review of wireless sensors and sensor networks for "
        "structural health monitoring'. Shock and Vibration Digest, 38(2), 91-130."
    ),
    "farrar_worden_2007": (
        "Farrar, C. R., & Worden, K. (2007). "
        "'An introduction to structural health monitoring'. "
        "Philosophical Transactions of the Royal Society A, 365(1851), 303-315."
    ),
    "sohn_2004": (
        "Sohn, H., Farrar, C. R., Hemez, F. M., et al. (2004). "
        "'A review of structural health monitoring literature: 1996-2001'. "
        "Los Alamos National Laboratory Report, LA-13976-MS."
    ),
    "brownjohn_2007": (
        "Brownjohn, J. M. W. (2007). "
        "'Structural health monitoring of civil infrastructure'. "
        "Philosophical Transactions of the Royal Society A, 365(1851), 589-622."
    ),
    "doebling_1996": (
        "Doebling, S. W., Farrar, C. R., Prime, M. B., & Shevitz, D. W. (1996). "
        "'Damage identification and health monitoring of structural and mechanical "
        "systems from changes in their vibration characteristics: A literature review'. "
        "Los Alamos National Laboratory Report, LA-13070-MS."
    ),
    "worden_cross_2018": (
        "Worden, K., Cross, E. J., Dervilis, N., Papatheou, E., & Antoniadou, I. (2018). "
        "'Structural health monitoring: from structures to systems-of-systems'. "
        "IFAC-PapersOnLine, 51(24), 1-17."
    ),

    # ═══════════════════════════════════════════════════════════════
    # RECYCLED CONCRETE / ALTERNATIVE MATERIALS
    # ═══════════════════════════════════════════════════════════════
    "rilem_recycled": (
        "RILEM TC 235-CTC (2018). "
        "'Recommendations for the formulation, manufacturing and modeling of "
        "recycled aggregate concrete'. Materials and Structures, 51(5), 1-13."
    ),
    "silva_2014": (
        "Silva, R. V., de Brito, J., & Dhir, R. K. (2014). "
        "'Properties and composition of recycled aggregates from construction "
        "and demolition waste suitable for concrete production'. "
        "Construction and Building Materials, 65, 201-217."
    ),
    "xiao_2012": (
        "Xiao, J., Li, W., Fan, Y., & Huang, X. (2012). "
        "'An overview of study on recycled aggregate concrete in China (1996-2011)'. "
        "Construction and Building Materials, 31, 364-383."
    ),
    "tam_2005": (
        "Tam, V. W. Y., Gao, X. F., & Tam, C. M. (2005). "
        "'Microstructural analysis of recycled aggregate concrete produced from "
        "two-stage mixing approach'. Cement and Concrete Research, 35(6), 1195-1203."
    ),
    "behera_2014": (
        "Behera, M., Bhattacharyya, S. K., Minocha, A. K., Deoliya, R., & Maiti, S. (2014). "
        "'Recycled aggregate from C&D waste & its use in concrete -- A breakthrough "
        "towards sustainability in construction sector: A review'. "
        "Construction and Building Materials, 68, 501-516."
    ),
    "recycled_thermal_2019": (
        "Bravo, M., de Brito, J., Pontes, J., & Evangelista, L. (2019). "
        "'Thermal performance of concrete with recycled aggregates from CDW plants'. "
        "Applied Sciences, 9(2), 267."
    ),

    # ═══════════════════════════════════════════════════════════════
    # SEISMIC ENGINEERING & GROUND MOTION
    # ═══════════════════════════════════════════════════════════════
    "peer_berkeley": (
        "PEER (Pacific Earthquake Engineering Research Center). (2014). "
        "'NGA-West2 Ground Motion Database'. UC Berkeley. "
        "Available: https://ngawest2.berkeley.edu."
    ),
    "cismid_peru": (
        "CISMID (Centro Peruano Japones de Investigaciones Sismicas). "
        "'Red Acelerografica Nacional del Peru (REDACIS)'. UNI, Lima, Peru. "
        "Available: http://www.cismid.uni.edu.pe."
    ),
    "chopra_2017": (
        "Chopra, A. K. (2017). "
        "'Dynamics of Structures: Theory and Applications to Earthquake Engineering'. "
        "5th ed., Pearson."
    ),
    "newmark_hall_1982": (
        "Newmark, N. M., & Hall, W. J. (1982). "
        "'Earthquake Spectra and Design'. EERI Monograph Series."
    ),
    "opensees": (
        "McKenna, F., Fenves, G. L., & Scott, M. H. (2000). "
        "'Open System for Earthquake Engineering Simulation (OpenSees)'. "
        "Pacific Earthquake Engineering Research Center, UC Berkeley."
    ),
    "eurocode8": (
        "CEN. (2004). 'Eurocode 8: Design of structures for earthquake resistance -- "
        "Part 1: General rules, seismic actions and rules for buildings'. "
        "EN 1998-1:2004, European Committee for Standardization."
    ),
    "e030_peru": (
        "SENCICO. (2018). 'Norma E.030: Diseno Sismorresistente'. "
        "Reglamento Nacional de Edificaciones, Lima, Peru."
    ),

    # ═══════════════════════════════════════════════════════════════
    # EDGE COMPUTING & IoT FOR SHM
    # ═══════════════════════════════════════════════════════════════
    "shi_2017": (
        "Shi, W., Cao, J., Zhang, Q., Li, Y., & Xu, L. (2016). "
        "'Edge computing: Vision and challenges'. "
        "IEEE Internet of Things Journal, 3(5), 637-646."
    ),
    "lora_shm_2020": (
        "Tokognon, C. A., Gao, B., Tian, G. Y., & Yan, Y. (2017). "
        "'Structural health monitoring framework based on Internet of Things: "
        "A survey'. IEEE Internet of Things Journal, 4(3), 619-635."
    ),
    "sony_2019": (
        "Sony, S., Laventure, S., & Sadhu, A. (2019). "
        "'A literature review of next-generation smart sensing technology in "
        "structural health monitoring'. Structural Control and Health Monitoring, 26(3), e2321."
    ),
    "park_2008": (
        "Park, G., Sohn, H., Farrar, C. R., & Inman, D. J. (2003). "
        "'Overview of piezoelectric impedance-based health monitoring and path forward'. "
        "Shock and Vibration Digest, 35(6), 451-463."
    ),
    "nicla_sense": (
        "Arduino. (2022). 'Nicla Sense ME: Technical Reference'. "
        "Available: https://docs.arduino.cc/hardware/nicla-sense-me."
    ),

    # ═══════════════════════════════════════════════════════════════
    # MACHINE LEARNING & DEEP LEARNING FOR SHM
    # ═══════════════════════════════════════════════════════════════
    "lstm_ttf": (
        "Hochreiter, S., & Schmidhuber, J. (1997). "
        "'Long short-term memory'. Neural Computation, 9(8), 1735-1780."
    ),
    "pinns_sota": (
        "Raissi, M., Perdikaris, P., & Karniadakis, G. E. (2019). "
        "'Physics-informed neural networks: A deep learning framework for solving "
        "forward and inverse problems involving nonlinear partial differential equations'. "
        "Journal of Computational Physics, 378, 686-707."
    ),
    "xai_trust": (
        "Samek, W., Montavon, G., Vedaldi, A., Hansen, L. K., & Muller, K. R. (Eds.). (2019). "
        "'Explainable AI: Interpreting, Explaining and Visualizing Deep Learning'. "
        "Springer Nature, LNCS 11700."
    ),
    "gal_dropout_2016": (
        "Gal, Y., & Ghahramani, Z. (2016). "
        "'Dropout as a Bayesian approximation: Representing model uncertainty in deep learning'. "
        "In Proceedings of the 33rd International Conference on Machine Learning (ICML), 1050-1059."
    ),
    "mc_dropout_shm": (
        "Abdeljaber, O., Avci, O., Kiranyaz, S., Gabbouj, M., & Inman, D. J. (2017). "
        "'Real-time vibration-based structural damage detection using one-dimensional "
        "convolutional neural networks'. Journal of Sound and Vibration, 388, 154-170."
    ),
    "zhao_2019": (
        "Zhao, R., Yan, R., Chen, Z., Mao, K., Wang, P., & Gao, R. X. (2019). "
        "'Deep learning and its applications to machine health monitoring'. "
        "Mechanical Systems and Signal Processing, 115, 213-237."
    ),
    "bao_2019": (
        "Bao, Y., Chen, Z., Wei, S., Xu, Y., Tang, Z., & Li, H. (2019). "
        "'The state of the art of data science and engineering in structural health monitoring'. "
        "Engineering, 5(2), 234-242."
    ),
    "flah_2021": (
        "Flah, M., Nunez, I., Ben Chaabene, W., & Nehdi, M. L. (2021). "
        "'Machine learning algorithms in civil structural health monitoring: A systematic review'. "
        "Archives of Computational Methods in Engineering, 28(4), 2621-2643."
    ),

    # ═══════════════════════════════════════════════════════════════
    # SIGNAL PROCESSING & KALMAN FILTERING
    # ═══════════════════════════════════════════════════════════════
    "kalman_1960": (
        "Kalman, R. E. (1960). "
        "'A new approach to linear filtering and prediction problems'. "
        "Journal of Basic Engineering, 82(1), 35-45."
    ),
    "yang_kalman_2006": (
        "Yang, J. N., Lin, S., Huang, H., & Zhou, L. (2006). "
        "'An adaptive extended Kalman filter for structural damage identification'. "
        "Structural Control and Health Monitoring, 13(4), 849-867."
    ),

    # ═══════════════════════════════════════════════════════════════
    # CRYPTOGRAPHY & DATA INTEGRITY
    # ═══════════════════════════════════════════════════════════════
    "sha256_nist": (
        "NIST. (2015). 'FIPS 180-4: Secure Hash Standard (SHS)'. "
        "National Institute of Standards and Technology, U.S. Department of Commerce."
    ),
    "blockchain_iot_2019": (
        "Reyna, A., Martin, C., Chen, J., Soler, E., & Diaz, M. (2018). "
        "'On blockchain and its integration with IoT: Challenges and opportunities'. "
        "Future Generation Computer Systems, 88, 173-190."
    ),
    "data_integrity_shm": (
        "Zhu, L., Wu, Y., Gai, K., & Choo, K. K. R. (2019). "
        "'Controllable and trustworthy blockchain-based cloud data management'. "
        "Future Generation Computer Systems, 91, 527-535."
    ),

    # ═══════════════════════════════════════════════════════════════
    # DIGITAL TWINS
    # ═══════════════════════════════════════════════════════════════
    "grieves_2014": (
        "Grieves, M., & Vickers, J. (2017). "
        "'Digital twin: Mitigating unpredictable, undesirable emergent behavior "
        "in complex systems'. In Transdisciplinary Perspectives on Complex Systems, "
        "Springer, 85-113."
    ),
    "tao_2019": (
        "Tao, F., Zhang, H., Liu, A., & Nee, A. Y. C. (2019). "
        "'Digital twin in industry: State-of-the-art'. "
        "IEEE Transactions on Industrial Informatics, 15(4), 2405-2415."
    ),
    "shm_digital_twin_2021": (
        "Ye, C., Butler, L. J., Elshafie, M. Z. E. B., & Middleton, C. R. (2021). "
        "'Evaluating prestressed concrete bridge girder health monitoring data using "
        "a digital twin approach'. In Proceedings of the Institution of Civil Engineers - "
        "Smart Infrastructure and Construction, 174(2), 52-68."
    ),

    # ═══════════════════════════════════════════════════════════════
    # CODES & STANDARDS
    # ═══════════════════════════════════════════════════════════════
    "asce_7_22": (
        "ASCE. (2022). 'ASCE/SEI 7-22: Minimum Design Loads and Associated Criteria "
        "for Buildings and Other Structures'. American Society of Civil Engineers."
    ),
    "aci_318": (
        "ACI. (2019). 'ACI 318-19: Building Code Requirements for Structural Concrete'. "
        "American Concrete Institute."
    ),

    # ═══════════════════════════════════════════════════════════════
    # BELICO STACK (SELF-REFERENCE)
    # ═══════════════════════════════════════════════════════════════
    "belico_stack": (
        "Belico Stack Architecture. (2026). "
        "'Cryptographic Edge-AI Structural Health Monitoring via LoRa IoT'. "
        "Open Source. Available: https://github.com/your-username/belico-stack."
    ),

    # ═══════════════════════════════════════════════════════════════
    # FLUID DYNAMICS & CFD (Water Domain)
    # ═══════════════════════════════════════════════════════════════
    "logg_2012": (
        "Logg, A., Mardal, K.-A., & Wells, G. (2012). "
        "'Automated Solution of Differential Equations by the Finite Element Method: "
        "The FEniCS Book'. Springer."
    ),
    "alnaes_2015": (
        "Alnaes, M. S., Blechta, J., Hake, J., et al. (2015). "
        "'The FEniCS Project Version 1.5'. "
        "Archive of Numerical Software, 3(100)."
    ),
    "scroggs_2022": (
        "Scroggs, M. W., Dokken, J. S., Richardson, C. N., & Wells, G. N. (2022). "
        "'Construction of Arbitrary Order Finite Element Degree-of-Freedom Maps "
        "on Polygonal and Polyhedral Cell Meshes'. "
        "ACM Transactions on Mathematical Software, 48(2)."
    ),
    "john_2016": (
        "John, V. (2016). "
        "'Finite Element Methods for Incompressible Flow Problems'. Springer."
    ),
    "chanson_2004": (
        "Chanson, H. (2004). "
        "'The Hydraulics of Open Channel Flow: An Introduction'. "
        "2nd ed., Butterworth-Heinemann."
    ),
    "dam_shm_2017": (
        "Salazar, F., Moran, R., Toledo, M. A., & Onate, E. (2017). "
        "'Data-Based Models for the Prediction of Dam Behaviour: "
        "A Review and Some Methodological Considerations'. "
        "Archives of Computational Methods in Engineering, 24(1), 1-21."
    ),

    # ═══════════════════════════════════════════════════════════════
    # WIND ENGINEERING & AERODYNAMICS (Air Domain)
    # ═══════════════════════════════════════════════════════════════
    "su2_2016": (
        "Economon, T. D., Palacios, F., Copeland, S. R., et al. (2016). "
        "'SU2: An Open-Source Suite for Multiphysics Simulation and Design'. "
        "AIAA Journal, 54(3), 828-846."
    ),
    "simiu_2019": (
        "Simiu, E., & Yeo, D. (2019). "
        "'Wind Effects on Structures: Modern Structural Design for Wind'. "
        "4th ed., Wiley."
    ),
    "kareem_2020": (
        "Kareem, A., Kwon, D. K., & Tamura, Y. (2020). "
        "'Wind-Induced Vibration of Structures: A Historical and State-of-the-Art Review'. "
        "Journal of Wind Engineering and Industrial Aerodynamics, 206, 104336."
    ),
    "blocken_2015": (
        "Blocken, B. (2015). "
        "'Computational Fluid Dynamics for Urban Physics: Importance, Scales, "
        "Possibilities, Limitations and Ten Tips and Tricks Towards Accurate "
        "and Reliable Simulations'. Building and Environment, 91, 219-245."
    ),
}

# Category mappings for automatic selection
CATEGORIES = {
    "shm": ["shm_wsn", "farrar_worden_2007", "sohn_2004", "brownjohn_2007",
             "doebling_1996", "worden_cross_2018"],
    "recycled_materials": ["rilem_recycled", "silva_2014", "xiao_2012", "tam_2005",
            "behera_2014", "recycled_thermal_2019"],
    "seismic": ["peer_berkeley", "cismid_peru", "chopra_2017",
                "newmark_hall_1982", "opensees", "eurocode8", "e030_peru"],
    "edge_iot": ["shi_2017", "lora_shm_2020", "sony_2019", "park_2008", "nicla_sense"],
    "ml_dl": ["lstm_ttf", "pinns_sota", "xai_trust", "gal_dropout_2016",
              "mc_dropout_shm", "zhao_2019", "bao_2019", "flah_2021"],
    "signal": ["kalman_1960", "yang_kalman_2006"],
    "crypto": ["sha256_nist", "blockchain_iot_2019", "data_integrity_shm"],
    "digital_twin": ["grieves_2014", "tao_2019", "shm_digital_twin_2021"],
    "codes": ["asce_7_22", "aci_318", "e030_peru", "eurocode8"],
    "cfd": ["logg_2012", "alnaes_2015", "scroggs_2022", "john_2016"],
    "hydraulics": ["chanson_2004", "dam_shm_2017"],
    "wind": ["su2_2016", "simiu_2019", "kareem_2020", "blocken_2015"],
}


def get_refs_by_categories(categories: list) -> list:
    """Return unique citation keys for the given category names."""
    keys = []
    for cat in categories:
        keys.extend(CATEGORIES.get(cat, []))
    return list(dict.fromkeys(keys))  # preserve order, remove dupes


def generate_bibliography(sources_used: list, style: str = "numbered") -> str:
    """
    Build the References section for the Markdown paper.

    Args:
        sources_used: list of citation keys or category names
        style: 'numbered' (default) or 'apa'
    """
    # Expand category names into individual keys
    expanded = []
    for s in sources_used:
        if s in CATEGORIES:
            expanded.extend(CATEGORIES[s])
        else:
            expanded.append(s)

    # Default sources always included
    default_sources = ["belico_stack", "shm_wsn"]
    all_sources = list(dict.fromkeys(default_sources + expanded))

    bib_text = "\n## References\n\n"
    for idx, key in enumerate(all_sources, 1):
        if key in CITATION_VAULT:
            bib_text += f"[{idx}] {CITATION_VAULT[key]}\n\n"
        else:
            bib_text += f"[{idx}] *Unknown citation key:* `{key}`\n\n"

    return bib_text


def generate_conference_bibliography(extra_keys: list = None) -> str:
    """
    Generate a focused bibliography for a conference paper (20-30 refs).
    Selects the most impactful references from each category.
    """
    conference_keys = [
        # SHM core (3)
        "farrar_worden_2007", "sohn_2004", "shm_wsn",
        # Recycled Concrete (2)
        "silva_2014", "behera_2014",
        # Seismic (4)
        "peer_berkeley", "chopra_2017", "opensees", "e030_peru",
        # Edge IoT (3)
        "shi_2017", "lora_shm_2020", "nicla_sense",
        # ML/DL (4)
        "lstm_ttf", "gal_dropout_2016", "bao_2019", "flah_2021",
        # Signal (1)
        "kalman_1960",
        # Crypto (2)
        "sha256_nist", "blockchain_iot_2019",
        # Digital Twin (2)
        "grieves_2014", "tao_2019",
        # Codes (2)
        "asce_7_22", "eurocode8",
        # Self (1)
        "belico_stack",
    ]
    if extra_keys:
        conference_keys.extend(extra_keys)

    conference_keys = list(dict.fromkeys(conference_keys))
    return generate_bibliography(conference_keys)


if __name__ == "__main__":
    print(f"Total references in vault: {len(CITATION_VAULT)}")
    print("\nConference bibliography preview:")
    print(generate_conference_bibliography())
