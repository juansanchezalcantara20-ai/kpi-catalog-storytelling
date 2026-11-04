# Indicadores que se entienden

**Un indicador no depende de la herramienta.** Cada indicador de este sitio se define una sola vez, se
calcula una sola vez y se presenta de dos formas: como una **historia** que explica qué pasó y qué decidir,
y como un **tablero** para revisarlo cada semana.

<div class="grid cards" markdown>

- **[Cinco casos](cases/service.md)**: atención de solicitudes, mantenimiento, inventario, clientes y calidad de los
  datos. Cada uno cuenta qué pasó, por qué importa y qué se decidió.
- **[Errores comunes al medir](antipatterns.md)**: el mismo dato mostrado de una forma que engaña y de una forma honesta, lado a lado.
- **[Catálogo de indicadores](catalog/index.md)**: qué mide cada indicador, cómo se calcula, un ejemplo con números y
  qué decisión ayuda a tomar.
- **[Tablero](dashboard/index.html)**: los 28 indicadores con su semáforo, su tendencia y su meta, con filtros.

</div>

## Para quién es

Para quien tiene que decidir con números sin ser analista: un jefe de operaciones, de mantenimiento, de
logística o de servicio al cliente. Si es la primera vez, empiece por [Cómo leer este sitio](como-leer.md): en un
minuto explica qué es un indicador, qué es una meta y cómo leer el semáforo 🟢 En meta · 🟡 Vigilar · 🔴 Actuar.

## De dónde salen los datos

El caso de atención de solicitudes usa **solicitudes ciudadanas reales de la ciudad de Nueva York** (servicio 311).
Los casos de mantenimiento, inventario y clientes usan **datos públicos reales** del repositorio UCI combinados con
simulaciones para lo que esas fuentes no registran. Cada página dice claramente qué parte es real y qué parte es
simulada; los detalles están en [Fuentes de datos](data-sources.md).
