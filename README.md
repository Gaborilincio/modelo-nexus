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
│   │
│   └── modelos/
│
├── notebooks/
│   ├── 02_limpieza.ipynb
│   └── 03_modelado.ipynb
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   └── modelo.pkl
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

> `datos/procesados/` y `datos/modelos/` son generadas por los notebooks. `modelo.pkl` será generado posteriormente durante el proceso de entrenamiento.

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

El modelo de Machine Learning será entrenado utilizando los datos procesados.

Una vez finalizado el entrenamiento, el modelo será serializado para poder utilizarlo posteriormente desde el servicio de predicción.

El archivo generado será:

```text
app/modelo.pkl
```

## 🚀 API

El servicio de predicción estará implementado en:

```text
app/main.py
```

Se utilizará una API para permitir que otros componentes del proyecto Nexus puedan enviar datos y obtener predicciones del modelo.

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
