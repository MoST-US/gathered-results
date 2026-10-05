# ¿Es aditiva la capacidad del servidor cuando se mezclan peticiones?

Interpretación de los resultados del análisis de aditividad y acotabilidad sobre el archivo
`MIT_MST_results` (3 modelos de 7–8 B en una A40: DeepSeek-R1-Distill-Qwen-7B, Gemma-7B y
Llama-3.1-8B-Instruct; 140 ejecuciones de mezclas, 77 mezclas distintas, 5.788 evaluaciones).

## Contexto

Medimos cuántas peticiones por minuto aguanta un servidor de IA con cada tipo de petición por
separado (cortas, largas…). Después le enviamos mezclas de tipos de dos maneras:

- **Mitad y mitad:** el mismo número de peticiones de cada tipo.
- **Repartidas según su coste:** proporciones como 97 % / 3 %, calculadas para que cada tipo ocupe la
  misma parte del servidor.

La pregunta: ¿podemos predecir cuánto aguantará la mezcla sin tener que medirla?

## Los 4 resultados

### 1. Sí se puede predecir, si se suma lo que gasta cada petición

Cada tipo de petición gasta una parte del servidor, y una larga puede gastar 30 veces más que una
corta. Si sumamos lo que gasta cada petición de la mezcla, sabemos cuántas caben en total. Pasa
como con un camión: lo que cabe depende del espacio que ocupa cada paquete, no del número de paquetes.
Esta regla (ley armónica, `1/C_mezcla = Σ pᵢ / Cᵢ`) acierta con las dos formas de mezclar.

> Ejemplo (DeepSeek, MIT): las peticiones cortas aguantan ~11.000/min y las largas ~360/min. Con una
> mezcla mitad y mitad, la regla predice ~700/min y se midieron ~656/min. El promedio simple
> (~5.700/min) se equivoca por un factor de 8.

### 2. La mezcla nunca supera los límites de sus componentes

Una mezcla nunca aguanta más que su tipo de petición más rápido ni menos que el más lento. Se cumple
en 138 de 140 pruebas, y las dos excepciones fallan por poco. Además, las peticiones pesadas mandan:
aunque sean pocas, acercan la capacidad de la mezcla a la del tipo lento.

### 3. La predicción es algo optimista, pero poco

De media, la mezcla aguanta un 5 % menos de lo que dice la regla. Es un error pequeño, pero conviene
dejar ese margen al planificar. La forma de mezclar no cambia este resultado de manera
significativa, y además confirma que el cálculo de proporciones según el coste reparte bien la carga
(cada tipo consume de media el 51 % del servidor).

| Diseño | Prueba | Ejecuciones | Desviación media | Dentro de ±10 % |
|---|---|---|---|---|
| Mitad y mitad | MIT | 26 | −5,8 % | 81 % |
| Mitad y mitad | MST | 24 | −11,4 % | 58 % |
| Según su coste | MIT | 48 | −4,8 % | 73 % |
| Según su coste | MST | 30 | −3,9 % | 50 % |
| 4–5 tipos | MIT | 12 | −3,5 % | 58 % |

### 4. Con pruebas cortas la predicción es fiable; con carga sostenida, mucho menos

- En pruebas de 2 minutos (MIT), la regla acierta con un margen de ±13 %.
- En pruebas de 30 minutos (MST), el margen sube a ±40 %, y casi siempre el servidor aguanta menos
  de lo previsto.
- El peor caso es la mezcla mitad y mitad en carga sostenida, alrededor de un 11 % por debajo de lo
  previsto, aunque aún hacen falta más pruebas para confirmarlo.

## En resumen

Sabiendo lo que aguanta el servidor con cada tipo de petición por separado, podemos calcular
bastante bien lo que aguantará con cualquier mezcla, sobre todo en pruebas cortas. Para cargas
largas y sostenidas, conviene dejar un margen de seguridad amplio.

## Siguientes pasos

- Repetir la celda pura de Gemma-7B MST `600-1000_1000-1500`. Su capacidad medida (~6,5 req/min) es
  anómala y explica las mayores desviaciones positivas (+44 % y +86 %).
- Añadir réplicas a las celdas puras MST, que ahora solo tienen 1–2 búsquedas cada una.
- Repetir más mezclas mitad y mitad en MST para confirmar o descartar la penalización de −11 %.

## Respaldo estadístico (resumen)

- **Ley de combinación:** el exponente estimado de la media potencia es q = −0,94 (IC bayesiano
  90 %: −0,99 a −0,90; perfil de verosimilitud 95 %: −1,00 a −0,88). La ley armónica es q = −1. Las
  leyes geométrica (q = 0) y aritmética (q = +1) se rechazan con claridad en la puntuación
  predictiva (−135 y −232 log-unidades frente a la armónica).
- **Calibración:** regresión del log de la capacidad medida sobre el log de la predicción armónica,
  con pendiente 1,003 (IC 95 %: 0,96–1,04) y R² = 0,98.
- **Sesgo global:** −4,9 % (IC bayesiano 90 %: −11 % a +2,6 %). La probabilidad de que el sesgo esté
  dentro de ±10 % es del 88 %. La prueba de equivalencia TOST ±10 % da p = 0,0001.
- **Ruido:** la variación entre réplicas de una celda pura es ~0,7 % (MIT) y ~2 % (MST). La
  desviación propia de cada mezcla es ~5,5 % (MIT) y ~20 % (MST).
- **Diseño de la mezcla:** no hay diferencias significativas entre mitad y mitad y según su coste
  (Mann–Whitney p = 0,28 en MIT y 0,15 en MST).

## Reproducir

```
python analysis/additivity_analysis.py --out <dir>     # análisis frecuentista + bayesiano (PyMC)
python analysis/build_report.py <dir> report.html      # informe HTML con las figuras
```

Requiere `pandas numpy scipy statsmodels pymc arviz`. El informe interactivo generado está en
[`analysis/report/additivity-report.html`](report/additivity-report.html).
