# Migración del recomendador real de Nexus a SageMaker

Estado: alcance aprobado por el usuario. Fecha: 18 noviembre 2026.

## Objetivo y supuestos
Migrar entrenamiento e inferencia del modelo del proyecto a SageMaker en us-east-1, con los datos procesados existentes de Nexus y LabRole. «Reales» significa datos del proyecto, no certifica que su origen sea comercial o no sintético.

Conservar la familia/pipeline seleccionados en EP2, orden de features, codificación categórica, corrección por popularidad, consentimiento, exclusión de compras previas y formato de recomendaciones. No sustituirlos por las cinco columnas sintéticas de L10.

Se propone mantener en la API el cálculo de features, candidatos y ranking, y enviar al endpoint únicamente las features necesarias en lotes para obtener scores. El modelo predictivo se ejecutará en SageMaker. La carga del modelo local se conservará solo para verificación y recuperación del despliegue anterior, no como fallback silencioso de inferencia remota.

## Hallazgos que condicionan la implementación
- app/recomendador.py invoca decision_function y agrega pop_alpha * log(n_compradores + eps_pop).
- notebooks/03_modelado.ipynb selecciona hiperparámetros con cortes temporales y exporta un pipeline scikit-learn. El ajuste final concatena entrenamiento y validación.
- datos/preparar.py solo corrige CSV existentes; no regenera por sí solo los conjuntos de entrenamiento. La preparación completa está en los notebooks.
- Tests existentes verifican API, calidad de datos y paridad de features.
- README.md contiene un cambio local previo: preservarlo.

## Alcance técnico
1. Inspeccionar metadatos/artefactos, particiones, versiones y diferencias entre copia local y despliegue. Registrar hashes y contrato de features.
2. Preparar datos para entrenamiento y evaluación sin identificadores personales innecesarios; subir a un prefijo S3 exclusivo de Nexus. Mantener particiones temporales separadas y documentar la reutilización previa de validación. No declarar resultados como prueba independiente si se usaron para selección o ajuste.
3. Crear scripts reproducibles para Training Job del pipeline real, exportación de artefacto/metadatos y despliegue de un endpoint propio nexus, separado de l10-recomendacion.
4. Elegir imagen/versión scikit-learn compatible con el artefacto y probarla. Serverless primero; alternativa permitida de tiempo real solo con evidencia de limitación y limpieza/costo documentados.
5. Adaptar la IA a invoke_endpoint mediante el rol EC2, validar respuesta y usar más vendidos ante error/timeout, sin perder controles de consentimiento ni exclusiones.
6. Verificar localmente, desplegar únicamente la IA necesaria en EC2 con recuperación al despliegue previo disponible, y comprobar el flujo actual por HTTPS.

La nueva ruta pública /api/predict, cambios de estado HTTP/persistencia en dominio y demás brechas EP3 se tratarán después de esta migración; el contrato interno actual /predict se conserva en este bloque.

## Estructura y comandos
Reutilizar app/features.py y app/recomendador.py. Nuevos scripts de entrenamiento/despliegue en sagemaker/; pruebas en tests/; evidencia y documentación de recursos junto a esos scripts.

Comandos existentes desde la raíz del repositorio:
```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/test_datos.py tests/test_paridad.py tests/test_api.py -q
python -m pytest tests -q
docker build -t nexus-ia:ep3-sagemaker .
```
Los comandos concretos de preparación, Training Job y despliegue se fijarán en el plan después de verificar versiones y formato de los datos.

## Estilo
Mantener Python tipado, nombres en español y patrones existentes. Ejemplo del comportamiento a conservar:
```python
puntaje = puntaje + self.meta_modelo["pop_alpha"] * np.log(
    X["n_compradores"].to_numpy(float) + self.meta_modelo["eps_pop"]
)
```

## Verificación y criterios de éxito
- Training Job Completed usando datos del proyecto en S3; artefacto, versiones, features, hashes y versión de modelo registrados.
- Endpoint propio InService e invocación real desde el contenedor IA mediante rol, sin claves en .env.
- Paridad de scores remotos frente al mismo artefacto cargado localmente, con tolerancia numérica documentada, y top-k estable para usuarios representativos.
- Pruebas de columnas/orden/tipos inválidos, respuesta remota inválida, error/timeout y fallback; ninguna prueba obligatoria nueva puede pasar por skip de datos faltantes.
- Métricas de clasificación y ranking @5 registradas con identificación honesta del conjunto evaluado y su uso previo.
- Medir latencias calientes y frías; no afirmar p95 <200 ms por tener un timeout configurado. El cumplimiento end-to-end EP3 exige trabajo posterior en dominio/gateway y carga.
- Flujo actual HTTPS funciona con inferencia SageMaker y fallback verificable; actualizar RETOMAR_EP3.md y documentar recursos/costos.

## Límites
- Siempre: conservar trabajo previo, comprobar consumidores, validar inputs/outputs, limitar payloads, usar rol y prefijos propios, registrar evidencia real y mantener recuperación del despliegue anterior.
- Consultar antes: cambio de algoritmo, modificación de esquema de base de datos, borrado de recursos ajenos o publicación remota de commits/imágenes.
- Nunca: borrar volúmenes, subir secretos o tablas de identidad innecesarias, inventar prueba independiente, afirmar que datos de L10 son los datos del proyecto.

## Decisión aprobada
Pipeline real scikit-learn entrenado y servido en SageMaker, integrado en la IA actual; nueva ruta pública y resto de EP3 después. La selección exacta de contenedor/versiones y la disponibilidad de una prueba temporal independiente se resolverán mediante inspección, antes de entrenar.
