# Plan: migración SageMaker Nexus

Alcance aprobado: ../SPEC-SAGEMAKER.md. Este plan está pendiente de aprobación.

## Datos confirmados del despliegue
Boosting, 25 features, cuatro categóricas (region, canal_captacion, categoria, marca). Hiperparámetros: learning_rate=0.05, max_leaf_nodes=8, l2_regularization=0.0. Prior activo: alpha=1, eps=0.001. Artefacto y runtime coinciden: scikit-learn 1.9.1, pandas 3.0.6, numpy 2.5.4.

El contenedor actual contiene CSV de servicio y metadatos, pero no los conjuntos de entrenamiento: se usarán los archivos locales verificados. README.md tiene trabajo previo sin commit; conservarlo.

## Arquitectura
- S3 con prefijo propio nexus: matrices de entrenamiento y metadatos mínimos, identificadas mediante hashes.
- Training Job del pipeline real, con versiones compatibles verificadas y evaluación temporal documentada.
- Endpoint nexus separado del sintético L10. Recibe features en orden validado y devuelve scores; no recibe nombre, RUT, correo ni dirección.
- IA en EC2 conserva ensamblado de features, consentimiento, candidatos, prior y top-k. Invoca SageMaker con LabRole y fallback de más vendidos ante falla.
- Desplegar la IA solo tras paridad satisfactoria; mantener imagen/configuración previa disponibles para recuperación.

## Secuencia
1. Auditar artefactos, datos, particiones y consumidores; verificar contenedor y versiones.
2. Preparar entrenamiento reproducible y pruebas locales del contrato.
3. Subir datos mínimos y ejecutar Training Job; registrar métricas y artefactos.
4. Desplegar endpoint y comprobar paridad de scores.
5. Integrar cliente remoto y fallback en la IA con pruebas.
6. Desplegar IA, comprobar flujo HTTPS y cerrar documentación/evidencias.

Dependencias: 1 → 2 → 3 → 4 → 5 → 6. Tareas detalladas en todo.md.

## Verificaciones y límites
- Antes de crear recursos, contrastar soporte de imágenes/versiones con documentación oficial y disponibilidad real de AWS. No cambiar algoritmo ni degradar versiones silenciosamente.
- No presentar validacion.pkl como prueba independiente: el modelo previo lo usó en su ajuste final. Auditar cortes antes de fijar evaluación.
- Serverless primero; medir cold start y errores. No declarar cumplimiento de 200 ms por configurar timeouts.
- Si hace falta publicar imagen en un registro, solicitar autorización antes de publicarla; usar build local en EC2 cuando sea suficiente para la IA.
- Preservar L10 y datos originales; prefijos propios y limpieza de recursos fallidos de esta migración.
- La nueva ruta pública /api/predict queda para el bloque siguiente; comprobar aquí el flujo público existente.

## Puntos de control
Al terminar auditoría/compatibilidad y al terminar paridad remota: registrar evidencia y comunicar hallazgos. Bloquear el cambio de producción si falla la paridad, el contrato o el fallback.
