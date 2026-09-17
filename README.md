# La Pregunta del Dia

App para lanzar una pregunta comprometida (tipo "ColaCao vs Nesquik") cada dia,
que la gente vote A o B indicando su ciudad/pueblo, y ver el resultado
proyectado en un mapa de Espana.

Usa Postgres como base de datos (no SQLite), para poder desplegarse en
plataformas serverless como Vercel.

## Instalar

```
pip install -r requirements.txt
```

## Configurar

Necesitas una base de datos Postgres (gratis en [Neon](https://neon.tech) o
en la pestana "Storage" de tu proyecto de Vercel) y copiar `.env.example` a
`.env` (o exportar las variables) con:

```
DATABASE_URL=postgresql://usuario:password@host/basededatos?sslmode=require
ESPANA_DICE_ADMIN_PASSWORD=tu-contrasena
ESPANA_DICE_SECRET=una-clave-larga-aleatoria
```

Las tablas se crean solas (`CREATE TABLE IF NOT EXISTS`) la primera vez que
arranca la app.

## Arrancar en local

```
python app.py
```

La app queda en `http://localhost:8420`.

## Desplegar en Vercel (con GitHub)

1. Crea un repositorio en tu cuenta **personal** de GitHub y sube este codigo:
   ```
   git init
   git add .
   git commit -m "La Pregunta del Dia"
   git remote add origin https://github.com/tu-usuario/tu-repo.git
   git branch -M main
   git push -u origin main
   ```
2. En [vercel.com](https://vercel.com), inicia sesion con tu cuenta personal
   de GitHub (no la de empresa) e importa ese repositorio nuevo.
3. En el proyecto de Vercel, pestana **Storage**, crea una base de datos
   Postgres (usa Neon por debajo) y conectala al proyecto: esto rellena
   `DATABASE_URL` automaticamente.
4. En **Settings > Environment Variables**, anade tambien
   `ESPANA_DICE_ADMIN_PASSWORD` y `ESPANA_DICE_SECRET` con tus propios
   valores.
5. Vuelve a desplegar (Vercel lo hace solo al hacer push a `main`, o dale a
   "Redeploy").

## Uso diario

1. Entra en `/admin/login`, mete la contrasena y en `/admin` escribe las dos
   opciones del dia (A y B) y, si quieres, sube una imagen (por ejemplo el
   "vs" de los dos productos). Esto sobreescribe la pregunta de hoy si ya
   existia.
2. Comparte el enlace principal (`/`) con la gente para que vote su ciudad/
   pueblo y elija A o B.
3. Todos ven el resultado agregado en la propia pagina "Hoy", con un mapa de
   Espana: cada localidad aparece coloreada segun cual gano ahi (amarillo =
   opcion A, rosa = opcion B), y el tamano del circulo indica cuantos votos
   hay. Tambien se puede buscar una ciudad concreta y compartir el resultado.

## Paginas

- **Hoy** (`/`): pregunta del dia, votacion, mapa y ultimas preguntas.
- **Historico** (`/historico`): preguntas de dias anteriores con su resultado
  final.
- **Mapa** (`/mapa`): resultados por ciudad o por Comunidad Autonoma, de
  cualquier dia pasado, eligiendo la fecha en el desplegable.
- **Comunidades** (`/comunidades`): mapa clicable coloreado por Comunidad
  Autonoma.
- **Propuestas** (`/propuestas`): cualquiera propone una pregunta y las vota;
  la mas votada se puede lanzar como pregunta del dia desde `/admin`.
- **Por que hacemos esto?** (`/sobre-el-proyecto`): el porque del proyecto.

## Limitaciones

- El listado de ciudades/pueblos es una seleccion de capitales de provincia
  y algunos pueblos conocidos (fichero `cities.py`), cada una con su
  Comunidad Autonoma asignada. Se puede ampliar facilmente anadiendo mas
  entradas.
- El limite de "un voto por dia" se controla con una cookie de dispositivo,
  no con login. Es suficiente para un grupo cerrado de amigos/familia/oficina,
  pero alguien que borre cookies podria volver a votar.
