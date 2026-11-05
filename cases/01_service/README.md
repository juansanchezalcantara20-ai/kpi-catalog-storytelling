# Caso 1 · Atención de solicitudes

**Datos reales:** [NYC 311 Service Requests](https://data.cityofnewyork.us/Social-Services/311-Service-Requests-from-2010-to-Present/erm2-nwe9)
(NYC Open Data), sin cuenta ni clave. Configuración en `config/fuentes.yaml`: solo el Departamento de Transporte
(DOT) y los últimos 12 meses completos hasta el fin del mes anterior.

- **Privacidad:** solo se piden las columnas número, fecha de apertura, fecha de cierre, agencia, tipo, canal, estado y
  distrito. Nunca direcciones, coordenadas ni textos libres.
- **Descarga:** paginada de 50 000 filas, con 4 reintentos; si llegan menos de 5 000 filas se considera fallida.
- **Supuesto propio:** prioridad y plazo por tipo de reclamo (tabla en `config/fuentes.yaml` y en *Fuentes de datos*).
- **Sin dato en la fuente:** primera respuesta, contactos y reaperturas.
- **Fecha de corte:** último minuto del mes anterior; lo cerrado después cuenta como abierto.

**Plan B:** `src/kpistory/data/tickets.py`, semilla `7`, año 2024. Mesa de ayuda con cuatro equipos (Facturación,
Soporte técnico, Soporte en terreno, Cuentas), prioridades Urgente 8 h · Alta 24 h · Media 72 h · Baja 120 h, y una
capacidad diaria de 1.3 veces la demanda normal. Desde el 1 de septiembre de 2024 la demanda de «Soporte en terreno»
sube 60 % sin más personal. Defectos agregados para el caso 5: 0.5 % de duplicados, 1.2 % sin canal, 0.2 % con cierre
anterior a la apertura y 2.5 % cargados con más de 24 h de atraso.
