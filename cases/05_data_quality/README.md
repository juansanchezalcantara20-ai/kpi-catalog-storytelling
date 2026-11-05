# Caso 5 · Calidad de los datos

Se mide sobre los datos de los casos 1 a 4 **tal como llegan**, antes de limpiarlos, con las reglas de
`kpis/dq_rules.yaml`: campos obligatorios, clave de negocio, reglas de validez y plazo de carga.

Los conjuntos sin hora de carga (NYC 311 y los de UCI) no se pueden medir en oportunidad; la página lo dice en vez de
inventar un valor.
