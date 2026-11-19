# Migración del recomendador Nexus a SageMaker

Mismo pipeline del notebook 03 (celda 25): `ColumnTransformer` con `OrdinalEncoder` sobre
`region`, `canal_captacion`, `categoria`, `marca` + `HistGradientBoostingClassifier`
(`learning_rate=0.05`, `max_leaf_nodes=8`, `l2_regularization=0.0`, `max_iter=150`,
`random_state=42`), 25 features en el orden de `esquema.json`, ajuste final con
entrenamiento + validación (18.125 filas, 3.625 positivas) y corrección de popularidad
`pop_alpha * log(n_compradores + eps_pop)` aplicada por la API, igual que en EP2.

Datos exportados sin `usuario_id`, `sku` ni `corte`: 2,4 MB en CSV con features y etiqueta.

## Flujo

1. `exportar_datos.py` — corre donde haya pandas 3 (contenedor de la IA o el de auditoría).
   Genera `salida/train.csv`, `salida/validation.csv` y `esquema.json`.
2. `aws_entrenar.py` — sube datos y código, lanza el Training Job en `ml.m5.large`.
3. `Dockerfile.ecr` — imagen derivada del contenedor oficial (ver limitación 3).
4. `desplegar.py` — empaqueta el artefacto con `code/` (handler + esquema), crea modelo y
   configuración serverless y deja el endpoint `nexus-reco` InService.
5. `probar.py` — paridad, entradas inválidas, latencia y métricas contra el artefacto previo.
6. La IA usa `app/sagemaker_cliente.py` con `SAGEMAKER_ENDPOINT=nexus-reco`; el puntaje se
   calcula en SageMaker y la API conserva consentimiento, exclusiones, prior y top-4..8.

## Recursos creados (us-east-1, LabRole, sin claves de acceso)

| Recurso | Nombre | Detalle |
|---|---|---|
| Bucket | `nexus-sagemaker-222104404118` | `nexus/datos` 2,4 MB; `nexus/modelos` ≈ 260 KB |
| Training Job | `nexus-reco-20261119-000622` | ml.m5.large, 69 s facturados |
| Artefacto | `.../nexus/modelos/nexus-reco-20261119-000622/output/model.tar.gz` | sklearn 1.9.0 |
| Repositorio ECR | `nexus-reco` | tag `1.9-0-root`, ~2,5 GB |
| Endpoint | `nexus-reco` | serverless 3072 MB, concurrencia 2, modelo `nexus-reco-20261119-012857` |
| Configuración previa | `nexus-reco-20261119-011734` | mismo artefacto, sirve de rollback inmediato |
| IA en EC2 | `nexus-ia:ep3-sagemaker` | `SAGEMAKER_ENDPOINT=nexus-reco`, `SAGEMAKER_TIMEOUT=10` |

## Evidencia (19 de noviembre de 2026, UTC)

- Paridad endpoint vs artefacto local: 2.995 filas, diferencia máxima **0.00e+00**.
- Entradas inválidas (24 columnas, `Content-Type: text/csv`) rechazadas con `ModelError`.
- Endpoint directo, matriz de 1.497 filas: p50 **114 ms**, p95 **191 ms** (20 llamadas, 3/s).
- Ruta pública HTTPS en caliente: 6 llamadas, p50 **163 ms**, máximo **244 ms**.
- Tras desplegar, la primera petición pública cayó al respaldo (502 del contenedor en arranque);
  desde la segunda, todas respondieron con el modelo. También se observó un timeout de 4 s por
  arranque en frío tras 18 minutos sin tráfico.
- Métricas con prior sobre `ranking_validacion` (641 usuarios, K=5) y pares de validación:

| Modelo | AUC pares | AP pares | nDCG@5 | MAP@5 | hit@5 |
|---|---|---|---|---|---|
| Nuevo (SageMaker) | 0.7210 | 0.4590 | 0.2240 | 0.1816 | 0.3838 |
| Previo EP2 | 0.7211 | 0.4590 | 0.2241 | 0.1816 | 0.3838 |

- Recomendaciones públicas idénticas a las de antes del cambio para U100002, U100003 y U100004
  (dos rondas en caliente).
- Fallback real: contenedor con `SAGEMAKER_ENDPOINT=nexus-reco-inexistente` devolvió
  `origen: fallback`, `motivo: error al calcular la predicción` y más vendidos.
- Archivos: `sagemaker/evidencias/{entrenamiento,despliegue-final,pruebas-endpoint,limitacion-serverless}.txt`,
  `antes-*.json` y `despues-*.json`.

## Limitaciones

1. `validacion.pkl` también se usó en el ajuste final: sus métricas son diagnóstico, no
   prueba independiente. No existe conjunto de prueba separado.
2. El contenedor oficial trae scikit-learn 1.9.0; el artefacto previo se entrenó con 1.9.1.
   La paridad medida fue exacta, pero no se probó con datos fuera de este proyecto.
3. El contenedor oficial no puede instalar el handler (`pip` en `/opt/venv` sin permisos) y el
   endpoint corre sin privilegios. La imagen `Dockerfile.ecr` solo habilita escritura en
   `/opt/venv`; no agrega datos ni secretos. Sin ella el modelo no arranca.
4. **El laboratorio deniega endpoints de tiempo real.** Con `LabRole`, `CreateEndpointConfig`
   con `InstanceType` devuelve *explicit deny* en `VocLabPolicy3`; solo queda serverless.
5. **Arranque en frío del serverless: 19–23 s medidos.** El dominio corta a los 4 s, así que la
   primera petición tras desplegar o tras 10–15 min sin tráfico cae al respaldo; después responde
   en 110–250 ms. Además, con 2048 MB los `gunicorn` workers recibieron SIGKILL (memoria); con
   3072 MB y 2 handlers el endpoint se mantuvo estable. Con concurrencia 1 el endpoint empieza a
   devolver `ThrottlingException` bajo ráfagas de 3/s, por eso se quedó en 2.
6. La IA todavía carga `modelo_recomendador.joblib` local para metadatos y verificación de
   versión, pero **no puntúa localmente**: si `SAGEMAKER_ENDPOINT` está definido, todo puntaje
   viene del endpoint.

## Reproducir

```bash
# 1. datos (en un entorno con pandas 3, desde la raíz del repositorio)
python sagemaker/exportar_datos.py

# 2. entrenamiento
python sagemaker/aws_entrenar.py

# 3. imagen derivada (solo si no existe)
export DOCKER_CONFIG=$(mktemp -d)
aws ecr get-login-password --region us-east-1 |
  docker login --username AWS --password-stdin 222104404118.dkr.ecr.us-east-1.amazonaws.com
docker buildx build --provenance=false --sbom=false \
  --output type=image,name=222104404118.dkr.ecr.us-east-1.amazonaws.com/nexus-reco:1.9-0-root,oci-mediatypes=false,push=true \
  -f sagemaker/Dockerfile.ecr sagemaker

# 4. endpoint
NEXUS_IMAGEN=222104404118.dkr.ecr.us-east-1.amazonaws.com/nexus-reco:1.9-0-root \
NEXUS_MEMORIA=3072 NEXUS_CONCURRENCIA=2 \
  python sagemaker/desplegar.py

# 5. pruebas (requiere pandas 3 y boto3; en EC2 con red del host)
# El primer arranque tarda 20 s: conviene calentar antes o usar SAGEMAKER_TIMEOUT=30.
SAGEMAKER_TIMEOUT=30 python sagemaker/probar.py
```

Antes de una demostración, ejecutar `probar.py` o una invocación de calentamiento: tras 10–15
minutos sin tráfico el primer request público cae al respaldo por el arranque en frío.

Costos aproximados de esta corrida: Training Job 69 s de `ml.m5.large` (centavos); endpoint
serverless de 3072 MB facturado por uso (las pruebas suman menos de 150 invocaciones de
~0,1 s, más los arranques en frío); ECR ~2,5 GB ≈ USD 0,25/mes; S3 < 3 MB. No se consultó la
factura final.

## Revertir

```bash
cd /home/ubuntu/nexus-dominio
cp compose.yaml.before-sagemaker compose.yaml
docker compose -p equipo2 up -d ia
# opcional, si se quiere apagar el endpoint:
aws sagemaker delete-endpoint --endpoint-name nexus-reco --region us-east-1
```
