# Tarjetas Trello — Wave 4: Data Analysis Service (Python + Flask)

> **Servicio:** `data-analysis` · 2 instancias (2× Alibaba Cloud)  
> **Stack:** Python + Flask  
> **Duración:** 8–12 días · 1–2 personas  
> **Dependencia:** Wave 3 completa (Early Warning operativo)  
> **Referencia:** Bai et al. (2020) §2.4 — Service Layer

---

## Lista: To Do

---

### 🃏 Card 4X0 — Setup del proyecto Flask + estructura base

**Lista:** To Do  
**Asignado a:** Persona A + Persona B (juntos — medio día)  
**Estimación:** 0.5 días  
**Bloqueo:** debe completarse antes de 4A1, 4A2, 4B1, 4B2

**Descripción:**  
Crear el repositorio y la estructura base del servicio `data-analysis` para que ambas personas puedan trabajar en paralelo sin conflictos de estructura. Esta tarjeta es el equivalente a la Tarea 0 pero para Wave 4.

**Estructura de carpetas acordada:**
```
data-analysis/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── routes/
│   │   ├── outliers.py      # 4A1
│   │   ├── denoise.py       # 4A2
│   │   ├── regression.py    # 4B1
│   │   └── predict.py       # 4B2
│   ├── services/            # lógica de negocio, separada de los endpoints
│   └── cache.py             # wrapper Redis (prefix analysis_cache:)
├── tests/
├── requirements.txt
├── Dockerfile
├── deploy/
│   └── data-analysis.service   # systemd unit
└── README.md
```

**Subtareas:**
1. Crear repo, `requirements.txt` con todas las librerías (`flask`, `numpy`, `scipy`, `PyWavelets`, `PyEMD`, `scikit-learn`, `statsmodels`, `redis`).
2. Flask app factory con blueprint vacío por módulo (uno por cada card 4A1–4B2).
3. Endpoint `GET /health` que responde `{"status": "ok"}` — sin lógica de librerías aún.
4. `GET /` devuelve lista de endpoints disponibles (autodiscovery mínimo).
5. Swagger/OpenAPI configurado (`flask-smorest` o `flasgger`) — vacío pero funcional.
6. Pipeline CI básico: install + `pytest` (aunque no haya tests aún).

**Definition of Done:**
- [ ] Repo creado y cloneable por ambas personas.
- [ ] `flask run` levanta sin errores.
- [ ] `GET /health` responde `200`.
- [ ] Blueprints vacíos registrados para `outliers`, `denoise`, `regression`, `predict`.
- [ ] CI pasa en verde (aunque con 0 tests).

---

### 🃏 Card 4A1 — Identificación de outliers

**Lista:** To Do  
**Asignado a:** Persona A  
**Estimación:** 2 días

**Descripción:**  
Implementar los tres criterios de detección de outliers descritos en el paper (§2.4):

- **Pauta criterion (3-sigma):** marcar como outlier toda lectura fuera de μ ± 3σ de la serie.
- **Chauvenet criterion:** calcular la probabilidad de observar el valor y rechazar si n·P < 0.5.
- **Interquartile Range (IQR):** outlier si valor < Q1 − 1.5·IQR o > Q3 + 1.5·IQR.

Exponer un endpoint REST que recibe una serie de tiempo y devuelve los índices de los puntos identificados como outliers, con el criterio aplicado y el valor umbral.

**Endpoint:**
```
POST /analysis/outliers
Body: { "values": [...], "timestamps": [...], "method": "3sigma|chauvenet|iqr" }
Response: { "outlier_indices": [...], "method": "...", "threshold": ... }
```

**Librerías:** `numpy`, `scipy`

**Definition of Done:**
- [ ] Los 3 criterios implementados y testeados con series sintéticas.
- [ ] Tests con datos GNSS reales del caso Shangtan (sensores GXZM-DB01 a GXZM-DB08).
- [ ] Mensajes inválidos devuelven `400` con mensaje descriptivo.
- [ ] Endpoint documentado en Swagger/OpenAPI.

---

### 🃏 Card 4A2 — Denoising de señales

**Lista:** To Do  
**Asignado a:** Persona A  
**Estimación:** 2 días

**Descripción:**  
Implementar los tres métodos de denoising descritos en el paper (§2.4):

- **Wavelet:** descomposición por wavelets con umbralización de coeficientes (`PyWavelets`).
- **EMD — Empirical Mode Decomposition:** descomponer en IMFs y reconstruir eliminando las de alta frecuencia (`PyEMD`).
- **SVM-based denoising:** entrenar un regresor SVM sobre la serie y usar la predicción como señal denoised (`scikit-learn`).

El endpoint recibe la serie ruidosa y el método, y devuelve la señal filtrada junto con los parámetros aplicados.

**Endpoint:**
```
POST /analysis/denoise
Body: { "values": [...], "timestamps": [...], "method": "wavelet|emd|svm" }
Response: { "denoised_values": [...], "method": "...", "params": { ... } }
```

**Librerías:** `PyWavelets`, `PyEMD`, `scikit-learn`

**Definition of Done:**
- [ ] Los 3 métodos implementados.
- [ ] Comparativa visual (matplotlib) del efecto de cada método sobre un segmento de datos Shangtan, guardada como artefacto de test.
- [ ] Endpoint documentado en Swagger/OpenAPI.
- [ ] Tests unitarios por método con series sintéticas de ruido gaussiano.

---

### 🃏 Card 4B1 — Regresión

**Lista:** To Do  
**Asignado a:** Persona B  
**Estimación:** 2 días

**Descripción:**  
Implementar los dos modelos de regresión descritos en el paper (§2.4):

- **Regresión polinomial:** ajuste de polinomio de grado `n` (parámetro de entrada) por mínimos cuadrados (`numpy.polyfit`).
- **Regresión Bayesiana:** ajuste con priors gaussianos; devuelve distribución posterior de coeficientes (`scikit-learn BayesianRidge`).

El endpoint recibe la serie de tiempo, el modelo y el grado (para polinomial), y devuelve los coeficientes del modelo ajustado + la curva ajustada.

**Endpoint:**
```
POST /analysis/regression
Body: { "values": [...], "timestamps": [...], "model": "polynomial|bayesian", "degree": 3 }
Response: { "coefficients": [...], "fitted_values": [...], "r2_score": ..., "model": "..." }
```

**Librerías:** `numpy`, `scikit-learn`

**Definition of Done:**
- [ ] Ambos modelos implementados.
- [ ] Tests de bondad de ajuste (R²) con datos de desplazamiento acumulado del caso Shangtan (Figura 8 del paper).
- [ ] Endpoint documentado en Swagger/OpenAPI.
- [ ] El servicio responde en < 2s para series de hasta 10.000 puntos.

---

### 🃏 Card 4B2 — Predicción: ARIMA y Grey Model GM(1,1)

**Lista:** To Do  
**Asignado a:** Persona B  
**Estimación:** 3 días

**Descripción:**  
Implementar los dos modelos de predicción descritos en el paper (§2.4):

- **ARIMA:** para series estacionarias o estacionarizables. Detectar orden (p,d,q) automáticamente o aceptarlos como parámetros. Usar `statsmodels.tsa.arima.model.ARIMA`. Devolver valores predichos con intervalos de confianza al 95%.
- **Grey Model GM(1,1):** para series cortas (≥ 4 puntos) con tendencia monotónica. Implementar desde cero: acumulación (AGO), ecuación de desarrollo en sombra, ajuste de coeficientes b y a, predicción inversa (IAGO). Especialmente útil cuando ARIMA no converge por falta de datos.

**Endpoint:**
```
POST /analysis/predict
Body: {
  "values": [...],
  "timestamps": [...],
  "model": "arima|gm11",
  "horizon": 30,
  "arima_order": [1, 1, 1]   // opcional, solo para arima
}
Response: {
  "predicted_values": [...],
  "predicted_timestamps": [...],
  "confidence_lower": [...],   // solo arima
  "confidence_upper": [...],   // solo arima
  "model": "...",
  "params": { ... }
}
```

**Librerías:** `statsmodels` (ARIMA), implementación propia (GM(1,1))

**Definition of Done:**
- [ ] ARIMA implementado con manejo de series no estacionarias (diferenciación automática).
- [ ] GM(1,1) implementado y testeado contra los valores calculados en el paper.
- [ ] Predicción validada sobre los **últimos 30 días** del caso Lingzhan (sensores LZ-DB01, LZ-DB02, LZ-DB03).
- [ ] Endpoint documentado en Swagger/OpenAPI.
- [ ] Errores de convergencia de ARIMA manejados con fallback informativo (no 500).

---

### 🃏 Card 4A3 — Integración con Early Warning + Caché Redis + Deploy

**Lista:** To Do  
**Asignado a:** Persona A  
**Estimación:** 2 días  
**Bloqueo:** requiere 4A1, 4A2, 4B1, 4B2 completas

**Descripción:**  
Integrar Data Analysis con Early Warning y poner el servicio en producción.

**Subtareas:**

1. **Integración con Early Warning:** Early Warning ya llama a `POST /analysis/*` desde la tarea 3A3. Verificar que los reportes periódicos incluyen sección de predicción (ARIMA o GM(1,1) según longitud de la serie) y sección de denoising.

2. **Caché Redis:** implementar caché de resultados con TTL de 1 hora. Clave de caché: `analysis:{hash(body)}`. Si los datos de entrada no cambiaron, devolver resultado cacheado sin recalcular. Usar el mismo Redis de Wave 1 (`sensor_buffer` prefix ya documentado; usar prefix `analysis_cache:`).

3. **Health check + Consul:** endpoint `/health` que verifica que las librerías críticas están disponibles (`import pywt`, `import PyEMD`, `import statsmodels`). Registro en Consul al arranque con tags `version`, `lang-python`, `env`. Heartbeat cada 10s.

4. **Deploy 2 instancias:** desplegar en los 2 servidores Alibaba Cloud (Table 2 del paper). Nginx balancea entre ellas (round-robin).

**Definition of Done:**
- [ ] Early Warning genera reporte con sección de predicción sobre datos reales.
- [ ] Caché Redis operativa: segunda llamada idéntica no recalcula (verificado por latencia y logs).
- [ ] Latencia del endpoint < 2s para series de hasta 10.000 puntos (medida sin caché).
- [ ] 2 instancias registradas en Consul con estado `healthy`.
- [ ] Nginx balancea tráfico entre las 2 instancias (verificado por logs).

---

## Lista: Punto de sincronización Wave 4

> ✅ **Wave 4 cierra cuando:**
> - Early Warning genera reportes periódicos que incluyen denoising + predicción.
> - La predicción está validada sobre los últimos 30 días del caso Lingzhan.
> - Las 2 instancias de `data-analysis` están registradas en Consul y sirviendo tráfico.
> - Latencia < 2s para series de 10.000 puntos.

---

## Referencia de algoritmos (del paper §2.4)

| Módulo | Algoritmos | Librería |
|---|---|---|
| Outliers | Pauta criterion, Chauvenet criterion, IQR | `numpy`, `scipy` |
| Denoising | Wavelet, EMD, SVM | `PyWavelets`, `PyEMD`, `scikit-learn` |
| Regresión | Polynomial regression, Bayesian regression | `numpy`, `scikit-learn` |
| Predicción | ARIMA, Grey Model GM(1,1) | `statsmodels`, implementación propia |
