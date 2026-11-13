#!/usr/bin/env node
/* Ejecuta la pagina real contra un DOM simulado.
 *
 * verificar_paridad.py prueba que el MOTOR no derivo. Este verificador prueba
 * que la PAGINA que lo envuelve hace lo que dice: que las cuatro celdas no son
 * la misma imagen, que el idioma cambia de verdad, que las cifras se imprimen
 * enteras y que un canvas sin contexto no la tumba.
 *
 * RC 0 = la pagina se comporta. RC 1 = no. RC 3 = falta index.html.
 */
"use strict";

var fs = require("fs");
var path = require("path");
var vm = require("vm");

var DIR = __dirname;
var RUTA = path.join(DIR, "index.html");
if (!fs.existsSync(RUTA)) {
  console.error("RC 3 · falta " + RUTA);
  process.exit(3);
}
var HTML = fs.readFileSync(RUTA, "utf8");

var fallos = [];
function falla(m) { fallos.push(m); }

/* ---------- extraccion de los dos bloques <script> ---------- */
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
if (!MOTOR) { console.error("RC 1 · la pagina no tiene <script id=\"motor\">"); process.exit(1); }
if (!UI) { console.error("RC 1 · la pagina no tiene el script de interfaz"); process.exit(1); }

/* ---------- DOM simulado ---------- */
function Nodo(tag, attrs) {
  this.tagName = tag.toUpperCase();
  this.attrs = attrs || {};
  this.id = this.attrs.id || "";
  this._texto = "";
  this._html = "";
  this.className = "";
  this.style = {};
  this.oyentes = {};
  this.width = parseInt(this.attrs.width || "0", 10);
  this.height = parseInt(this.attrs.height || "0", 10);
  this._value = this.ajustaPaso(this.attrs.value !== undefined ? this.attrs.value
    : (this.tagName === "SELECT" ? "64" : ""));
}
/* El navegador no guarda el value que se le asigna: lo ajusta al paso declarado.
   Sin esta regla el stub aceptaba 0.25 en un control step=0.02 y el verificador
   daba RC 0 sobre una pagina que en Chrome encendia 0.26. */
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
  set: function (v) { this._texto = String(v); }
});
Object.defineProperty(Nodo.prototype, "innerHTML", {
  get: function () { return this._html; },
  set: function (v) { this._html = String(v); }
});
Nodo.prototype.getContext = function (tipo) {
  if (tipo !== "2d") return null;
  if (ctxNulo) return null;
  var self = this;
  var ctx = {
    _pintados: 0,
    _ops: 0,
    _hash: "",
    _textos: [],
    createImageData: function (w, h) {
      return { width: w, height: h, data: new Uint8ClampedArray(w * h * 4) };
    },
    putImageData: function (img) {
      self._ultimo = img;
      ctx._pintados++;
      var s = 2166136261;
      var d = img.data;
      for (var i = 0; i < d.length; i++) { s ^= d[i]; s = (s * 16777619) >>> 0; }
      ctx._hash = s.toString(16) + ":" + img.width + "x" + img.height;
    },
    clearRect: function () { ctx._ops++; }, beginPath: function () { ctx._ops++; },
    moveTo: function () { ctx._ops++; }, lineTo: function () { ctx._ops++; },
    stroke: function () { ctx._ops++; }, fillText: function (t) { ctx._textos.push(String(t)); ctx._ops++; },
    setLineDash: function () { ctx._ops++; }, strokeRect: function () { ctx._ops++; }
  };
  self._ctx = ctx;
  return ctx;
};

var ctxNulo = false;
var nodosPorId = {}, todos = [];

function censo() {
  nodosPorId = {}; todos = [];
  var re = /<([a-zA-Z][\w-]*)((?:[^>"]|"[^"]*")*)>/g, m;
  while ((m = re.exec(HTML)) !== null) {
    var tag = m[1], crudo = m[2];
    if (/^<\/|^!/.test(tag)) continue;
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
  getElementById: function (id) { return nodosPorId[id] || null; },
  querySelectorAll: function (sel) {
    var clave = sel.replace(/^\[|\]$/g, "");
    var out = [];
    for (var i = 0; i < todos.length; i++) {
      if (todos[i].attrs[clave] !== undefined) out.push(todos[i]);
    }
    return out;
  },
  addEventListener: function () {}
};

/* ---------- ejecucion ---------- */
function arranca(htmlNulo) {
  censo();
  ctxNulo = !!htmlNulo;
  var sandbox = {
    document: documentStub,
    console: console,
    Math: Math,
    Number: Number,
    String: String,
    Array: Array,
    Object: Object,
    JSON: JSON,
    isNaN: isNaN,
    isFinite: isFinite,
    parseInt: parseInt,
    parseFloat: parseFloat,
    Float64Array: Float64Array,
    Uint8Array: Uint8Array,
    Uint8ClampedArray: Uint8ClampedArray,
    RangeError: RangeError,
    Error: Error,
    Infinity: Infinity,
    NaN: NaN,
    undefined: undefined
  };
  sandbox.window = sandbox;
  var ctx = vm.createContext(sandbox);
  try {
    vm.runInContext(MOTOR + "\n" + UI, ctx, { filename: "pagina.js", timeout: 20000 });
  } catch (e) {
    return { ctx: ctx, error: e };
  }
  return { ctx: ctx, error: null };
}

var r = arranca(false);
if (r.error) {
  console.error("RC 1 · la pagina no arranca: " + (r.error && r.error.stack || r.error));
  process.exit(1);
}
var T = r.ctx.T;
if (!T || typeof T.pintar !== "function") {
  console.error("RC 1 · la pagina arranco pero no expuso T (contrato del verificador)");
  process.exit(1);
}

function id(nombre) { return nodosPorId[nombre]; }
function texto(nombre) { var n = id(nombre); return n ? n.textContent : null; }
function entero(nombre) {
  var t = texto(nombre);
  var m = t === null ? null : /^(\d+) de (\d+)$/.exec(t);
  return m ? { viol: parseInt(m[1], 10), total: parseInt(m[2], 10) } : null;
}
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

/* ---------- A1 · toda clave data-t existe en los dos idiomas ---------- */
(function () {
  var claves = documentStub.querySelectorAll("[data-t]");
  if (!claves.length) { falla("A1 · el HTML no tiene ninguna clave data-t"); return; }
  for (var i = 0; i < claves.length; i++) {
    var k = claves[i].attrs["data-t"];
    if (T.TEXTO.es[k] === undefined) falla("A1 · falta la traduccion ES de '" + k + "'");
    if (T.TEXTO.en[k] === undefined) falla("A1 · falta la traduccion EN de '" + k + "'");
  }
  /* Los dos diccionarios tienen que tener exactamente las mismas claves: una
   * clave renombrada en un solo idioma no la ve ningun data-t, y su texto se
   * imprimiria como "undefined" (es lo que paso en la Pieza #1 con el motivo
   * del motor, en espanol dentro de la vista EN). */
  var es = Object.keys(T.TEXTO.es), en = Object.keys(T.TEXTO.en);
  for (var j = 0; j < es.length; j++) {
    if (T.TEXTO.en[es[j]] === undefined) falla("A1 · la clave '" + es[j] + "' existe en ES y no en EN");
  }
  for (var l = 0; l < en.length; l++) {
    if (T.TEXTO.es[en[l]] === undefined) falla("A1 · la clave '" + en[l] + "' existe en EN y no en ES");
  }
})();

/* ---------- A2 · arranque: todos los sellos y pies escritos ---------- */
(function () {
  var ids = ["sello-local-honesto", "sello-local-contaminado", "sello-const-honesto",
             "sello-const-contaminado", "pie-local-honesto", "pie-local-contaminado",
             "pie-const-honesto", "pie-const-contaminado"];
  for (var i = 0; i < ids.length; i++) {
    var n = id(ids[i]);
    if (!n) { falla("A2 · falta el elemento #" + ids[i] + " en el HTML"); continue; }
    if (!n.textContent) falla("A2 · #" + ids[i] + " quedo vacio tras pintar");
  }
  var textos = documentStub.querySelectorAll("[data-t]");
  var vistos = 0;
  for (var k = 0; k < textos.length; k++) {
    if (textos[k].textContent) vistos++;
  }
  if (vistos !== textos.length) {
    falla("A2 · " + (textos.length - vistos) + " elementos data-t sin texto");
  }
  var conId = ["sello-local-honesto", "sello-local-contaminado", "sello-const-honesto",
               "sello-const-contaminado", "pie-local-honesto", "pie-local-contaminado",
               "pie-const-honesto", "pie-const-contaminado", "tabla-medidas", "pie-comando"];
  for (var q = 0; q < conId.length; q++) {
    var nq = id(conId[q]);
    if (!nq) continue;
    var s = nq === id("tabla-medidas") ? nq.innerHTML : nq.textContent;
    if (/undefined|NaN|\[object/.test(String(s))) {
      falla("A2 · #" + conId[q] + " imprime un valor ausente: '" + String(s).slice(0, 60) + "'");
    }
  }
})();

/* ---------- A3 · estilo de los sellos declarado ---------- */
(function () {
  var ids = ["sello-local-honesto", "sello-local-contaminado", "sello-const-honesto", "sello-const-contaminado"];
  for (var i = 0; i < ids.length; i++) {
    var n = id(ids[i]);
    if (!n) continue;
    if (!/sello (ok|no|nd)/.test(n.className)) {
      falla("A3 · #" + ids[i] + " no lleva clase 'sello ok|no|nd': '" + n.className + "'");
    }
  }
})();

/* ---------- A4 · delta = 0: las dos columnas son el mismo campo ---------- */
(function () {
  if (!presiona("honesto")) { falla("A4 · no hay preset 'honesto'"); return; }
  var a = entero("pie-local-honesto"), b = entero("pie-local-contaminado");
  var c = entero("pie-const-honesto"), d = entero("pie-const-contaminado");
  if (!a || !b || !c || !d) { falla("A4 · pies ilegibles"); return; }
  if (a.viol !== b.viol) falla("A4 · con delta=0 la columna local no coincide consigo misma: " + a.viol + " vs " + b.viol);
  if (c.viol !== d.viol) falla("A4 · con delta=0 la columna constante no coincide consigo misma: " + c.viol + " vs " + d.viol);
  if (a.viol !== 0) falla("A4 · el campo honesto viola su propio piso en " + a.viol + " nodos");
  if (c.viol !== 0) falla("A4 · el campo honesto viola eps=tau_max en " + c.viol + " nodos");
})();

/* ---------- A5 · la tesis: local ve, constante no ---------- */
(function () {
  if (!presiona("ciego")) { falla("A5 · no hay preset 'ciego'"); return; }
  var loc = entero("pie-local-contaminado"), cons = entero("pie-const-contaminado");
  if (!loc || !cons) { falla("A5 · pies ilegibles"); return; }
  if (!(loc.viol > 0)) falla("A5 · la compuerta local NO ve la contaminacion delta=0.5 (0 violaciones)");
  if (cons.viol !== 0) falla("A5 · la compuerta constante deberia ser ciega a delta=0.5 y viola en " + cons.viol);
  var hon = entero("pie-const-honesto");
  if (hon && hon.viol !== 0) falla("A5 · con eps=tau_max el campo honesto no deberia violar");
})();

/* ---------- A6 · falsos positivos: bajar eps ensucia el campo honesto ---------- */
(function () {
  if (!presiona("falso_rojo")) { falla("A6 · no hay preset 'falso_rojo'"); return; }
  var hon = entero("pie-const-honesto");
  if (!hon) { falla("A6 · pie ilegible"); return; }
  if (!(hon.viol > 0)) falla("A6 · el preset de falso rojo ya no enciende nodos honestos: la compuerta constante no muestra su segundo modo de fallo");
})();

/* ---------- A7 · i18n: cambia de verdad y no deja restos ---------- */
(function () {
  var claves = documentStub.querySelectorAll("[data-t]");
  var btn = id("btn-idioma");
  if (!btn) { falla("A7 · falta #btn-idioma"); return; }
  var antes = btn.textContent;
  btn.dispara("click", { currentTarget: btn, target: btn });
  if (documentStub.documentElement.lang !== "en") falla("A7 · el toggle no puso <html lang=en>");
  if (btn.textContent === antes) falla("A7 · el boton de idioma no cambia de etiqueta al pasar a EN");
  for (var i = 0; i < claves.length; i++) {
    var k = claves[i].attrs["data-t"];
    if (claves[i].textContent !== T.TEXTO.en[k]) {
      falla("A7 · EN sin pintar en '" + k + "': quedo '" + String(claves[i].textContent).slice(0, 48) + "'");
    }
  }
  var sellos = ["sello-local-honesto", "sello-local-contaminado", "sello-const-honesto", "sello-const-contaminado"];
  var vocab = [T.TEXTO.en.est_conserva, T.TEXTO.en.est_viola, T.TEXTO.en.est_no_medido];
  for (var s1 = 0; s1 < sellos.length; s1++) {
    var t1 = texto(sellos[s1]);
    if (vocab.indexOf(t1) < 0) falla("A7 · sello en EN fuera de vocabulario: '" + t1 + "' en #" + sellos[s1]);
  }
  var pies = ["pie-local-honesto", "pie-local-contaminado", "pie-const-honesto", "pie-const-contaminado"];
  var rePie = new RegExp("^\\d+ " + T.TEXTO.en.de + " \\d+$");
  for (var s2 = 0; s2 < pies.length; s2++) {
    if (!rePie.test(String(texto(pies[s2])))) {
      falla("A7 · pie en EN con formato ES: '" + texto(pies[s2]) + "' en #" + pies[s2]);
    }
  }
  btn.dispara("click", { currentTarget: btn, target: btn });
  if (documentStub.documentElement.lang !== "es") falla("A7 · el toggle no volvio a <html lang=es>");
  for (var j = 0; j < claves.length; j++) {
    var k2 = claves[j].attrs["data-t"];
    if (claves[j].textContent !== T.TEXTO.es[k2]) {
      falla("A7 · ES sin restaurar en '" + k2 + "'");
    }
  }
  if (btn.textContent !== antes) falla("A7 · el boton volvio a ES pero su etiqueta no es la inicial");
})();

/* ---------- A8 · cifras crudas: nada de notacion cientifica truncada ---------- */
(function () {
  var d = id("ctl-delta");
  if (!d) { falla("A8 · falta #ctl-delta"); return; }
  var casos = ["0.34", "0.02", "1.2"];
  for (var i = 0; i < casos.length; i++) {
    d.value = casos[i];
    d.dispara("input", { currentTarget: d, target: d });
    var impreso = texto("val-delta");
    if (impreso !== casos[i]) {
      falla("A8 · el control imprime '" + impreso + "' donde se movio '" + casos[i] + "'");
    }
  }
  var e = id("ctl-eps");
  if (e) {
    e.value = "0.35";
    e.dispara("input", { currentTarget: e, target: e });
    if (texto("val-eps") !== "0.35") falla("A8 · val-eps imprime '" + texto("val-eps") + "' en vez de 0.35");
  }
})();

/* ---------- A9 · las cuatro celdas no son la misma imagen ---------- */
(function () {
  presiona("ciego");
  var cs = ["mapa-local-honesto", "mapa-local-contaminado", "mapa-const-honesto", "mapa-const-contaminado"];
  var hashes = [], faltan = [];
  for (var i = 0; i < cs.length; i++) {
    var n = id(cs[i]);
    if (!n || !n._ctx || !n._ctx._hash) { faltan.push(cs[i]); continue; }
    hashes.push(n._ctx._hash);
  }
  if (faltan.length) { falla("A9 · canvas sin pintar: " + faltan.join(", ")); return; }
  var distintos = {};
  for (var j = 0; j < hashes.length; j++) distintos[hashes[j]] = 1;
  if (Object.keys(distintos).length !== 4) {
    falla("A9 · las cuatro celdas producen " + Object.keys(distintos).length +
          " imagenes distintas; el campo contaminado no se distingue del honesto");
  }
  var perfil = id("perfil");
  if (!perfil || !perfil._ctx || perfil._ctx._ops < 10) falla("A9 · el perfil no se pinto");
})();

/* ---------- A10 · tabla autoconsistente y completa ---------- */
(function () {
  var tb = id("tabla-medidas");
  if (!tb) { falla("A10 · falta #tabla-medidas"); return; }
  var filas = tb.innerHTML.split("<tr>").length - 1;
  if (filas < 12) falla("A10 · la tabla de medidas tiene " + filas + " filas, se esperaban >= 12");
  if (/<td[^>]*><\/td>/.test(tb.innerHTML)) falla("A10 · la tabla tiene celdas vacias");
  var c = T.calcular();
  if (Math.abs(c.perfil.tau_max_por_N2 - c.perfil.tau_max * c.N * c.N) > 1e-6 * Math.abs(c.perfil.tau_max_por_N2)) {
    falla("A10 · tau_max*N^2 no cuadra con tau_max*N^2");
  }
  if (!(c.nMask > 0)) falla("A10 · la mascara esta vacia: la pagina no mediria nada");
})();

/* ---------- A11 · un canvas sin contexto no tumba la pagina ---------- */
(function () {
  var r2 = arranca(true);
  if (r2.error) falla("A11 · sin contexto 2D la pagina revienta: " + r2.error.message);
})();

/* ---------- A12 · cero enlaces a repos privados, comando reproducible ---------- */
(function () {
  var prohibido = /href="[^"]*platino-labs[^"]*"/i;
  if (prohibido.test(HTML)) falla("A12 · la pagina enlaza a platino-labs (repo privado): 404 garantizado");
  var pie = texto("pie-comando");
  if (!pie || !/piso_de_deteccion\.py/.test(pie)) {
    falla("A12 · el pie no publica el comando reproducible del oraculo");
  }
})();

/* ---------- A13 · cada preset sobrevive el viaje por su control ---------- */
(function () {
  var r3 = arranca(false);
  if (r3.error) { falla("A13 · la pagina no arranca en limpio: " + r3.error.message); return; }
  var T3 = r3.ctx.T, disp = T3 && T3.DISPOSICION;
  if (!disp) { falla("A13 · la pagina no expone DISPOSICION (contrato del verificador)"); return; }
  var mapa = { delta: "ctl-delta", margen: "ctl-margen", eps: "ctl-eps" };
  var claves = Object.keys(disp);
  for (var i = 0; i < claves.length; i++) {
    var k = claves[i];
    if (!presiona(k)) { falla("A13 · el preset '" + k + "' no tiene boton"); continue; }
    for (var campo in mapa) {
      var querido = disp[k][campo];
      if (querido === undefined) continue;
      var c = id(mapa[campo]);
      if (!c) { falla("A13 · falta #" + mapa[campo]); continue; }
      var puesto = parseFloat(c.value);
      if (Math.abs(puesto - querido) > 1e-12) {
        falla("A13 · el preset '" + k + "' pide " + campo + "=" + querido + " y el control lo deja en " +
              puesto + " (min=" + c.attrs.min + " max=" + c.attrs.max + " step=" + c.attrs.step + "): el navegador redondea al paso");
      }
      var rotulo = texto("val-" + campo);
      if (rotulo !== String(querido)) {
        falla("A13 · el preset '" + k + "' deja el rotulo val-" + campo + " en '" + rotulo + "', no en " + querido);
      }
    }
  }
})();

/* ---------- A14 · todo texto visible que no sea cifra pasa por el diccionario ---------- */
(function () {
  var r4 = arranca(false);
  if (r4.error) { falla("A14 · la pagina no arranca en limpio: " + r4.error.message); return; }
  var T4 = r4.ctx.T;
  /* una etiqueta lleva prosa; "1e-3" y "127.80" no. Se exige una corrida de tres letras
     latinas para no confundir la notacion cientifica con texto que deba traducirse. */
  var PROSA = /[a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]{3,}/i;
  function enDiccionario(s, valores) {
    for (var q = 0; q < valores.length; q++) { if (valores[q].indexOf(s) >= 0) return true; }
    return false;
  }
  var idiomas = ["es", "en"];
  for (var i = 0; i < idiomas.length; i++) {
    if (T4.est.idioma !== idiomas[i]) {
      if (!id("btn-idioma")) { falla("A14 · falta #btn-idioma"); return; }
      id("btn-idioma").dispara("click", { currentTarget: id("btn-idioma"), target: id("btn-idioma") });
    }
    if (T4.est.idioma !== idiomas[i]) { falla("A14 · no se pudo pasar a " + idiomas[i]); return; }
    presiona("honesto");
    var dicc = T4.TEXTO[idiomas[i]] || {};
    var valores = Object.keys(dicc).map(function (kk) { return String(dicc[kk]); });

    var p = id("perfil");
    if (!p || !p._ctx) { falla("A14 · el perfil no se pinto en " + idiomas[i]); return; }
    var pintados = p._ctx._textos || [];
    for (var j = 0; j < pintados.length; j++) {
      var s1 = pintados[j];
      if (!PROSA.test(s1)) continue;
      if (!enDiccionario(s1, valores)) {
        falla("A14 · el canvas pinta '" + s1 + "' con idioma " + idiomas[i] +
              " y esa cadena no esta en el diccionario: no cambia al cambiar de idioma");
      }
    }

    var tb = id("tabla-medidas");
    if (!tb) { falla("A14 · falta #tabla-medidas"); continue; }
    var celdas = tb.innerHTML.match(/<td[^>]*>([\s\S]*?)<\/td>/g) || [];
    for (var j2 = 0; j2 < celdas.length; j2++) {
      var s2 = celdas[j2].replace(/<[^>]*>/g, "");
      if (!PROSA.test(s2)) continue;
      if (!enDiccionario(s2, valores)) {
        falla("A14 · la tabla imprime '" + s2 + "' con idioma " + idiomas[i] +
              " y esa etiqueta no esta en el diccionario: no cambia al cambiar de idioma");
      }
    }
  }
})();

/* ---------- resultado ---------- */
if (fallos.length) {
  console.error("RC 1 · la pagina no se comporta como declara (" + fallos.length + " defectos)");
  for (var i = 0; i < fallos.length; i++) console.error("  · " + fallos[i]);
  process.exit(1);
}
console.log("UI OK · 14 comprobaciones · la pagina mide, traduce y no enlaza al repo privado");
process.exit(0);
