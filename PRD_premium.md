# PRD — Producto Premium "Mundial 2026" (capa de pago para fans)

**Versión:** 1.0 · **Fecha:** 2026-06-03 · **Dueño:** Pedro (ppena)
**Estado:** Borrador para aprobación

---

## 1. Resumen ejecutivo
Capa de **suscripción de pago** sobre el motor de predicciones del Mundial 2026 (ya
automatizado en la nube). El producto entrega, cada día, **pronósticos detallados de
todos los partidos** (1X2 modelo + mercado, goles esperados, value, lesiones/XI, análisis
breve) más el **seguimiento del campeón** y el **movimiento de línea (sharp money)**.

Posicionamiento: **análisis y entretenimiento basado en datos**, NUNCA "tips garantizados".
El diferenciador es la credibilidad de un modelo real (Dixon-Coles + 20.000 simulaciones
Montecarlo, consciente del torneo) y la transparencia del historial de aciertos.

Objetivo del MVP: lanzar antes del **11 de junio de 2026** y convertir el pico de atención
del Mundial (~5 semanas) en suscriptores recurrentes y una marca que sobreviva al torneo.

---

## 2. Problema y oportunidad
- **Problema del usuario final:** hay un exceso de "opinadores" sin método; el fan serio
  quiere números creíbles, de todos los partidos, en un solo lugar, fáciles de digerir.
- **Oportunidad:** el Mundial es el mayor pico de atención del año (~104 partidos en ~5
  semanas). El contenido ya se produce solo → el costo marginal de servir a un suscriptor
  es casi cero. La ventana es corta, así que hay que **capturar audiencia rápido** y
  retenerla con un producto de pago de bajo precio y alto valor percibido.

## 3. Objetivos y no-objetivos
**Objetivos (qué SÍ):**
- O1. Entregar un **digest diario premium** con todos los partidos del día, automatizado.
- O2. Convertir seguidores gratis en suscriptores de pago ($3–5/mes o "Pase Mundial").
- O3. Construir **confianza** con un historial público de aciertos (track record).
- O4. Dejar la infraestructura lista para **reusarse post-Mundial** (otras ligas).

**No-objetivos (qué NO):**
- N1. NO vender "pronósticos ganadores" ni prometer ganancias.
- N2. NO promover casas de apuestas en el MVP (riesgo legal/plataforma).
- N3. NO construir app móvil propia (usar plataformas existentes).
- N4. NO hacer apuestas con dinero real ni dar asesoría financiera.

## 4. Usuario objetivo (personas)
- **El fan analítico (primario):** sigue el Mundial, le gustan los datos/probabilidades,
  quizá apuesta recreativamente. Paga $3–5 por ahorrar tiempo y verse "informado".
- **El creador de contenido pequeño / quiniela de amigos:** usa los números para su propio
  contenido o su porra. Valor: insumo listo y creíble.
- **El curioso casual (gratis → embudo):** llega por un video viral; se convierte si el
  contenido gratis engancha.

## 5. Propuesta de valor
> "Los números que mueven el Mundial, todos los días, explicados simple — del único modelo
> que se actualiza con lo que pasa en la cancha."

Diferenciadores: (a) modelo real y validado, (b) **consciente del torneo** (se ajusta a
resultados, lesiones y XI), (c) **value vs mercado limpio** (corrige el sesgo del modelo),
(d) **transparencia** (historial de aciertos público).

---

## 6. Alcance del producto

### 6.1 Niveles (packaging)
| Nivel | Precio | Qué incluye |
|---|---|---|
| **Gratis** (embudo) | $0 | 1 gráfico diario del campeón (TikTok), 1 "partido destacado" del día, resumen corto |
| **Premium** | **$4/mes** | TODO lo de abajo (sección 6.2). Renovación mensual |
| **Pase Mundial** | **$9.99 único** | Premium por todo el torneo (sin renovar). *Ideal por ser evento corto* |

> Recomendación: destacar el **Pase Mundial** como opción principal (evita la fricción de
> "suscripción" para un evento de 5 semanas y maximiza ingreso por fan).

### 6.2 Entregable diario Premium ("El Digest")
Cada día, automáticamente, el suscriptor recibe:
1. **Todos los partidos del día** — por cada uno:
   - Probabilidad **1X2**: modelo, mercado limpio, y ensemble.
   - **Goles esperados** y **marcador más probable**.
   - **Lesiones/bajas** relevantes y, si está disponible (~1h antes), el **XI confirmado**.
   - Señal de **value** (★) cuando el modelo supera al mercado limpio con margen.
   - 2–3 líneas de **lectura humana** (contexto que el modelo no ve: "noticia blanda").
2. **Seguimiento del campeón** — probabilidades actualizadas (modelo consciente del torneo)
   + "quién subió/bajó" desde ayer.
3. **Sharp money** — movimientos de línea destacados (de la capa de dinero ya construida).
4. **Gráficos** listos para compartir (partido + resumen del día).
5. **Historial de aciertos** (semanal) — para transparencia y confianza.

### 6.3 Comunidad (Premium)
- Canal de **Discord** privado para suscriptores: discusión, preguntas, "¿qué peso le doy a
  tal noticia?", encuestas.
- Acceso anticipado a los números (ej. 30–60 min antes que el contenido gratis).

---

## 7. Posicionamiento legal y de cumplimiento (CRÍTICO)
- Marca y copy siempre como **"análisis / entretenimiento basado en datos"**.
- **Disclaimer fijo** en cada entrega: *"Contenido informativo y de entretenimiento. No es
  consejo de apuestas ni garantía de resultados. +18. Juega con responsabilidad."*
- **Sin CTAs** del tipo "apuesta ahora" ni enlaces a casas en el MVP.
- Cumplir las **políticas de la plataforma** de pago/contenido y la **ley local** del país.
- Tener **Términos de Servicio** y **política de reembolso** claros antes de cobrar.
- Nada de promesas de rentabilidad. El historial se muestra como métrica de calibración, no
  como "cuánto habrías ganado".

---

## 8. Canales y plataforma (decisión de stack)
| Opción | Pagos | Comunidad | Email/Web | Veredicto |
|---|---|---|---|---|
| **Patreon** | ✅ integrado | ✅ Discord gateado | posts + email | Buen todo-en-uno |
| **Whop** | ✅ integrado | ✅ Discord gateado | ✅ | Pensado para esto; recomendado |
| **Substack** | ✅ (newsletter) | parcial | ✅ email/web | Mejor si el foco es email |
| **Discord + bot** | vía bot externo | ✅ nativo | — | Más control, más setup |

**Recomendación MVP:** **Whop o Patreon** para cobros + **Discord gateado** para comunidad,
y **email** como canal de respaldo del digest. (Decisión final del dueño según pagos
disponibles en su país.)

---

## 9. Arquitectura técnica (cómo se conecta a lo ya construido)
El pipeline en la nube (GitHub Actions) ya produce: `champ_today.json`, `champ_ensemble.json`,
`injuries.json`, `odds_live.json`, `odds_history.jsonl`, y los gráficos. Lo nuevo:

- **`daily_digest.py` (NUEVO):** orquesta el entregable premium:
  1. Obtiene los **partidos del día** (API ESPN / calendario openfootball).
  2. Por cada partido corre el 1X2 (reusa la lógica de `predict_match.py`) con lesiones/XI.
  3. Marca **value** comparando con el mercado (reusa `make_ensemble`/`fetch_odds --h2h`).
  4. Compila un **digest** en Markdown + HTML + un gráfico-resumen.
  5. **Distribuye**: (a) POST a un **webhook de Discord**, (b) email (API tipo Resend/SMTP),
     (c) borrador para Patreon/Substack.
- **Workflow `digest.yml` (NUEVO):** corre cada día tras el pipeline (o 2x: mañana + ~2h
  antes del primer partido para capturar XI). Reusa los Secrets ya configurados; añade
  `DISCORD_WEBHOOK_URL` y/o la API key del email como nuevos Secrets.
- **`track_record.py` (NUEVO):** guarda cada predicción y, al cerrarse el partido (resultado
  ESPN), calcula acierto/Brier; publica el resumen semanal.

> Todo encaja con el modelo actual sin tocar su núcleo: el digest **consume** los JSON que ya
> se generan. Costo de infra: $0 (sigue en GitHub Actions).

## 10. MVP — alcance mínimo para lanzar (antes del 11-jun)
- [ ] Elegir y configurar plataforma de cobro + Discord gateado.
- [ ] `daily_digest.py` que arme el digest de todos los partidos del día y lo postee a Discord.
- [ ] Texto de marca, disclaimers, ToS y política de reembolso.
- [ ] Página/perfil de venta con los 3 niveles (Gratis / Premium / Pase Mundial).
- [ ] 3–4 piezas gratis de "presentación del modelo" para calentar audiencia.

**Fuera del MVP (fase 2+):** track record automático publicado, encuestas, value-bet log
con calibración, versiones por idioma, re-apuntar a otras ligas.

## 11. Roadmap por fases (atado al calendario del Mundial)
- **Fase 0 — Pre-lanzamiento (hoy → 10 jun):** stack de cobro, `daily_digest.py`, embudo
  gratis, calentar redes.
- **Fase 1 — Lanzamiento (11 jun):** contenido gratis diario + digest premium de todos los
  partidos. Empujar el **Pase Mundial**.
- **Fase 2 — Mitad de torneo (~22 jun):** Discord activo, track record público, optimizar
  conversión, 1–2 patrocinios.
- **Fase 3 — Eliminatorias (28 jun+):** activar cuadro real (`sim_live_ko`), contenido de
  alta tensión (cada partido importa), picos de venta.
- **Fase 4 — Post-Mundial (jul+):** re-apuntar el motor a otra competición; campaña de
  retención ("seguimos todo el año").

## 12. Métricas de éxito (KPIs)
- **Adquisición:** seguidores nuevos/día, vistas, CTR al perfil de venta.
- **Conversión:** % de gratis → pago (objetivo MVP: 2–4%).
- **Ingreso:** MRR + ventas de Pase Mundial; ARPU.
- **Retención:** churn mensual (<15% sano para suscripción de evento), recompra post-WC.
- **Engagement:** apertura del digest (>40%), actividad en Discord, mensajes/encuestas.
- **Confianza:** calibración del modelo (Brier/% acierto) publicada.
- **Meta concreta MVP (5 semanas):** 200–500 suscriptores de pago / Pases vendidos.

## 13. Embudo (gratis → pago)
Video viral (TikTok/Reels) → perfil con link → página de venta → Gratis (digest recortado +
muestra del premium) → CTA al **Pase Mundial** → Discord premium → retención post-WC.

## 14. Riesgos y mitigaciones
| Riesgo | Mitigación |
|---|---|
| Ventana corta (5 semanas) | **Pase Mundial** único + plan de reúso post-WC |
| Política de plataforma (apuestas) | Enmarcar como análisis; sin CTAs de apuesta; disclaimers |
| Variación de aciertos (rachas malas) | Track record transparente; gestionar expectativas |
| Churn alto en suscripción | Preferir Pase único; comunidad pegajosa (Discord) |
| Pagos en su país | Elegir plataforma que opere en su región (Whop/Patreon/local) |
| Fragilidad de datos gratis (ESPN/proxy) | Ya hay respaldos; vigilar runs diarios |
| Fatiga de contenido | Automatizar el grueso; el humano solo aporta la "lectura" |

## 15. Decisiones tomadas / preguntas abiertas
**Decidido (2026-06-03):**
- **País/jurisdicción:** Canadá. Apuestas legales/reguladas; producto enmarcado como
  análisis/entretenimiento, sin promover casas → bajo riesgo. Mantener disclaimers + 18.
- **Canal principal:** newsletter de **email** (recomendado: **Beehiiv** — pago vía Stripe en
  Canadá, versión gratis, API para envío automático; alternativa: Buttondown).
- **Envío:** **email automático** (adaptador Resend ya implementado en `daily_digest.py`).

**Decidido (2026-06-03, cont.):**
- **Idioma:** solo **español**.
- **Marca:** **aiwithpedro** (handle **@aiwithpedro**) · producto "Mundial de fútbol 2026".
  Ya aplicada al digest y al gráfico de TikTok.

**Pendiente de decidir:**
1. ¿Precio final y peso del "Pase Mundial" vs mensual? (propuesta: Premium $4/mes, Pase $9.99)

**Estado de construcción:** `daily_digest.py` YA construido y probado (genera el digest de
todos los partidos del día + carrera por el título, en Markdown/HTML, con envío opcional por
email vía Resend). Falta: crear cuenta Beehiiv/Resend, conseguir API key, y montar el
workflow `digest.yml` para enviarlo automático cada día.

---

## 16. Siguiente paso técnico recomendado
Construir **`daily_digest.py` + `digest.yml`** (envío automático del digest de todos los
partidos del día a Discord/email), reutilizando el pipeline actual. Es el corazón del
producto y se puede tener funcionando en una sesión corta.

*Disclaimer del producto: contenido informativo y de entretenimiento. No es consejo de
apuestas ni garantía de resultados. +18. Juega con responsabilidad.*
