# Decisiones del proyecto

Cada decisión que no es obvia, con su motivo. Están agrupadas por etapa del proyecto.

## 1 · Catálogo, motor de cálculo y pruebas

| Decisión | Por qué |
|---|---|
| Un solo archivo de catálogo es la única fuente de verdad de los indicadores, y se valida automáticamente. | Si un indicador se define en dos lugares, tarde o temprano los dos dicen cosas distintas. La validación revisa que no falten campos, que la meta sea coherente con el sentido del indicador y que los indicadores relacionados existan. |
| Cada indicador tiene una sola función de cálculo, y la validación falla si falta alguna o sobra alguna. | «Nada se define dos veces» tiene que cumplirse por diseño, no por disciplina. |
| Los parámetros (por ejemplo, el límite de 7 días de las pendientes) se escriben una sola vez en el catálogo. | Cambiar una regla de negocio es cambiar una línea, y el cambio llega a todo el cálculo. |
| Cada indicador tiene también una consulta SQL de referencia al lado de su definición. | Permite comprobar con dos implementaciones distintas que la fórmula significa lo que dice la definición. |
| Las proporciones se guardan como fracción y se muestran como porcentaje con un solo formato («89.2 %»). | Evita el error de no saber si 0.9 es 90 % o 0.9 %, y da un formato único en todo el sitio. |
| Hay tres sentidos posibles: más alto es mejor, más bajo es mejor y dentro de una franja. | Los días de cobertura y el sesgo del pronóstico son malos tanto si son muy altos como si son muy bajos. |
| El límite de la meta cuenta como cumplido (90 % con meta de 90 % está en meta). | Así se escriben las metas («al menos 90 %») y una prueba lo fija. |
| Si no hay datos para calcular, el resultado es «Sin dato», nunca cero. | Un 0 % de cumplimiento en una semana sin solicitudes sería una falsa alarma. |
| El tiempo medio de reparación se mantiene como promedio y siempre se muestra junto a la reparación típica. | Solo con promedios se cumple que la disponibilidad depende del tiempo entre fallas y del tiempo de reparación; el error de lectura se documenta en vez de cambiar la definición. |
| Los tiempos de respuesta y de resolución usan la solicitud típica (mediana). | Son tiempos con colas largas y no hay ninguna identidad que dependa de ellos. |
| Cada indicador tiene un ejemplo calculado a mano, con el resultado escrito, que se comprueba contra el cálculo y contra la consulta SQL. | Es la forma más barata de demostrar que una fórmula hace lo que dice. Los mismos ejemplos aparecen en cada ficha del catálogo. |
| El catálogo no puede recomendar gráficos de torta. | El catálogo recomienda gráficos; no debe poder recomendar el que las reglas de estilo prohíben. |
| La segmentación de clientes es una herramienta; el indicador es el ingreso en riesgo. | Una segmentación no tiene meta; la parte del ingreso en riesgo sí, y dispara una decisión. |
| La recomendación se calcula como promotores menos detractores y se muestra con su margen de error. | Los dos errores más comunes son promediar las notas y sobreinterpretar muestras pequeñas. |

## 2 · Datos y plan B

| Decisión | Por qué |
|---|---|
| Cada fuente pública tiene un plan B: un generador con semilla fija y la misma estructura. | Si una descarga falla, el sitio se sigue publicando, y siempre con los mismos números. |
| De dónde salió cada dato se registra en cada actualización y se muestra en cada página. | El lector siempre tiene que saber si un gráfico es real o simulado. |
| Las órdenes de trabajo, el inventario, el pronóstico, las entregas y la encuesta se simulan con reglas explícitas. | Las fuentes públicas tienen la demanda y el proceso, pero no esa mitad operativa; se simula de forma transparente en vez de presentarla como observada. |
| El pronóstico es, a propósito, un promedio de las últimas 8 semanas. | Es el método más común en la práctica y su atraso frente a la temporada es justamente la historia del caso 3. |
| Los quiebres de stock solo cuentan los productos activos. | La primera versión mostraba 18 % de quiebres, casi todos de productos no lanzados o ya descontinuados. |
| La calidad de los datos se mide sobre los datos tal como llegan, antes de limpiarlos. | Medir después de limpiar siempre daría 100 %. |
| Las mesas de ayuda simuladas usan una cola con capacidad diaria. | Una primera versión con tiempos al azar no generaba pendientes; con capacidad limitada aparecen la acumulación y los incumplimientos, como en la realidad. |

## 3 · Presentación

| Decisión | Por qué |
|---|---|
| El sitio se genera desde los datos y no se guardan las páginas generadas. | Cada número de un título o de una frase sale de los datos: el texto no puede contradecir al gráfico, y sigue siendo correcto con datos reales o simulados. |
| Los títulos de los gráficos son conclusiones calculadas. | La regla «el título es la conclusión» solo sobrevive a un cambio de datos si la conclusión se calcula. Cuando la conclusión depende de los datos, la frase completa cambia, no solo el número. |
| Un color para destacar (azul) y gris para el contexto; verde, amarillo y rojo solo para el semáforo, siempre con texto. | Paleta apta para daltonismo; el estado nunca depende solo del color. |
| Las barras empiezan en cero, salvo la disponibilidad por máquina, que lo dice en su subtítulo. | Todas las máquinas están entre 75 % y 100 %; romper la regla abiertamente es mejor que esconderlo. |
| Solo se usan periodos completos (meses, trimestres, semanas). | Un periodo a medias parece una caída que no existió. |
| La segunda presentación es un tablero interactivo en la misma web. | Todo funciona en el navegador y se actualiza en la nube; las historias explican el porqué y el tablero sirve para el seguimiento semanal. |
| Cada indicador tiene un único valor de referencia, que usan el caso, el catálogo y el tablero. | Un mismo indicador no puede mostrar dos números distintos en el sitio; una prueba lo comprueba. |

## 4 · Español, lectura sencilla y datos reales

| Decisión | Por qué |
|---|---|
| Todo lo que lee una persona está en español; los nombres internos del código quedan en inglés pero nunca se muestran sin su etiqueta. | El lector es un jefe de operaciones o un reclutador, no un programador. |
| Cada caso empieza con un recuadro «En 30 segundos» y termina con un «Detalle técnico» cerrado. | Quien decide lee lo primero; quien revisa el cálculo abre lo último. Solo ahí aparecen nombres de columnas y fórmulas. |
| Las prioridades se llaman Urgente, Alta, Media y Baja, con su plazo al lado; los trimestres se escriben «oct–dic 2024». | Los códigos internos no le dicen nada a un lector común. |
| Una prueba automática revisa la legibilidad de cada página publicada. | Falla si encuentra palabras técnicas en inglés, siglas sin explicar o código fuera del detalle técnico. |
| Se revisó la aparente contradicción del caso 1: tiempo típico de resolución en meta y pendientes antiguas en rojo. | No era un error: el primero mira solo las solicitudes cerradas y el segundo las que siguen abiertas al corte. La página lo explica con números y una prueba fija qué cuenta cada uno. |
| Una prueba comprueba que ningún porcentaje quede fuera de 0 a 100 % y que el caso, el catálogo y el tablero muestren la misma cifra. | La coherencia de los números es parte del método, no un detalle. |
| El caso 1 usa solicitudes ciudadanas reales de Nueva York (servicio 311) del Departamento de Transporte. | Es una fuente abierta, estable, sin clave y con fechas de apertura y cierre, tipo y canal. No se encontró una fuente peruana equivalente con fechas de cierre que se pueda descargar de forma estable sin registro. |
| La prioridad y el plazo de cada tipo de reclamo son un supuesto propio, documentado en Fuentes de datos. | La ciudad no publica plazos por tipo de reclamo; presentarlo como regla oficial sería falso. |
| Solo se descargan columnas sin datos personales, y un control falla la publicación si aparece algún dato personal. | Se publican cifras agregadas, nunca direcciones, nombres, teléfonos ni textos de ciudadanos. |
| La descarga corre en GitHub Actions cada mes y cuando alguien la pide, y solo publica si pasan todas las pruebas. | El entorno de desarrollo no tiene internet; la nube sí, y una actualización que rompe una prueba no llega al sitio. |
| Si la descarga trae menos filas de las esperadas, se considera fallida y se usa el plan B, avisándolo. | Una descarga incompleta mostraría números equivocados con apariencia de reales. |

## 5 · Explicaciones al pasar el mouse, gráficos que responden y valor en soles

| Decisión | Por qué |
|---|---|
| Las explicaciones de cada tarjeta salen en un tooltip propio y accesible: se abre al pasar el mouse, con el teclado o con un toque, y se cierra con Esc. | El atributo de título del navegador no funciona en celulares ni con teclado, y no se puede leer completo. El texto sale del catálogo, nunca escrito a mano. |
| En el celular, el primer toque abre la explicación y el segundo sigue el enlace. | Si el toque navegara de inmediato, la explicación nunca se vería en el celular. |
| El tooltip se ubica abajo, arriba o al costado de la tarjeta según el espacio, y nunca sale de la pantalla. | Con tarjetas cerca del borde inferior, una explicación larga quedaba cortada. |
| Un glosario de siglas se agrega solo a todas las páginas y se muestra al pasar el mouse. | Explicar cada sigla en cada página una sola vez, sin repetir el texto a mano. |
| Cada gráfico responde una pregunta, y el tipo de gráfico depende de la pregunta: bala para «cuánto falta», Pareto para «dónde se concentra», histograma para «cómo se reparte», cascada para «qué explica el cambio», pequeños múltiples para comparar grupos. | La misma línea para los 28 indicadores no ayudaba a decidir. |
| Las series de tiempo muestran la zona en meta, el margen de alerta y el evento clave anotado. | El lector ve de un vistazo cuándo empezó el problema y qué tan lejos está. |
| Todos los gráficos tienen su tabla «Ver datos»; si un gráfico no la trae, se arma sola a partir de sus datos. | Ningún gráfico depende del mouse para leerse, y una prueba lo comprueba. |
| Los supuestos económicos están en un archivo propio, en soles, todos marcados como ilustrativos y editables en la web. | El método tiene que servir con los números de cualquier empresa; no se usan datos de empleadores, clientes ni sueldos reales. |
| El costo de una brecha es lineal y nunca negativo: base × distancia a la meta × costo por unidad. Si el indicador ya está en meta, cuesta cero y se dice. | Es fácil de explicar, de revisar y de cambiar; un modelo más complejo escondería los supuestos. |
| «Decisión → resultado» es un escenario simulado y transparente de seis meses, con y sin la decisión, y un intervalo que responde «¿es ruido?». | Los datos terminan en la fecha de corte; inventar un «después» observado sería falso. Simularlo, y decirlo, muestra el método completo. |
| El resumen para gerencia es la primera página del menú y la portada del tablero; la portada del sitio muestra el valor total en juego. | Un gerente tiene que salir pensando cuánto le ahorra esto al mes. |
| La portada, el resumen, los casos y el tablero leen el mismo cálculo de valor, y una prueba verifica que las cifras coinciden. | Igual que con los indicadores: un número, una verdad. |
| La revisión visual con Playwright (escritorio y celular de 390 px) corre en el entorno de desarrollo y deja capturas en el repositorio; no corre en cada cambio de la nube. | Instalar un navegador completo en cada ejecución es lento; las pruebas de legibilidad, coherencia y gráficos sí corren siempre. |
| Los nombres de los campos del catálogo siguen en inglés (por ejemplo, el nombre del indicador y su definición corta); sus valores están en español. | Son identificadores internos, como acordamos; el lector nunca los ve. |
| Al revisar las cifras, el cumplimiento del plazo en el tablero publicado (94.4 %, todo el año) no coincidía con el del caso (89.2 %, último trimestre). Ahora todos muestran el mismo valor de referencia con su periodo. | Era un error de coherencia: dos periodos distintos para la misma tarjeta. |
