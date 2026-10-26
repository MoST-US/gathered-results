# ¿Se puede predecir la capacidad del servidor con mezclas de peticiones?

Interpretación del análisis de aditividad y acotabilidad sobre el archivo `MIT_MST_results`.

- **Modelos:** DeepSeek-R1-Distill-Qwen-7B, Gemma-7B y Llama-3.1-8B-Instruct, cada uno en una A40.
- **Volumen:** 301 ejecuciones de 114 mezclas distintas y 7.944 evaluaciones del SLA.
- **Tipos de prueba:** MIT (2 minutos) y MST (30 minutos de carga sostenida).

> **Cómo leer las cifras:** salvo que se diga lo contrario, salen del análisis frecuentista, que
> toma cada diseño de mezcla como unidad (las repeticiones se promedian). La sección 6 resume el
> análisis bayesiano, que llega a las mismas conclusiones.
>
> **Para verlo de forma intuitiva:** [`docs/animaciones.html`](../docs/animaciones.html) tiene 9
> escenas interactivas que ilustran cada idea de este documento (en inglés:
> [`docs/animations.html`](../docs/animations.html)). El informe con todas las figuras y tablas
> está en [`docs/report.html`](../docs/report.html), y los activos para el artículo en LaTeX, en
> [`latex/`](latex/).

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

```text
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

Según el paper de SCALE, MoST da por superada una prueba MST si se cumplen tres condiciones:
(i) los tiempos de respuesta no suben de forma sostenida, (ii) no se acumulan peticiones sin
procesar y (iii) el éxito es ≥ 95 %. Como la celda pesada de Gemma falla con un 100 % de éxito,
**falla por la tendencia del tiempo de respuesta o por la cola**, no por el éxito.

En una mezcla, esas métricas se calculan **sobre todas las peticiones juntas**, y las cortas, que
son muchas y rápidas, "diluyen" a las lentas. Con un 50 % de cada tipo, la métrica queda justo en
la frontera entre ambos, lo que también explicaría por qué ese diseño da resultados distintos al
repetirlo.

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

## 6. Lo que añade el análisis bayesiano

El modelo bayesiano usa cada veredicto de pasa/falla del SLA, no solo el resultado final de la
búsqueda, y separa tres fuentes de variación. Se ajusta en dos etapas: primero las capacidades
puras, solo con datos puros; después las mezclas. Así, unas pocas mezclas extremas no deforman la
capacidad estimada de las celdas puras.

| Fuente de variación | MIT | MST |
| --- | --- | --- |
| Repetir una celda pura | 0,3 % | 1,7 % |
| Repetir un mismo diseño de mezcla | 0,3 % | 1,8 % |
| Desviación propia de cada diseño respecto a la regla | 6 % | 21 % |

Esto confirma que **las repeticiones son muy estables** y que lo que se desvía es el diseño, no la
medida.

- **La regla:** exponente q = −0,96 (intervalo creíble 95 %: −1,02 a −0,88). Incluye la armónica
  (q = −1). Dejar q libre no mejora la capacidad predictiva (+1,7 ± 3,3), mientras que la media
  geométrica (−265) y el promedio simple (−441) predicen mucho peor.
- **El sesgo:** −5,5 % de media (intervalo creíble 90 %: −9,9 % a −1,0 %). La probabilidad de que
  esté dentro de ±10 % es del 92 %.
- **Por modelo:** DeepSeek y Llama quedan un 7–9 % por debajo de la regla. Gemma queda prácticamente
  en ella (−0,3 % en MIT, −4,6 % en MST). El modelo trata como casos atípicos sus pocas mezclas con
  el tipo pesado (hasta +200 %), en vez de desplazar todo el grupo. Es la misma conclusión que el
  ANOVA: Gemma solo se aparta cuando hay peticiones pesadas.
- **Margen para planificar:** una banda del 90 % alrededor de la predicción armónica es de **±15 % en
  MIT** y **±39 % en MST**.
- **Límites:** el 98 % de las ejecuciones queda, con probabilidad posterior, entre su tipo más lento
  y su tipo más rápido.

---

## 7. En resumen

1. Para predecir la capacidad de una mezcla hay que **sumar lo que ocupa cada petición** (regla
   armónica), no promediar capacidades.
2. La regla acierta en media en **MIT y MST por igual** (−3 % a −5 %). En **MIT** la predicción
   concreta es fiable (±10–15 %); en **MST** es el doble de imprecisa.
3. La regla falla con **peticiones muy pesadas**, y ahí el resultado depende del modelo. El que
   más memoria usa por token (Gemma) es el que más se desvía.
4. Parte del fallo probablemente viene de **cómo se evalúa el SLA** en mezclas, más que del
   servidor.
5. **Repetir da el mismo resultado:** la variación entre repeticiones es inferior al 2 %.

---

## 8. Qué significa todo esto para el paper SCALE

Esta sección relaciona los resultados con el borrador *"Making the most of On-Premise LLMaaS with
SCALE"* (ICSOC 2026) y propone cómo usarlos para mejorarlo.

### 8.1. La regla armónica es la contabilidad de SCALE

En la sección 4, el paper define el coste de una petición como el inverso de la capacidad de su
clase:

```text
K_r = SK_max / MST_r
```

SCALE cobra a cada usuario Q (proporcional a K) por cada petición y vigila que la suma de K por
minuto no supere SK_max. Esto solo es correcto si **los K de distintas clases se suman** cuando se
mezclan. Esa suposición es exactamente la regla armónica:

```text
Σ pᵢ · Kᵢ ≤ SK_max   ⟺   C_mezcla = 1 / Σ (pᵢ / MSTᵢ)
```

Por tanto, la frase del paper *"a request rated at 4 K consumes four times as much service
capacity"* es una hipótesis de aditividad, y **el paper no la comprueba**. Su simulación de la RQ2
usa una sola clase de petición (100–300 tokens de prompt y 1–100 de respuesta, 1 K/req), así que
nunca mezcla clases.

**Este análisis es la primera validación empírica de que la moneda de SCALE funciona con cargas
mixtas:** 114 diseños de mezcla, 3 modelos y las dos pruebas de MoST, con q = −0,96 (95 %: −1,02 a
−0,88).

### 8.2. Qué implica cada resultado para SCALE

| Resultado | Implicación para SCALE |
| --- | --- |
| **Ley armónica (q ≈ −1)** | Cobrar Q = Σ K por petición está justificado. Un promedio simple de capacidades sobreestimaría la capacidad en torno a un 50 %. |
| **Sesgo de −3 % a −5 %** | La contabilidad en K es algo optimista: una mezcla rinde un poco menos de lo que suman sus K. Con ρ = 1,2, el compromiso real sobre la capacidad física sería ≈ 1,2 / 0,95 ≈ **1,26**. Conviene un margen de ~5 % sobre SK_max, o tenerlo en cuenta al fijar ρ. |
| **MST es el doble de imprecisa que MIT** (banda del 90 %: ±39 % frente a ±15 %) | Afecta justo a la moneda de usuario, porque **Q se basa solo en SK (MST)**. IK (MIT), que SCALE usa como umbral de throttling, es más precisa. |
| **Las desviaciones dependen del diseño, no del ruido** | No se compensan al haber más usuarios: si una organización envía de forma sistemática un tipo de mezcla, su desviación se mantiene. La multiplexación estadística en la que se apoya la sobresuscripción no la absorbe. |
| **Las peticiones pesadas dependen del modelo** | Las clases con K más alto (≈ 11–17 en la Figura 3) son donde la contabilidad es menos fiable. En Llama, las mezclas con peticiones pesadas rinden hasta un −24 % (riesgo de sobreutilización); en Gemma, más de lo previsto (se cobra de más a esos usuarios). |
| **Las repeticiones son estables** (< 2 %) | Responde a la amenaza de validez interna sobre el ruido de la búsqueda binaria, que ahora queda cuantificado: σ_rep = 0,3 % en MIT y 1,7 % en MST. |

### 8.3. Matiz a la RQ1 (portabilidad)

El paper concluye que K es portable porque la **forma** de la matriz (el gradiente de color) es
parecida en los tres modelos. Nuestros datos añaden un matiz: la **aditividad** de K sí depende del
modelo en las clases pesadas. Sin peticiones pesadas, los tres modelos se comportan igual
(ANOVA, p = 0,54); con ellas, el modelo influye (p = 0,0007).

Una explicación plausible es la memoria de la caché KV por token: ~448 KB en Gemma-7B (MHA) frente
a ~128 KB en Llama-3.1-8B y ~56 KB en DeepSeek (GQA). Con 3 modelos no se puede demostrar, pero es
coherente con la amenaza de *construct validity* que el paper ya reconoce ("may not fully represent
other resource bottlenecks such as memory bandwidth, KV-cache exhaustion").

### 8.4. El hallazgo del SLA afecta a MoST y a la QoE que promete SCALE

Si los criterios de MoST se evalúan sobre todas las peticiones de una mezcla (sección 4), una mezcla
puede "pasar" el SLA mientras **los usuarios que envían peticiones pesadas reciben una QoE mala**.
Como SCALE promete QoE por plan de suscripción, convendría que MoST evaluara sus criterios **por
clase de petición** en cargas mixtas. Encaja como amenaza a la validez o como trabajo futuro.

### 8.5. Cubre una amenaza a la validez que el paper deja abierta

En *Conclusion validity*, el paper admite que la portabilidad *"rests on visual inspection of
heatmap distributions"* y deja como trabajo futuro *"a more rigorous statistical comparison"*. El
marco de este análisis aporta exactamente eso:

- un análisis frecuentista con el diseño como unidad y una prueba de equivalencia (TOST);
- un modelo bayesiano en dos etapas que trata la capacidad como un umbral latente a partir de los
  veredictos de pasa/falla de la búsqueda binaria.

El mismo marco serviría para la portabilidad: probar la equivalencia de los K normalizados entre
arquitecturas.

### 8.6. Qué es novedoso y qué no

- **No es novedoso:** que la capacidad de una mezcla siga la media armónica. Es la ley de
  utilización del análisis operacional (U = X · D, con D = 1/C la demanda de servicio), y K es
  justamente esa demanda normalizada (Denning y Buzen, 1978; Lazowska et al., 1984; Jain, 1991).
  Usar la media armónica para promediar tasas también está documentado (Smith, 1988; John, 2004).
  Presentarlo como hallazgo sería un error ante un revisor del área.
- **Sí puede ser novedoso:**
  - Comprobar empíricamente que esa aditividad se cumple en inferencia de LLM con batching continuo,
    donde la caché KV y la interferencia entre prefill y decodificación podrían romperla.
  - Cuantificar cuánto se desvía y cuándo falla (clases pesadas, según el modelo).
  - El efecto del SLA agregado sobre la medida de capacidad de las mezclas.

Estas referencias están citadas de memoria y hay que verificarlas. Falta además revisar la
literatura reciente específica de LLMs.

### 8.7. Aviso sobre la coherencia de los datos

Los valores de la Figura 3 del paper no coinciden del todo con los de este archivo:

- La celda 600-1000 → 1000-1500 de DeepSeek tiene MST 160 en la Figura 3, frente a ~103 aquí.
- En el paper, Gemma está en una **A100**; aquí, en una **A40**.
- El paper menciona un nodo A40 con 4 GPU para la simulación; las fuentes de este archivo son de 1
  GPU.

Probablemente vienen de experimentos distintos. Antes de usar estos resultados en el paper hay que
aclarar qué datos alimentan cada figura y, si hace falta, unificar las fuentes.

### 8.8. Propuestas concretas para la próxima versión del paper

1. **Sección 4 (Capacity Units):** presentar K como la *demanda de servicio* del análisis
   operacional, con su referencia. La aditividad pasa a ser un supuesto explícito y con base
   teórica, en vez de una consecuencia implícita de la definición.
2. **Nueva pregunta de investigación:** *"RQ3 (Additivity): Do the K costs of different request
   classes add up when classes are mixed?"*
3. **Evaluación, subsección *Additivity of Capacity Units*:**
   - la figura de capacidad medida frente a predicha (Figura 1 del informe);
   - el exponente q y la comparación entre leyes (Figura 2);
   - el sesgo por modelo y prueba (Figura 3);
   - la diferencia de precisión MIT/MST y el papel de las clases pesadas.
4. **Mecanismo de SCALE (sección 5):**
   - recomendar un margen de ~5 % sobre SK_max al fijar ρ;
   - usar los *request-specific factors* F_r, que el paper ya contempla, para corregir las clases
     pesadas según el modelo.
5. **Threats to validity:**
   - *Internal:* el ruido de la búsqueda binaria, ahora cuantificado (< 2 %).
   - *Construct:* el SLA agregado en mezclas y la dependencia del modelo en las clases de K alto.
   - *Conclusion:* remitir al análisis estadístico en lugar de la inspección visual.
6. **Related work:** situar K en la tradición del análisis operacional y de la caracterización de
   rendimiento con medias armónicas.

## 9. El burst factor: cuánto aguantan las ráfagas

### 9.1. Qué es

MoST mide dos capacidades para cada tipo de petición:

- **MST:** el ritmo sostenible durante 30 minutos.
- **MIT:** el ritmo que aguanta durante una ráfaga de 2 minutos.

El **burst factor** es su cociente:

```text
B_r = MIT_r / MST_r
```

Indica cuántas veces su ritmo sostenible puede alcanzar un cliente durante una ráfaga de 2 minutos.

**Por qué importa para SCALE.** SCALE cobra con una sola moneda (Q), basada en la capacidad
sostenible (SK), y usa la capacidad instantánea (IK) solo como umbral de seguridad para las ráfagas.
Como IK_r / SK_r = (IK_max / SK_max) / B_r, las dos contabilidades tratan igual a todos los tipos de
petición **solo si B es el mismo para todos**. Un burst factor constante es lo que justifica usar una
sola moneda.

### 9.2. Resultados

- **Es prácticamente constante.** La mediana es **3,50** en los 60 tipos de petición de los tres
  modelos (rango intercuartílico 3,41–3,94). Por modelo sale 3,57 en DeepSeek, 3,56 en Gemma y 3,55
  en Llama (análisis bayesiano, intervalos del 95 % entre 3,48 y 3,65).
- **No depende del modelo** (ANOVA p = 0,74). La razón entre los burst factors de dos modelos
  cualesquiera está a menos de un 3,5 % de 1, con probabilidad ≈ 1 de ser equivalentes dentro de
  ±10 %.
- **El 77 %** de los tipos de petición quedan a menos de ±15 % de la mediana de su modelo.
- **Excepciones sistemáticas:**
  - Las respuestas cortas (1–100 tokens) aguantan ráfagas algo mayores: B = 4,15 frente a 3,68
    (+13 %, p = 0,0004).
  - Las dos celdas de Gemma con prompt largo y respuesta larga llegan a B = 6 y 11,6. Coinciden con
    la anomalía del SLA en MST (sección 4): su MST es anormalmente bajo, no su MIT alto.
- **En mezclas**, el burst factor medido es un ~19 % mayor que el que se predice a partir de sus
  tipos. Se debe a que la regla armónica se cumple peor en MST que en MIT (sección 3.4).

### 9.3. Qué significa para SCALE y para el paper

- **Una sola moneda es suficiente.** Para el 77 % de los tipos, cobrar las ráfagas con la moneda
  sostenible se equivoca en menos de un 15 % sobre su carga instantánea.
- **Regla práctica para el Token Bucket:** a un plan con ritmo sostenible *s* se le pueden permitir
  ráfagas de unas **3,5 · s** durante 2 minutos (algo más si sus peticiones tienen respuestas
  cortas).
- **El ejemplo de la introducción del paper es muy conservador.** Una cuota de 30.000 peticiones
  cada 30 minutos con un ritmo de 1.400 por minuto implica B ≈ 1,4, frente al ≈ 3,5 medido.
  Conviene recalcular los ejemplos de las Tablas 1–3 con el valor medido.
- **Refuerza la RQ1 (portabilidad).** A diferencia de K, que es relativo a cada despliegue, B se
  puede comparar entre modelos en términos absolutos, y sale igual en los tres. Es un argumento
  cuantitativo de portabilidad que sustituye a la inspección visual de los mapas de calor.
- **Propuesta:** incluirlo en el paper como una pregunta de investigación nueva, *"RQ4 (Burst
  factor)"*. El borrador está en [`latex/section_additivity_burst.tex`](latex/section_additivity_burst.tex),
  con sus tablas, figuras y macros.

### 9.4. Activos para el artículo

[`latex/`](latex/) contiene todo lo necesario para incorporar estos resultados al paper, en inglés:

- [`macros.tex`](latex/macros.tex): 115 constantes con todos los valores citados (por ejemplo,
  `\scaleQHatBayes` o `\scaleBurstMedian`), generadas a partir de los resultados. Si se recalcula
  el análisis, el texto se actualiza solo.
- [`tables/`](latex/tables/): 6 tablas con booktabs (leyes de combinación, sesgo por modelo, MIT
  frente a MST, tipo pesado, burst factor resumido y por celda).
- [`figures/`](latex/figures/): 4 figuras vectoriales en PDF a la medida de LNCS.
- [`section_additivity_burst.tex`](latex/section_additivity_burst.tex): borrador de las
  subsecciones RQ3 y RQ4 escrito con las macros.
- [`preview.pdf`](latex/preview.pdf): todo compilado con la clase LNCS, para revisarlo.

---

## 10. Siguientes pasos

- Revisar en el código de MoST cómo se calcula el veredicto del SLA en MST. Si es agregado,
  evaluarlo también por tipo de petición.
- Repetir las mezclas con el tipo pesado una vez revisado el SLA.
- Para separar el efecto de la arquitectura, comparar modelos que difieran solo en la atención (MHA
  frente a GQA) con tamaño similar.
- Unificar las fuentes de datos entre este archivo y la Figura 3 del paper.
- Verificar las referencias clásicas y revisar la literatura reciente sobre capacidad de servidores
  de LLM con cargas mixtas.
- Redactar la subsección de aditividad (RQ3) para el paper, a partir de las secciones 3, 6 y 8.

---

## Notas sobre los datos

- **Repeticiones:** se usan todas como repeticiones de su diseño. Los contrastes toman el diseño
  como unidad, promediando sus repeticiones para no contar varias veces la misma mezcla.
- **Copias exactas:** se cuentan una sola vez 114 carpetas que eran copias exactas byte a byte de
  otra ejecución (mismos instantes y mismo `results.csv`). Están guardadas con un segundo nombre de
  carpeta o copiadas en un experimento posterior. Son una única ejecución, no una repetición.

## Reproducir

```text
python -m pip install -r analysis/requirements.txt
python analysis/run_all.py                # todo: análisis, LaTeX y sitio (15-30 min)
python analysis/run_all.py --skip-bayes   # solo la parte frecuentista, unos minutos
python analysis/run_all.py --reuse        # regenera LaTeX y sitio a partir de analysis/output
```

Las instrucciones completas del artefacto, en inglés, están en [`README.md`](README.md). En
Windows, conviene crear el entorno virtual en una ruta corta, porque pip falla con rutas largas si
no están habilitadas.
