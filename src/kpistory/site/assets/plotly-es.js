// Spanish locale for Plotly: month names, decimal point and a space as thousands separator.
Plotly.register({
  moduleType: "locale",
  name: "es",
  dictionary: {},
  format: {
    days: ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"],
    shortDays: ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"],
    months: ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
    shortMonths: ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"],
    date: "%d/%m/%Y",
    decimal: ".",
    thousands: " ",
  },
});
