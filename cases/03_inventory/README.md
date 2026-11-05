# Caso 3 · Inventario y demanda

**Datos reales:** [Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii) (UCI, CC BY 4.0):
todas las líneas de factura de una tienda en línea de regalos, dic 2009 – dic 2011.

**Plan B:** `src/kpistory/data/retail.py`, semilla `2011`: unos 4 200 clientes y 900 productos con temporada de fin de
año y los mismos defectos del archivo real.

**Simulación de inventario (siempre simulada, semilla 31):** los 40 productos más vendidos y 8 que dejaron de venderse;
pronóstico = promedio de las últimas 8 semanas; revisión semanal, pedido hasta 5 semanas de pronóstico, proveedor de 10
a 17 días; lo que no hay en inventario se pierde; entrega prometida en 3 días; costo = 60 % del precio mediano.
