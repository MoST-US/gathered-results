# ¿Se puede predecir la capacidad del servidor con mezclas de peticiones?

Interpretación del análisis de aditividad y acotabilidad sobre el archivo `MIT_MST_results`.

- **Modelos:** DeepSeek-R1-Distill-Qwen-7B, Gemma-7B y Llama-3.1-8B-Instruct, cada uno en una A40.
- **Volumen:** 301 ejecuciones de 114 mezclas distintas y 7.944 evaluaciones del SLA.
- **Tipos de prueba:** MIT (2 minutos) y MST (30 minutos de carga sostenida).

> **Estado:** las cifras de este documento salen del análisis frecuentista, que toma cada diseño
> de mezcla como unidad (las repeticiones se promedian). El ajuste bayesiano con los datos nuevos
> está pendiente de converger. Cuando lo haga se regenerará el informe HTML y se añadirán aquí
> sus cifras.

---

## 1. La pregunta

Medimos cuántas peticiones por minuto aguanta el servidor con **cada tipo de petición por separado**
(prompts cortos o largos, respuestas cortas o largas). Después le enviamos **mezclas** de tipos, de
dos maneras:

- **Mitad y mitad:** el mismo número de peticiones de cada tipo.
- **Repartidas según su coste:** proporciones como 97 % / 3 %, calculadas para que cada tipo ocupe
  la misma parte del servidor.

**¿Podemos calcular cuánto aguantará una mezcla sin tener que medirla?**

---

## 2. La regla: sumar lo que ocupa cada petición (media armónica)

### La idea en una frase

**Lo que se suma no son las capacidades, sino el tiempo que el servidor dedica a cada petición.**

### Una analogía: la caja del supermercado

Una cajera tarda **1 minuto** con un cliente que lleva pocos productos (60 clientes/hora) y
**10 minutos** con un carro lleno (6 clientes/hora). Llegan clientes mitad de cada tipo.

- **Respuesta intuitiva, pero errónea:** el promedio, (60 + 6) / 2 = **33 clientes/hora**.
- **Respuesta correcta:** cada pareja de clientes le lleva 1 + 10 = 11 minutos. En una hora caben
  unas 5,5 parejas, es decir, **unos 11 clientes/hora**.

Se suman los **tiempos**, no los "clientes por hora". Además, quien domina el resultado es el
cliente lento: 11 está mucho más cerca de 6 que de 60.

### Lo mismo con el servidor

Si el servidor aguanta 11.000 peticiones cortas por minuto, cada petición corta ocupa 1/11.000 del
servidor durante un minuto. Si aguanta 360 largas, cada larga ocupa 1/360, unas 30 veces más. Para
una mezcla se calcula lo que ocupa de media una petición y se le da la vuelta:

```
1 / C_mezcla  =  p₁ / C₁  +  p₂ / C₂  +  ...
```

donde **pᵢ** es la proporción de cada tipo y **Cᵢ** lo que aguanta el servidor con ese tipo solo.

### Ejemplo real (DeepSeek, prueba MIT, mezcla al 50 %)

| | Cálculo | Resultado |
| --- | --- | --- |
| Promedio simple (intuición) | (11.000 + 360) / 2 | 5.680 peticiones/min |
| **Regla armónica** | 1 / (0,5/11.000 + 0,5/360) | **≈ 700 peticiones/min** |
| **Medido** | | **≈ 656 peticiones/min** |

La regla acierta con un error del 6 %, mientras que el promedio se equivoca por un factor de 8.

### ¿Por qué "armónica"?

Porque es la **media armónica**, que se calcula al revés que el promedio normal:

1. Se invierte cada capacidad (1/C es el "coste" de cada petición).
2. Se promedian los costes.
3. Se invierte el resultado.

Es la misma media del clásico problema "voy a 60 km/h y vuelvo a 30 km/h": la velocidad media no
es 45, sino 40, porque a la vuelta pasas más tiempo en la carretera.

### Las dos formas de mezclar, vistas con la regla

- **Mitad y mitad:** el tipo pesado acapara casi todo el servidor (en el ejemplo, el 97 % del
  tiempo), así que la capacidad de la mezcla queda cerca de la del tipo lento.
- **Según su coste:** cada tipo ocupa la mitad del servidor. Solo en este caso la regla armónica
  predice el promedio simple de las capacidades.

Las dos formas son predicciones de **la misma regla**, y por eso que acierte en ambas es una prueba
exigente.

### Cómo sabemos que es esta regla y no otra

Probamos una familia de reglas con un parámetro *q*: **q = +1** es el promedio simple, **q = 0** la
media geométrica y **q = −1** la media armónica. Dejamos que los datos eligieran *q*, y el
resultado fue **q = −0,91** (intervalo de confianza 95 %: −0,98 a −0,84), prácticamente la
armónica.

---

## 3. Los resultados en 6 puntos

### 3.1. La regla funciona

- **Comparada con el promedio simple**, la regla armónica acierta mejor en el **97 %** de las
  ejecuciones. El promedio simple sobreestima la capacidad en torno a un **50 %** y la media
  geométrica en torno a un 40 %.
- **Calibración:** si se compara lo medido con lo predicho, la pendiente es **0,96** (intervalo
  0,90–1,02) y R² = 0,97. La regla escala bien desde ~60 hasta ~5.500 peticiones/min.

### 3.2. La mezcla nunca supera los límites de sus componentes

En **294 de 301** ejecuciones, la capacidad de la mezcla queda entre la de su tipo más lento y la
de su tipo más rápido. Ninguna supera el promedio simple, que actúa como techo.

Las excepciones son:

- Seis ejecuciones de Llama en MST, entre un 2 % y un 23 % por debajo del tipo más lento.
- Una de Gemma, un −0,5 %, que es simple ruido de medida.

### 3.3. La predicción es algo optimista, pero poco

De media, una mezcla aguanta un **3 % menos** de lo que dice la regla (intervalo 95 %: −6,9 % a
+1,0 %). Ese sesgo está dentro de ±10 % (prueba de equivalencia TOST, p = 0,001). Para planificar
basta con dejar un margen del 10 %.

### 3.4. MIT y MST: misma regla, distinta precisión

| | MIT (2 min) | MST (30 min) | ¿Hay diferencia? |
| --- | --- | --- | --- |
| Sesgo medio frente a la regla | −2,9 % | −3,1 % | **No** (p = 0,51) |
| Error medio de cada predicción | 9,8 % | 22,5 % | **Sí** (p = 0,02) |
| Dispersión de los errores | 0,12 | 0,30 | **Sí** (p = 0,0005) |
| Mezclas que aciertan dentro de ±10 % | 61 % | 48 % | |
| … sin peticiones pesadas | 75 % | 58 % | Más dispersión en MST (p = 0,007) |
| … con peticiones pesadas | 42 % | 25 % | |
| Repeticiones que difieren más de un 10 % | 5 % | 10 % | MST algo menos estable |

**En común:** en las dos pruebas se cumple la misma regla, con el mismo sesgo medio (~−3 %).

**La diferencia:** en carga sostenida (MST), cada predicción concreta es **el doble de imprecisa**,
incluso sin peticiones pesadas. Con ellas, el error medio en MST llega al 45 %.

### 3.5. La excepción son las peticiones muy pesadas, y depende del modelo

El tipo `600-1000 → 1000-1500` (prompt largo y respuesta larga) es donde la regla falla.

**Efecto del modelo.** Un ANOVA sobre las desviaciones, controlando el tipo de prueba y el tipo
pesado, da estos resultados:

- El **modelo influye** (p = 0,0007); el tipo de prueba no afecta a la media (p = 0,78).
- **Todo el efecto del modelo viene de las mezclas con el tipo pesado.** Sin él, los tres modelos
  se comportan igual (p = 0,54).

| Desviación media | Sin tipo pesado (MIT / MST) | Con tipo pesado (MIT / MST) |
| --- | --- | --- |
| DeepSeek | −4 % / −1 % | −12 % / −8 % |
| Gemma | −1 % / −10 % | **+16 % / +64 %** |
| Llama | −5 % / −9 % | −9 % / −24 % |

**¿Es la arquitectura?** Es una hipótesis razonable. El recurso que más consumen las peticiones
largas es la memoria de la caché de atención (KV cache), y los tres modelos difieren mucho en ella
(valores de sus configuraciones públicas, en fp16):

| Modelo | Atención | Caché por token | Capacidad del tipo pesado solo (MIT / MST) |
| --- | --- | --- | --- |
| Gemma-7B | MHA (16 cabezas KV × 256) | ~448 KB | 78 / 7 peticiones/min |
| Llama-3.1-8B | GQA (8 × 128) | ~128 KB | 252 / 76 peticiones/min |
| DeepSeek (base Qwen2.5-7B) | GQA (4 × 128) | ~56 KB | 360 / 103 peticiones/min |

El orden coincide: cuanta más memoria por token, peor maneja el modelo las peticiones pesadas y más
se desvía la mezcla. Pero **con 3 modelos no se puede demostrar**, porque la arquitectura va unida
al tamaño, el vocabulario, el entrenamiento y la configuración del servidor.

### 3.6. Los resultados son estables al repetirlos

Cada diseño se repitió entre 2 y 6 veces: 270 ejecuciones de 83 diseños. Las repeticiones están
integradas en el análisis, como ejecuciones de un mismo diseño.

- En el **66 % (MIT) y el 74 % (MST)** de los diseños, todas las repeticiones dan exactamente el
  mismo resultado.
- Solo **3 diseños son inestables** (cambian ×2–3 entre repeticiones), y los tres contienen el tipo
  pesado:
  - Gemma MST, mitad corta + mitad pesada: unas veces ~13 peticiones/min, otras ~41.
  - Llama MST, la misma mezcla: ×2,3 entre repeticiones.
  - Llama MIT, 97 % corta + 3 % pesada: ×2,2 en una de sus seis repeticiones.

---

## 4. Una pista sobre la causa: cómo se evalúa el SLA

Gemma ofrece el caso más claro:

- Con **solo** peticiones pesadas, el SLA falla a **8 peticiones/min**, aunque se completa el 100 %
  de ellas. Esto está medido dos veces: ~6,5 y ~6,9 peticiones/min.
- En una mezcla al 50 %, el SLA se cumple a **~40 peticiones/min**, es decir, ~20 peticiones
  pesadas por minuto.

Esto sugiere que el SLA de MST se calcula **sobre todas las peticiones juntas** (por ejemplo, con
un percentil de latencia). Las peticiones cortas "tapan" a las lentas. Con un 50 % de cada tipo, el
percentil cae justo en la frontera entre ambos, lo que también explicaría por qué ese diseño da
resultados distintos al repetirlo.

Si es así, **los recursos del servidor sí se suman, pero el veredicto del SLA no**. Hay que
comprobarlo en el código de evaluación de MoST.

---

## 5. ¿Influye la forma de mezclar?

En media, no: la desviación es parecida al 50 % y según el coste.

| | Diseños | Desviación media | Dentro de ±10 % |
| --- | --- | --- | --- |
| MIT, mitad y mitad | 18 | −3,0 % | 94 % |
| MIT, según su coste | 34 | −4,0 % | 56 % |
| MIT, 4–5 tipos | 10 | +1,0 % | 20 % |
| MST, mitad y mitad | 18 | −2,1 % | 44 % |
| MST, según su coste | 33 | −3,8 % | 48 % |

El cálculo de proporciones según el coste reparte la carga como se pretendía: cada tipo consume de
media alrededor de la mitad del servidor.

---

## 6. En resumen

1. Para predecir la capacidad de una mezcla hay que **sumar lo que ocupa cada petición** (regla
   armónica), no promediar capacidades.
2. La regla acierta en media en **MIT y MST por igual** (~−3 %). En **MIT** la predicción concreta
   es fiable (±10 %); en **MST** es el doble de imprecisa.
3. La regla falla con **peticiones muy pesadas**, y ahí el resultado depende del modelo. El que
   más memoria usa por token (Gemma) es el que más se desvía.
4. Parte del fallo probablemente viene de **cómo se evalúa el SLA** en mezclas, más que del
   servidor.

## 7. Siguientes pasos

- Revisar en el código de MoST cómo se calcula el veredicto del SLA en MST. Si es agregado,
  evaluarlo también por tipo de petición.
- Repetir las mezclas con el tipo pesado una vez revisado el SLA.
- Para separar el efecto de la arquitectura, comparar modelos que difieran solo en la atención (MHA
  frente a GQA) con tamaño similar.
- Terminar el ajuste bayesiano y regenerar el informe con los datos nuevos.

---

## Notas sobre los datos

- **Repeticiones:** se usan todas como repeticiones de su diseño. Los contrastes toman el diseño
  como unidad, promediando sus repeticiones para no contar varias veces la misma mezcla.
- **Copias exactas:** se cuentan una sola vez 114 carpetas que eran copias exactas byte a byte de
  otra ejecución (mismos instantes y mismo `results.csv`). Están guardadas con un segundo nombre de
  carpeta o copiadas en un experimento posterior. Son una única ejecución, no una repetición.

## Reproducir

```
python analysis/additivity_analysis.py --out <dir>     # análisis frecuentista + bayesiano (PyMC)
python analysis/build_report.py <dir> report.html      # informe HTML con las figuras
```

Requiere `pandas numpy scipy statsmodels pymc arviz`. En Windows, conviene crear el entorno virtual
en una ruta corta, porque pip falla con rutas largas si no están habilitadas.
