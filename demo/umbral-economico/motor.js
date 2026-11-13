/* motor.js — el núcleo de «umbral», escrito para dar el mismo bit que umbral.py.
 *
 * Un intento cuesta C y paga V con probabilidad p, hasta m intentos. Hay tres
 * cómputos independientes del mismo número: la suma de términos positivos, la
 * forma cerrada y un Monte Carlo con PRNG especificado (no heredado). Cuando no
 * hay un oráculo previo contra el que portar, el falsificador no compara un
 * port con su original: compara dos caminos que deberían llegar al mismo sitio.
 *
 * Este archivo es la copia canónica. La página embebe el cuerpo de arriba del
 * centinela «fin del cuerpo portable» carácter por carácter, y
 * `verificar_paridad.py` falla si los dos textos divergen.
 */

var SEMILLA_DEFECTO = 20261113;
var N_MONTECARLO_DEFECTO = 8000;

function potencia(u, m) {
  // Elevación al cuadrado: la misma secuencia de multiplicaciones que umbral.py.
  // IEEE 754 es determinista, así que esto sale paritario bit a bit.
  var r = 1.0, b = u, e = m | 0;
  while (e) {
    if (e & 1) r *= b;
    b *= b;
    e >>= 1;
  }
  return r;
}

function supervivenciaTrasM(p, m) {
  return potencia(1.0 - p, m);
}

function exitoEnM(p, m) {
  return 1.0 - supervivenciaTrasM(p, m);
}

function umbral(V, C) {
  return C / V;
}

function evPorIntento(p, V, C) {
  return p * V - C;
}

function esperanzaIntentosSuma(p, m) {
  var u = 1.0 - p, t = 1.0, s = 0.0, k;
  for (k = 1; k <= m; k++) {
    s += k * p * t;
    t *= u;
  }
  return s + m * t;
}

function esperanzaIntentosCerrada(p, m) {
  return (1.0 - potencia(1.0 - p, m)) / p;
}

function evPolitica(p, V, C, m) {
  return exitoEnM(p, m) * V - C * esperanzaIntentosSuma(p, m);
}

function evPoliticaCerrada(p, V, C, m) {
  return exitoEnM(p, m) * (V - C / p);
}

/* Intentos necesarios para que la ruina baje del objetivo. Búsqueda entera a
 * propósito: `Math.log` de V8 y `math.log` de CPython no coinciden en el último
 * ULP, y meterlo aquí rompería la paridad que este archivo promete. */
function intentosParaRuina(p, objetivo, tope) {
  if (tope === undefined) tope = 200000;
  var m = 1;
  while (m <= tope) {
    if (supervivenciaTrasM(p, m) <= objetivo) return m;
    m += 1;
  }
  return -1;
}

function Lcg(semilla) {
  this.s = semilla >>> 0;
}
Lcg.prototype.siguiente = function () {
  // Math.imul da el producto 32x32 en 32 bits exactos: el mismo entero que
  // `(1664525 * s + 1013904223) & 0xFFFFFFFF` en Python.
  this.s = (Math.imul(1664525, this.s) + 1013904223) >>> 0;
  return this.s;
};
Lcg.prototype.uniforme = function () {
  return this.siguiente() / 4294967296.0;
};

function montecarlo(p, V, C, m, n, semilla) {
  if (n === undefined) n = N_MONTECARLO_DEFECTO;
  if (semilla === undefined) semilla = SEMILLA_DEFECTO;
  var gen = new Lcg(semilla), ruinas = 0, suma = 0.0, i, k, neto;
  for (i = 0; i < n; i++) {
    k = 0;
    neto = -m * C;
    while (k < m) {
      k += 1;
      if (gen.uniforme() < p) {
        neto = V - k * C;
        break;
      }
    }
    if (neto === -m * C) ruinas += 1;
    suma += neto;
  }
  return { n: n, semilla: semilla, ruinas: ruinas, ruina_mc: ruinas / n, media_mc: suma / n };
}

function medir(p, V, C, m, n, semilla) {
  var u = 1.0 - p, pmin = umbral(V, C);
  var r = {
    p: p, V: V, C: C, m: m,
    u_m: potencia(u, m),
    p_min: pmin,
    ratio: p / pmin,
    ev_intento: evPorIntento(p, V, C),
    q_exito: exitoEnM(p, m),
    ruina: supervivenciaTrasM(p, m),
    ek: esperanzaIntentosSuma(p, m),
    ek_cerrada: esperanzaIntentosCerrada(p, m),
    ev_politica: evPolitica(p, V, C, m),
    ev_politica_cerrada: evPoliticaCerrada(p, V, C, m),
    perdida_maxima: m * C,
    m_ruina_50: intentosParaRuina(p, 0.50),
    m_ruina_10: intentosParaRuina(p, 0.10)
  };
  /* n <= 0 no es «cero mediciones»: es la ausencia de la medición, y una
   * ausencia no se publica como cero. La clave no viaja. */
  if (n === undefined) n = N_MONTECARLO_DEFECTO;
  if (n > 0) r.montecarlo = montecarlo(p, V, C, m, n, semilla);
  return r;
}

var CLAVES_EXACTAS = [
  "u_m", "p_min", "ratio", "ev_intento", "q_exito", "ruina",
  "ek", "ek_cerrada", "ev_politica", "ev_politica_cerrada",
  "perdida_maxima", "m_ruina_50", "m_ruina_10"
];

/* ===== fin del cuerpo portable =====
 * Lo de arriba es lo que la página embebe en <script id="motor">, carácter por
 * carácter. Lo de abajo sólo existe para node: exigir el módulo y nada más.
 */
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    SEMILLA_DEFECTO: SEMILLA_DEFECTO,
    N_MONTECARLO_DEFECTO: N_MONTECARLO_DEFECTO,
    potencia: potencia,
    supervivenciaTrasM: supervivenciaTrasM,
    exitoEnM: exitoEnM,
    umbral: umbral,
    evPorIntento: evPorIntento,
    esperanzaIntentosSuma: esperanzaIntentosSuma,
    esperanzaIntentosCerrada: esperanzaIntentosCerrada,
    evPolitica: evPolitica,
    evPoliticaCerrada: evPoliticaCerrada,
    intentosParaRuina: intentosParaRuina,
    montecarlo: montecarlo,
    medir: medir,
    CLAVES_EXACTAS: CLAVES_EXACTAS
  };
}
