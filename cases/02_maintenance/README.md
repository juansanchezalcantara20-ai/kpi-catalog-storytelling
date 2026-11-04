# Caso 2 · Mantenimiento

**Datos reales:** [AI4I 2020 Predictive Maintenance Dataset](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset)
(UCI, CC BY 4.0): 10 000 registros de proceso con cinco tipos de falla.

**Plan B:** `generate_ai4i()`, semilla `2020`. AI4I es un conjunto sintético con reglas publicadas; el plan B las
reproduce (temperaturas, torque, velocidad, desgaste de herramienta y reglas de cada falla).

**Supuesto:** los 10 000 registros se reparten en 10 bloques seguidos = 10 máquinas; cada registro es una corrida de 4
horas y hay 4 corridas por día hábil.

**Órdenes de trabajo (siempre simuladas, semilla 2021):** una reparación por falla (duración típica de 1.5 a 4 h; 9 %
espera repuestos entre 16 y 60 h), cambios de herramienta planificados y un preventivo semanal por máquina (las
cuadrillas de M07 y M08 se atrasan 38 % de las veces). Defectos: 3 % de reparaciones sin tipo de falla, 0.4 % con cero
horas, 0.3 % duplicadas; M07 y M08 registran 35 % de sus órdenes con 1 a 4 días de atraso.
