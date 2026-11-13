#!/usr/bin/env node
/* Ejecuta la pagina real contra un DOM simulado.
 *
 * verificar_paridad.py prueba que el MOTOR da las mismas cifras que el oraculo
 * en Python. Este verificador prueba que la PAGINA que lo envuelve hace lo que
 * dice: que la frontera del mapa se mueve cuando cambia el precio, que las dos
 * curvas de ruina no son la misma curva, que ningun rotulo del canvas se queda
 * sin traducir y que ningun numero se imprime truncado.
 *
 * RC 0 = la pagina se comporta. RC 1 = no. RC 3 = falta index.html.
 */
"use strict";

var fs = require("fs");
var path = require("path");
var vm = require("vm");

var RUTA = path.join(__dirname, "index.html");
if (!fs.existsSync(RUTA)) {
  console.error("RC 3 · falta " + RUTA);
  process.exit(3);
}
var HTML = fs.readFileSync(RUTA, "utf8");

var fallos = [];
function falla(m) { fallos.push(m); }

function extraeScript(id) {
  var re = new RegExp('<script[^>]*id="' + id + '"[^>]*>([\\s\\S]*?)<\\/script>');
  var m = re.exec(HTML);
  return m ? m[1] : null;
}
function extraeUi() {
  var re = /<script(?![^>]*\bid=)[^>]*>([\s\S]*?)<\/script>/g;
  var trozos = [], m;
  while ((m = re.exec(HTML)) !== null) trozos.push(m[1]);
  return trozos.length ? trozos[trozos.length - 1] : null;
}

var MOTOR = extraeScript("motor");
var UI = extraeUi();
if (!MOTOR) { console.error('RC 1 · la pagina no tiene <script id="motor">'); process.exit(1); }
if (!UI) { console.error("RC 1 · la pagina no tiene el script de interfaz"); process.exit(1); }

/* ---------- DOM simulado ---------- */
var ctxNulo = false;

function Nodo(tag, attrs) {
  this.tagName = tag.toUpperCase();
  this.attrs = attrs || {};
  this.id = this.attrs.id || "";
  this._texto = "";
  this._html = "";
  this.className = this.attrs["class"] || "";
  this.style = {};
  this.oyentes = {};
  this.width = parseInt(this.attrs.width || "0", 10);
  this.height = parseInt(this.attrs.height || "0", 10);
  this._value = this.ajustaPaso(this.attrs.value !== undefined ? this.attrs.value : "");
}
/* El navegador no guarda el value que se le asigna: lo ajusta al paso declarado.
   Sin esta regla el stub acepta 0.25 en un control step=0.02 y el verificador da
   RC 0 sobre una pagina que en Chrome enciende 0.26. */
Nodo.prototype.ajustaPaso = function (v) {
  if (this.tagName !== "INPUT" || this.attrs.type !== "range") return v;
  var x = parseFloat(v);
  if (!isFinite(x)) return v;
  var min = parseFloat(this.attrs.min), max = parseFloat(this.attrs.max), paso = parseFloat(this.attrs.step);
  if (isFinite(paso) && paso > 0) x = (isFinite(min) ? min : 0) + Math.round((x - (isFinite(min) ? min : 0)) / paso) * paso;
  if (isFinite(max)) x = Math.min(x, max);
  if (isFinite(min)) x = Math.max(x, min);
  return String(+x.toFixed(6));
};
Object.defineProperty(Nodo.prototype, "value", {
  get: function () { return this._value; },
  set: function (v) { this._value = this.ajustaPaso(v); }
});
Nodo.prototype.getAttribute = function (n) {
  return this.attrs[n] !== undefined ? this.attrs[n] : null;
};
Nodo.prototype.setAttribute = function (n, v) { this.attrs[n] = v; };
Nodo.prototype.addEventListener = function (t, fn) {
  (this.oyentes[t] || (this.oyentes[t] = [])).push(fn);
};
Nodo.prototype.dispara = function (t, ev) {
  var l = this.oyentes[t] || [];
  for (var i = 0; i < l.length; i++) l[i](ev || { currentTarget: this, target: this });
  return l.length;
};
Object.defineProperty(Nodo.prototype, "textContent", {
  get: function () { return this._texto; },
  set: function (v) { this._texto = String(v); documentStub._textosPintados.push(String(v)); }
});
Object.defineProperty(Nodo.prototype, "innerHTML", {
  get: function () { return this._html; },
  set: function (v) { this._html = String(v); documentStub._htmlPintado.push(String(v)); }
});
Nodo.prototype.getContext = function (tipo) {
  if (tipo !== "2d") return null;
  if (ctxNulo) return null;
  var self = this;
  if (self._ctx) return self._ctx;
  var ctx = {
    fillStyle: "#000000", strokeStyle: "#000000", font: "", lineWidth: 1,
    _textos: [], _rects: [], _trazos: [], _trazoActual: null,
    beginPath: function () { ctx._trazoActual = { color: ctx.strokeStyle, puntos: [] }; },
    moveTo: function (x, y) { if (ctx._trazoActual) ctx._trazoActual.puntos.push([x, y]); },
    lineTo: function (x, y) { if (ctx._trazoActual) ctx._trazoActual.puntos.push([x, y]); },
    stroke: function () { if (ctx._trazoActual) { ctx._trazos.push(ctx._trazoActual); ctx._trazoActual = null; } },
    fillRect: function (x, y, w, h) { ctx._rects.push({ x: x, y: y, w: w, h: h, color: ctx.fillStyle }); },
    /* un canvas de verdad borra sus pixeles: si el stub no borra lo que
       registro, un repintado acumula rotulos y el verificador no lo ve. */
    clearRect: function () { ctx._textos = []; ctx._rects = []; ctx._trazos = []; },
    strokeRect: function () {}, setLineDash: function () {},
    fillText: function (t, x, y) { ctx._textos.push({ t: String(t), x: x, y: y }); },
    createImageData: function (w, h) { return { width: w, height: h, data: new Uint8ClampedArray(w * h * 4) }; },
    putImageData: function () {}
  };
  self._ctx = ctx;
  return ctx;
};

var nodosPorId = {}, todos = [];

function censo() {
  nodosPorId = {}; todos = [];
  var re = /<([a-zA-Z][\w-]*)((?:[^>"]|"[^"]*")*)>/g, m;
  while ((m = re.exec(HTML)) !== null) {
    var tag = m[1], crudo = m[2];
    if (/^\/|^!/.test(tag)) continue;
    var attrs = {}, ar = /([\w:-]+)(?:="([^"]*)")?/g, a;
    while ((a = ar.exec(crudo)) !== null) {
      if (a[1] === "" || a[1].charAt(0) === "/") continue;
      attrs[a[1]] = a[2] !== undefined ? a[2] : "";
    }
    if (!attrs.id && attrs["data-t"] === undefined && attrs["data-preset"] === undefined) continue;
    var n = new Nodo(tag, attrs);
    todos.push(n);
    if (attrs.id) {
      if (nodosPorId[attrs.id]) falla("A1 · id duplicado en el HTML: " + attrs.id);
      nodosPorId[attrs.id] = n;
    }
  }
}

var documentStub = {
  readyState: "complete",
  documentElement: { lang: "" },
  _textosPintados: [],
  _htmlPintado: [],
  getElementById: function (id) { return nodosPorId[id] || null; },
  querySelectorAll: function (sel) {
    var out = [], i;
    if (/^[a-zA-Z][\w-]*$/.test(sel)) {
      for (i = 0; i < todos.length; i++) if (todos[i].tagName === sel.toUpperCase()) out.push(todos[i]);
      return out;
    }
    var clave = sel.replace(/^\[|\]$/g, "");
    for (i = 0; i < todos.length; i++) if (todos[i].attrs[clave] !== undefined) out.push(todos[i]);
    return out;
  },
  addEventListener: function () {}
};

function arranca(htmlNulo) {
  censo();
  documentStub._textosPintados = [];
  documentStub._htmlPintado = [];
  ctxNulo = !!htmlNulo;
  var sandbox = {
    document: documentStub, console: console, Math: Math, Number: Number,
    String: String, Array: Array, Object: Object, JSON: JSON,
    isNaN: isNaN, isFinite: isFinite, parseInt: parseInt, parseFloat: parseFloat,
    Float64Array: Float64Array, Uint8Array: Uint8Array, Uint8ClampedArray: Uint8ClampedArray,
    RangeError: RangeError, Error: Error, Infinity: Infinity, NaN: NaN, undefined: undefined
  };
  sandbox.window = sandbox;
  var ctx = vm.createContext(sandbox), res;
  try {
    vm.runInContext(MOTOR + "\n" + UI, ctx, { filename: "pagina.js", timeout: 30000 });
    res = { ctx: ctx, error: null };
  } catch (e) {
    res = { ctx: ctx, error: e };
  }
  /* el canvas nulo es un caso de A13, no un estado del verificador: si queda
     encendido, cualquier aserto posterior mide una pagina sin contexto. */
  ctxNulo = false;
  return res;
}

var r = arranca(false);
if (r.error) {
  console.error("RC 1 · la pagina no arranca: " + ((r.error && r.error.stack) || r.error));
  process.exit(1);
}
var T = r.ctx.T;
if (!T || typeof T.pintar !== "function") {
  console.error("RC 1 · la pagina arranco pero no expuso T (contrato del verificador)");
  process.exit(1);
}

function id(n) { return nodosPorId[n]; }
function porT(clave) {
  var l = documentStub.querySelectorAll("[data-t]");
  for (var i = 0; i < l.length; i++) if (l[i].attrs["data-t"] === clave) return l[i];
  return null;
}
function pon(nombre, v) { id(nombre).value = String(v); }
function presiona(clave) {
  var bs = documentStub.querySelectorAll("[data-preset]");
  for (var i = 0; i < bs.length; i++) {
    if (bs[i].attrs["data-preset"] === clave) {
      bs[i].dispara("click", { currentTarget: bs[i], target: bs[i] });
      return true;
    }
  }
  return false;
}
function limpiaCanvas() {
  ["mapa", "ruina"].forEach(function (cv) {
    var n = id(cv);
    if (n && n._ctx) { n._ctx._textos = []; n._ctx._rects = []; n._ctx._trazos = []; }
  });
}
function idioma(clave) {
  id("btn-idioma").dispara("click", { currentTarget: id("btn-idioma"), target: id("btn-idioma") });
  if (T.est.idioma !== clave) falla("A9 · pulsar el boton no lleva a idioma '" + clave + "'");
}
function celda(clave) {
  var etiqueta = T.TEXTO[T.est.idioma][clave];
  var re = /<th>([\s\S]*?)<\/th><td class="nv">([\s\S]*?)<\/td>/g, m;
  while ((m = re.exec(id("tabla").innerHTML)) !== null) {
    if (m[1].indexOf(etiqueta) >= 0) return m[2];
  }
  return null;
}

/* ---------- A1 · toda clave data-t existe en los dos idiomas ---------- */
(function () {
  var claves = documentStub.querySelectorAll("[data-t]");
  if (!claves.length) { falla("A1 · el HTML no tiene ninguna clave data-t"); return; }
  for (var i = 0; i < claves.length; i++) {
    var k = claves[i].attrs["data-t"];
    if (T.TEXTO.es[k] === undefined) falla("A1 · falta la traduccion ES de '" + k + "'");
    if (T.TEXTO.en[k] === undefined) falla("A1 · falta la traduccion EN de '" + k + "'");
  }
  var es = Object.keys(T.TEXTO.es), en = Object.keys(T.TEXTO.en);
  for (var j = 0; j < es.length; j++) if (T.TEXTO.en[es[j]] === undefined)
    falla("A1 · la clave '" + es[j] + "' existe en ES y no en EN");
  for (var l = 0; l < en.length; l++) if (T.TEXTO.es[en[l]] === undefined)
    falla("A1 · la clave '" + en[l] + "' existe en EN y no en ES");
})();

/* ---------- A2 · arranque: todo rotulo con texto, nada sin pintar ---------- */
(function () {
  var textos = documentStub.querySelectorAll("[data-t]");
  var vacios = [];
  for (var i = 0; i < textos.length; i++) if (!textos[i].textContent) vacios.push(textos[i].attrs["data-t"]);
  if (vacios.length) falla("A2 · elementos data-t sin texto: " + vacios.join(", "));
  var cuerpos = [id("v-cifra").textContent, id("v-frase").textContent,
                 id("tabla").innerHTML, id("identidad").innerHTML, id("pie").innerHTML];
  for (var k = 0; k < cuerpos.length; k++) {
    if (/undefined|NaN|\[object/.test(String(cuerpos[k])))
      falla("A2 · un cuerpo imprime un valor ausente: '" + String(cuerpos[k]).slice(0, 70) + "'");
  }
})();

/* ---------- A3 · la tabla tiene las 12 filas y ninguna sale como raya ---------- */
(function () {
  var html = id("tabla").innerHTML;
  var filas = (html.match(/<tr/g) || []).length;
  if (filas !== 12) falla("A3 · la tabla pinta " + filas + " filas, se declararon 12");
  if (html.indexOf("\u2014") >= 0) falla("A3 · la tabla imprime una raya: hay una medida que no existe");
})();

/* ---------- A4 · la tesis: signo y supervivencia son ejes independientes ---------- *
 * En los cuatro presets, el signo del valor esperado por intento NO depende de
 * m, y la ruina SI. Si alguien "arreglara" el veredicto mezclando las dos cosas,
 * esta asercion caeria. */
(function () {
  var casos = [
    { id: "al-filo", esperaPaga: true, esperaRuinaAlta: true },
    { id: "solido", esperaPaga: true, esperaRuinaAlta: false },
    { id: "bajo-umbral", esperaPaga: false, esperaRuinaAlta: false },
    { id: "una-bala", esperaPaga: true, esperaRuinaAlta: true }
  ];
  var frases = {};
  for (var i = 0; i < casos.length; i++) {
    if (!presiona(casos[i].id)) { falla("A4 · no hay preset '" + casos[i].id + "'"); continue; }
    var e = T.est.r;
    var paga = e.ev_intento > 0, alta = e.ruina >= 0.10;
    if (paga !== casos[i].esperaPaga)
      falla("A4 · preset '" + casos[i].id + "': paga=" + paga + " y se declaro " + casos[i].esperaPaga);
    if (alta !== casos[i].esperaRuinaAlta)
      falla("A4 · preset '" + casos[i].id + "': ruina alta=" + alta + " y se declaro " + casos[i].esperaRuinaAlta);
    frases[id("v-frase").textContent] = 1;
    /* el signo del valor esperado NO se mueve al mover m en el mismo precio */
    var base = T.medir(e.p, e.V, e.C, 1, 40);
    var tope = T.medir(e.p, e.V, e.C, 200, 40);
    if ((base.ev_intento > 0) !== (tope.ev_intento > 0))
      falla("A4 · el signo del valor esperado cambio con m en '" + casos[i].id + "'");
    if (!(tope.ruina < base.ruina))
      falla("A4 · la ruina no baja al subir m en '" + casos[i].id + "'");
  }
  if (Object.keys(frases).length < 3)
    falla("A4 · los cuatro presets producen " + Object.keys(frases).length + " veredictos distintos; se declararon 3");
  var clases = ["ok", "alerta", "malo"];
  var caja = id("veredicto");
  var lleva = false;
  for (var c = 0; c < clases.length; c++) if (caja.className.indexOf("veredicto " + clases[c]) >= 0) lleva = true;
  if (!lleva) falla("A4 · #veredicto no lleva clase 'veredicto ok|alerta|malo': '" + caja.className + "'");
})();

/* ---------- A5 · la frontera del mapa se mueve cuando cambia el precio ---------- *
 * La linea blanca de p_min es una propiedad del precio (C/V), no del intento.
 * Si estuviera clavada en x fijo, "donde estas en el mapa" seria un dibujo. */
(function () {
  function xFrontera(V, C, m) {
    ctxNulo = false;
    pon("pp", 300); pon("V", V); pon("C", C); pon("m", m || 5);
    limpiaCanvas();
    T.pintar();
    var cv = id("mapa");
    if (!cv._ctx) { falla("A5 · el canvas del mapa no se pinto"); return null; }
    var rects = cv._ctx._rects;
    for (var i = rects.length - 1; i >= 0; i--) {
      if (rects[i].w <= 2 && rects[i].h > 50 && rects[i].color === "#ffffff") return rects[i].x;
    }
    return null;
  }
  var a = xFrontera(100, 10);
  var b = xFrontera(100, 25);
  var c = xFrontera(100, 5);
  if (a === null || b === null || c === null) {
    falla("A5 · no se encontro la linea de p_min en el mapa (blanca, vertical)");
    return;
  }
  if (!(b > a && a > c))
    falla("A5 · la frontera no se mueve con C/V: C=5 -> " + c + " · C=10 -> " + a + " · C=25 -> " + b);
  var igual = xFrontera(100, 10, 120);
  if (igual !== a) falla("A5 · la frontera se movio al cambiar m: " + a + " -> " + igual);
})();

/* ---------- A6 · las dos curvas de ruina no son la misma curva ---------- */
(function () {
  pon("pp", 300); pon("V", 100); pon("C", 10); pon("m", 20);
  limpiaCanvas();
  T.pintar();
  var cv = id("ruina");
  var trazos = cv._ctx._trazos.filter(function (t) { return t.puntos.length > 50; });
  if (trazos.length < 2) {
    falla("A6 · el canvas de ruina pinto " + trazos.length + " curvas largas; se declararon 2");
    return;
  }
  var humana = null, frontera = null, i;
  for (i = 0; i < trazos.length; i++) {
    if (trazos[i].color === "#5fb3a1") humana = trazos[i];
    if (trazos[i].color === "#c62828") frontera = trazos[i];
  }
  if (!humana || !frontera) { falla("A6 · falta una de las dos curvas (color 5fb3a1 / c62828)"); return; }
  var distintos = 0;
  for (i = 0; i < Math.min(humana.puntos.length, frontera.puntos.length); i++) {
    if (Math.abs(humana.puntos[i][1] - frontera.puntos[i][1]) > 0.5) distintos++;
  }
  if (distintos < humana.puntos.length / 2)
    falla("A6 · las dos curvas son casi la misma (" + distintos + " de " + humana.puntos.length + " puntos distintos)");
})();

/* ---------- A7 · ningun rotulo del canvas se queda sin traducir ---------- *
 * Esta es la mutacion que la Pieza #1 vivio en vivo: texto del motor pintado en
 * espanol dentro de la vista EN. Aqui se mide en los dos idiomas. */
(function () {
  function letras(s) { return (s.match(/[A-Za-zÁÉÍÓÚáéíóúñÑ]{3,}/g) || []); }
  var problemas = [];
  function recoge(lg, caso) {
    var T2 = T.TEXTO[lg], permitido = {};
    Object.keys(T2).forEach(function (k) { permitido[T2[k]] = 1; });
    ["mapa", "ruina"].forEach(function (cv) {
      var textos = id(cv)._ctx._textos;
      for (var i = 0; i < textos.length; i++) {
        var t = textos[i].t;
        if (!letras(t).length) continue;
        if (!permitido[t]) problemas.push(lg + "/" + caso + " · " + cv + " · '" + t + "'");
      }
    });
  }
  ["es", "en"].forEach(function (lg) {
    if (T.est.idioma !== lg) idioma(lg);
    /* dos casos por idioma: el mapa pintable y el mapa fuera de rango. El
       segundo pinta un rotulo que el primero nunca pinta — y fue justo el que
       estaba en espanol dentro de la vista EN. */
    presiona("al-filo");
    limpiaCanvas();
    T.pintar();
    recoge(lg, "al-filo");
    pon("pp", 300); pon("V", 10); pon("C", 100); pon("m", 5);
    limpiaCanvas();
    T.pintar();
    recoge(lg, "fuera");
  });
  if (problemas.length) falla("A7 · rotulos de canvas sin traducir: " + problemas.join(" | "));
})();

/* ---------- A8 · ningun numero se imprime truncado ---------- *
 * El defecto real de la Pieza #1: 3.3356409519815204e-9 leido como "3.33".
 * Aqui: un p_min de 0.001 no puede salir como "0.00", y una ruina de 1e-9 no
 * puede salir como "0.0000". */
(function () {
  pon("pp", 300); pon("V", 1000); pon("C", 1); pon("m", 200);
  T.pintar();
  var v = celda("fila_p_min");
  if (v === null) { falla("A8 · no se encontro la fila de p_min en la tabla"); return; }
  if (!/0\.001/.test(v)) falla("A8 · p_min=0.001 se imprime como '" + v + "'");
  var ruina = T.est.r.ruina;
  if (!(ruina > 0 && ruina < 1e-30)) {
    falla("A8 · el caso de prueba ya no produce ruina diminuta (" + ruina + "); la asercion no mide nada");
    return;
  }
  var texto = celda("fila_ruina");
  if (!/e-/.test(String(texto))) falla("A8 · ruina " + ruina + " se imprime como '" + texto + "' en vez de notacion cientifica");
})();

/* ---------- A9 · el idioma cambia de verdad ---------- */
(function () {
  pon("pp", 105); pon("V", 100); pon("C", 10); pon("m", 5);
  T.pintar();
  if (T.est.idioma !== "es") idioma("es");
  var esTitulo = porT("titulo").textContent;
  idioma("en");
  var enTitulo = porT("titulo").textContent;
  if (esTitulo === enTitulo) falla("A9 · el titulo no cambia al cambiar de idioma");
  if (enTitulo !== T.TEXTO.en.titulo) falla("A9 · el titulo EN no es el declarado");
  if (documentStub.documentElement.lang !== "en") falla("A9 · <html lang> no sigue al idioma");
  if (id("v-frase").textContent !== T.TEXTO.en.veredicto_alerta)
    falla("A9 · el veredicto no se tradujo: '" + id("v-frase").textContent + "'");
  idioma("es");
})();

/* ---------- A10 · todo preset sobrevive al paso de su control ---------- */
(function () {
  var d = T.DISPOSICION;
  for (var i = 0; i < d.length; i++) {
    if (!presiona(d[i].id)) { falla("A10 · no hay preset '" + d[i].id + "'"); continue; }
    var leido = { pp: +id("pp").value, V: +id("V").value, C: +id("C").value, m: +id("m").value };
    ["pp", "V", "C", "m"].forEach(function (k) {
      if (leido[k] !== d[i][k])
        falla("A10 · preset '" + d[i].id + "': el control " + k + " quedo en " + leido[k] + " y se declaro " + d[i][k]);
    });
  }
})();

/* ---------- A11 · la identidad impresa cierra aritmeticamente ---------- *
 * El panel no cuenta una historia: imprime el producto. Se recalcula del texto. */
(function () {
  presiona("al-filo");
  var html = id("identidad").innerHTML;
  var m = /([\d.]+) · \(([\d.\-]+) [\u2212-] ([\d.]+)\) = <strong>([+\-]?[\d.]+)<\/strong>/.exec(html);
  if (!m) { falla("A11 · el panel de la identidad no imprime el producto con numeros: '" + html.slice(0, 90) + "'"); return; }
  var q = parseFloat(m[1]), V = parseFloat(m[2]), Cp = parseFloat(m[3]), impreso = parseFloat(m[4]);
  var producto = q * (V - Cp);
  if (Math.abs(producto - impreso) > 1e-3)
    falla("A11 · el producto impreso no cierra: " + q + " * (" + V + " - " + Cp + ") = " + producto + " y se imprime " + impreso);
  var motor = T.est.r.ev_politica;
  if (Math.abs(motor - impreso) > 1e-3)
    falla("A11 · lo impreso (" + impreso + ") no es el valor esperado del motor (" + motor + ")");
})();

/* ---------- A12 · el idioma del documento no secuestra los numeros ---------- */
(function () {
  pon("pp", 105); pon("V", 100); pon("C", 10); pon("m", 5);
  T.pintar();
  var a = id("tabla").innerHTML;
  T.pintar();
  var b = id("tabla").innerHTML;
  if (a !== b) falla("A12 · dos pintadas iguales dan tablas distintas: hay estado escondido");
  if (/,\d{3}\.\d/.test(a)) falla("A12 · la tabla imprime separador de miles en formato ajeno");
})();

/* ---------- A13 · un canvas sin contexto no tumba la pagina ---------- */
(function () {
  var r2 = arranca(true);
  if (r2.error) { falla("A13 · la pagina revienta cuando getContext devuelve null: " + r2.error.message); return; }
  /* arranca() vuelve a censar el DOM: cada corrida deja una generacion nueva de
     nodos. Sin un arranque bueno detras, los asertos siguientes mezclan las
     funciones de una generacion con los nodos de otra y el boton de idioma deja
     de responder — medido: A18 fallaba con est.idioma clavado en "es". */
  var r3 = arranca(false);
  if (r3.error) { falla("A13 · la pagina no vuelve a arrancar sin canvas nulo: " + r3.error.message); return; }
  T = r3.ctx.T;
})();

/* ---------- A14 · cero enlaces a repositorios privados ---------- */
(function () {
  var privados = HTML.match(/https?:\/\/[^"'\s]*(platino-labs|alexisromtz-lab\/platino)[^"'\s]*/g);
  if (privados) falla("A14 · la pagina enlaza un repositorio privado: " + privados.join(", "));
})();

/* ---------- A15 · el precio y el intento se pintan en controles distintos -- */
(function () {
  for (var i = 0; i < T.CONTROLES.length; i++) {
    var c = T.CONTROLES[i], n = id(c.id);
    if (!n) { falla("A15 · falta el control #" + c.id); continue; }
    if (n.attrs.type !== "range") falla("A15 · #" + c.id + " no es un range");
    if (+n.attrs.step !== c.step) falla("A15 · #" + c.id + " declara step=" + n.attrs.step + " y el contrato dice " + c.step);
    if (+n.attrs.min !== c.min || +n.attrs.max !== c.max)
      falla("A15 · #" + c.id + " va de " + n.attrs.min + " a " + n.attrs.max + " y el contrato dice " + c.min + ".." + c.max);
  }
})();

/* ---------- A16 · ninguna clave se declara dos veces dentro de un idioma ---- *
 * Este es el defecto que A7 no puede ver por construccion: si en el bloque EN
 * se declara `fuera_mapa` dos veces y la segunda copia esta en espanol, el mapa
 * EN contiene una cadena espanola y A7 la acepta, porque la cadena SI figura en
 * el diccionario EN — la que sobra la puso ahi. Medido el 12-Nov-2026: asi
 * estaba, y esta asercion es la que lo nombra. */
(function () {
  function bloque(idioma) {
    var abre = HTML.indexOf("\n  " + idioma + ": {");
    if (abre < 0) return null;
    /* el bloque de ES cierra con "  }," y el de EN con "};": los dos terminan. */
    var fines = [HTML.indexOf("\n  },", abre), HTML.indexOf("\n};", abre)].filter(function (x) { return x > abre; });
    if (!fines.length) return null;
    return HTML.slice(abre, Math.min.apply(null, fines));
  }
  ["es", "en"].forEach(function (lg) {
    var b = bloque(lg);
    if (b === null) { falla("A16 · no se encontro el bloque TEXTO." + lg); return; }
    var re = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:/gm, vistos = {}, m, repes = [];
    while ((m = re.exec(b)) !== null) {
      if (vistos[m[1]]) repes.push(m[1]);
      vistos[m[1]] = 1;
    }
    if (repes.length) falla("A16 · TEXTO." + lg + " declara dos veces: " + repes.join(", "));
  });
})();

/* ---------- A17 · la barra blanca de "estas aqui" cae en tu m ------------- *
 * El mapa tiene un cuadrado blanco en (p, m); esta grafica tiene una barra que
 * dice en que m estas. Una barra clavada en una x fija es un adorno: medido el
 * 12-Nov-2026 en el render, parecia estar fuera de su sitio. Aqui se comprueba
 * contra la curva real: el nudo de la curva que cae bajo la barra tiene indice m. */
(function () {
  var casos = [37, 5, 120];
  for (var k = 0; k < casos.length; k++) {
    pon("pp", 300); pon("V", 100); pon("C", 10); pon("m", casos[k]);
    limpiaCanvas();
    T.pintar();
    var ctx = id("ruina")._ctx;
    var barra = null, i;
    for (i = ctx._rects.length - 1; i >= 0; i--) {
      if (ctx._rects[i].color === "#ffffff" && ctx._rects[i].w <= 4 && ctx._rects[i].h > 50) barra = ctx._rects[i];
    }
    if (!barra) { falla("A17 · no se encontro la barra blanca de m en la grafica de ruina"); continue; }
    var centro = barra.x + barra.w / 2, curva = null;
    for (i = 0; i < ctx._trazos.length; i++) {
      if (ctx._trazos[i].color === "#5fb3a1" && ctx._trazos[i].puntos.length > 50) curva = ctx._trazos[i];
    }
    if (!curva) { falla("A17 · no se encontro la curva verde para contrastar la barra"); continue; }
    var mejor = -1, dist = Infinity;
    for (i = 0; i < curva.puntos.length; i++) {
      var d = Math.abs(curva.puntos[i][0] - centro);
      if (d < dist) { dist = d; mejor = i; }
    }
    /* los nudos de la curva son m = 1..M_MAX_EJE, en orden */
    var mNudo = mejor + 1;
    if (mNudo !== casos[k])
      falla("A17 · con m=" + casos[k] + " la barra cae sobre el nudo de m=" + mNudo);
    if (dist > 2)
      falla("A17 · con m=" + casos[k] + " la barra no toca la curva (distancia " + dist.toFixed(1) + " px)");
  }
})();

/* ---------- A18 · cambiar de idioma no deja el rotulo viejo debajo ------- *
 * Defecto real del 12-Nov-2026, encontrado mirando el render y no el RC: los
 * pintores no limpiaban el lienzo, asi que al pasar ES -> EN el rotulo ingles
 * se dibujaba ENCIMA del espanol y se leian los dos. El stub no lo veia porque
 * A7 limpia a mano antes de medir; con clearRect real, se ve. */
(function () {
  var lg0 = T.est.idioma;
  if (lg0 !== "es") idioma("es");
  id("mapa")._ctx = null; id("ruina")._ctx = null;   /* lienzos nuevos, sin historia */
  T.pintar();
  if (T.est.idioma !== "en") idioma("en");           /* pintar sin limpiar a mano */
  var T2 = T.TEXTO.en, permitido = {}, sobras = [];
  Object.keys(T2).forEach(function (k) { permitido[T2[k]] = 1; });
  ["mapa", "ruina"].forEach(function (cv) {
    var textos = id(cv)._ctx._textos;
    for (var i = 0; i < textos.length; i++) {
      var t = textos[i].t;
      if (!/[A-Za-zÁÉÍÓÚáéíóúñÑ]{3,}/.test(t)) continue;
      if (!permitido[t]) sobras.push(cv + " · '" + t + "'");
    }
  });
  if (sobras.length) falla("A18 · tras cambiar a EN quedan rotulos viejos en el lienzo: " + sobras.join(" | "));
})();

if (fallos.length) {
  console.error("RC 1 · la pagina no se comporta (" + fallos.length + " fallos)");
  fallos.forEach(function (f) { console.error("  " + f); });
  process.exit(1);
}
console.log("UI OK · 18 aserciones sobre la pagina real · 0 fallos");
console.log("      A1 rotulos bilingues · A2 arranque · A3 tabla 12 filas · A4 tesis 2x2");
console.log("      A5 frontera movil · A6 curvas distintas · A7 canvas traducido · A8 sin truncar");
console.log("      A9 idioma · A10 presets · A11 identidad · A12 determinismo · A13 sin contexto");
console.log("      A14 cero enlaces privados · A15 controles · A16 claves sin repetir");
console.log("      A17 la barra de m cae en tu m · A18 el lienzo se limpia al repintar");
