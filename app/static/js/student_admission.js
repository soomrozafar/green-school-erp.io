(function(){
  const $=id=>document.getElementById(id);
  let studentMap, parentMap, studentMarker, parentMarker;
  function initMap(elId, latId, lngId, lat=24.8607, lng=67.0011){
    if(!window.L || !$(elId)) return null;
    const la=parseFloat($(latId)?.value)||lat, lo=parseFloat($(lngId)?.value)||lng;
    const map=L.map(elId).setView([la,lo], $(latId)?.value?15:11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'}).addTo(map);
    let marker=null; if($(latId)?.value && $(lngId)?.value) marker=L.marker([la,lo]).addTo(map);
    map.on('click',e=>{ if(marker) marker.setLatLng(e.latlng); else marker=L.marker(e.latlng).addTo(map); $(latId).value=e.latlng.lat.toFixed(7); $(lngId).value=e.latlng.lng.toFixed(7); });
    return map;
  }
  studentMap=initMap('studentMap','latitude','longitude'); parentMap=initMap('parentMap','parentLatitude','parentLongitude');
  function drawFamily(children, parent){
    const box=$('familyTree'); if(!box) return;
    box.classList.remove('empty-family'); box.innerHTML='<div class="family-root"><i class="bi bi-person-heart"></i><strong>'+escapeHtml(parent.name)+'</strong><small>'+escapeHtml(parent.mobile||parent.phone||parent.email||'')+'</small></div><div class="family-line"></div><div class="family-children">'+(children.length?children.map(c=>'<a class="family-child" href="/students/'+c.id+'"><i class="bi bi-mortarboard"></i><strong>'+escapeHtml(c.name)+'</strong><small>'+escapeHtml(c.code)+' · '+escapeHtml(c.class)+'</small></a>').join(''):'<span class="text-muted">No children linked yet.</span>')+'</div>';
  }
  function escapeHtml(x){return String(x||'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
  async function geocode(address, latId, lngId, map){ if(!address) return; try{ const r=await fetch('https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q='+encodeURIComponent(address)); const d=await r.json(); if(!d.length){alert('Address location not found. You can click the map manually.');return;} const lat=+d[0].lat,lon=+d[0].lon; $(latId).value=lat.toFixed(7); $(lngId).value=lon.toFixed(7); if(map){map.setView([lat,lon],16);L.marker([lat,lon]).addTo(map);} }catch(e){alert('Map lookup is temporarily unavailable. Please select the location manually.');} }
  $('locateStudent')?.addEventListener('click',()=>geocode($('studentAddress').value,'latitude','longitude',studentMap));
  $('locateParent')?.addEventListener('click',()=>geocode($('parentAddress').value,'parentLatitude','parentLongitude',parentMap));
  $('lookupGuardian')?.addEventListener('click',async()=>{
    const q=$('guardianLookup').value.trim(); if(!q) return;
    const r=await fetch('/students/parent-lookup?q='+encodeURIComponent(q)); const d=await r.json();
    if(!d.found){$('familyTree').innerHTML='<span class="text-muted">No guardian found. New guardian details can be entered below.</span>';return;}
    $('parentSelect').value=d.id; $('parentName').value=d.name; $('parentRelation').value=d.relation; $('parentMobile').value=d.mobile; $('parentPhone').value=d.phone; $('parentEmail').value=d.email; $('parentCnic').value=d.cnic; $('parentAddress').value=d.address; $('parentLatitude').value=d.latitude||''; $('parentLongitude').value=d.longitude||'';
    if(parentMap && d.latitude && d.longitude){parentMap.setView([d.latitude,d.longitude],15); L.marker([d.latitude,d.longitude]).addTo(parentMap);}
    drawFamily(d.children,d); const alert=document.createElement('div'); alert.className='alert alert-success mt-2'; alert.textContent='Existing guardian found. Children linked to this family are shown below.'; $('familyTree').prepend(alert);
  });
})();
