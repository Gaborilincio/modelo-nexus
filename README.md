# modelo-nexus

Repositorio dedicado al componente de **Inteligencia Artificial y procesamiento de datos** del proyecto Nexus.

Aquí se desarrolla el flujo de preparación de datos, entrenamiento del modelo y servicio de predicción.

## 📌 Objetivo

El objetivo de este repositorio es centralizar el desarrollo relacionado con:

- Limpieza y preparación de datos.
- Análisis y validación de los datos.
- Preparación de datos para Machine Learning.
- Entrenamiento y evaluación del modelo.
- Serialización del modelo entrenado.
- Servicio de predicciones mediante una API.
- Pruebas del componente de IA.
- Automatización mediante CI/CD.

## 📁 Estructura del proyecto

```text
modelo-nexus/
│
├── .github/
│   └── workflows/
│       └── ci-cd.yml
│
├── datos/
│   ├── crudos/
│   │   ├── clickstream.csv
│   │   ├── productos.csv
│   │   ├── transacciones.csv
│   │   └── usuarios.csv
│   │
│   ├── procesados/
│   │   ├── clickstream_limpio.csv
│   │   ├── productos_limpio.csv
│   │   ├── transacciones_limpio.csv
│   │   ├── usuarios_limpio.csv
│   │   ├── entrenamiento.pkl
│   │   ├── validacion.pkl
│   │   ├── ranking_validacion.pkl
│   │   ├── ranking_seleccion.pkl
│   │   ├── sku_recomendables.pkl
│   │   └── metadatos.pkl
│   │
│   └── modelos/
│       ├── modelo_recomendador.joblib
│       ├── modelo_metadatos.joblib
│       └── fallback_mas_vendidos.joblib
│
├── notebooks/
│   ├── 02_limpieza.ipynb
│   └── 03_modelado.ipynb
│
├── app/
│   ├── __init__.py
│   └── main.py
│
├── tests/
│   ├── __init__.py
│   ├── test_datos.py
│   └── test_api.py
│
├── Dockerfile
├── requirements.txt
├── .gitignore
├── .env.example
└── README.md
```

> `datos/procesados/` es generada por el notebook 02 y `datos/modelos/` por el notebook 03.

## 🔄 Flujo del proyecto

El flujo principal del componente de IA será:

```text
Datos crudos
     ↓
Perfilado y análisis
     ↓
Limpieza de datos
     ↓
Datos procesados
     ↓
Preparación para Machine Learning
     ↓
Entrenamiento
     ↓
Evaluación
     ↓
Modelo serializado
     ↓
API de predicción
```

## 📊 Datos

Los datos originales del Caso 1 se encuentran en:

```text
datos/crudos/
```

Actualmente se utilizan los siguientes archivos:

- `clickstream.csv`
- `productos.csv`
- `transacciones.csv`
- `usuarios.csv`

Los archivos de esta carpeta corresponden a los datos originales y **no deben ser modificados directamente**.

Los datos resultantes del proceso de limpieza y preparación son almacenados en:

```text
datos/procesados/
```

## 🧹 Preparación de datos

La limpieza y preparación de los datos se realiza en los notebooks de la carpeta `notebooks/`, principalmente en:

```text
notebooks/02_limpieza.ipynb
```

Este notebook se encarga de:

1. Cargar los datos originales.
2. Aplicar las decisiones de negocio acordadas, cada una como una regla con su propia función y una tabla de auditoría (filas antes y después de cada regla).
3. Construir la variable objetivo de compra con cuatro cortes temporales de 90 días.
4. Construir los predictores usando únicamente información anterior a cada corte.
5. Validar los datos (sin fuga de información, consentimiento de los usuarios, ausencia de nulos en los predictores).
6. Exportar los datos procesados y los conjuntos de entrenamiento y validación a `datos/procesados/`.

## ▶️ Ejecución

Los notebooks se ejecutan en orden y de principio a fin:

1. Colocar los archivos originales en `datos/crudos/`.
2. Ejecutar `notebooks/02_limpieza.ipynb`: genera los archivos de `datos/procesados/`.
3. Ejecutar `notebooks/03_modelado.ipynb`: lee `datos/procesados/`, entrena y evalúa los modelos, y guarda el modelo en `datos/modelos/`.

El notebook 03 depende de los archivos que genera el 02, por lo que siempre debe ejecutarse después de este.

## 🤖 Modelo

El modelo se entrena y evalúa en `notebooks/03_modelado.ipynb`. Se trata de un modelo de propensión de compra que puntúa cada producto para cada usuario; los productos se recomiendan ordenándolos por ese puntaje.

Al terminar, el notebook guarda tres archivos en `datos/modelos/`. **Solo el primero es un modelo entrenado**; los otros dos lo acompañan:

| Archivo                        | Qué es                                                                                                                                                   | Para qué se usa                                                                                             |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `modelo_recomendador.joblib`   | Modelo de Machine Learning entrenado (el elegido entre regresión logística y boosting)                                                                   | Calcular el puntaje de cada producto para un usuario y generar las recomendaciones                          |
| `modelo_metadatos.joblib`      | Configuración del modelo: variables que espera, hiperparámetros, parámetro de corrección de popularidad, métricas de validación y versiones de librerías | Preparar los datos de entrada de la misma forma en que se entrenó el modelo y aplicar la fórmula de puntaje |
| `fallback_mas_vendidos.joblib` | Lista de los 50 productos más vendidos (y recomendables) de los últimos 90 días. No es un modelo                                                         | Plan B: recomendar cuando el modelo no puede responder (por ejemplo, ante un error o un usuario sin datos)  |

Las recomendaciones se generan así: se calculan las variables del usuario, se obtiene el puntaje con `modelo_recomendador`, se excluyen los productos ya comprados, se filtra a los SKU recomendables y se devuelven los mejores. Si algo falla, se responde con `fallback_mas_vendidos`.

## 🚀 API

El servicio de predicción estará implementado en:

```text
app/main.py
```

Se utilizará una API para permitir que otros componentes del proyecto Nexus puedan enviar datos y obtener predicciones del modelo.

Al iniciar, la API carga los tres archivos de `datos/modelos/`:

- `POST /predict` usa `modelo_recomendador.joblib` junto con `modelo_metadatos.joblib`, y recurre a `fallback_mas_vendidos.joblib` si no puede generar la recomendación.
- `GET /health` puede comprobar que los tres archivos se cargaron correctamente.

La API contemplará, como mínimo:

```text
GET  /health
POST /predict
```

La implementación definitiva de los endpoints se realizará durante el desarrollo del proyecto.

## 🧪 Pruebas

Las pruebas estarán ubicadas en:

```text
tests/
```

Se contemplan pruebas para:

- Validación de la calidad de los datos.
- Validación de los datos procesados.
- Funcionamiento del modelo.
- Funcionamiento del endpoint de predicción.
- Endpoint de salud de la API.

## 🐳 Docker

El proyecto contará con un `Dockerfile` para permitir ejecutar el servicio de IA dentro de un contenedor.

## 🔀 Ramas

El repositorio utiliza las siguientes ramas principales:

```text
main → versión estable
dev  → desarrollo
```

El desarrollo se realiza principalmente en `dev`.

Los cambios que estén listos podrán integrarse posteriormente a `main` mediante un Pull Request.

## ⚙️ Instalación

Clonar el repositorio:

```bash
git clone https://github.com/Gaborilincio/modelo-nexus.git
```

Ingresar al proyecto:

```bash
cd modelo-nexus
```

Crear y activar un entorno virtual:

```bash
python -m venv venv
```

En Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

Instalar las dependencias:

```bash
pip install -r requirements.txt
```

## 👨‍💻 Estado del proyecto

Actualmente el repositorio se encuentra en la etapa de **preparación y análisis de los datos**.

Próximas etapas:

- [ ] Analizar los datos originales.
- [ ] Definir reglas de limpieza.
- [ ] Generar datos procesados.
- [ ] Preparar dataset para Machine Learning.
- [ ] Entrenar y evaluar el modelo.
- [ ] Serializar el modelo.
- [ ] Implementar API de predicción.
- [ ] Crear pruebas.
- [ ] Configurar CI/CD.
- [ ] Contenerizar el servicio con Docker.
