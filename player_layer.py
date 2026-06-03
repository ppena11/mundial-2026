"""
CAPA A NIVEL JUGADOR (v8) — andamiaje listo para feed en vivo.
Idea: la fuerza de ataque/defensa de una seleccion = base (del modelo de resultados v7)
      AJUSTADA por el XI realmente disponible.
Cada jugador aporta un 'valor de contribucion' (proxy: xG+xA por 90' y minutos, o valor de mercado).
Si una estrella esta lesionada/fuera del XI, se resta su aporte; entra el suplente con su aporte (menor).

Cuando tengas API key (API-Football / Sportmonks), solo reemplazas load_squad_data() por la llamada real.
El resto del modelo (v7: Poisson + Montecarlo) queda intacto: esta capa solo MODIFICA atk/dfn por partido.
"""
import json, math

# --- 1) MODELO DE CONTRIBUCION POR JUGADOR ---
# Para cada seleccion, repartimos su fuerza entre 'unidades' de jugador.
# Proxy publico disponible HOY: valor de mercado por jugador (Transfermarkt) como peso de importancia.
# Cuando entre el feed: sustituir 'weight' por (xG90+xA90)*min_share para atacantes, def_actions para defensas.

def player_adjustment(base_atk, base_dfn, starters_available, key_players):
    """
    base_atk, base_dfn: fuerza base de la seleccion (del v7)
    starters_available: fraccion 0..1 de la fuerza titular disponible (1.0 = XI ideal completo)
    key_players: lista de (nombre, peso, disponible?) — peso = share de la fuerza ofensiva del equipo
    Devuelve atk/dfn ajustados para ESE partido.
    """
    # Penalizacion ofensiva: suma de pesos de los ausentes (con amortiguacion por el suplente)
    SUB_RECOVERY = 0.55   # un suplente recupera ~55% del aporte del titular (calibrable)
    lost_attack = 0.0
    for name, weight, available in key_players:
        if not available:
            lost_attack += weight * (1 - SUB_RECOVERY)
    # convertir 'share perdido' a escala log-goles (suave): -0.5*ln(1-lost)
    atk_adj = base_atk + math.log(max(1 - lost_attack, 0.4))*0.5
    # disponibilidad global del XI afecta levemente a defensa tambien
    dfn_adj = base_dfn + math.log(max(starters_available, 0.7))*0.3
    return atk_adj, dfn_adj

# --- 2) DATOS DE LESIONES (automatico via fetch_injuries.py -> injuries.json) ---
# Peso = aporte ofensivo aprox del jugador (share del total del equipo, 0..1).
# El scraper no puede saber el peso; lo afinamos a mano para las estrellas conocidas.
STAR_WEIGHTS = {
    "Lionel Messi":0.22, "Kylian Mbappé":0.20, "Vinícius Júnior":0.18, "Jamal Musiala":0.16,
    "Lamine Yamal":0.18, "Rodrygo":0.14, "Neymar":0.10, "Raphinha":0.12, "Estêvão":0.10,
    "Xavi Simons":0.12, "Kaoru Mitoma":0.12, "Achraf Hakimi":0.10, "Mohammed Kudus":0.12,
    "Serge Gnabry":0.09, "Matthijs de Ligt":0.07, "Éder Militão":0.07, "William Saliba":0.07,
    "Alphonso Davies":0.10, "Arda Güler":0.12, "Luka Modrić":0.12,
}
DEFAULT_WEIGHT = 0.06   # jugador notable (ESPN solo lista relevantes) sin peso afinado
DOUBTFUL_PENALTY = 0.5  # un 'duda' cuenta a medias (entre disponible y fuera)

def load_squad_data(path="injuries.json"):
    """
    Construye el formato {seleccion: {starters_available, key_players:[(nombre,peso,disp?)]}}
    a partir de injuries.json (lo genera fetch_injuries.py, gratis desde ESPN).
    - 'out'      -> available=False (resta su peso completo)
    - 'doubtful' -> available=True pero con peso reducido (penalizacion parcial)
    Si no existe injuries.json, devuelve un ejemplo minimo para que la demo no falle.
    """
    try:
        inj = json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        inj = {}
    # lineups.json (manual): {equipo: [jugadores que NO están en el XI confirmado]}
    # Tiene PRIORIDAD sobre injuries.json: el XI confirmado es la realidad del partido.
    try:
        lineups = json.load(open("lineups.json", encoding="utf-8"))
    except FileNotFoundError:
        lineups = {}
    lineups = {k: v for k, v in lineups.items() if not k.startswith("_")}  # ignora notas

    data = {}
    teams = set(inj) | set(lineups)
    for team in teams:
        key_players, n_out = [], 0
        fuera_xi = set(lineups.get(team, []))
        seen = set()
        # 1) lesiones desde injuries.json
        for p in inj.get(team, []):
            name, status = p["player"], p["status"]
            seen.add(name)
            w = STAR_WEIGHTS.get(name, DEFAULT_WEIGHT)
            if name in fuera_xi or status == "out":   # XI confirmado manda
                key_players.append((name, w, False)); n_out += 1
            else:  # doubtful sin confirmar: disponible pero penalizado a medias
                key_players.append((name, w*DOUBTFUL_PENALTY, False))
        # 2) ausencias del XI que no estaban en el parte de lesiones (sano pero suplente)
        for name in fuera_xi - seen:
            key_players.append((name, STAR_WEIGHTS.get(name, DEFAULT_WEIGHT), False)); n_out += 1
        starters_available = max(0.7, 1 - 0.04*n_out)
        data[team] = {"starters_available": starters_available, "key_players": key_players}
    if not data:
        return {"Brasil": {"starters_available":0.9, "key_players":[("(sin injuries.json)",0.0,True)]}}
    return data

if __name__=="__main__":
    # Demo: ajuste a partir de injuries.json (generado por fetch_injuries.py).
    # Como base ATK/DEF no tenemos aquí los ratings v7, usamos una base neutra (0.0)
    # solo para ILUSTRAR el tamaño del ajuste por equipo (negativo = se debilita).
    data = load_squad_data()
    print(f"AJUSTE A NIVEL JUGADOR desde injuries.json ({len(data)} selecciones con bajas):\n")
    print(f"{'Selección':<14}{'ΔATK':>8}{'ΔDEF':>8}   ausentes / dudas (peso)")
    for team in sorted(data, key=lambda t: player_adjustment(0,0,data[t]['starters_available'],data[t]['key_players'])[0]):
        d=data[team]
        aa,da = player_adjustment(0.0, 0.0, d["starters_available"], d["key_players"])
        bajas=", ".join(f"{n}({w:.2f})" for n,w,av in d["key_players"] if not av)
        print(f"{team:<14}{aa:>+8.3f}{da:>+8.3f}   {bajas or '—'}")
    print("\nΔATK/ΔDEF = cuánto baja la fuerza ofensiva/defensiva por las bajas (en escala log-goles).")
    print("Con XI completo el ajuste es 0. Afina los pesos en STAR_WEIGHTS para las estrellas.")
