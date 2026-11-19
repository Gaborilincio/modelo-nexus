# Tareas de migración SageMaker

Completado el 19 de noviembre de 2026. Resumen, costos y límites en `sagemaker/README.md`.

## 1. Datos y compatibilidad
- [x] Comparar metadatos/artefactos locales con EC2, auditar cortes y consumidores, y verificar imagen compatible.
- Auditoría: 13.400 filas de entrenamiento (3 cortes), 4.725 de validación, 641 usuarios en ranking; 25 features de las que 4 son categóricas; pickle ilegible con pandas 2.2.3, legible con 3.0.6.
- Imagen oficial validada (Python 3.12, scikit-learn 1.9.0); limitación de permisos encontrada en el endpoint y resuelta con `Dockerfile.ecr`.

## 2. Entrenamiento reproducible
- [x] Extraer ajuste del pipeline seleccionado, exportación mínima de datos y evaluación.
- `sagemaker/exportar_datos.py` y `sagemaker/entrenar.py` replican el pipeline y el ajuste con entrenamiento + validación.
- `sagemaker/esquema.json` fija las 25 features y las 4 categóricas; `tests/test_sagemaker.py` comprueba que el handler coincide con el esquema.

## 3. Training Job
- [x] Subir matrices mínimas a prefijo propio y ejecutar entrenamiento con LabRole.
- `nexus-reco-20261119-000622`: Completed en 69 s facturados (ml.m5.large), artefacto en `nexus-sagemaker-222104404118/nexus/modelos/`.

## 4. Endpoint y paridad
- [x] Implementar contrato de inferencia y desplegar endpoint Nexus serverless compatible.
- `nexus-reco` InService (3072 MB, concurrencia 2; el laboratorio deniega tiempo real); paridad 0.00e+00 sobre 2.995 filas; entradas inválidas rechazadas; p50 114 ms y p95 191 ms en el endpoint, p50 163 ms por HTTPS.

## 5. Integración IA
- [x] Sustituir cálculo local de scores por invoke_endpoint con validación, timeouts y fallback.
- `app/sagemaker_cliente.py` + `Recomendador(puntuador=...)`; consentimiento, exclusiones, prior y top-4..8 intactos; `/health` expone `origen_puntajes`.
- Fallback real probado con endpoint inexistente: `origen: fallback` y más vendidos.

## 6. Despliegue y cierre
- [x] Construir IA, actualizar solo su despliegue y comprobar HTTPS con recuperación preparada.
- Imagen `nexus-ia:ep3-sagemaker`, respaldo `compose.yaml.before-sagemaker`; recomendaciones públicas idénticas a las previas.
- [x] Registrar recursos, costos medidos, limitaciones y actualizar RETOMAR_EP3.md.
- `sagemaker/README.md` y evidencias en `sagemaker/evidencias/`; 29 pruebas pasan.
