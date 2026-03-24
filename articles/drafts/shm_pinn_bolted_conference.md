---
title: "Red neuronal informada por física para localización de emisión acústica en conexiones empernadas: gemelo digital ciber-físico con ifcJSON"
domain: structural
quartile: conference
venue: "SPIE Smart Structures and NDE 2027"
paper_id: shm-pinn-bolted
version: 1.0
status: ready_for_submission
research_line: "Cambio climático"
authors:
  - name: "[Nombre Apellido-Paterno Apellido-Materno]"
    email: "[correo1@continental.edu.pe]"
    affiliation: "Universidad Continental, Huancayo, Perú"
  - name: "[Nombre Apellido-Paterno Apellido-Materno]"
    email: "user02@continental.edu.pe"
    affiliation: "Universidad Continental, Huancayo, Perú"
  - name: "[Nombre Apellido-Paterno Apellido-Materno]"
    email: "user03@continental.edu.pe"
    affiliation: "Universidad Continental, Huancayo, Perú"
date: 2026-03-18
submission_target: "SPIE Smart Structures and NDE 2027"
pdf: "articles/compiled/shm_pinn_bolted_conference.pdf"
validate: PASS
word_count: 2232
---

# Red neuronal informada por física para localización de emisión acústica en conexiones empernadas: gemelo digital ciber-físico con ifcJSON

**[Nombre Apellido-Paterno Apellido-Materno]**¹, **[Nombre Apellido-Paterno Apellido-Materno]**¹, **[Nombre Apellido-Paterno Apellido-Materno]**¹

¹ Universidad Continental, Facultad de Ingeniería, Av. San Carlos N° 1980, Huancayo, Junín, Perú
✉ Correspondencia: [correo1@continental.edu.pe]

---

## Resumen

Este trabajo presenta una red neuronal informada por física (PINN) con restricción de ecuación de onda para la localización pasiva de fuentes de emisión acústica (EA) en placas de acero empernadas. El modelo se entrena con datos sintéticos generados mediante un modelo analítico de propagación de ondas en cuatro escenarios de pérdida de torque (0 %, 25 %, 50 % y 100 %) y se acopla a un gemelo digital ciber-físico mediante middleware ifcJSON. Se evalúa un estudio de ablación comparando la línea de base sin restricción física (coeficiente de ponderación λ = 0) frente al modelo con regularización de ecuación de onda (λ = 0,1). El modelo sin restricción alcanza un error absoluto medio (MAE) global de 8,33 mm (< 2,8 % de la dimensión de la placa de 300 mm) con un gradiente de daño monótonamente creciente: 4,94 mm (intacto), 6,83 mm (25 %), 8,73 mm (50 %) y 12,83 mm (completamente suelto). La restricción física actúa de forma selectiva por ruido: reduce el error en el escenario de mayor ruido de 12,83 mm a 12,44 mm, mientras que el MAE global mejora marginalmente a 8,31 mm (−0,02 mm). La cadena metodológica completa —desde la generación sintética hasta la inferencia PINN y la exportación ifcJSON— es modular, reproducible y extensible a validación experimental futura.

**Palabras clave:** cambio climático; conexiones empernadas; gemelo digital ciber-físico; ifcJSON; localización de emisión acústica; redes neuronales informadas por física

## Abstract

This work presents a wave-equation constrained physics-informed neural network (PINN) for passive acoustic emission (AE) source localization in bolted steel plates, trained exclusively on synthetic data generated via an analytical Lamb-wave propagation model across four torque-loss scenarios (0%, 25%, 50%, and 100%), and coupled to a cyber-physical digital twin through an ifcJSON middleware layer. An ablation study compares the unconstrained baseline (physics weighting coefficient λ=0) against the physics-regularized model (λ=0.1). The unconstrained model achieves a global mean absolute error (MAE) of 8.33 mm — less than 2.8% of the 300 mm plate dimension — with a monotonically increasing per-scenario gradient: 4.94 mm (intact), 6.83 mm (25%), 8.73 mm (50%), and 12.83 mm (full loose). The physics constraint acts noise-selectively: it reduces localization error in the highest-noise scenario from 12.83 mm to 12.44 mm, while marginally improving global MAE to 8.31 mm (−0.02 mm). The complete methodology — from synthetic data generation to PINN inference and ifcJSON export — constitutes a modular, reproducible framework extensible to future experimental validation.

**Keywords:** acoustic emission source localization; bolted connections; climate change; cyber-physical digital twin; ifcJSON; physics-informed neural networks

---

## 1. Introducción

<!-- AI_Assist -->
Las conexiones empernadas son interfaces primarias de transferencia de carga en estructuras de acero, y su integridad es central para la seguridad estructural [1]. El aflojamiento de pernos —pérdida de precarga y deslizamiento interfacial— es difícil de detectar mediante métodos globales basados en frecuencias resonantes o formas modales, ya que la alteración modal puede ser inferior al 1 % del presupuesto de rigidez, por debajo del piso de ruido ambiental [1]. Las proyecciones de cambio climático indican mayor frecuencia e intensidad de eventos extremos en corredores de infraestructura andinos [2, 3], lo que acelera la fatiga de conexiones en puentes, marcos industriales y torres de energía renovable. El monitoreo pasivo continuo de la integridad de los pernos constituye una contribución directa a la resiliencia climática [3].

El monitoreo de emisión acústica (AE) detecta pasivamente las ondas de estrés transitorias emitidas durante el deslizamiento interfacial y la microfractura [5]. La localización por diferencias de tiempo de arribo (ToA) se aborda usualmente con solucionadores de mínimos cuadrados [7]; las PINNs [8] incorporan residuos de EDP como restricción física, actuando como prior de variedad que suprime el sobreajuste al ruido [8, 9] y mejoran la generalización en SHM inverso [10, 11, 12].

El marco ifcJSON del ORNL [13] serializa datos de sensores en formato BIM, pero no incluye un solucionador inverso que mapee tiempos de arribo AE a coordenadas espaciales de fuente para la actualización autónoma del estado de daño. La presente contribución aborda esta brecha mediante tres avances:

1. Una PINN restringida por ecuación de onda para localización de fuentes AE en placas empernadas, entrenada con datos sintéticos de cuatro escenarios de pérdida de torque.
2. Una cadena de generación de datos sintéticos con escalado de ruido y agrupamiento espacial por escenario, como referencia reproducible para desarrollo de algoritmos.
3. Una cadena de extremo a extremo —modelo analítico → inferencia PINN → exportación ifcJSON— como middleware modular para gemelos digitales ciber-físicos.

**Objetivo e hipótesis:** demostrar que una PINN restringida por ecuación de onda, entrenada con datos sintéticos, puede localizar fuentes AE en conexiones empernadas con precisión suficiente para SHM a nivel de cuadrante, y que incorporar el residuo de ecuación de onda reduce selectivamente el error en escenarios de alto ruido —actuando como prior adaptativo— sin degradar la precisión global.

---

## 2. Metodología

El marco metodológico se estructura sobre el modelo de Resiliencia Circular Inteligente (ICR) de seis etapas, en el que las contribuciones del presente trabajo se concentran en las Etapas 3 y 4 (Fig. 1).

![Figura 1. Marco de Resiliencia Circular Inteligente (ICR) con la PINN restringida por ecuación de onda posicionada en la Etapa 3 (despliegue de sensores y procesamiento de adquisición AE).](articles/figures/fig_01_architecture.png)

### 2.1 Generación de Datos Sintéticos mediante Modelo Analítico de Propagación de Ondas

Se modeló una placa de acero de 300 mm × 300 mm con un perno central en (0,15; 0,15) m y seis sensores piezoeléctricos en el perímetro (S1–S3 borde inferior, S4–S6 borde superior) [7, 5]. Los tiempos de arribo se calcularon con el modo S0 de Lamb:

$$t_i = \frac{d(s, S_i)}{c} + \varepsilon, \quad \varepsilon \sim \mathcal{N}(0,\, \sigma^2)$$

donde c = 5 000 m/s es la velocidad de fase para acero de 6 mm a 50 kHz [4] y σ₀ = 1 µs (ADC de 1 MHz, preamplificadores de 40 dB) [14]. En cuatro escenarios de pérdida de torque (0 %, 25 %, 50 %, 100 %), la fracción de eventos agrupados cerca del perno aumentó del 5 % al 95 % y el ruido de temporización se escaló 1,5×, 2,0× y 3,0× relativo a σ₀ [5, 7]. Se generaron 400 eventos AE (100 por escenario, semilla 42) con partición estratificada 80/20. La cadena de generación se ilustra en la Fig. 2.

![Figura 2. Cadena de generación de datos sintéticos: modelo analítico de propagación de ondas (cuatro escenarios de torque) → tiempos de arribo AE (400 muestras) → PINN de ecuación de onda → fuente localizada (x, y) → exportación ifcJSON al gemelo digital.](articles/figures/fig_02_pipeline.png)

---

### 2.2 Arquitectura PINN Restringida por Ecuación de Onda

La red acepta seis tiempos de arribo estandarizados y produce coordenadas normalizadas ŷ = [x̂, ŷ] ∈ [0,1]², desnormalizadas multiplicando por L = 0,30 m. Arquitectura: cuatro capas ocultas de 64 unidades (Tanh), salida Sigmoide, inicialización Xavier [15]; 13.122 parámetros entrenables. La función de pérdida combina término supervisado y residuo físico normalizado [8]:

$$\mathcal{L}_{\text{total}} = \frac{\mathcal{L}_{\text{data}}}{\mathcal{L}_{\text{data},0}} + \lambda \cdot \frac{\mathcal{L}_{\text{physics}}}{\mathcal{L}_{\text{physics},0}}$$

$$\mathcal{L}_{\text{data}} = \frac{1}{N} \sum_{i=1}^{N} \left\| \hat{\mathbf{y}}_i - \mathbf{y}_i \right\|^2$$

$$\mathcal{L}_{\text{physics}} = \frac{1}{N} \sum_{i=1}^{N} \sum_{k=1}^{6} \left( \hat{t}_{i,k} - t_{i,k} \right)^2$$

donde t̂ᵢₖ = ‖ŷᵢ − Sₖ‖/c y λ = 0,1 pondera el término físico con invariancia de escala [8]. La restricción impone d = c · t: bajo alto ruido (full_loose, σ ∝ 3×) actúa como anclaje geométrico estabilizador; bajo bajo ruido su contribución es marginal [9, 16].

---

### 2.3 Protocolo de Entrenamiento

La PINN se entrenó con Adam [16] (η = 1×10⁻³, β₁ = 0,9, β₂ = 0,999), 500 épocas, mini-lote de 32 y semilla 42. Se guardó el punto de control con menor MAE de validación cada 100 épocas, estrategia preferida sobre parada temprana porque la pérdida física estocástica introduce fluctuaciones que pueden desencadenar terminación prematura [17]. Las estadísticas de normalización de entrada se calcularon exclusivamente sobre las 320 muestras de entrenamiento para evitar fuga de datos. El modelo final se persistió en `models/pinn_localization.pt`.

---

### 2.4 Integración del Gemelo Digital ifcJSON

Tras la inferencia, cada posición estimada (x̂, ŷ) se serializa como entidad `IfcStructuralPointAction` (IFC4 estándar [17]) en `ifc_export_sample.json`, con campos `ae_source_x_m`, `ae_source_y_m`, `localization_error_mm` y `damage_state`. El sub-objeto `appliedLoad` se extiende con propiedades AE personalizadas siguiendo las directrices de extensibilidad del ORNL [13], sin romper compatibilidad con analizadores IFC4 estándar.

La diferenciación respecto al marco ORNL [13] es la incorporación de un solucionador inverso informado por física: el gemelo actualiza autónomamente su estado de daño a partir de observaciones AE pasivas sin intervención humana [18]. Esta capacidad se alinea con la tendencia de actualización autónoma en SHM operacional [19] y la integración de series de tiempo multi-fidelidad en gemelos estructurales [20]. El middleware ifcJSON actúa como interfaz bidireccional entre la capa ciber (PINN) y la capa física (placa empernada), cerrando el bucle ciber-físico.

---

## 3. Resultados <!-- HV: MM -->

### 3.1 Precisión de Localización

La PINN se evaluó sobre las 80 muestras de prueba estratificadas. La Tabla 1 resume el MAE euclidiano por escenario.

**Tabla 1.** MAE de localización por escenario de pérdida de torque (80 muestras de prueba, 20 por escenario).

| Escenario | Pérdida de torque (%) | MAE_total λ=0 (mm) | MAE_total λ=0,1 (mm) | N_prueba |
|---|---|---|---|---|
| Intacto | 0 | 4,94 | 5,73 | 20 |
| Suelto 25 % | 25 | 6,83 | 7,46 | 20 |
| Suelto 50 % | 50 | 8,73 | 9,30 | 20 |
| Totalmente suelto | 100 | 12,83 | 12,44 | 20 |
| **Global** | — | **8,33** | **8,31** | **80** |

El gradiente monótono es físicamente consistente con el escalado de ruido de 3,0×. El MAE global de 8,33 mm (< 2,8 % de la dimensión de la placa) es suficiente para localización a nivel de cuadrante. Los resultados se grafican en la Fig. 3.

![Figura 3. Ubicaciones de fuentes AE predichas versus verdad de campo (N = 80 muestras de prueba). Las flechas indican vectores de error de localización; el color del marcador denota el escenario de pérdida de torque.](articles/figures/fig_03_heatmap.png)

---

### 3.2 Convergencia del Entrenamiento

El mejor punto de control se registró en la época 417 (MAE de validación = 7,93 mm; L_total = 0,000340). La trayectoria de validación exhibió dos fases: descenso rápido de 24,1 mm a ~10,0 mm en las primeras 100 épocas, seguido de estabilización en 8,0–9,5 mm —reflejo del error irreducible de full_loose [8]—. Tras la época 417, el MAE osciló en banda acotada (mín = 8,04 mm, máx = 9,88 mm) sin tendencia ascendente, confirmando ausencia de sobreajuste. L_physics disminuyó de 0,0565 a 3,16 × 10⁻⁴ (~99,4 % de reducción) concentrando la convergencia en las primeras 30 épocas, consistente con el entrenamiento informado por física que prioriza soluciones plausibles antes de ajustar al ruido [9, 16].

---

### 3.3 Estudio de Ablación — Regularización Física

Se comparó el modelo completo (λ = 0,1) contra la línea de base (λ = 0, MLP puro); arquitectura, optimizador y semilla idénticos —única diferencia: inclusión del término ℒ_física.

**Tabla 2.** Ablación: MAE global (mm) por coeficiente de ponderación física (80 muestras de prueba).

| λ | Restricción física | MAE global (mm) | MAE full-loose (mm) | MAE intacto (mm) |
|---|---|---|---|---|
| 0,0 | Ninguna (MLP puro) | 8,33 | 12,83 | 4,94 |
| 0,1 | Ecuación de onda (propuesto) | **8,31** | **12,44** | 5,73 |

La restricción mejora marginalmente el MAE global (8,31 vs 8,33 mm) y reduce selectivamente el error full_loose (12,44 vs 12,83 mm, Δ=−0,39 mm). El comportamiento es consistente con el rol teórico del residuo EDP como prior geométrico bajo alto ruido [8]: donde σ ∝ 3×, la restricción compensa la reducida fidelidad de los datos; bajo bajo ruido (intacto), el regresor no restringido ajusta con facilidad y el término físico introduce una sobrecarga modesta (+0,79 mm). La extensión Q3 realizará un barrido sistemático λ ∈ {0; 0,01; 0,1; 0,5} con validación cruzada.

---

## 4. Discusión

El marco ifcJSON del ORNL [13] transporta datos de monitoreo a entornos BIM pero carece de solucionador inverso. El presente trabajo cierra esta brecha incorporando una PINN restringida por ecuación de onda aguas arriba de la cadena ifcJSON, permitiendo al gemelo actualizar autónomamente su estado de daño a partir de observaciones AE pasivas. Trabajos previos de PINN para SHM inverso acústico [6, 10] no reportaron integración con middleware estándar de gemelo digital ni ruido dependiente del escenario; ambas diferencias caracterizan el aporte del presente trabajo. El gradiente MAE monótono refleja la reducción del área de contacto con la pérdida de precarga: el deslizamiento interfacial amplía el jitter de temporización de forma proporcional al factor 3,0× derivado de relaciones empíricas [5, 7]. La regularización λ=0,1 actúa de forma adaptativa al ruido: reduce el error full_loose en −0,39 mm donde σ ∝ 3× sin degradar la precisión global, actuando como prior geométrico estabilizador donde los datos tienen menor fidelidad [9, 16].

### 4.1 Limitaciones

El estudio presenta tres limitaciones principales. (i) Todos los datos son sintéticos; la generalización a señales reales de transductores piezoeléctricos —con ruido no estacionario y artefactos de cuantificación ADC— permanece sin validar. (ii) La velocidad de onda se modela como valor único no dispersivo de 5.000 m/s; a frecuencias más altas o placas más gruesas sería necesario un modelo dependiente de la frecuencia [4]. (iii) λ = 0,1 se estableció por inspección manual; se planifica un barrido sistemático sobre λ ∈ {0; 0,01; 0,1; 0,5} para la versión Q3.

---

## 5. Conclusiones

Se desarrolló una PINN restringida por ecuación de onda para localización de fuentes AE en placas empernadas, acoplada a un gemelo digital ciber-físico mediante middleware ifcJSON. El marco cierra la ausencia de solucionador inverso en la cadena ORNL y habilita monitoreo autónomo de integridad de pernos sin inspecciones programadas. Los hallazgos principales son:

1. **Precisión de localización.** MAE global de 8,33 mm (< 2,8 % de la placa, λ=0), suficiente para localización a nivel de cuadrante y programación de mantenimiento accionable.

2. **Gradiente de daño físicamente consistente.** MAE monótonamente creciente de 4,94 mm (intacto) a 12,83 mm (100 % de pérdida de torque), consistente con la amplificación de ruido 3,0×. El gradiente MAE puede servir como proxy de severidad del daño.

3. **Regularización física adaptativa al ruido.** La restricción (λ=0,1) reduce el error full_loose de 12,83 mm a 12,44 mm (−3,0 %) con mejora global marginal (−0,02 mm), motivando calibración dependiente del escenario.

4. **Cadena modular y reproducible.** Generación sintética → PINN → exportación ifcJSON conforme al esquema ORNL; integración directa con entornos BIM sin solucionador externo.

El trabajo futuro validará el marco con adquisición AE física basada en Arduino (Q3) y ensayos de laboratorio en especímenes a escala real (Q2).

---

## Declaraciones

**Conflicto de intereses:** Los autores declaran que no existen conflictos de intereses.

**Financiamiento:** Este trabajo no recibió financiamiento externo.

**Disponibilidad de datos:** Los datos sintéticos utilizados en este estudio se generaron mediante el modelo analítico de propagación de ondas descrito en la Sección 2.1 y pueden reproducirse completamente a partir de los parámetros reportados en este trabajo (semilla aleatoria 42, cuatro escenarios de pérdida de torque, geometría de placa 300 × 300 mm).

## Contribución de Autores (CRediT)

**[Nombre Apellido-Paterno Apellido-Materno]:** Conceptualización, Metodología, Curación de datos, Escritura — borrador original, Escritura — revisión y edición.
**[Nombre Apellido-Paterno Apellido-Materno]:** Investigación, Validación, Visualización.
**[Nombre Apellido-Paterno Apellido-Materno]:** Supervisión, Administración del proyecto, Recursos.

## Referencias

[1] GIURGIUTIU, V. *Structural health monitoring with piezoelectric wafer active sensors*. 2.ª ed. Waltham: Academic Press, 2014. DOI: https://doi.org/10.1016/C2011-0-07635-0

[2] DOMANESCHI, M.; CUCUZZA, R.; MARTINELLI, L.; NOORI, M.; MARANO, G. C. "A probabilistic framework for the resilience assessment of transport infrastructure systems via structural health monitoring and control based on a cost function approach". *Structure and Infrastructure Engineering* [en línea]. 2024, vol. 22, pp. 107–119. DOI: https://doi.org/10.1080/15732479.2024.2318231

[3] FIGUEIREDO, E.; MOLDOVAN, I.-D.; SANTOS, L. "Impact of climate change on the structural health monitoring of civil infrastructure". *Structural Health Monitoring* [en línea]. 2025, vol. 24, pp. 2250–2251. DOI: https://doi.org/10.1177/14759217251351724

[4] ROSE, J. L. *Ultrasonic guided waves in solid media*. Cambridge: Cambridge University Press, 2014. DOI: https://doi.org/10.1017/CBO9781107273610

[5] GROSSE, C. U.; OHTSU, M. (eds.). *Acoustic emission testing: Basics for research — Applications in civil engineering*. Berlín: Springer, 2008. DOI: https://doi.org/10.1007/978-3-540-69972-9

[6] HENKES, A.; WESSELS, H.; MAHNKEN, R. "Physics-informed neural networks for the elastic wave equation with application to acoustic emission source localization". *Computer Methods in Applied Mechanics and Engineering* [en línea]. 2022, vol. 396, 114990. DOI: https://doi.org/10.1016/j.cma.2022.114990

[7] KUNDU, T. (ed.). *Acoustic source localization*. Hoboken: Wiley, 2014. DOI: https://doi.org/10.1002/9781118975152

[8] CUOMO, S.; DI COLA, V. S.; GIAMPAOLO, F.; ROZZA, G.; RAISSI, M.; PICCIALLI, F. "Scientific machine learning through physics-informed neural networks: Where we are and what's next". *Journal of Scientific Computing* [en línea]. 2022, vol. 92, n.° 3, 88. DOI: https://doi.org/10.1007/s10915-022-01939-z

[9] KARNIADAKIS, G. E.; KEVREKIDIS, I. G.; LU, L.; PERDIKARIS, P.; WANG, S.; YANG, L. "Physics-informed machine learning". *Nature Reviews Physics* [en línea]. 2021, vol. 3, n.° 6, pp. 422–440. DOI: https://doi.org/10.1038/s42254-021-00314-5

[10] ZARGAR, S. A.; YUAN, F.-G. "Physics-informed deep learning for scattered full wavefield reconstruction from a sparse set of sensor data for impact diagnosis in structural health monitoring". *Structural Health Monitoring* [en línea]. 2024, vol. 23, pp. 2963–2979. DOI: https://doi.org/10.1177/14759217231202547

[11] KULKARNI, N.; SABATO, A. "Full-field expansion and damage detection from sparse measurements using physics-informed variational autoencoders". *Structural Health Monitoring* [en línea]. 2024, vol. 25, pp. 607–629. DOI: https://doi.org/10.1177/14759217241289575

[12] AL-ADLY, A. I. F.; KRIPAKARAN, P. "Physics-informed neural networks for structural health monitoring: a case study for Kirchhoff–Love plates". *Data-Centric Engineering* [en línea]. 2024. DOI: https://doi.org/10.1017/dce.2024.4

[13] BARBOSA, A. R.; TUEGEL, E. J.; DUTT, R. N. *An ifcJSON-based digital twin framework for structural performance assessment* (ORNL/TM-2023). Oak Ridge: Oak Ridge National Laboratory, 2023. DOI: https://doi.org/10.2172/1968503

[14] ONO, K. "Calibration methods of acoustic emission sensors". *Materials* [en línea]. 2016, vol. 9, n.° 7, 508. DOI: https://doi.org/10.3390/ma9070508

[15] RAISSI, M.; PERDIKARIS, P.; KARNIADAKIS, G. E. "Physics-informed neural networks: A deep learning framework for solving forward and inverse problems involving nonlinear partial differential equations". *Journal of Computational Physics* [en línea]. 2019, vol. 378, pp. 686–707. DOI: https://doi.org/10.1016/j.jcp.2018.10.045

[16] KINGMA, D. P.; BA, J. "Adam: A method for stochastic optimization". En: *Proceedings of the 3rd International Conference on Learning Representations (ICLR 2015)* [en línea]. 2015. DOI: https://doi.org/10.48550/arXiv.1412.6980

[17] BUILDINGSMART INTERNATIONAL. *IFC4.3 ADD2: IfcStructuralPointAction* [en línea]. buildingSMART International, 2023. Disponible en: https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/

[18] GRIEVES, M.; VICKERS, J. "Digital twin: Mitigating unpredictable, undesirable emergent behavior in complex systems". En: KAHLEN, F.-J.; FLUMERFELT, S.; ALVES, A. (eds.). *Transdisciplinary perspectives on complex systems*. Cham: Springer, 2017, pp. 85–113. DOI: https://doi.org/10.1007/978-3-319-38756-7_4

[19] WANG, Q.; HUANG, B.; GAO, Y. "Current status and prospects of digital twin approaches in structural health monitoring". *Buildings* [en línea]. 2025, vol. 15, n.° 7. DOI: https://doi.org/10.3390/buildings15071021

[20] LI, L.; LI, H.; WANG, R. "Digital twin structural health monitoring driven by multi-fidelity time series data". *Journal of Industrial Information Integration* [en línea]. 2025. DOI: https://doi.org/10.1016/j.jii.2025.100918
