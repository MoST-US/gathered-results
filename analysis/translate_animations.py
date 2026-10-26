"""Derive the English animations template from the Spanish one (animations_template.html).

Usage: python analysis/translate_animations.py   -> writes analysis/animations_template_en.html

The Spanish page is the master copy used in group meetings; the English page is the one published
with the paper artifact. Every pair below must match exactly once or more, so a change to the Spanish
page that is not mirrored here fails loudly instead of leaving untranslated text behind.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent

PAIRS = [
    ("<title>Aditividad explicada</title>", "<title>Additivity Explained</title>"),
    ("MoST · capacidad de servidores LLM con mezclas de peticiones", "MoST · LLM serving capacity under request mixes"),
    ("Aditividad, explicada en 9 escenas", "Additivity, explained in 9 scenes"),
    ("Por qué la capacidad de una mezcla se calcula sumando lo que ocupa cada petición, qué tal funciona con los datos reales de DeepSeek, Gemma y Llama, y dónde deja de funcionar. Cada escena se puede tocar: mueve los controles.",
     "Why the capacity of a request mix is obtained by adding up what each request occupies, how well that works with the real measurements of DeepSeek, Gemma and Llama, and where it stops working. Every scene is interactive: move the controls."),
    (">El servidor reparte su tiempo<", ">The server shares out its time<"),
    (">Por qué no sirve el promedio<", ">Why the average is wrong<"),
    (">Las dos formas de mezclar<", ">Two ways to mix<"),
    (">Los datos eligen la regla<", ">The data choose the rule<"),
    (">MIT y MST: misma media, distinta precisión<", ">MIT and MST: same mean, different precision<"),
    (">Peticiones pesadas y memoria<", ">Heavy requests and memory<"),
    (">El SLA agregado tapa a las lentas<", ">An aggregate SLA hides the slow requests<"),
    (">Las repeticiones son estables<", ">Repeated runs are stable<"),
    (">Las ráfagas: 3,5 veces durante dos minutos<", ">Bursts: 3.5 times for two minutes<"),
    ("Escena 1<", "Scene 1<"), ("Escena 2 · datos reales", "Scene 2 · real data"), ("Escena 3<", "Scene 3<"),
    ("Escena 4 · datos reales", "Scene 4 · real data"), ("Escena 5 · datos reales", "Scene 5 · real data"),
    ("Escena 6 · ilustración", "Scene 6 · illustration"), ("Escena 7 · simulación ilustrativa", "Scene 7 · illustrative simulation"),
    ("Escena 8 · datos reales", "Scene 8 · real data"), ("Escena 9 · datos reales", "Scene 9 · real data"),
    # scene 1
    ("Imagina un minuto de servidor como una barra. Una petición ligera ocupa un trocito; una pesada ocupa mucho más. Cuántas peticiones caben depende de cuánto ocupa cada una, no de cuántos tipos haya.",
     "Picture one minute of server time as a bar. A light request takes a small slice; a heavy one takes much more. How many requests fit depends on how much each one occupies, not on how many types there are."),
    ('aria-label="Coste de la petición pesada"', 'aria-label="Cost of the heavy request"'),
    ("Cajera: pesada = 10×", "Cashier: heavy = 10×"), ("DeepSeek: pesada = 30×", "DeepSeek: heavy = 30×"),
    ("Peticiones pesadas <input", "Heavy requests <input"),
    ("▶ Llenar el minuto", "▶ Fill the minute"),
    ("petición ligera (ocupa 1)", "light request (takes 1)"), ("petición pesada (ocupa ", "heavy request (takes "),
    ("peticiones caben en el minuto", "requests fit in the minute"),
    ("regla armónica (sumar lo que ocupan)", "harmonic rule (add up what they occupy)"),
    ("promedio simple de capacidades", "plain average of capacities"),
    ("Lo que cabe coincide con la regla armónica: 1 / C<sub>mezcla</sub> = Σ pᵢ / Cᵢ. El promedio simple se pasa de largo en cuanto hay peticiones pesadas.",
     "What fits matches the harmonic rule: 1 / C<sub>mix</sub> = Σ pᵢ / Cᵢ. The plain average overshoots as soon as heavy requests appear."),
    ('"un minuto de servidor"', '"one minute of server time"'),
    # scene 2
    ("DeepSeek en la prueba MIT: <span id=\"s2-cl\"></span> peticiones/min si todas son cortas, <span id=\"s2-ch\"></span> si todas son de prompt largo y respuesta larga. La línea discontinua es el promedio simple; la continua, la regla armónica. Los puntos son mezclas medidas.",
     "DeepSeek in the MIT test: <span id=\"s2-cl\"></span> requests/min if all are short, <span id=\"s2-ch\"></span> if all have a long prompt and a long answer. The dashed line is the plain average; the solid line, the harmonic rule. The dots are measured mixes."),
    (">regla armónica</span>", ">harmonic rule</span>"), (">promedio simple</span>", ">plain average</span>"),
    (">mezcla medida</span>", ">measured mix</span>"),
    ("predice la regla armónica", "predicted by the harmonic rule"), ("predice el promedio simple", "predicted by the plain average"),
    ("el promedio se equivoca por", "the average is off by"),
    ("La curva armónica cae en picado: con solo un 3 % de peticiones pesadas, la capacidad ya se reduce a la mitad. Las mezclas medidas quedan cerca de esa curva (a un 6 % al 50 % y a un 20 % al 3 %) y muy lejos de la recta del promedio, que se equivoca hasta por un factor de 8.",
     "The harmonic curve drops sharply: with only 3 % heavy requests, capacity is already halved. The measured mixes lie close to that curve (6 % off at 50 % and 20 % off at 3 %) and far from the straight line of the average, which is off by up to a factor of 8."),
    ("<b>Mezcla medida</b><br>${(100 * d.heavy_share).toFixed(1)} % pesadas<br>${nf(d.obs)} peticiones/min<br>regla armónica: ",
     "<b>Measured mix</b><br>${(100 * d.heavy_share).toFixed(1)} % heavy<br>${nf(d.obs)} requests/min<br>harmonic rule: "),
    ('"porcentaje de peticiones pesadas en la mezcla"', '"share of heavy requests in the mix"'),
    ('"peticiones/min (escala log)"', '"requests/min (log scale)"'),
    # scene 3
    ("Contar peticiones no es lo mismo que contar tiempo. Con una pesada que ocupa 30 veces más, mezclar mitad y mitad en número deja casi todo el servidor a las pesadas. Repartir según su coste (97 % / 3 %) les da a cada tipo la mitad del tiempo.",
     "Counting requests is not the same as counting time. When a heavy request occupies 30 times more, an equal split by count leaves almost the whole server to the heavy ones. Splitting by cost (97 % / 3 %) gives each type half of the time."),
    ('aria-label="Forma de mezclar"', 'aria-label="How to mix"'),
    (">Mitad y mitad<", ">Equal shares<"), (">Según su coste<", ">By cost<"),
    ("></i>ligeras</span>", "></i>light</span>"), ("></i>pesadas</span>", "></i>heavy</span>"),
    ("Las dos formas son predicciones distintas de la misma regla. Que acierte en las dos es una prueba exigente.",
     "The two designs are different predictions of the same rule. That it holds for both is a demanding test."),
    ('"Cuántas peticiones"', '"How many requests"'), ('"Cuánto tiempo de servidor ocupan"', '"How much server time they take"'),
    ("% ligeras`", "% light`"), ("% pesadas`", "% heavy`"),
    # scene 4
    ("Hay una familia de reglas para combinar capacidades, con un parámetro q: q = +1 es el promedio simple, q = 0 la media geométrica, q = −1 la armónica. Mueve q y mira cómo se alinean (o no) las <span id=\"s4-n\"></span> mezclas reales con la diagonal.",
     "There is a family of rules to combine capacities, with one parameter q: q = +1 is the plain average, q = 0 the geometric mean, q = −1 the harmonic mean. Move q and watch the <span id=\"s4-n\"></span> real mixes line up (or not) with the diagonal."),
    ('<b id="s4-qv">+1,00</b>', '<b id="s4-qv">+1.00</b>'),
    ("Dejar que elijan los datos", "Let the data choose"),
    ("mezcla sin peticiones pesadas", "mix without heavy requests"), ("mezcla con peticiones pesadas", "mix with heavy requests"),
    ("error típico de la predicción", "typical prediction error"), ("q que minimiza el error", "q that minimises the error"),
    ("El error es mínimo cerca de q = −1: los datos, por sí solos, eligen sumar lo que ocupa cada petición.",
     "The error is smallest near q = −1: on their own, the data choose to add up what each request occupies."),
    ('"capacidad predicha con q"', '"capacity predicted with q"'), ('"capacidad medida"', '"measured capacity"'),
    ('[-1, "armónica"], [0, "geom."], [1, "promedio"]', '[-1, "harmonic"], [0, "geom."], [1, "average"]'),
    ('"error según q"', '"error by q"'),
    ("<br>medida ${nf(d.obs)} · armónica ", "<br>measured ${nf(d.obs)} · harmonic "),
    # scene 5
    ("Cada punto es un diseño de mezcla (sus repeticiones promediadas) y su desviación respecto a la regla armónica. La línea vertical es la media de cada prueba.",
     "Each dot is a mix design (its repeated runs averaged) and its departure from the harmonic rule. The vertical line is the mean of each test."),
    ("Incluir mezclas con peticiones pesadas", "Include mixes with heavy requests"),
    ("></i>sin peticiones pesadas</span>", "></i>without heavy requests</span>"),
    ("></i>con peticiones pesadas</span>", "></i>with heavy requests</span>"),
    ("Las dos pruebas siguen la misma regla con el mismo sesgo medio. En MST (30 minutos) los puntos se dispersan el doble: cada predicción concreta es menos fiable.",
     "Both tests follow the same rule with the same mean bias. In MST (30 minutes) the dots spread twice as much: each individual prediction is less reliable."),
    ("<br>desviación ${pctS(Math.exp(d.rH) - 1)} · ${d.runs} ejecución(es)", "<br>departure ${pctS(Math.exp(d.rH) - 1)} · ${d.runs} run(s)"),
    ('"capacidad medida frente a la regla armónica (banda = ±10 %; barra gris = ±1 desviación típica)"',
     '"measured capacity versus the harmonic rule (band = ±10 %; grey bar = ±1 standard deviation)"'),
    ("${k}: sesgo medio (${stats[k].n} diseños)", "${k}: mean bias (${stats[k].n} designs)"),
    ("${k}: error medio de cada predicción", "${k}: mean error of a single prediction"),
    # scene 6
    ("Cada token de una conversación ocupa memoria en la GPU (la caché KV). Una petición pesada tiene ~2.050 tokens. Mira cuántas caben a la vez en una A40 según la memoria por token de cada modelo.",
     "Every token of a conversation occupies GPU memory (the KV cache). A heavy request has ~2,050 tokens. See how many fit at once on an A40 given each model's memory per token."),
    ("▶ Llenar la GPU", "▶ Fill the GPU"),
    ("></i>pesos del modelo</span>", "></i>model weights</span>"), ("></i>una petición pesada en memoria</span>", "></i>one heavy request in memory</span>"),
    ("Supuestos: 48 GB × 90 % utilizables; pesos en fp16 (Gemma-7B ≈ 17 GB, Llama-3.1-8B ≈ 16 GB, DeepSeek-R1-Distill-Qwen-7B ≈ 15 GB); caché KV por token según la configuración pública de cada modelo; 800 tokens de prompt + 1.250 de respuesta. Es un orden de magnitud, no una medida.",
     "Assumptions: 48 GB × 90 % usable; fp16 weights (Gemma-7B ≈ 17 GB, Llama-3.1-8B ≈ 16 GB, DeepSeek-R1-Distill-Qwen-7B ≈ 15 GB); KV cache per token from each model's public configuration; 800 prompt tokens + 1,250 answer tokens. An order of magnitude, not a measurement."),
    ("Gemma usa unas 8 veces más memoria por token que DeepSeek, y es el modelo cuyas mezclas con peticiones pesadas más se desvían. Con tres modelos es una hipótesis, no una prueba.",
     "Gemma uses about 8 times more memory per token than DeepSeek, and it is the model whose mixes with heavy requests depart the most. With three models this is a hypothesis, not a proof."),
    ("KB por token`", "KB per token`"), ('"a la vez"', '"at once"'),
    # scene 7
    ("Supón que el SLA exige que la mediana de latencia de todas las peticiones de la prueba esté por debajo de un umbral. Las pesadas solas lo incumplen siempre. Pero en una mezcla, la mediana la deciden las ligeras mientras sean mayoría.",
     "Suppose the SLA requires the median latency of all the requests of a test to stay below a threshold. Heavy requests alone always fail it. But in a mix, the light requests decide the median as long as they are the majority."),
    ("></i>latencia de ligeras</span>", "></i>latency of light requests</span>"), ("></i>latencia de pesadas</span>", "></i>latency of heavy requests</span>"),
    ("></i>mediana de todas</span>", "></i>median of all</span>"), ("></i>umbral del SLA</span>", "></i>SLA threshold</span>"),
    ("Latencias simuladas. Es la hipótesis que explicaría por qué las mezclas 50/50 de Gemma cumplen el SLA con 20 peticiones pesadas por minuto cuando solas lo incumplen con 8, y por qué ese diseño da resultados distintos al repetirlo: al 50 %, la mediana cae justo en la frontera. Hay que comprobarlo en el código de MoST.",
     "Simulated latencies. This is the hypothesis that would explain why Gemma's 50/50 mixes pass the SLA with 20 heavy requests per minute when heavy requests alone fail it at 8, and why that design gives different results when repeated: at 50 %, the median falls right on the boundary. It still has to be checked against the MoST code."),
    ("Si el SLA se mide sobre todas las peticiones juntas, los recursos se suman pero el veredicto del SLA no. Evaluarlo por tipo de petición lo evitaría.",
     "If the SLA is measured over all requests together, resources add up but the SLA verdict does not. Evaluating it per request type would avoid this."),
    ('"✓ Cumple el SLA" : "✗ No cumple el SLA"', '"✓ Meets the SLA" : "✗ Fails the SLA"'),
    ('"umbral"', '"threshold"'), ("`mediana ${med.toFixed(1)} s`", "`median ${med.toFixed(1)} s`"),
    ('"latencia de cada petición (simulada, escala log)"', '"latency of each request (simulated, log scale)"'),
    # scene 8
    ("Cada punto es una ejecución repetida de un diseño, colocada según cuánto se aparta de la mediana de su diseño. Casi todas caen exactamente en cero: repetir da el mismo resultado.",
     "Each dot is a repeated run of a design, placed by how far it departs from its design's median. Almost all fall exactly on zero: repeating gives the same result."),
    ("▶ Repetir la animación", "▶ Replay the animation"),
    ("diseño sin peticiones pesadas", "design without heavy requests"), ("diseño con peticiones pesadas", "design with heavy requests"),
    ("Las pocas ejecuciones que se apartan mucho pertenecen a diseños con peticiones pesadas: la inestabilidad tiene una causa concreta, no es ruido general.",
     "The few runs that depart a lot belong to designs with heavy requests: the instability has a specific cause, it is not general noise."),
    ("<br>${d.n} repeticiones · esta: ${pctS(Math.exp(d.dev) - 1)} frente a la mediana", "<br>${d.n} repeats · this one: ${pctS(Math.exp(d.dev) - 1)} versus the median"),
    ('v === 0 ? "igual"', 'v === 0 ? "same"'),
    ('"cada ejecución frente a la mediana de su diseño"', '"each run versus the median of its design"'),
    ("<span>de las ${R.length} ejecuciones repetidas dan exactamente el resultado de su diseño</span>",
     "<span>of the ${R.length} repeated runs give exactly their design's result</span>"),
    ("<span>se apartan más de un 10 %</span>", "<span>depart by more than 10 %</span>"),
    ("<span>de esas son de diseños con peticiones pesadas</span>", "<span>of those belong to designs with heavy requests</span>"),
    # scene 9
    ("El <i>burst factor</i> de un tipo de petición es MIT / MST: cuántas veces su ritmo sostenible (la prueba de 30 minutos) aguanta el servidor durante una ráfaga de 2 minutos. Cada barra es uno de los 60 tipos de petición de los tres modelos, ordenados de menor a mayor.",
     "The <i>burst factor</i> of a request type is MIT / MST: how many times its sustainable rate (the 30-minute test) the server withstands during a 2-minute burst. Each bar is one of the 60 request types of the three models, sorted from lowest to highest."),
    ("></i>a menos del 15 % de la mediana de su modelo</span>", "></i>within 15 % of its model's median</span>"),
    ("></i>más lejos</span>", "></i>further away</span>"), ("></i>mediana ± 15 %</span>", "></i>median ± 15 %</span>"),
    ("Casi todos los tipos de petición aguantan ráfagas de unas 3,5 veces su ritmo sostenible, y el valor es prácticamente el mismo en los tres modelos. Por eso una sola moneda basada en MST sirve también para las ráfagas: basta con permitir unas 3,5 veces el ritmo del plan durante 2 minutos.",
     "Almost every request type withstands bursts of about 3.5 times its sustainable rate, and the value is practically the same for the three models. That is why a single MST-based currency also works for bursts: it is enough to allow about 3.5 times the plan's rate over 2 minutes."),
    ('const DEC = ",";', 'const DEC = ".";'),
    ('const L9 = {median: "mediana", axis: "60 tipos de petición (3 modelos × 20), ordenados por burst factor = MIT / MST",\n  r1: "burst factor mediano de los 60 tipos", r2: "de los tipos a menos del 15 % de la mediana de su modelo",\n  r3: "respuestas cortas (1-100 tokens) / el resto"};',
     'const L9 = {median: "median", axis: "60 request types (3 models × 20), sorted by burst factor = MIT / MST",\n  r1: "median burst factor of the 60 types", r2: "of the types within 15 % of their model\'s median",\n  r3: "short answers (1-100 tokens) / the rest"};'),
    # formatting and fallback
    ('toLocaleString("es-ES")', 'toLocaleString("en-US")'),
    ('Math.abs(q).toFixed(2).replace(".", ",")', 'Math.abs(q).toFixed(2)'),
    ('"q = " + Q.best.toFixed(2).replace(".", ",")', '"q = " + Q.best.toFixed(2)'),
    ("No se han podido cargar los datos o la librería de gráficos.", "The data or the charting library could not be loaded."),
]


def main():
    src = (HERE / "animations_template.html").read_text(encoding="utf-8")
    out = src
    missing = [a for a, _ in PAIRS if a not in out]
    if missing:
        raise SystemExit("untranslated (pattern not found):\n  " + "\n  ".join(m[:90] for m in missing))
    for a, b in PAIRS:
        out = out.replace(a, b)
    (HERE / "animations_template_en.html").write_text(out, encoding="utf-8")
    print("wrote animations_template_en.html with", len(PAIRS), "replacements")


if __name__ == "__main__":
    main()
