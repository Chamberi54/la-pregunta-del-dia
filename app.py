import io
import os
import sqlite3
import uuid
from datetime import date, datetime
from functools import wraps

import psycopg
from psycopg.rows import dict_row
from psycopg.errors import UniqueViolation as PgUniqueViolation
from flask import (
    Flask, g, render_template, request, redirect, url_for, session,
    jsonify, make_response, flash, Response, abort,
)

from cities import CITIES, CA_IMAGES
from share_image import generate_share_image

# Errores de "voto duplicado" que puede lanzar cualquiera de los dos backends.
UniqueViolation = (PgUniqueViolation, sqlite3.IntegrityError)

WEEKDAYS_ES = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def spanish_date_label(d):
    return f"{WEEKDAYS_ES[d.weekday()]}, {d.day} de {MONTHS_ES[d.month - 1]}"


def parse_date_label(date_str):
    return spanish_date_label(datetime.strptime(date_str, "%Y-%m-%d").date())


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_DB_PATH = os.path.join(BASE_DIR, "espana_dice.db")
DATABASE_URL = os.environ.get("DATABASE_URL")
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
MIMETYPES = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "webp": "image/webp", "gif": "image/gif",
}

app = Flask(__name__)
app.secret_key = os.environ.get("ESPANA_DICE_SECRET", "cambia-esta-clave")
ADMIN_PASSWORD = os.environ.get("ESPANA_DICE_ADMIN_PASSWORD", "admin123")

app.jinja_env.globals["parse_date_label"] = parse_date_label


class DBConn:
    """Envoltorio fino que deja usar Postgres (psycopg) o SQLite local con el
    mismo codigo: traduce los placeholders %s -> ? cuando hace falta."""

    def __init__(self, conn, is_sqlite):
        self._conn = conn
        self.is_sqlite = is_sqlite

    def execute(self, query, params=()):
        if self.is_sqlite:
            query = query.replace("%s", "?")
        return self._conn.execute(query, params)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def get_db():
    if "db" not in g:
        if DATABASE_URL:
            conn = psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=False)
            g.db = DBConn(conn, is_sqlite=False)
        else:
            conn = sqlite3.connect(LOCAL_DB_PATH)
            conn.row_factory = sqlite3.Row
            g.db = DBConn(conn, is_sqlite=True)
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    if DATABASE_URL:
        raw = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        id_col = "id SERIAL PRIMARY KEY"
        blob_type = "BYTEA"
        used_col = "used BOOLEAN NOT NULL DEFAULT FALSE"
        ts_type = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    else:
        raw = sqlite3.connect(LOCAL_DB_PATH)
        id_col = "id INTEGER PRIMARY KEY AUTOINCREMENT"
        blob_type = "BLOB"
        used_col = "used INTEGER NOT NULL DEFAULT 0"
        ts_type = "TEXT DEFAULT CURRENT_TIMESTAMP"

    db = DBConn(raw, is_sqlite=not DATABASE_URL)
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS questions (
            {id_col},
            question_date TEXT UNIQUE NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            image_data {blob_type},
            image_mimetype TEXT,
            created_at {ts_type}
        )
        """
    )
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS votes (
            {id_col},
            question_id INTEGER NOT NULL REFERENCES questions(id),
            device_id TEXT NOT NULL,
            city TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            choice TEXT NOT NULL CHECK (choice IN ('A', 'B')),
            created_at {ts_type},
            UNIQUE (question_id, device_id)
        )
        """
    )
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS proposals (
            {id_col},
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            {used_col},
            created_at {ts_type}
        )
        """
    )
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS proposal_votes (
            {id_col},
            proposal_id INTEGER NOT NULL REFERENCES proposals(id),
            device_id TEXT NOT NULL,
            created_at {ts_type},
            UNIQUE (proposal_id, device_id)
        )
        """
    )
    db.commit()
    db.close()


def get_or_set_device_id():
    return request.cookies.get("device_id") or str(uuid.uuid4())


def get_question_by_date(db, date_str):
    return db.execute(
        """
        SELECT id, question_date, option_a, option_b, created_at,
               (image_data IS NOT NULL) AS has_image
        FROM questions WHERE question_date = %s
        """,
        (date_str,),
    ).fetchone()


def today_question(db):
    return get_question_by_date(db, date.today().isoformat())


def list_questions_with_totals(db, limit=None, exclude_date=None):
    query = """
        SELECT
            q.id, q.question_date, q.option_a, q.option_b,
            COALESCE(SUM(CASE WHEN v.choice = 'A' THEN 1 ELSE 0 END), 0) AS votes_a,
            COALESCE(SUM(CASE WHEN v.choice = 'B' THEN 1 ELSE 0 END), 0) AS votes_b
        FROM questions q
        LEFT JOIN votes v ON v.question_id = q.id
        {where}
        GROUP BY q.id
        ORDER BY q.question_date DESC
        {limit}
    """
    where = "WHERE q.question_date != %s" if exclude_date else ""
    limit_clause = "LIMIT %s" if limit else ""
    params = []
    if exclude_date:
        params.append(exclude_date)
    if limit:
        params.append(limit)
    return db.execute(query.format(where=where, limit=limit_clause), params).fetchall()


def list_proposals(db, include_used=False, limit=None):
    query = """
        SELECT
            p.id, p.option_a, p.option_b, p.used, p.created_at,
            COUNT(pv.id) AS votes
        FROM proposals p
        LEFT JOIN proposal_votes pv ON pv.proposal_id = p.id
        {where}
        GROUP BY p.id
        ORDER BY votes DESC, p.created_at ASC
        {limit}
    """
    where = "" if include_used else "WHERE p.used = FALSE"
    limit_clause = "LIMIT %s" if limit else ""
    params = [limit] if limit else []
    return db.execute(query.format(where=where, limit=limit_clause), params).fetchall()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped


def is_allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def city_image_url(city_name):
    city = CITIES.get(city_name)
    if not city:
        return None
    slug = CA_IMAGES.get(city["ca"])
    if not slug:
        return None
    return url_for("static", filename=f"images/ca/{slug}.jpg")


@app.route("/")
def index():
    db = get_db()
    question = today_question(db)
    device_id = get_or_set_device_id()
    already_voted = False
    if question:
        existing = db.execute(
            "SELECT 1 FROM votes WHERE question_id = %s AND device_id = %s",
            (question["id"], device_id),
        ).fetchone()
        already_voted = existing is not None

    recent_questions = list_questions_with_totals(
        db, limit=8, exclude_date=date.today().isoformat()
    )

    resp = make_response(
        render_template(
            "index.html",
            active_page="hoy",
            question=question,
            already_voted=already_voted,
            city_names=sorted(CITIES.keys()),
            today_label=spanish_date_label(date.today()),
            recent_questions=recent_questions,
        )
    )
    resp.set_cookie("device_id", device_id, max_age=60 * 60 * 24 * 365)
    return resp


@app.route("/vote", methods=["POST"])
def vote():
    db = get_db()
    question = today_question(db)
    if not question:
        return jsonify({"error": "No hay pregunta activa hoy"}), 400

    device_id = get_or_set_device_id()
    city_name = request.form.get("city", "").strip()
    choice = request.form.get("choice", "").strip().upper()

    city = CITIES.get(city_name)
    if not city or choice not in ("A", "B"):
        return jsonify({"error": "Datos invalidos"}), 400

    try:
        db.execute(
            "INSERT INTO votes (question_id, device_id, city, lat, lon, choice) VALUES (%s, %s, %s, %s, %s, %s)",
            (question["id"], device_id, city_name, city["lat"], city["lon"], choice),
        )
        db.commit()
    except UniqueViolation:
        db.rollback()
        return jsonify({"error": "Ya has votado hoy"}), 400

    resp = jsonify({"ok": True})
    resp.set_cookie("device_id", device_id, max_age=60 * 60 * 24 * 365)
    return resp


@app.route("/resultados")
def results_page():
    return redirect(url_for("index"))


@app.route("/historico")
def historico():
    db = get_db()
    questions = list_questions_with_totals(db)
    return render_template(
        "historico.html", active_page="historico", questions=questions, today=date.today().isoformat()
    )


@app.route("/mapa")
def mapa():
    db = get_db()
    selected_date = request.args.get("date", date.today().isoformat())
    question = get_question_by_date(db, selected_date)
    available_dates = [row["question_date"] for row in db.execute(
        "SELECT question_date FROM questions ORDER BY question_date DESC"
    ).fetchall()]
    return render_template(
        "mapa.html",
        active_page="mapa",
        question=question,
        selected_date=selected_date,
        available_dates=available_dates,
    )


@app.route("/comunidades")
def comunidades():
    db = get_db()
    selected_date = request.args.get("date", date.today().isoformat())
    question = get_question_by_date(db, selected_date)
    available_dates = [row["question_date"] for row in db.execute(
        "SELECT question_date FROM questions ORDER BY question_date DESC"
    ).fetchall()]
    return render_template(
        "comunidades.html",
        active_page="comunidades",
        question=question,
        selected_date=selected_date,
        available_dates=available_dates,
        ca_images=CA_IMAGES,
    )


@app.route("/sobre-el-proyecto")
def sobre_el_proyecto():
    return render_template("sobre.html", active_page="sobre")


@app.route("/propuestas", methods=["GET", "POST"])
def propuestas():
    db = get_db()
    device_id = get_or_set_device_id()

    if request.method == "POST":
        option_a = request.form.get("option_a", "").strip()
        option_b = request.form.get("option_b", "").strip()
        if option_a and option_b:
            db.execute(
                "INSERT INTO proposals (option_a, option_b) VALUES (%s, %s)",
                (option_a, option_b),
            )
            db.commit()
        else:
            flash("Rellena las dos opciones para proponer una pregunta.")
        resp = make_response(redirect(url_for("propuestas")))
        resp.set_cookie("device_id", device_id, max_age=60 * 60 * 24 * 365)
        return resp

    proposals = list_proposals(db)
    voted_ids = {
        row["proposal_id"]
        for row in db.execute(
            "SELECT proposal_id FROM proposal_votes WHERE device_id = %s", (device_id,)
        ).fetchall()
    }

    resp = make_response(
        render_template(
            "propuestas.html",
            active_page="propuestas",
            proposals=proposals,
            voted_ids=voted_ids,
        )
    )
    resp.set_cookie("device_id", device_id, max_age=60 * 60 * 24 * 365)
    return resp


@app.route("/propuestas/<int:proposal_id>/votar", methods=["POST"])
def votar_propuesta(proposal_id):
    db = get_db()
    device_id = get_or_set_device_id()

    proposal = db.execute("SELECT * FROM proposals WHERE id = %s", (proposal_id,)).fetchone()
    if not proposal or proposal["used"]:
        return jsonify({"error": "Propuesta no encontrada"}), 404

    try:
        db.execute(
            "INSERT INTO proposal_votes (proposal_id, device_id) VALUES (%s, %s)",
            (proposal_id, device_id),
        )
        db.commit()
    except UniqueViolation:
        db.rollback()
        return jsonify({"error": "Ya has votado esta propuesta"}), 400

    votes = db.execute(
        "SELECT COUNT(*) as c FROM proposal_votes WHERE proposal_id = %s", (proposal_id,)
    ).fetchone()["c"]

    resp = jsonify({"ok": True, "votes": votes})
    resp.set_cookie("device_id", device_id, max_age=60 * 60 * 24 * 365)
    return resp


@app.route("/api/resultados")
def api_results():
    db = get_db()
    selected_date = request.args.get("date", date.today().isoformat())
    question = get_question_by_date(db, selected_date)
    if not question:
        return jsonify({"question": None, "cities": [], "totals": {"A": 0, "B": 0}})

    rows = db.execute(
        "SELECT city, lat, lon, choice, COUNT(*) as votes FROM votes WHERE question_id = %s GROUP BY city, lat, lon, choice",
        (question["id"],),
    ).fetchall()

    cities = {}
    totals = {"A": 0, "B": 0}
    for row in rows:
        entry = cities.setdefault(
            row["city"],
            {
                "city": row["city"],
                "lat": row["lat"],
                "lon": row["lon"],
                "A": 0,
                "B": 0,
                "image": city_image_url(row["city"]),
                "ca": CITIES.get(row["city"], {}).get("ca"),
            },
        )
        entry[row["choice"]] = row["votes"]
        totals[row["choice"]] += row["votes"]

    return jsonify(
        {
            "question": {
                "option_a": question["option_a"],
                "option_b": question["option_b"],
                "date": question["question_date"],
            },
            "cities": list(cities.values()),
            "totals": totals,
        }
    )


@app.route("/api/comunidades")
def api_comunidades():
    db = get_db()
    selected_date = request.args.get("date", date.today().isoformat())
    question = get_question_by_date(db, selected_date)
    if not question:
        return jsonify({"question": None, "comunidades": [], "totals": {"A": 0, "B": 0}})

    rows = db.execute(
        "SELECT city, choice, COUNT(*) as votes FROM votes WHERE question_id = %s GROUP BY city, choice",
        (question["id"],),
    ).fetchall()

    ca_totals = {}
    totals = {"A": 0, "B": 0}
    for row in rows:
        city_info = CITIES.get(row["city"])
        ca_name = city_info["ca"] if city_info else "Otros"
        entry = ca_totals.setdefault(ca_name, {"ca": ca_name, "A": 0, "B": 0})
        entry[row["choice"]] += row["votes"]
        totals[row["choice"]] += row["votes"]

    comunidades_list = sorted(
        ca_totals.values(), key=lambda c: c["A"] + c["B"], reverse=True
    )

    return jsonify(
        {
            "question": {
                "option_a": question["option_a"],
                "option_b": question["option_b"],
                "date": question["question_date"],
            },
            "comunidades": comunidades_list,
            "totals": totals,
        }
    )


@app.route("/question-image/<int:question_id>")
def question_image(question_id):
    db = get_db()
    row = db.execute(
        "SELECT image_data, image_mimetype FROM questions WHERE id = %s", (question_id,)
    ).fetchone()
    if not row or not row["image_data"]:
        abort(404)
    return Response(bytes(row["image_data"]), mimetype=row["image_mimetype"] or "image/jpeg")


@app.route("/share-image.png")
def share_image_route():
    db = get_db()
    selected_date = request.args.get("date", date.today().isoformat())
    question = get_question_by_date(db, selected_date)
    if not question:
        abort(404)

    rows = db.execute(
        "SELECT choice, COUNT(*) as c FROM votes WHERE question_id = %s GROUP BY choice",
        (question["id"],),
    ).fetchall()
    totals = {"A": 0, "B": 0}
    for row in rows:
        totals[row["choice"]] = row["c"]
    total_votes = totals["A"] + totals["B"]
    pct_a = round(totals["A"] / total_votes * 100) if total_votes else 50
    pct_b = 100 - pct_a

    img = generate_share_image(
        question["option_a"],
        question["option_b"],
        pct_a,
        pct_b,
        total_votes,
        date_label=spanish_date_label(datetime.strptime(selected_date, "%Y-%m-%d").date()),
    )
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return Response(
        buffer.getvalue(),
        mimetype="image/png",
        headers={"Cache-Control": "public, max-age=60"},
    )


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin"))
        error = "Contrasena incorrecta"
    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("index"))


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    db = get_db()
    if request.method == "POST":
        option_a = request.form.get("option_a", "").strip()
        option_b = request.form.get("option_b", "").strip()
        image_data = None
        image_mimetype = None

        image_file = request.files.get("image")
        if image_file and image_file.filename and is_allowed_image(image_file.filename):
            ext = image_file.filename.rsplit(".", 1)[1].lower()
            image_data = image_file.read()
            image_mimetype = MIMETYPES.get(ext, "image/jpeg")

        if option_a and option_b:
            if image_data:
                db.execute(
                    """
                    INSERT INTO questions (question_date, option_a, option_b, image_data, image_mimetype)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (question_date) DO UPDATE SET
                        option_a = excluded.option_a,
                        option_b = excluded.option_b,
                        image_data = excluded.image_data,
                        image_mimetype = excluded.image_mimetype
                    """,
                    (date.today().isoformat(), option_a, option_b, image_data, image_mimetype),
                )
            else:
                db.execute(
                    """
                    INSERT INTO questions (question_date, option_a, option_b)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (question_date) DO UPDATE SET
                        option_a = excluded.option_a,
                        option_b = excluded.option_b
                    """,
                    (date.today().isoformat(), option_a, option_b),
                )
            db.commit()
            flash("Pregunta guardada")
        return redirect(url_for("admin"))

    question = today_question(db)
    top_proposals = list_proposals(db, limit=10)
    return render_template(
        "admin.html", question=question, proposals=top_proposals
    )


@app.route("/admin/propuestas/<int:proposal_id>/usar", methods=["POST"])
@admin_required
def usar_propuesta(proposal_id):
    db = get_db()
    proposal = db.execute("SELECT * FROM proposals WHERE id = %s", (proposal_id,)).fetchone()
    if proposal:
        db.execute(
            """
            INSERT INTO questions (question_date, option_a, option_b, image_data, image_mimetype)
            VALUES (%s, %s, %s, NULL, NULL)
            ON CONFLICT (question_date) DO UPDATE SET
                option_a = excluded.option_a,
                option_b = excluded.option_b,
                image_data = NULL,
                image_mimetype = NULL
            """,
            (date.today().isoformat(), proposal["option_a"], proposal["option_b"]),
        )
        db.execute("UPDATE proposals SET used = TRUE WHERE id = %s", (proposal_id,))
        db.commit()
    return redirect(url_for("admin"))


init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8420))
    app.run(debug=True, host="0.0.0.0", port=port)
