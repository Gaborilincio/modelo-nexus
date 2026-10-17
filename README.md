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
│   ├── preparar.py        # limpieza reproducible de datos/procesados/
│   │
│   └── modelos/
│       ├── modelo_recomendador.joblib
│       ├── modelo_metadatos.joblib
│       └── fallback_mas_vendidos.joblib
│
├── notebooks/
│   ├── 01_exploracion_datos.ipynb
│   ├── 02_limpieza.ipynb
│   └── 03_modelado.ipynb
│
├── app/
│   ├── __init__.py
│   ├── main.py            # API (FastAPI): /health y /predict
│   ├── recomendador.py    # carga del modelo y generación de recomendaciones
│   └── features.py        # cálculo de variables (misma lógica que el notebook 02)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_paridad.py    # las variables de la API = las del notebook 02
│   ├── test_datos.py      # calidad de los datos limpios y procesados
│   └── test_api.py
│
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
├── .gitignore
├── .env.example
└── README.md
```

> `datos/procesados/` es generada por el notebook 02 (y depurada por `datos/preparar.py`) y `datos/modelos/` por el notebook 03.

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

### Limpieza de calidad reproducible (`datos/preparar.py`)

Después del notebook 02 existe `datos/preparar.py`, un script que corrige de forma **reproducible** los valores pendientes de `datos/procesados/` **sin alterar la estructura de los archivos**: conserva los mismos nombres, orden y cantidad de columnas, y no toca los notebooks ni el código de la API.

- `productos_limpio.csv`: imputa `precio_lista` nulo o ≤ 0 con la mediana de su categoría (y la mediana global si la categoría no tuviera precios válidos); `stock` nulo → 0; `stock` negativo → 0 en productos **no** recomendables, o `stock_minimo` = 3 (valor de `metadatos.pkl`) en productos **recomendables**.
- `usuarios_limpio.csv`: rellena `email_valido` nulo con el valor `"desconocido"`.
- `transacciones_limpio.csv` y `clickstream_limpio.csv`: se verifican las reglas de calidad de `tests/test_datos.py`; no requieren cambios.

Se ejecuta **después** del notebook 02 y **antes** del 03:

```bash
python datos/preparar.py
```

Antes de modificar nada, guarda una copia de los CSV originales en `datos/procesados_backup_limpieza/` (ignorada por git).

## ▶️ Ejecución

Los notebooks se ejecutan en orden y de principio a fin:

1. Colocar los archivos originales en `datos/crudos/`.
2. Ejecutar `notebooks/02_limpieza.ipynb`: genera los archivos de `datos/procesados/`.
3. Ejecutar `python datos/preparar.py`: corrige los valores pendientes de `datos/procesados/` (precios, stock y `email_valido`).
4. Ejecutar `notebooks/03_modelado.ipynb`: lee `datos/procesados/`, entrena y evalúa los modelos, y guarda el modelo en `datos/modelos/`.

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

El servicio de predicción está en `app/main.py` (FastAPI). Al iniciar carga los tres archivos de `datos/modelos/` y los CSV limpios de `datos/procesados/`, y deja calculado el estado de usuarios y productos a la fecha de corte (el fin de los datos, `fin_datos` en `metadatos.pkl`).

Ejecutar (desde la raíz del repositorio, después de correr los notebooks 02 y 03):

```bash
uvicorn app.main:app --reload
```

La documentación interactiva queda en `http://localhost:8000/docs`.

### `POST /predict`

Entrada:

```json
{ "usuario_id": "U100001", "k": 8 }
```

`k` es la cantidad de recomendaciones (de 4 a 8, por defecto 8). La API calcula las variables del usuario, puntúa los productos recomendables que no ha comprado y devuelve los mejores:

```json
{
  "usuario_id": "U100001",
  "origen": "modelo",
  "motivo": null,
  "recomendaciones": [
    {
      "puesto": 1,
      "sku": "NX-10033",
      "categoria": "...",
      "marca": "...",
      "precio_lista": 75389.0,
      "puntaje": 2.84
    }
  ]
}
```

`origen` indica de dónde salió la respuesta:

| `origen`   | Cuándo ocurre                                                                        | Qué se devuelve                                                                              |
| ---------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| `modelo`   | Usuario con consentimiento e historial de compras                                    | Recomendaciones personalizadas (`modelo_recomendador` + `modelo_metadatos`)                  |
| `fallback` | Usuario sin consentimiento o desconocido, usuario sin historial, o error al predecir | Los más vendidos de los últimos 90 días (`fallback_mas_vendidos`); `motivo` explica la causa |

A los usuarios sin consentimiento nunca se les calcula un perfil.

### `GET /health`

Responde `200` con el modelo en uso, la fecha de corte y las cantidades cargadas. Si el modelo no pudo cargarse responde `503` con el error. Además avisa si la versión de scikit-learn es distinta a la del entrenamiento.

### Mantener la API al día

- Los datos se leen al iniciar: si se vuelven a ejecutar los notebooks, hay que reiniciar la API.
- `app/features.py` repite la lógica de variables del notebook 02. Si se cambia una variable en el notebook, hay que cambiarla también ahí; `tests/test_paridad.py` falla si ambas dejan de coincidir.
- Las rutas se pueden cambiar con las variables de entorno `DIR_PROCESADOS` y `DIR_MODELOS`.

## 🧪 Pruebas

Las pruebas estarán ubicadas en:

```text
tests/
```

Se contemplan pruebas para:

- Calidad de los datos limpios y procesados (`test_datos.py`): consentimiento, SKU y fechas válidos, sin nulos en los predictores, cortes temporales ordenados y sin fuga entre entrenamiento y validación.
- Paridad entre las variables de la API y las del notebook 02.
- Funcionamiento del endpoint de predicción (sin repetir compras, solo productos recomendables, plan B, validación de entrada).
- Endpoint de salud de la API.

Se ejecutan con `pytest`. Si faltan los archivos que generan los notebooks 02 y 03, las pruebas de la API se omiten en lugar de fallar.

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

Instalar las dependencias de la API:

```bash
pip install -r requirements.txt
```

Para desarrollo (pruebas y notebooks) instalar además `requirements-dev.txt`, que incluye las de la API:

```bash
pip install -r requirements-dev.txt
```

## 👨‍💻 Estado del proyecto

El repositorio cuenta con el flujo completo: limpieza y preparación de datos, entrenamiento y serialización del modelo, API de predicción, pruebas automatizadas, CI/CD y contenedor.

- [x] Analizar los datos originales.
- [x] Definir reglas de limpieza.
- [x] Generar datos procesados.
- [x] Preparar dataset para Machine Learning.
- [x] Entrenar y evaluar el modelo.
- [x] Serializar el modelo.
- [x] Implementar API de predicción.
- [x] Crear pruebas.
- [x] Configurar CI/CD.
- [x] Contenerizar el servicio con Docker.
- [x] Limpieza de calidad de `datos/procesados/` (`datos/preparar.py`).
