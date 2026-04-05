# Frontend Integration - Cambios necesarios en RegularidadNav.html

## 1. Añadir campo de clave de regata en Setup (después de línea 250)

Después de:
```html
<div class="s-sl">Nombre del barco</div>
<div class="s-iw"><input id="iBoat" type="text" placeholder="AISHTERU" maxlength="20"></div>
```

Añadir:
```html
<div class="s-sl">Clave de regata (opcional)</div>
<div class="s-iw"><input id="iKey" type="text" placeholder="ABC12345" maxlength="8" style="text-transform:uppercase"></div>
```

## 2. Añadir bloque API al inicio del script (después de `var G = {...}` ~línea 482)

```javascript
// === BACKEND API INTEGRATION ===
var API_BASE = ''; // Set to 'https://regularidadnav.elena-agents.com' when deployed
var API_KEY = '';
var API_BARCO_ID = null;
var API_WS = null;
var API_POS_INTERVAL = null;

function apiCall(method, path, body) {
  if (!API_KEY) return Promise.resolve(null);
  var url = API_BASE + '/api/regatas/' + API_KEY + path;
  var opts = { method: method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  return fetch(url, opts).then(function(r) { return r.ok ? r.json() : null }).catch(function() { return null });
}

function apiConnect() {
  if (!API_KEY || API_WS) return;
  var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  var wsUrl = API_BASE ? API_BASE.replace(/^http/, 'ws') + '/ws/' + API_KEY : proto + '//' + location.host + '/ws/' + API_KEY;
  API_WS = new WebSocket(wsUrl);
  API_WS.onclose = function() { API_WS = null; setTimeout(apiConnect, 5000) };
  API_WS.onmessage = function(e) {
    try {
      var msg = JSON.parse(e.data);
      // Can use msg.tipo to update UI with other boats' positions
      console.log('[WS]', msg);
    } catch(err) {}
  };
}

function apiSendPos() {
  if (!API_KEY || !API_BARCO_ID || !G.lat) return;
  apiCall('POST', '/barcos/' + API_BARCO_ID + '/posicion', {
    lat: G.lat, lng: G.lng, cog: G.cog, speed_kn: G.gspd
  });
}

function apiSendPaso(balizaOrden, timestampReal) {
  if (!API_KEY || !API_BARCO_ID) return;
  apiCall('POST', '/barcos/' + API_BARCO_ID + '/paso', {
    baliza_orden: balizaOrden,
    timestamp_real: timestampReal,
    lat: G.lat, lng: G.lng,
    registrado_por: 'manual'
  });
}
// === END API ===
```

## 3. Modificar `goPrestart()` (línea 533) para inscribir barco

Reemplazar la función `goPrestart` con:
```javascript
function goPrestart(){
  var v=el('iBoat').value.trim();
  if(!v){el('iBoat').style.borderColor='var(--r)';el('iBoat').focus();setTimeout(function(){el('iBoat').style.borderColor=''},1800);return}
  if(route.length<2){alert('Mínimo 2 balizas');return}
  G.boat=v.toUpperCase();G.wps=buildWPs();
  el('psName').textContent=G.boat;el('psSpd').textContent=G.spd;
  el('psSal').textContent=route[0].n;el('psCoord').textContent=route[0].lat.toFixed(4)+'°N · '+route[0].lng.toFixed(4)+'°E';

  // API: register boat if key provided
  API_KEY = (el('iKey').value.trim() || '').toUpperCase();
  if (API_KEY) {
    apiCall('POST', '/barcos', { nombre: G.boat, velocidad_declarada: G.spd }).then(function(r) {
      if (r && r.id) { API_BARCO_ID = r.id; apiConnect(); }
    });
  }

  startGPS();go(2);
}
```

## 4. Modificar `startRace()` (línea 560) para registrar salida y enviar posiciones

Añadir al final de `startRace()`, justo antes de `go(3)`:
```javascript
  // API: register start and begin position tracking
  if (API_KEY && API_BARCO_ID) {
    apiCall('POST', '/barcos/' + API_BARCO_ID + '/salida');
    if (API_POS_INTERVAL) clearInterval(API_POS_INTERVAL);
    API_POS_INTERVAL = setInterval(apiSendPos, 10000);
  }
```

## 5. Modificar `regWP()` (línea 678) para enviar paso al backend

Añadir después de `wp.ok=true;wp.ts=G.secs;wp.pen=pen;G.pen+=pen;G.nwp++;`:
```javascript
  // API: send checkpoint
  apiSendPaso(G.nwp - 1, G.secs);
```

## 6. Modificar `resetAll()` (línea 782) para limpiar API

Añadir al inicio de `resetAll()`:
```javascript
  if (API_POS_INTERVAL) { clearInterval(API_POS_INTERVAL); API_POS_INTERVAL = null; }
  if (API_WS) { API_WS.close(); API_WS = null; }
  API_KEY = ''; API_BARCO_ID = null;
```

---

Estos cambios son **aditivos** y no rompen la funcionalidad offline existente.
Si no se introduce clave de regata, la app funciona exactamente igual que antes.
