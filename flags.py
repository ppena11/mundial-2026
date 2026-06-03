"""
flags.py — banderas de cada selección (descarga gratis de flagcdn.com, cacheadas en flags/).
Mapea el nombre en español del modelo a su código ISO y devuelve la ruta del PNG.
"""
import os, urllib.request

ISO = {
 "Mexico":"mx","Sudafrica":"za","Corea del Sur":"kr","Chequia":"cz","Canada":"ca","Bosnia":"ba",
 "Catar":"qa","Suiza":"ch","Brasil":"br","Marruecos":"ma","Haiti":"ht","Escocia":"gb-sct",
 "Estados Unidos":"us","Paraguay":"py","Australia":"au","Turquia":"tr","Alemania":"de","Curazao":"cw",
 "Costa de Marfil":"ci","Ecuador":"ec","Paises Bajos":"nl","Japon":"jp","Suecia":"se","Tunez":"tn",
 "Belgica":"be","Egipto":"eg","Iran":"ir","Nueva Zelanda":"nz","Espana":"es","Cabo Verde":"cv",
 "Arabia Saudi":"sa","Uruguay":"uy","Francia":"fr","Senegal":"sn","Irak":"iq","Noruega":"no",
 "Argentina":"ar","Argelia":"dz","Austria":"at","Jordania":"jo","Portugal":"pt","R.D. Congo":"cd",
 "Uzbekistan":"uz","Colombia":"co","Inglaterra":"gb-eng","Croacia":"hr","Ghana":"gh","Panama":"pa",
}
CACHE = "flags"
HEAD = {"User-Agent": "Mozilla/5.0"}

def flag_path(team, w=160):
    """Devuelve la ruta local del PNG de la bandera (la descarga y cachea si hace falta). None si falla."""
    iso = ISO.get(team)
    if not iso:
        return None
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{iso}_{w}.png")
    if os.path.exists(path):
        return path
    url = f"https://flagcdn.com/w{w}/{iso}.png"
    try:
        req = urllib.request.Request(url, headers=HEAD)
        with urllib.request.urlopen(req, timeout=20) as r, open(path, "wb") as f:
            f.write(r.read())
        return path
    except Exception:
        return None
