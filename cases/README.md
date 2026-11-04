# Casos

Cada caso se cuenta en el sitio con la misma estructura: **en 30 segundos → pregunta → indicadores → lo que
encontramos → qué decidimos → cómo lo seguimos midiendo → detalle técnico**.

| # | Caso | Datos reales | Plan B (si la descarga falla) |
|---|------|------|------|
| 1 | [Atención de solicitudes](01_service/README.md) | NYC 311, Departamento de Transporte | mesa de ayuda simulada |
| 2 | [Mantenimiento](02_maintenance/README.md) | AI4I 2020 (UCI) | AI4I regenerado con sus reglas publicadas |
| 3 | [Inventario y demanda](03_inventory/README.md) | Online Retail II (UCI) | ventas simuladas con la misma estructura y defectos |
| 4 | [Clientes](04_customers/README.md) | Online Retail II (UCI) | las mismas ventas simuladas |
| 5 | [Calidad de los datos](05_data_quality/README.md) | los datos de los casos 1 a 4 | sigue a los otros casos |

El origen usado en cada actualización queda en `data/processed/manifest.json` y en la página *Fuentes de datos*.
