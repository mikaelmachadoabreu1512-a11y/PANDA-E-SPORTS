import asyncio
import io
import json
import os
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from typing import Any, Optional

import discord
import qrcode
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()

DB_PATH = "bot_apostas.sqlite3"
RED = discord.Color(0x2B2D31)  # cinza/neutro
BOT_NAME = "Panda Supreme Apostas"

EMOJI_ADM = "<:staff:1516913606795464805>"
EMOJI_OFFLINE = "<:offline:1516915772922794015>"
EMOJI_ONLINE = "<:online:1516915759790559315>"
EMOJI_EMPATE = "<a:atualizar:1516913555276955778>"
EMOJI_SALAS = "<:salas:1516920962258305075>"
EMOJI_RENOMEAR = "<:editar:1516913582070304768>"
EMOJI_ENCERRAR = "<a:erro_animado:1516913586054631558>"
EMOJI_FINALIZAR_WO = "<:ranking_trofeu:1516913603863908373>"
EMOJI_GANHADOR = "<a:ganhador:1516913568639877140>"
EMOJI_FORM = "📧"
EMOJI_ALERTA = "<a:alerta_staff_animado:1516913572280533063>"
EMOJI_COMPUTER = "<:computador:1516913579591340284>"
EMOJI_FF = "<:free_fire:1516913587967361055>"
EMOJI_GELO = "<:gelo:1516915451999813682>"
EMOJI_PIX = "<:pix:1516913599988105378>"
EMOJI_UMP = "<:arma_ump:1516913575237652572>"
EMOJI_BLUESTACKS = "<:emulador_bluestacks:1516913584679026731>"
EMOJI_V = "<a:sucesso_animado:1516913609303658506>"
EMOJI_X = "<a:erro_animado:1516913586054631558>"
EMOJI_PRECO = "<:preco:1516913562147229726>"
EMOJI_VAGAS_MEDIADOR = "<:staff:1516913606795464805>"
EMOJI_EVENTO = "<:presente:1516913602399834132>"
EMOJI_DIVULGACAO = "<:divulgacao:1516913611304603842>"
EMOJI_RELOGIO = "<:relogio:1516913566253580470>"
EMOJI_GANHADOR_TROFEU = "<a:ganhador:1516913568639877140>"
EMOJI_WO = "<:ranking_trofeu:1516913603863908373>"
EMOJI_REEMBOLSO = "<:preco_dinheiro:1516919186046058658>"
EMOJI_SUPORTE = "<:56644tools1:1516917629841969232>"
EMOJI_VERIFICADO = EMOJI_V
EMOJI_EMU = EMOJI_BLUESTACKS
EMOJI_SAIR = EMOJI_X

ALLOWED_GUILD_ID = int(os.getenv("ALLOWED_GUILD_ID", "0") or "0")

QUEUE_PANEL_SLOTS = [
    ("1v1_mobile", "1v1 Mobile", "1v1", "mobile"),
    ("2v2_mobile", "2v2 Mobile", "2v2", "mobile"),
    ("3v3_mobile", "3v3 Mobile", "3v3", "mobile"),
    ("4v4_mobile", "4v4 Mobile", "4v4", "mobile"),
    ("1v1_emulador", "1v1 Emulador", "1v1", "emulador"),
    ("2v2_emulador", "2v2 Emulador", "2v2", "emulador"),
    ("3v3_emulador", "3v3 Emulador", "3v3", "emulador"),
    ("4v4_emulador", "4v4 Emulador", "4v4", "emulador"),
    ("2v2_misto", "2v2 Misto", "2v2", "misto"),
    ("3v3_misto", "3v3 Misto", "3v3", "misto"),
    ("4v4_misto", "4v4 Misto", "4v4", "misto"),
]


def money_to_cents(value: str) -> int:
    clean = value.strip().replace("R$", "").replace(" ", "")
    if "," in clean and "." in clean:
        clean = clean.replace(".", "").replace(",", ".")
    elif "," in clean:
        clean = clean.replace(",", ".")
    return int(round(float(clean) * 100))


def cents_to_money(cents: int) -> str:
    reais = cents / 100
    return f"R$ {reais:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def split_values(raw: str) -> list[int]:
    values = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            values.append(money_to_cents(part))
    return values


def normalize_word(value: str) -> str:
    return value.strip().lower().replace("emu", "emulador")


def pretty_mode(mode: str) -> str:
    return {
        "gel": "GEL",
        "mobile": "Mobile",
        "emulador": "Emulador",
        "misto": "Misto",
    }.get(mode, mode.title())


def pretty_type(kind: str) -> str:
    return kind.strip().lower()


def title_for_queue(kind: str) -> str:
    styled = {
        "1v1": "𝟏𝐕𝟏",
        "2v2": "𝟐𝐕𝟐",
        "3v3": "𝟑𝐕𝟑",
        "4v4": "𝟒𝐕𝟒",
    }.get(kind, kind.upper())
    return f"╭ {styled}・𝐅𝐈𝐋𝐀𝐒 ╮"


def styled_title(text: str) -> str:
    return f"╭ {text} ╮"


def valid_image_url(url: str) -> Optional[str]:
    url = url.strip()
    if not url:
        return None
    allowed = (".png", ".jpg", ".jpeg", ".webp", ".gif")
    if not url.startswith("https://") or not url.lower().endswith(allowed):
        raise ValueError("A URL precisa comecar com https:// e terminar com .png, .jpg, .jpeg, .webp ou .gif")
    return url


def ensure_channel_name(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9-]+", "-", name)
    return re.sub(r"-+", "-", name).strip("-") or "fila"


def emv_field(field_id: str, value: str) -> str:
    return f"{field_id}{len(value):02d}{value}"


def clean_pix_text(value: str, max_len: int) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = re.sub(r"[^A-Za-z0-9 .-]", "", ascii_text).strip().upper()
    return ascii_text[:max_len] or "SEM NOME"


def crc16_pix(payload: str) -> str:
    crc = 0xFFFF
    for char in payload.encode("utf-8"):
        crc ^= char << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def pix_copy_code(pix_key: str, receiver_name: str, amount_cents: int, txid: str) -> str:
    merchant_account = emv_field("00", "br.gov.bcb.pix") + emv_field("01", pix_key.strip())
    amount = f"{amount_cents / 100:.2f}"
    payload = (
        emv_field("00", "01")
        + emv_field("26", merchant_account)
        + emv_field("52", "0000")
        + emv_field("53", "986")
        + emv_field("54", amount)
        + emv_field("58", "BR")
        + emv_field("59", clean_pix_text(receiver_name, 25))
        + emv_field("60", "SAO PAULO")
        + emv_field("62", emv_field("05", clean_pix_text(txid, 25)))
    )
    payload_with_crc = payload + "6304"
    return payload_with_crc + crc16_pix(payload_with_crc)


def make_qr_file(text: str) -> discord.File:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#00CC44", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(buffer, filename="pix-qrcode.png")


class Store:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.setup()

    def setup(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                guild_id INTEGER PRIMARY KEY,
                admin_role_id INTEGER,
                owner_role_id INTEGER,
                staff_role_id INTEGER,
                queue_category_id INTEGER,
                payment_category_id INTEGER,
                alert_channel_id INTEGER,
                bets_enabled INTEGER NOT NULL DEFAULT 1,
                queue_counter INTEGER NOT NULL DEFAULT 0,
                payment_counter INTEGER NOT NULL DEFAULT 0,
                mediator_channel_id INTEGER,
                form_channel_id INTEGER,
                form_fee_cents INTEGER NOT NULL DEFAULT 300,
                form_enabled INTEGER NOT NULL DEFAULT 1,
                private_guild_id INTEGER,
                divulgacao_message TEXT,
                divulgacao_link TEXT
            );

            CREATE TABLE IF NOT EXISTS pix (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                pix_key TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS admin_presence (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                is_online INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS admin_stats (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                match_count INTEGER NOT NULL DEFAULT 0,
                last_assigned_at TEXT,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS queue_panel_channels (
                guild_id INTEGER NOT NULL,
                slot_key TEXT NOT NULL,
                channel_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, slot_key)
            );

            CREATE TABLE IF NOT EXISTS queue_panel_values (
                guild_id INTEGER PRIMARY KEY,
                values_text TEXT NOT NULL DEFAULT '10',
                fee_cents INTEGER NOT NULL DEFAULT 0,
                image_url TEXT
            );

            CREATE TABLE IF NOT EXISTS queue_panel_messages (
                guild_id INTEGER NOT NULL,
                slot_key TEXT NOT NULL,
                queue_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS queues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER,
                kind TEXT NOT NULL,
                mode TEXT NOT NULL,
                value_cents INTEGER NOT NULL,
                fee_cents INTEGER NOT NULL,
                image_url TEXT,
                players_json TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'open'
            );

            CREATE TABLE IF NOT EXISTS bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                queue_id INTEGER,
                queue_channel_id INTEGER,
                payment_channel_id INTEGER,
                player1_id INTEGER NOT NULL,
                player2_id INTEGER NOT NULL,
                admin_id INTEGER,
                kind TEXT NOT NULL,
                mode TEXT NOT NULL,
                value_cents INTEGER NOT NULL,
                fee_cents INTEGER NOT NULL,
                confirms_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'confirming'
            );

            CREATE TABLE IF NOT EXISTS ticket_settings (
                guild_id INTEGER PRIMARY KEY,
                staff_role_id INTEGER,
                category_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                helper_id INTEGER,
                topic TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS ticket_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                ticket_id INTEGER,
                rating INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS blacklist (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reason TEXT,
                added_by INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS form_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                vacancy TEXT NOT NULL,
                answers_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                reviewer_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS divulgacao_channels (
                guild_id INTEGER NOT NULL,
                slot_key TEXT NOT NULL,
                channel_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, slot_key)
            );

            CREATE TABLE IF NOT EXISTS divulgacao_messages (
                guild_id INTEGER NOT NULL,
                slot_key TEXT NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL
            );
            """
        )
        self.ensure_columns(
            "settings",
            {
                "mediator_channel_id": "INTEGER",
                "form_channel_id": "INTEGER",
                "form_fee_cents": "INTEGER NOT NULL DEFAULT 300",
                "form_enabled": "INTEGER NOT NULL DEFAULT 1",
                "private_guild_id": "INTEGER",
                "divulgacao_message": "TEXT",
                "divulgacao_link": "TEXT",
            },
        )
        self.conn.commit()

    def ensure_columns(self, table: str, columns: dict[str, str]) -> None:
        existing = {row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})").fetchall()}
        for name, ddl in columns.items():
            if name not in existing:
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")

    def settings(self, guild_id: int) -> sqlite3.Row:
        self.conn.execute("INSERT OR IGNORE INTO settings (guild_id) VALUES (?)", (guild_id,))
        self.conn.commit()
        return self.conn.execute("SELECT * FROM settings WHERE guild_id=?", (guild_id,)).fetchone()

    def update_setting(self, guild_id: int, field: str, value: Any) -> None:
        allowed = {
            "admin_role_id",
            "owner_role_id",
            "staff_role_id",
            "queue_category_id",
            "payment_category_id",
            "alert_channel_id",
            "bets_enabled",
            "mediator_channel_id",
            "form_channel_id",
            "form_fee_cents",
            "form_enabled",
            "private_guild_id",
            "divulgacao_message",
            "divulgacao_link",
        }
        if field not in allowed:
            raise ValueError("campo invalido")
        self.settings(guild_id)
        self.conn.execute(f"UPDATE settings SET {field}=? WHERE guild_id=?", (value, guild_id))
        self.conn.commit()

    def next_counter(self, guild_id: int, field: str) -> int:
        if field not in {"queue_counter", "payment_counter"}:
            raise ValueError("contador invalido")
        self.settings(guild_id)
        self.conn.execute(f"UPDATE settings SET {field}={field}+1 WHERE guild_id=?", (guild_id,))
        self.conn.commit()
        return self.settings(guild_id)[field]

    def save_pix(self, guild_id: int, user_id: int, name: str, pix_key: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO pix (guild_id, user_id, name, pix_key) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, name, pix_key),
        )
        self.conn.commit()

    def remove_pix(self, guild_id: int, user_id: int) -> None:
        self.conn.execute("DELETE FROM pix WHERE guild_id=? AND user_id=?", (guild_id, user_id))
        self.conn.commit()

    def remove_admin_data(self, guild_id: int, user_id: int) -> None:
        """Remove dados operacionais de quem perdeu o cargo de ADM."""
        self.conn.execute("DELETE FROM pix WHERE guild_id=? AND user_id=?", (guild_id, user_id))
        self.conn.execute("DELETE FROM admin_presence WHERE guild_id=? AND user_id=?", (guild_id, user_id))
        self.conn.execute("DELETE FROM admin_stats WHERE guild_id=? AND user_id=?", (guild_id, user_id))
        self.conn.commit()

    def get_pix(self, guild_id: int, user_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM pix WHERE guild_id=? AND user_id=?", (guild_id, user_id)).fetchone()

    def all_pix(self, guild_id: int) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM pix WHERE guild_id=? ORDER BY name", (guild_id,)).fetchall()

    def set_admin_online(self, guild_id: int, user_id: int, is_online: bool) -> None:
        self.conn.execute(
            """
            INSERT INTO admin_presence (guild_id, user_id, is_online, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                is_online=excluded.is_online,
                updated_at=CURRENT_TIMESTAMP
            """,
            (guild_id, user_id, 1 if is_online else 0),
        )
        self.conn.commit()

    def admin_online(self, guild_id: int, user_id: int) -> bool:
        row = self.conn.execute(
            "SELECT is_online FROM admin_presence WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ).fetchone()
        return bool(row and row["is_online"])

    def create_queue(
        self,
        guild_id: int,
        channel_id: int,
        kind: str,
        mode: str,
        value_cents: int,
        fee_cents: int,
        image_url: Optional[str],
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO queues (guild_id, channel_id, kind, mode, value_cents, fee_cents, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (guild_id, channel_id, kind, mode, value_cents, fee_cents, image_url),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def set_queue_message(self, queue_id: int, message_id: int) -> None:
        self.conn.execute("UPDATE queues SET message_id=? WHERE id=?", (message_id, queue_id))
        self.conn.commit()

    def queue(self, queue_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM queues WHERE id=?", (queue_id,)).fetchone()

    def active_queues(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM queues WHERE status='open'").fetchall()

    def queue_panel_channels(self, guild_id: int) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT slot_key, channel_id FROM queue_panel_channels WHERE guild_id=?",
            (guild_id,),
        ).fetchall()
        return {row["slot_key"]: int(row["channel_id"]) for row in rows}

    def set_queue_panel_channel(self, guild_id: int, slot_key: str, channel_id: int) -> None:
        self.conn.execute(
            """
            INSERT INTO queue_panel_channels (guild_id, slot_key, channel_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, slot_key) DO UPDATE SET channel_id=excluded.channel_id
            """,
            (guild_id, slot_key, channel_id),
        )
        self.conn.commit()

    def queue_panel_values(self, guild_id: int) -> sqlite3.Row:
        self.conn.execute("INSERT OR IGNORE INTO queue_panel_values (guild_id) VALUES (?)", (guild_id,))
        self.conn.commit()
        return self.conn.execute("SELECT * FROM queue_panel_values WHERE guild_id=?", (guild_id,)).fetchone()

    def set_queue_panel_values(self, guild_id: int, values_text: str, fee_cents: int, image_url: Optional[str]) -> None:
        self.queue_panel_values(guild_id)
        self.conn.execute(
            "UPDATE queue_panel_values SET values_text=?, fee_cents=?, image_url=? WHERE guild_id=?",
            (values_text, fee_cents, image_url, guild_id),
        )
        self.conn.commit()

    def add_queue_panel_message(self, guild_id: int, slot_key: str, queue_id: int, channel_id: int, message_id: int) -> None:
        self.conn.execute(
            "INSERT INTO queue_panel_messages (guild_id, slot_key, queue_id, channel_id, message_id) VALUES (?, ?, ?, ?, ?)",
            (guild_id, slot_key, queue_id, channel_id, message_id),
        )
        self.conn.commit()

    def queue_panel_messages(self, guild_id: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM queue_panel_messages WHERE guild_id=?",
            (guild_id,),
        ).fetchall()

    def clear_queue_panel_messages(self, guild_id: int) -> None:
        self.conn.execute("DELETE FROM queue_panel_messages WHERE guild_id=?", (guild_id,))
        self.conn.commit()

    def set_queue_players(self, queue_id: int, players: list[dict[str, Any]]) -> None:
        self.conn.execute("UPDATE queues SET players_json=? WHERE id=?", (json.dumps(players), queue_id))
        self.conn.commit()

    def close_queue(self, queue_id: int) -> None:
        self.conn.execute("UPDATE queues SET status='closed' WHERE id=?", (queue_id,))
        self.conn.commit()

    def create_bet(self, queue: sqlite3.Row, players: list[dict[str, Any]], admin_id: Optional[int]) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO bets (
                guild_id, queue_id, player1_id, player2_id, admin_id,
                kind, mode, value_cents, fee_cents
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                queue["guild_id"],
                queue["id"],
                players[0]["user_id"],
                players[1]["user_id"],
                admin_id,
                queue["kind"],
                queue["mode"],
                queue["value_cents"],
                queue["fee_cents"],
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def bet(self, bet_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM bets WHERE id=?", (bet_id,)).fetchone()

    def bet_by_channel(self, guild_id: int, channel_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM bets WHERE guild_id=? AND (queue_channel_id=? OR payment_channel_id=?) AND status!='closed'",
            (guild_id, channel_id, channel_id),
        ).fetchone()

    def update_bet(self, bet_id: int, **fields: Any) -> None:
        if not fields:
            return
        allowed = {"queue_channel_id", "payment_channel_id", "confirms_json", "status", "admin_id"}
        for key in fields:
            if key not in allowed:
                raise ValueError("campo invalido")
        sets = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(f"UPDATE bets SET {sets} WHERE id=?", (*fields.values(), bet_id))
        self.conn.commit()

    def admin_busy(self, guild_id: int, admin_id: int) -> bool:
        row = self.conn.execute(
            "SELECT id FROM bets WHERE guild_id=? AND admin_id=? AND status!='closed' LIMIT 1",
            (guild_id, admin_id),
        ).fetchone()
        return row is not None

    def admin_assignment_count(self, guild_id: int, admin_id: int) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS total FROM bets WHERE guild_id=? AND admin_id=?",
            (guild_id, admin_id),
        ).fetchone()
        return int(row["total"]) if row else 0

    def admin_last_assigned(self, guild_id: int, admin_id: int) -> str:
        row = self.conn.execute(
            "SELECT last_assigned_at FROM admin_stats WHERE guild_id=? AND user_id=?",
            (guild_id, admin_id),
        ).fetchone()
        return str(row["last_assigned_at"] or "") if row else ""

    def record_admin_assignment(self, guild_id: int, admin_id: int) -> None:
        self.conn.execute(
            """
            INSERT INTO admin_stats (guild_id, user_id, match_count, last_assigned_at)
            VALUES (?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                match_count=match_count+1,
                last_assigned_at=CURRENT_TIMESTAMP
            """,
            (guild_id, admin_id),
        )
        self.conn.commit()

    def admin_rank_rows(self, guild_id: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT admin_id AS user_id, COUNT(*) AS total
            FROM bets
            WHERE guild_id=? AND admin_id IS NOT NULL
            GROUP BY admin_id
            ORDER BY total DESC, admin_id ASC
            """,
            (guild_id,),
        ).fetchall()

    def add_blacklist(self, guild_id: int, user_id: int, reason: str, added_by: int) -> None:
        self.conn.execute(
            """
            INSERT INTO blacklist (guild_id, user_id, reason, added_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                reason=excluded.reason,
                added_by=excluded.added_by,
                created_at=CURRENT_TIMESTAMP
            """,
            (guild_id, user_id, reason, added_by),
        )
        self.conn.commit()

    def remove_blacklist(self, guild_id: int, user_id: int) -> None:
        self.conn.execute("DELETE FROM blacklist WHERE guild_id=? AND user_id=?", (guild_id, user_id))
        self.conn.commit()

    def is_blacklisted(self, guild_id: int, user_id: int) -> bool:
        row = self.conn.execute(
            "SELECT user_id FROM blacklist WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ).fetchone()
        return row is not None

    def blacklist_rows(self, guild_id: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM blacklist WHERE guild_id=? ORDER BY created_at DESC",
            (guild_id,),
        ).fetchall()

    def create_form_submission(self, guild_id: int, user_id: int, vacancy: str, answers: dict[str, str]) -> int:
        cur = self.conn.execute(
            "INSERT INTO form_submissions (guild_id, user_id, vacancy, answers_json) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, vacancy, json.dumps(answers, ensure_ascii=False)),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def form_submission(self, submission_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM form_submissions WHERE id=?", (submission_id,)).fetchone()

    def update_form_submission(self, submission_id: int, status: str, reviewer_id: int) -> None:
        self.conn.execute(
            "UPDATE form_submissions SET status=?, reviewer_id=? WHERE id=?",
            (status, reviewer_id, submission_id),
        )
        self.conn.commit()

    def divulgacao_channels(self, guild_id: int) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT slot_key, channel_id FROM divulgacao_channels WHERE guild_id=?",
            (guild_id,),
        ).fetchall()
        return {row["slot_key"]: int(row["channel_id"]) for row in rows}

    def set_divulgacao_channel(self, guild_id: int, slot_key: str, channel_id: int) -> None:
        self.conn.execute(
            """
            INSERT INTO divulgacao_channels (guild_id, slot_key, channel_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, slot_key) DO UPDATE SET channel_id=excluded.channel_id
            """,
            (guild_id, slot_key, channel_id),
        )
        self.conn.commit()

    def add_divulgacao_message(self, guild_id: int, slot_key: str, channel_id: int, message_id: int) -> None:
        self.conn.execute(
            "INSERT INTO divulgacao_messages (guild_id, slot_key, channel_id, message_id) VALUES (?, ?, ?, ?)",
            (guild_id, slot_key, channel_id, message_id),
        )
        self.conn.commit()

    def divulgacao_messages(self, guild_id: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM divulgacao_messages WHERE guild_id=?",
            (guild_id,),
        ).fetchall()

    def clear_divulgacao_messages(self, guild_id: int) -> None:
        self.conn.execute("DELETE FROM divulgacao_messages WHERE guild_id=?", (guild_id,))
        self.conn.commit()

    def backup_data(self, guild_id: int) -> dict[str, Any]:
        tables = [
            "settings",
            "pix",
            "admin_presence",
            "admin_stats",
            "queue_panel_channels",
            "queue_panel_values",
            "ticket_settings",
            "blacklist",
            "form_submissions",
            "divulgacao_channels",
        ]
        data: dict[str, Any] = {"guild_id": guild_id, "tables": {}}
        for table in tables:
            rows = self.conn.execute(f"SELECT * FROM {table} WHERE guild_id=?", (guild_id,)).fetchall()
            data["tables"][table] = [dict(row) for row in rows]
        return data

    def restore_data(self, guild_id: int, data: dict[str, Any]) -> None:
        tables = data.get("tables", {})
        allowed_tables = {
            "settings",
            "pix",
            "admin_presence",
            "admin_stats",
            "queue_panel_channels",
            "queue_panel_values",
            "ticket_settings",
            "blacklist",
            "form_submissions",
            "divulgacao_channels",
        }
        with self.conn:
            for table, rows in tables.items():
                if table not in allowed_tables:
                    continue
                self.conn.execute(f"DELETE FROM {table} WHERE guild_id=?", (guild_id,))
                for row in rows:
                    row = dict(row)
                    row["guild_id"] = guild_id
                    columns = list(row.keys())
                    placeholders = ", ".join("?" for _ in columns)
                    names = ", ".join(columns)
                    self.conn.execute(
                        f"INSERT OR REPLACE INTO {table} ({names}) VALUES ({placeholders})",
                        [row[name] for name in columns],
                    )

    # ── TICKET ──────────────────────────────────────────────────────────────

    def ticket_settings(self, guild_id: int) -> sqlite3.Row:
        self.conn.execute("INSERT OR IGNORE INTO ticket_settings (guild_id) VALUES (?)", (guild_id,))
        self.conn.commit()
        return self.conn.execute("SELECT * FROM ticket_settings WHERE guild_id=?", (guild_id,)).fetchone()

    def update_ticket_settings(self, guild_id: int, staff_role_id: int, category_id: int) -> None:
        self.ticket_settings(guild_id)
        self.conn.execute(
            "UPDATE ticket_settings SET staff_role_id=?, category_id=? WHERE guild_id=?",
            (staff_role_id, category_id, guild_id),
        )
        self.conn.commit()

    def create_ticket(self, guild_id: int, channel_id: int, user_id: int, topic: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO support_tickets (guild_id, channel_id, user_id, topic) VALUES (?, ?, ?, ?)",
            (guild_id, channel_id, user_id, topic),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def ticket_by_channel(self, channel_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM support_tickets WHERE channel_id=?", (channel_id,)
        ).fetchone()

    def close_ticket(self, channel_id: int) -> None:
        self.conn.execute(
            "UPDATE support_tickets SET status='closed' WHERE channel_id=?", (channel_id,)
        )
        self.conn.commit()

    def add_ticket_rating(self, guild_id: int, user_id: int, ticket_id: int, rating: int) -> None:
        # uma avaliação por pessoa por ticket
        existing = self.conn.execute(
            "SELECT id FROM ticket_ratings WHERE guild_id=? AND user_id=? AND ticket_id=?",
            (guild_id, user_id, ticket_id),
        ).fetchone()
        if existing:
            self.conn.execute(
                "UPDATE ticket_ratings SET rating=? WHERE id=?",
                (rating, existing["id"]),
            )
        else:
            self.conn.execute(
                "INSERT INTO ticket_ratings (guild_id, user_id, ticket_id, rating) VALUES (?, ?, ?, ?)",
                (guild_id, user_id, ticket_id, rating),
            )
        self.conn.commit()

    def ticket_rating_counts(self, guild_id: int) -> dict[int, int]:
        rows = self.conn.execute(
            "SELECT rating, COUNT(*) AS total FROM ticket_ratings WHERE guild_id=? GROUP BY rating",
            (guild_id,),
        ).fetchall()
        counts = {i: 0 for i in range(1, 6)}
        for row in rows:
            counts[int(row["rating"])] = int(row["total"])
        return counts


store = Store(DB_PATH)

# migrações
for col in ["alert_channel_id INTEGER", "owner_role_id INTEGER"]:
    try:
        store.conn.execute(f"ALTER TABLE settings ADD COLUMN {col}")
        store.conn.commit()
    except Exception:
        pass


intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.presences = True
intents.message_content = True

bot = commands.Bot(command_prefix="?", intents=intents)
queue_locks: dict[int, asyncio.Lock] = {}


def queue_lock(queue_id: int) -> asyncio.Lock:
    lock = queue_locks.get(queue_id)
    if lock is None:
        lock = asyncio.Lock()
        queue_locks[queue_id] = lock
    return lock


def red_embed(title: str, description: Optional[str] = None) -> discord.Embed:
    if title.startswith("⟦ ") and title.endswith(" ⟧"):
        title = title[2:-2].strip()
    if not title.startswith("╭ "):
        title = styled_title(title)
    return discord.Embed(title=title, description=description, color=RED)


def queue_players(queue: sqlite3.Row) -> list[dict[str, Any]]:
    return json.loads(queue["players_json"] or "[]")


def queue_embed(queue: sqlite3.Row) -> discord.Embed:
    players = queue_players(queue)
    if players:
        text = "\n".join(f"{EMOJI_ADM} <@{p['user_id']}> - {p['choice']}" if p.get("choice") else f"{EMOJI_ADM} <@{p['user_id']}>" for p in players)
        if len(players) < 2:
            text += f"\n\n{EMOJI_ADM} 𝐀𝐠𝐮𝐚𝐫𝐝𝐚𝐧𝐝𝐨 𝐨𝐮𝐭𝐫𝐨 𝐣𝐨𝐠𝐚𝐝𝐨𝐫..."
    else:
        text = f"{EMOJI_ADM} 𝐀𝐠𝐮𝐚𝐫𝐝𝐚𝐧𝐝𝐨 𝐣𝐨𝐠𝐚𝐝𝐨𝐫𝐞𝐬..."
    embed = red_embed(
        title_for_queue(queue["kind"]),
        (
            f"{EMOJI_FF} 𝐌𝐨𝐝𝐨: **{queue['kind']} {pretty_mode(queue['mode'])}**\n"
            f"{EMOJI_PRECO} 𝐕𝐚𝐥𝐨𝐫: **{cents_to_money(queue['value_cents'])}**\n"
            f"{EMOJI_REEMBOLSO} 𝐓𝐚𝐱𝐚: **{cents_to_money(queue['fee_cents'])}**\n\n"
            f"{EMOJI_ADM} 𝐉𝐨𝐠𝐚𝐝𝐨𝐫𝐞𝐬:\n{text}"
        ),
    )
    if queue["image_url"]:
        embed.set_thumbnail(url=queue["image_url"])
    return embed


def queue_button_kind(kind: str, mode: str) -> str:
    if kind == "1v1" and mode in {"mobile", "emulador"}:
        return "gel"
    if mode == "misto":
        return "misto"
    return "normal"


class QueueView(discord.ui.View):
    def __init__(self, queue_id: int, kind: str, mode: str):
        super().__init__(timeout=None)
        button_kind = queue_button_kind(kind, mode)
        if button_kind == "gel":
            self.add_item(QueueButton(queue_id, "Gel Infinito", EMOJI_GELO, discord.ButtonStyle.secondary))
            self.add_item(QueueButton(queue_id, "Gel Normal", EMOJI_GELO, discord.ButtonStyle.secondary))
        elif button_kind == "misto":
            max_emu = {"2v2": 1, "3v3": 2, "4v4": 3}.get(kind, 1)
            for i in range(1, max_emu + 1):
                self.add_item(QueueButton(queue_id, f"{i} EMU", EMOJI_BLUESTACKS, discord.ButtonStyle.secondary))
        else:
            self.add_item(QueueButton(queue_id, "Entrar", EMOJI_V, discord.ButtonStyle.secondary))
            self.add_item(QueueButton(queue_id, "Full Ump Xm8", EMOJI_UMP, discord.ButtonStyle.secondary))
        self.add_item(LeaveQueueButton(queue_id))


class QueueButton(discord.ui.Button):
    def __init__(self, queue_id: int, choice: str, emoji: str, style: discord.ButtonStyle):
        super().__init__(
            label=choice,
            emoji=emoji,
            style=style,
            custom_id=f"queue:{queue_id}:enter:{choice}",
        )
        self.queue_id = queue_id
        self.choice = choice

    async def callback(self, interaction: discord.Interaction) -> None:
        async with queue_lock(self.queue_id):
            await enter_queue(interaction, self.queue_id, self.choice)


class LeaveQueueButton(discord.ui.Button):
    def __init__(self, queue_id: int):
        super().__init__(label="Sair", emoji=EMOJI_X, style=discord.ButtonStyle.secondary, custom_id=f"queue:{queue_id}:leave")
        self.queue_id = queue_id

    async def callback(self, interaction: discord.Interaction) -> None:
        async with queue_lock(self.queue_id):
            await self._leave(interaction)

    async def _leave(self, interaction: discord.Interaction) -> None:
        queue = store.queue(self.queue_id)
        if not queue or queue["status"] != "open":
            await interaction.response.send_message("⟦ ⚠️ 𝐅𝐈𝐋𝐀 𝐈𝐍𝐃𝐈𝐒𝐏𝐎𝐍𝐈́𝐕𝐄𝐋 ⟧", ephemeral=True)
            return
        players = queue_players(queue)
        if not any(p["user_id"] == interaction.user.id for p in players):
            await interaction.response.send_message("⟦ ⚠️ 𝐒𝐄𝐌 𝐅𝐈𝐋𝐀 ⟧\nVocê não está nesta fila.", ephemeral=True)
            return
        players = [p for p in players if p["user_id"] != interaction.user.id]
        store.set_queue_players(self.queue_id, players)
        queue = store.queue(self.queue_id)
        await interaction.message.edit(embed=queue_embed(queue), view=QueueView(queue["id"], queue["kind"], queue["mode"]))
        await interaction.response.send_message("⟦ <:sair:1516917997539692655> 𝐕𝐎𝐂𝐄̂ 𝐒𝐀𝐈𝐔 𝐃𝐀 𝐅𝐈𝐋𝐀 ⟧", ephemeral=True)


async def enter_queue(interaction: discord.Interaction, queue_id: int, choice: str) -> None:
    queue = store.queue(queue_id)
    if not queue or queue["status"] != "open":
        await interaction.response.send_message(f"{EMOJI_ALERTA} Fila indisponivel.", ephemeral=True)
        return
    settings = store.settings(interaction.guild_id)
    if not settings["bets_enabled"]:
        await interaction.response.send_message(f"{EMOJI_X} No momento as apostas estao desativadas.", ephemeral=True)
        return
    if store.is_blacklisted(interaction.guild_id, interaction.user.id):
        await interaction.response.send_message(f"{EMOJI_ALERTA} Voce esta na blacklist e nao pode entrar nas filas.", ephemeral=True)
        return

    players = queue_players(queue)
    players = [p for p in players if p["user_id"] != interaction.user.id]
    players.append({"user_id": interaction.user.id, "choice": choice if choice not in {"Entrar"} else ""})
    store.set_queue_players(queue_id, players)
    queue = store.queue(queue_id)

    await interaction.response.send_message(entry_private_message(queue, choice), ephemeral=True)
    await interaction.message.edit(embed=queue_embed(queue), view=QueueView(queue["id"], queue["kind"], queue["mode"]))

    if len(players) >= 2:
        await complete_queue(interaction.guild, queue, players[:2], interaction.channel)
        store.set_queue_players(queue_id, [])
        queue = store.queue(queue_id)
        await interaction.message.edit(embed=queue_embed(queue), view=QueueView(queue["id"], queue["kind"], queue["mode"]))


def entry_private_message(queue: sqlite3.Row, choice: str) -> str:
    extra = ""
    if choice not in {"Entrar"}:
        emoji = EMOJI_BLUESTACKS if "EMU" in choice else EMOJI_UMP if "Ump" in choice else EMOJI_GELO
        extra = f"\n{emoji} 𝐄𝐬𝐜𝐨𝐥𝐡𝐚: **{choice}**"
    return (
        f"{styled_title(f'{EMOJI_V} 𝐄𝐍𝐓𝐑𝐎𝐔・𝐍𝐀・𝐅𝐈𝐋𝐀')}\n\n"
        f"{EMOJI_ADM} 𝐉𝐨𝐠𝐚𝐝𝐨𝐫: <@{queue_players(queue)[-1]['user_id']}>\n"
        f"{EMOJI_FF} 𝐌𝐨𝐝𝐨: **{queue['kind']} {pretty_mode(queue['mode'])}**\n"
        f"{EMOJI_PRECO} 𝐕𝐚𝐥𝐨𝐫: **{cents_to_money(queue['value_cents'])}**\n"
        f"{EMOJI_REEMBOLSO} 𝐓𝐚𝐱𝐚: **{cents_to_money(queue['fee_cents'])}**"
        f"{extra}\n\n"
        f"{EMOJI_ADM} 𝐀𝐠𝐮𝐚𝐫𝐝𝐚𝐧𝐝𝐨 𝐨𝐮𝐭𝐫𝐨 𝐣𝐨𝐠𝐚𝐝𝐨𝐫..."
    )


async def choose_admin(guild: discord.Guild) -> Optional[discord.Member]:
    settings = store.settings(guild.id)
    role_id = settings["admin_role_id"]
    if not role_id:
        return None
    role = guild.get_role(role_id)
    if not role:
        return None
    members = [
        m for m in role.members
        if not m.bot
        and store.admin_online(guild.id, m.id)
        and m.status != discord.Status.offline
        and not store.admin_busy(guild.id, m.id)
    ]
    if not members:
        return None
    return sorted(
        members,
        key=lambda m: (
            store.admin_assignment_count(guild.id, m.id),
            store.admin_last_assigned(guild.id, m.id),
            m.id,
        ),
    )[0]


def mediator_alert_embed(bet: sqlite3.Row, channel: discord.TextChannel) -> discord.Embed:
    return red_embed(
        styled_title(f"{EMOJI_ADM} 𝐀𝐆𝐔𝐀𝐑𝐃𝐀𝐍𝐃𝐎・𝐌𝐄𝐃𝐈𝐀𝐃𝐎𝐑"),
        (
            f"{EMOJI_ADM} 𝐉𝐨𝐠𝐚𝐝𝐨𝐫𝐞𝐬: <@{bet['player1_id']}> vs <@{bet['player2_id']}>\n"
            f"{EMOJI_FF} 𝐌𝐨𝐝𝐨: **{bet['kind']} {pretty_mode(bet['mode'])}**\n"
            f"{EMOJI_REEMBOLSO} 𝐕𝐚𝐥𝐨𝐫: **{cents_to_money(bet['value_cents'])}**\n"
            f"{EMOJI_ADM} 𝐂𝐚𝐧𝐚𝐥 𝐝𝐚 𝐜𝐨𝐧𝐟𝐢𝐫𝐦𝐚𝐜̧𝐚̃𝐨: {channel.mention}\n\n"
            f"{EMOJI_ADM} 𝐂𝐥𝐢𝐪𝐮𝐞 𝐞𝐦 **𝐀𝐬𝐬𝐮𝐦𝐢𝐫 𝐀𝐩𝐨𝐬𝐭𝐚** 𝐩𝐚𝐫𝐚 𝐦𝐞𝐝𝐢𝐚𝐫."
        ),
    )


async def complete_queue(guild: discord.Guild, queue: sqlite3.Row, players: list[dict[str, Any]], origin: discord.abc.Messageable) -> bool:
    bet_id = store.create_bet(queue, players, None)
    settings = store.settings(guild.id)
    counter = store.next_counter(guild.id, "queue_counter")
    category = guild.get_channel(settings["queue_category_id"]) if settings["queue_category_id"] else None

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
    }
    staff_role = guild.get_role(settings["staff_role_id"]) if settings["staff_role_id"] else None
    if staff_role:
        overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    # Donos têm acesso a todos os canais
    try:
        owner_role_id = settings["owner_role_id"]
    except (IndexError, KeyError):
        owner_role_id = None
    if owner_role_id:
        owner_role = guild.get_role(owner_role_id)
        if owner_role:
            overwrites[owner_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    for player in players:
        member = guild.get_member(player["user_id"])
        if member:
            overwrites[member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

    channel = await guild.create_text_channel(f"fila-{counter:04d}", category=category, overwrites=overwrites)
    store.update_bet(bet_id, queue_channel_id=channel.id)
    await channel.send(
        content=f"<@{players[0]['user_id']}> <@{players[1]['user_id']}>",
        embed=match_embed(store.bet(bet_id)),
        view=ConfirmView(bet_id),
    )

    return True


def match_embed(bet: sqlite3.Row) -> discord.Embed:
    confirms = json.loads(bet["confirms_json"] or "{}")
    p1_status = "<a:sucesso_animado:1516913609303658506> Confirmado" if confirms.get(str(bet["player1_id"])) else "<:relogio:1516913566253580470> Aguardando"
    p2_status = "<a:sucesso_animado:1516913609303658506> Confirmado" if confirms.get(str(bet["player2_id"])) else "<:relogio:1516913566253580470> Aguardando"
    admin_text = f"<@{bet['admin_id']}>" if bet["admin_id"] else "𝐀𝐠𝐮𝐚𝐫𝐝𝐚𝐧𝐝𝐨 𝐦𝐞𝐝𝐢𝐚𝐝𝐨𝐫"
    return red_embed(
        styled_title(f"<:free_fire:1516913587967361055> 𝐌𝐀𝐓𝐂𝐇・𝐄𝐍𝐂𝐎𝐍𝐓𝐑𝐀𝐃𝐎 <:free_fire:1516913587967361055>"),
        (
            f"<@{bet['player1_id']}> <@{bet['player2_id']}>\n"
            f"{EMOJI_ADM} 𝐌𝐞𝐝𝐢𝐚𝐝𝐨𝐫: {admin_text}\n\n"
            f"{EMOJI_FF} 𝐌𝐨𝐝𝐨: **{bet['kind']} {pretty_mode(bet['mode'])}**\n"
            f"{EMOJI_REEMBOLSO} 𝐕𝐚𝐥𝐨𝐫: **{cents_to_money(bet['value_cents'])}**\n\n"
            f"{EMOJI_ADM} 𝐉𝐨𝐠𝐚𝐝𝐨𝐫 𝟏: <@{bet['player1_id']}> • {p1_status}\n"
            f"{EMOJI_ADM} 𝐉𝐨𝐠𝐚𝐝𝐨𝐫 𝟐: <@{bet['player2_id']}> • {p2_status}"
        ),
    )


class ConfirmView(discord.ui.View):
    def __init__(self, bet_id: int):
        super().__init__(timeout=None)
        self.bet_id = bet_id

    @discord.ui.button(label="Confirmar", emoji=EMOJI_V, style=discord.ButtonStyle.secondary, custom_id="bet_confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        bet = store.bet(self.bet_id)
        if not bet:
            await interaction.response.send_message("Aposta não encontrada.", ephemeral=True)
            return
        if interaction.user.id not in {bet["player1_id"], bet["player2_id"]}:
            await interaction.response.send_message("Somente jogadores podem confirmar.", ephemeral=True)
            return
        confirms = json.loads(bet["confirms_json"] or "{}")
        if confirms.get(str(interaction.user.id)):
            await interaction.response.send_message(
                "⟦ ⚠️ 𝐉𝐀́ 𝐂𝐎𝐍𝐅𝐈𝐑𝐌𝐎𝐔 ⟧\nVocê já confirmou antes. Aguarde o outro jogador.",
                ephemeral=True,
            )
            return
        confirms[str(interaction.user.id)] = True
        store.update_bet(self.bet_id, confirms_json=json.dumps(confirms))
        bet = store.bet(self.bet_id)
        await interaction.message.edit(embed=match_embed(bet), view=self)
        await interaction.response.send_message(f"{styled_title(f'{EMOJI_V} 𝐂𝐎𝐍𝐅𝐈𝐑𝐌𝐀𝐃𝐎')}\nSua confirmação foi registrada.", ephemeral=True)
        if confirms.get(str(bet["player1_id"])) and confirms.get(str(bet["player2_id"])):
            store.update_bet(self.bet_id, status="awaiting_mediator")
            bet = store.bet(self.bet_id)
            await interaction.message.edit(embed=match_embed(bet), view=None)
            await interaction.channel.send(
                embed=red_embed(
                    styled_title(f"{EMOJI_ADM} 𝐀𝐆𝐔𝐀𝐑𝐃𝐀𝐍𝐃𝐎・𝐌𝐄𝐃𝐈𝐀𝐃𝐎𝐑"),
                    (
                        f"{EMOJI_V} 𝐎𝐬 𝐝𝐨𝐢𝐬 𝐣𝐨𝐠𝐚𝐝𝐨𝐫𝐞𝐬 𝐜𝐨𝐧𝐟𝐢𝐫𝐦𝐚𝐫𝐚𝐦.\n"
                        f"{EMOJI_ADM} 𝐀𝐠𝐮𝐚𝐫𝐝𝐚𝐧𝐝𝐨 𝐮𝐦 𝐦𝐞𝐝𝐢𝐚𝐝𝐨𝐫 𝐚𝐬𝐬𝐮𝐦𝐢𝐫 𝐚 𝐚𝐩𝐨𝐬𝐭𝐚."
                    ),
                )
            )
            await send_mediator_alert(interaction.guild, bet, interaction.channel)

    @discord.ui.button(label="Regras", emoji="📜", style=discord.ButtonStyle.secondary, custom_id="bet_rules")
    async def rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"{styled_title('📜 𝐑𝐄𝐆𝐑𝐀𝐒・𝐃𝐀・𝐏𝐀𝐑𝐓𝐈𝐃𝐀')}\nCombine as regras da partida com seu adversário antes de confirmar.",
            ephemeral=True,
        )

    @discord.ui.button(label="Cancelar", emoji=EMOJI_X, style=discord.ButtonStyle.danger, custom_id="bet_cancel")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        bet = store.bet(self.bet_id)
        if not bet:
            return
        if interaction.user.id not in {bet["player1_id"], bet["player2_id"], bet["admin_id"]}:
            await interaction.response.send_message("Você não pode cancelar esta aposta.", ephemeral=True)
            return
        await interaction.response.send_message("⟦ ❌ 𝐏𝐀𝐑𝐓𝐈𝐃𝐀 𝐂𝐀𝐍𝐂𝐄𝐋𝐀𝐃𝐀 ⟧\nA fila foi finalizada com sucesso.")
        await close_bet_channel(interaction.channel, self.bet_id, winner_id=None)


async def send_mediator_alert(guild: discord.Guild, bet: sqlite3.Row, confirm_channel: discord.TextChannel) -> None:
    settings = store.settings(guild.id)
    try:
        alert_channel_id = settings["alert_channel_id"]
    except (IndexError, KeyError):
        alert_channel_id = None
    alert_channel = guild.get_channel(alert_channel_id) if alert_channel_id else None
    target = alert_channel or confirm_channel
    try:
        await target.send(
            content="@everyone @here",
            embed=mediator_alert_embed(bet, confirm_channel),
            view=AssumeBetView(bet["id"]),
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )
    except discord.HTTPException:
        pass


class AssumeBetView(discord.ui.View):
    def __init__(self, bet_id: int):
        super().__init__(timeout=None)
        self.bet_id = bet_id

    def _can_assume(self, member: discord.Member) -> bool:
        return is_owner_member(member) or is_admin_member(member)

    @discord.ui.button(label="Assumir Aposta", emoji=EMOJI_ADM, style=discord.ButtonStyle.success, custom_id="bet_assume")
    async def assume(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not self._can_assume(interaction.user):
            await interaction.response.send_message(
                f"{styled_title(f'{EMOJI_ALERTA} 𝐒𝐄𝐌・𝐏𝐄𝐑𝐌𝐈𝐒𝐒𝐀̃𝐎')}\nSomente ADM/mediador pode assumir esta aposta.",
                ephemeral=True,
            )
            return

        bet = store.bet(self.bet_id)
        if not bet or bet["status"] == "closed":
            await interaction.response.send_message("Esta aposta não está mais disponível.", ephemeral=True)
            return
        if bet["admin_id"]:
            await interaction.response.send_message("Esta aposta já foi assumida.", ephemeral=True)
            return

        store.update_bet(self.bet_id, admin_id=interaction.user.id, status="payment")
        store.record_admin_assignment(interaction.guild_id, interaction.user.id)
        bet = store.bet(self.bet_id)

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            embed=red_embed(
                styled_title(f"{EMOJI_ADM} 𝐌𝐄𝐃𝐈𝐀𝐃𝐎𝐑・𝐄𝐍𝐂𝐎𝐍𝐓𝐑𝐀𝐃𝐎"),
                (
                    f"{EMOJI_ADM} 𝐌𝐞𝐝𝐢𝐚𝐝𝐨𝐫: {interaction.user.mention}\n"
                    f"{EMOJI_ADM} 𝐉𝐨𝐠𝐚𝐝𝐨𝐫𝐞𝐬: <@{bet['player1_id']}> vs <@{bet['player2_id']}>\n"
                    f"{EMOJI_FF} 𝐌𝐨𝐝𝐨: **{bet['kind']} {pretty_mode(bet['mode'])}**\n"
                    f"{EMOJI_REEMBOLSO} 𝐕𝐚𝐥𝐨𝐫: **{cents_to_money(bet['value_cents'])}**"
                ),
            ),
            view=self,
        )

        confirm_channel = interaction.guild.get_channel(bet["queue_channel_id"]) if bet["queue_channel_id"] else None
        if confirm_channel:
            await confirm_channel.send(
                embed=red_embed(
                    styled_title(f"{EMOJI_ADM} 𝐌𝐄𝐃𝐈𝐀𝐃𝐎𝐑・𝐄𝐍𝐂𝐎𝐍𝐓𝐑𝐀𝐃𝐎"),
                    f"{interaction.user.mention} assumiu a aposta.\n{EMOJI_PIX} Criando canal de pagamento...",
                )
            )
            await asyncio.sleep(2)

        await create_payment_channel(interaction.guild, bet)
        if confirm_channel:
            try:
                await confirm_channel.delete(reason="Mediador assumiu e pagamento foi criado")
            except discord.HTTPException:
                pass


async def create_payment_channel(guild: discord.Guild, bet: sqlite3.Row) -> None:
    settings = store.settings(guild.id)
    counter = store.next_counter(guild.id, "payment_counter")
    category = guild.get_channel(settings["payment_category_id"]) if settings["payment_category_id"] else None
    admin = guild.get_member(bet["admin_id"])
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
    }
    if admin:
        overwrites[admin] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    staff_role = guild.get_role(settings["staff_role_id"]) if settings["staff_role_id"] else None
    if staff_role:
        overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    try:
        owner_role_id = settings["owner_role_id"]
    except (IndexError, KeyError):
        owner_role_id = None
    if owner_role_id:
        owner_role = guild.get_role(owner_role_id)
        if owner_role:
            overwrites[owner_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    for user_id in [bet["player1_id"], bet["player2_id"]]:
        member = guild.get_member(user_id)
        if member:
            overwrites[member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
    channel = await guild.create_text_channel(f"pagamento-{counter:04d}", category=category, overwrites=overwrites)
    store.update_bet(bet["id"], payment_channel_id=channel.id, status="payment")
    await channel.send(
        content=f"<@{bet['player1_id']}> <@{bet['player2_id']}> <@{bet['admin_id']}>",
        embed=payment_wait_embed(bet),
        view=PaymentView(bet["id"]),
    )


def payment_wait_embed(bet: sqlite3.Row) -> discord.Embed:
    return red_embed(
        styled_title(f"{EMOJI_PIX} 𝐏𝐀𝐆𝐀𝐌𝐄𝐍𝐓𝐎"),
        (
            f"{EMOJI_ADM} 𝐌𝐞𝐝𝐢𝐚𝐝𝐨𝐫: <@{bet['admin_id']}>\n"
            f"{EMOJI_ADM} 𝐉𝐨𝐠𝐚𝐝𝐨𝐫𝐞𝐬: <@{bet['player1_id']}> vs <@{bet['player2_id']}>\n"
            f"{EMOJI_PIX} 𝐕𝐚𝐥𝐨𝐫: {cents_to_money(bet['value_cents'])}\n"
            f"{EMOJI_PIX} 𝐏𝐈𝐗: aguardando liberação pelo ADM\n"
            "📧 𝐑𝐞𝐬𝐮𝐥𝐭𝐚𝐝𝐨: envie o print após a partida"
        ),
    )


class PaymentView(discord.ui.View):
    def __init__(self, bet_id: int):
        super().__init__(timeout=None)
        self.bet_id = bet_id

    @discord.ui.button(label="Liberar Pix", emoji=EMOJI_PIX, style=discord.ButtonStyle.secondary, custom_id="pay_release_pix")
    async def release_pix(self, interaction: discord.Interaction, button: discord.ui.Button):
        bet = store.bet(self.bet_id)
        if not bet:
            await interaction.response.send_message("Aposta não encontrada.", ephemeral=True)
            return
        if interaction.user.id != bet["admin_id"]:
            await interaction.response.send_message("Somente o ADM responsável pode liberar o Pix.", ephemeral=True)
            return
        pix = store.get_pix(interaction.guild_id, bet["admin_id"])
        if not pix:
            await interaction.response.send_message("Você (ADM) não tem Pix cadastrado. Use `/admconfig` para cadastrar.", ephemeral=True)
            return
        total = bet["value_cents"] + bet["fee_cents"]
        pix_code = pix_copy_code(pix["pix_key"], pix["name"], total, f"APOSTA{bet['id']}")
        file = make_qr_file(pix_code)
        embed = red_embed(
            f"⟦ {EMOJI_PIX} 𝐏𝐈𝐗 𝐋𝐈𝐁𝐄𝐑𝐀𝐃𝐎 ⟧",
            (
                f"<:staff:1516913606795464805> 𝐑𝐞𝐜𝐞𝐛𝐞𝐝𝐨𝐫: {pix['name']}\n"
                f"{EMOJI_PIX} 𝐕𝐚𝐥𝐨𝐫: {cents_to_money(total)}\n"
                f"{EMOJI_PIX} 𝐂𝐡𝐚𝐯𝐞 𝐏𝐈𝐗: `{pix['pix_key']}`\n\n"
                "<:pix:1516913599988105378> Escaneie o QR Code ou use os botões abaixo."
            ),
        )
        embed.set_image(url="attachment://pix-qrcode.png")
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message("⟦ ✅ 𝐂𝐇𝐀𝐕𝐄 𝐏𝐈𝐗 𝐋𝐈𝐁𝐄𝐑𝐀𝐃𝐀 ⟧\nUse `/apostas` no canal da aposta para gerenciar.", ephemeral=True)
        await interaction.channel.send(embed=embed, file=file, view=PixCopyView(pix["pix_key"], pix_code))


class PixCopyView(discord.ui.View):
    def __init__(self, pix_key: str, full_code: str):
        super().__init__(timeout=None)
        self.pix_key = pix_key
        self.full_code = full_code

    @discord.ui.button(label="Copiar chave PIX", emoji=EMOJI_PIX, style=discord.ButtonStyle.secondary, custom_id="pix_copy_key")
    async def key(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"⟦ <:pix:1516913599988105378> 𝐂𝐇𝐀𝐕𝐄 𝐏𝐈𝐗 ⟧\n`{self.pix_key}`", ephemeral=True)

    @discord.ui.button(label="Copiar código completo", emoji=EMOJI_PIX, style=discord.ButtonStyle.secondary, custom_id="pix_copy_full")
    async def full(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"⟦ <:pix:1516913599988105378> 𝐂𝐎́𝐃𝐈𝐆𝐎 𝐏𝐈𝐗 ⟧\n```text\n{self.full_code}\n```", ephemeral=True)


async def close_bet_channel(channel: discord.abc.Messageable, bet_id: int, winner_id: Optional[int]) -> None:
    bet = store.bet(bet_id)
    if not bet:
        return
    store.update_bet(bet_id, status="closed")
    guild = channel.guild
    if winner_id:
        winner = guild.get_member(winner_id)
        if winner:
            try:
                await winner.send(
                    "⟦ <a:ganhador:1516913568639877140> 𝐕𝐈𝐓𝐎́𝐑𝐈𝐀 𝐂𝐎𝐍𝐅𝐈𝐑𝐌𝐀𝐃𝐀 ⟧\n"
                    f"{winner.mention}, parabéns. Você venceu a aposta.\n\n"
                    f"<:free_fire:1516913587967361055> 𝐌𝐨𝐝𝐨: {bet['kind']} {pretty_mode(bet['mode'])}\n"
                    f"<:preco_dinheiro:1516919186046058658> 𝐕𝐚𝐥𝐨𝐫: {cents_to_money(bet['value_cents'])}\n"
                    f"<:staff:1516913606795464805> 𝐀𝐝𝐯𝐞𝐫𝐬𝐚́𝐫𝐢𝐨: <@{bet['player2_id'] if winner_id == bet['player1_id'] else bet['player1_id']}>\n\n"
                    "<a:sucesso_animado:1516913609303658506> Resultado registrado com sucesso."
                )
            except discord.HTTPException:
                pass
    admin = guild.get_member(bet["admin_id"]) if bet["admin_id"] else None
    if admin:
        try:
            await admin.send(
                "⟦ <:staff:1516913606795464805> OBRIGADO, ADM ⟧\n"
                f"{admin.mention}, você fez um ótimo trabalho nessa aposta.\n\n"
                "<a:sucesso_animado:1516913609303658506> Obrigado por ajudar a manter tudo organizado.\n"
                "📧 Agora você está livre para gerenciar uma nova aposta."
            )
        except discord.HTTPException:
            pass
    for n in range(5, 0, -1):
        await channel.send(f"<:relogio:1516913566253580470> Encerrando em {n}...")
        await asyncio.sleep(1)
    await channel.delete(reason="Aposta encerrada")


class PixModal(discord.ui.Modal, title="Cadastrar Pix"):
    name = discord.ui.TextInput(label="Nome", placeholder="Ex: Mikae", max_length=80)
    key = discord.ui.TextInput(label="Chave Pix", placeholder="CPF, email, telefone ou chave aleatoria", max_length=160)

    def __init__(self, update_adm_panel: bool = False):
        super().__init__()
        self.update_adm_panel = update_adm_panel

    async def on_submit(self, interaction: discord.Interaction):
        store.save_pix(interaction.guild_id, interaction.user.id, str(self.name), str(self.key))
        file = make_qr_file(str(self.key))
        embed = red_embed(
            f"⟦ {EMOJI_PIX} 𝐏𝐈𝐗 𝐂𝐀𝐃𝐀𝐒𝐓𝐑𝐀𝐃𝐎 ⟧",
            f"Seu Pix foi salvo com sucesso.\n{EMOJI_PIX} Esse é seu Pix: `{self.key}`",
        )
        embed.set_image(url="attachment://pix-qrcode.png")
        if self.update_adm_panel:
            await interaction.response.edit_message(embed=adm_config_embed(interaction.guild_id, interaction.user), view=AdmConfigView())
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            return
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)


def adm_config_embed(guild_id: int, user: discord.Member) -> discord.Embed:
    pix = store.get_pix(guild_id, user.id)
    pix_status = "Cadastrado" if pix else "Nao cadastrado"
    return red_embed(
        styled_title(f"{EMOJI_ADM} 𝐏𝐀𝐈𝐍𝐄𝐋・𝐀𝐃𝐌"),
        (
            f"{EMOJI_ADM} 𝐀𝐃𝐌: {user.mention}\n"
            f"{EMOJI_PIX} 𝐏𝐢𝐱: **{pix_status}**\n\n"
            f"{EMOJI_ADM} 𝐀𝐬 𝐚𝐩𝐨𝐬𝐭𝐚𝐬 𝐬𝐚̃𝐨 𝐚𝐬𝐬𝐮𝐦𝐢𝐝𝐚𝐬 𝐩𝐞𝐥𝐨 𝐛𝐨𝐭𝐚̃𝐨 **𝐀𝐬𝐬𝐮𝐦𝐢𝐫 𝐀𝐩𝐨𝐬𝐭𝐚**."
        ),
    )


class AdmConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    async def _check_admin(self, interaction: discord.Interaction) -> bool:
        if isinstance(interaction.user, discord.Member) and (is_admin_member(interaction.user) or is_owner_member(interaction.user)):
            return True
        await interaction.response.send_message("Somente ADM pode usar este painel.", ephemeral=True)
        return False

    @discord.ui.button(label="Ver Pix", emoji=EMOJI_PIX, style=discord.ButtonStyle.secondary)
    async def view_pix(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_admin(interaction):
            return
        pix = store.get_pix(interaction.guild_id, interaction.user.id)
        if not pix:
            await interaction.response.send_message(f"⟦ {EMOJI_PIX} SEU PIX ⟧\nVoce ainda nao cadastrou um Pix.", ephemeral=True)
            return
        text = f"{EMOJI_VERIFICADO} Nome: {pix['name']}\n{EMOJI_PIX} Chave: `{pix['pix_key']}`"
        await interaction.response.send_message(embed=red_embed(f"⟦ {EMOJI_PIX} SEU PIX ⟧", text), ephemeral=True)

    @discord.ui.button(label="Cadastrar Pix", emoji=EMOJI_PIX, style=discord.ButtonStyle.secondary)
    async def register_pix(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_admin(interaction):
            return
        await interaction.response.send_modal(PixModal(update_adm_panel=True))

    @discord.ui.button(label="Remover Pix", emoji=EMOJI_X, style=discord.ButtonStyle.secondary)
    async def remove_pix(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_admin(interaction):
            return
        store.remove_pix(interaction.guild_id, interaction.user.id)
        await interaction.response.edit_message(embed=adm_config_embed(interaction.guild_id, interaction.user), view=AdmConfigView())


class CreateQueueModal(discord.ui.Modal, title="Criar Fila"):
    mode = discord.ui.TextInput(label="Modalidade", placeholder="gel, mobile, emulador ou misto")
    kind = discord.ui.TextInput(label="Tipo", placeholder="1v1, 2v2, 3v3 ou 4v4")
    value = discord.ui.TextInput(label="Valor", placeholder="Ex: 10,50")
    fee = discord.ui.TextInput(label="Taxa", placeholder="Ex: 0,40")
    image = discord.ui.TextInput(label="URL imagem/GIF opcional", placeholder="https://site.com/imagem.gif", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            kind = pretty_type(str(self.kind))
            mode = normalize_word(str(self.mode))
            validate_kind_mode(kind, mode)
            queue_id = store.create_queue(
                interaction.guild_id,
                interaction.channel_id,
                kind,
                mode,
                money_to_cents(str(self.value)),
                money_to_cents(str(self.fee)),
                valid_image_url(str(self.image)),
            )
            queue = store.queue(queue_id)
            message = await interaction.channel.send(embed=queue_embed(queue), view=QueueView(queue_id, kind, mode))
            store.set_queue_message(queue_id, message.id)
            await interaction.response.send_message("⟦ ✅ 𝐅𝐈𝐋𝐀 𝐂𝐑𝐈𝐀𝐃𝐀 ⟧", ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(f"⟦ ⚠️ 𝐄𝐑𝐑𝐎 ⟧\n{exc}", ephemeral=True)


class CreateManyQueuesModal(discord.ui.Modal, title="Criar Filas em Massa"):
    kind = discord.ui.TextInput(label="Tipo", placeholder="1v1, 2v2, 3v3 ou 4v4")
    modes = discord.ui.TextInput(label="Modos", placeholder="gel,mobile,emulador,misto")
    values = discord.ui.TextInput(label="Valores", placeholder="100,50,20,10,5,3,2,1,0.50,0.40")
    fee = discord.ui.TextInput(label="Taxa", placeholder="0.40")
    image = discord.ui.TextInput(label="URL imagem/GIF opcional", placeholder="https://site.com/imagem.gif", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            kind = pretty_type(str(self.kind))
            modes = [normalize_word(m) for m in str(self.modes).split(",") if m.strip()]
            values = split_values(str(self.values))
            fee = money_to_cents(str(self.fee))
            image_url = valid_image_url(str(self.image))
            if not modes or not values:
                raise ValueError("Informe pelo menos um modo e um valor.")
            created = 0
            await interaction.response.defer(ephemeral=True)
            for mode in modes:
                validate_kind_mode(kind, mode)
                for value in values:
                    queue_id = store.create_queue(interaction.guild_id, interaction.channel_id, kind, mode, value, fee, image_url)
                    queue = store.queue(queue_id)
                    message = await interaction.channel.send(embed=queue_embed(queue), view=QueueView(queue_id, kind, mode))
                    store.set_queue_message(queue_id, message.id)
                    created += 1
            await interaction.followup.send(f"⟦ ✅ 𝐅𝐈𝐋𝐀𝐒 𝐂𝐑𝐈𝐀𝐃𝐀𝐒 ⟧\nTotal: {created}", ephemeral=True)
        except Exception as exc:
            if interaction.response.is_done():
                await interaction.followup.send(f"⟦ ⚠️ 𝐄𝐑𝐑𝐎 ⟧\n{exc}", ephemeral=True)
            else:
                await interaction.response.send_message(f"⟦ ⚠️ 𝐄𝐑𝐑𝐎 ⟧\n{exc}", ephemeral=True)


def queue_panel_embed(guild_id: int) -> discord.Embed:
    channels = store.queue_panel_channels(guild_id)
    cfg = store.queue_panel_values(guild_id)
    lines = []
    for slot_key, label, _kind, _mode in QUEUE_PANEL_SLOTS:
        channel_id = channels.get(slot_key)
        status = EMOJI_V if channel_id else EMOJI_X
        channel = f"<#{channel_id}>" if channel_id else "Nao definido"
        lines.append(f"{status} **{label}:** {channel}")
    description = (
        f"{EMOJI_PIX} **Valores:** `{cfg['values_text']}`\n"
        f"<:pix:1516913599988105378> **Taxa:** {cents_to_money(cfg['fee_cents'])}\n"
        f"<:salas:1516920962258305075> **Imagem:** {cfg['image_url'] or 'Nao definida'}\n\n"
        + "\n".join(lines)
    )
    return red_embed(f"⟦ {EMOJI_VERIFICADO} CONFIG FILAS ⟧", description)


async def check_queue_panel_owner(interaction: discord.Interaction) -> bool:
    if isinstance(interaction.user, discord.Member) and is_owner_member(interaction.user):
        return True
    await interaction.response.send_message("Somente Donos podem mexer neste painel.", ephemeral=True)
    return False


class QueuePanelView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        for slot_key, label, _kind, mode in QUEUE_PANEL_SLOTS:
            emoji = EMOJI_EMU if mode in {"emulador", "misto"} else EMOJI_V
            self.add_item(QueuePanelSlotButton(guild_id, slot_key, label, emoji))
        self.add_item(QueuePanelValuesButton(guild_id))
        self.add_item(QueuePanelCreateButton(guild_id))
        self.add_item(QueuePanelDeleteButton(guild_id))


class QueuePanelSlotButton(discord.ui.Button):
    def __init__(self, guild_id: int, slot_key: str, label: str, emoji: str):
        super().__init__(label=label, emoji=emoji, style=discord.ButtonStyle.secondary)
        self.guild_id = guild_id
        self.slot_key = slot_key
        self.slot_label = label

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await check_queue_panel_owner(interaction):
            return
        await interaction.response.edit_message(
            content=f"Selecione o canal para **{self.slot_label}**:",
            embed=queue_panel_embed(self.guild_id),
            view=QueuePanelChannelView(self.guild_id, self.slot_key),
        )


class QueuePanelChannelView(discord.ui.View):
    def __init__(self, guild_id: int, slot_key: str):
        super().__init__(timeout=120)
        self.add_item(QueuePanelChannelSelect(guild_id, slot_key))
        self.add_item(QueuePanelBackButton(guild_id))


class QueuePanelChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, guild_id: int, slot_key: str):
        super().__init__(
            placeholder="Selecione o canal da fila",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
        )
        self.guild_id = guild_id
        self.slot_key = slot_key

    async def callback(self, interaction: discord.Interaction):
        if not await check_queue_panel_owner(interaction):
            return
        channel = self.values[0]
        store.set_queue_panel_channel(self.guild_id, self.slot_key, channel.id)
        await interaction.response.edit_message(
            content=None,
            embed=queue_panel_embed(self.guild_id),
            view=QueuePanelView(self.guild_id),
        )


class QueuePanelBackButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Voltar", emoji=EMOJI_SAIR, style=discord.ButtonStyle.secondary)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await check_queue_panel_owner(interaction):
            return
        await interaction.response.edit_message(
            content=None,
            embed=queue_panel_embed(self.guild_id),
            view=QueuePanelView(self.guild_id),
        )


class QueuePanelValuesButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Configurar valores", emoji=EMOJI_PIX, style=discord.ButtonStyle.secondary)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await check_queue_panel_owner(interaction):
            return
        await interaction.response.send_modal(QueuePanelValuesModal(self.guild_id))


class QueuePanelValuesModal(discord.ui.Modal, title="Configurar Filas"):
    values = discord.ui.TextInput(label="Valores", placeholder="100,50,20,10,5,3,2,1,0.50", max_length=300)
    fee = discord.ui.TextInput(label="Taxa", placeholder="0,40", max_length=20)
    image = discord.ui.TextInput(label="URL imagem/GIF", placeholder="https://site.com/imagem.gif", required=False, max_length=300)

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not is_owner_member(interaction.user):
            await interaction.response.send_message("Somente Donos podem configurar filas.", ephemeral=True)
            return
        try:
            values_text = str(self.values).strip()
            if not split_values(values_text):
                raise ValueError("Informe pelo menos um valor.")
            fee_cents = money_to_cents(str(self.fee))
            image_url = valid_image_url(str(self.image))
            store.set_queue_panel_values(self.guild_id, values_text, fee_cents, image_url)
            await interaction.response.send_message(
                embed=queue_panel_embed(self.guild_id),
                view=QueuePanelView(self.guild_id),
                ephemeral=True,
            )
        except Exception as exc:
            await interaction.response.send_message(f"⟦ ⚠️ ERRO ⟧\n{exc}", ephemeral=True)


class QueuePanelCreateButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Criar filas", emoji=EMOJI_V, style=discord.ButtonStyle.secondary)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await check_queue_panel_owner(interaction):
            return
        channels = store.queue_panel_channels(self.guild_id)
        cfg = store.queue_panel_values(self.guild_id)
        values = split_values(cfg["values_text"])
        if not channels:
            await interaction.response.send_message("Configure pelo menos um canal antes de criar as filas.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        created = 0
        for slot_key, _label, kind, mode in QUEUE_PANEL_SLOTS:
            channel_id = channels.get(slot_key)
            if not channel_id:
                continue
            channel = interaction.guild.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await interaction.guild.fetch_channel(channel_id)
                except discord.HTTPException:
                    continue
            for value_cents in values:
                queue_id = store.create_queue(self.guild_id, channel.id, kind, mode, value_cents, cfg["fee_cents"], cfg["image_url"])
                queue = store.queue(queue_id)
                message = await channel.send(embed=queue_embed(queue), view=QueueView(queue_id, kind, mode))
                store.set_queue_message(queue_id, message.id)
                store.add_queue_panel_message(self.guild_id, slot_key, queue_id, channel.id, message.id)
                created += 1
        await interaction.followup.send(f"⟦ {EMOJI_V} FILAS CRIADAS ⟧\nTotal: **{created}** filas.", ephemeral=True)


class QueuePanelDeleteButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Excluir filas", emoji=EMOJI_X, style=discord.ButtonStyle.secondary)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await check_queue_panel_owner(interaction):
            return
        rows = store.queue_panel_messages(self.guild_id)
        if not rows:
            await interaction.response.send_message("Nao existem filas criadas por este painel para excluir.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        deleted = 0
        for row in rows:
            store.close_queue(row["queue_id"])
            channel = interaction.guild.get_channel(row["channel_id"])
            if channel is None:
                try:
                    channel = await interaction.guild.fetch_channel(row["channel_id"])
                except discord.HTTPException:
                    continue
            try:
                message = await channel.fetch_message(row["message_id"])
                await message.delete()
                deleted += 1
            except discord.HTTPException:
                pass
        store.clear_queue_panel_messages(self.guild_id)
        await interaction.followup.send(f"⟦ {EMOJI_X} FILAS EXCLUIDAS ⟧\nMensagens apagadas: **{deleted}**.", ephemeral=True)


def validate_kind_mode(kind: str, mode: str) -> None:
    if kind not in {"1v1", "2v2", "3v3", "4v4"}:
        raise ValueError("Tipo inválido. Use 1v1, 2v2, 3v3 ou 4v4.")
    if mode not in {"gel", "mobile", "emulador", "misto"}:
        raise ValueError("Modo inválido. Use gel, mobile, emulador ou misto.")
    if kind == "1v1" and mode == "misto":
        raise ValueError("Misto não pode ser usado em filas 1v1. Escolha 2v2, 3v3 ou 4v4.")


def is_owner_member(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    if member.id == member.guild.owner_id:
        return True
    settings = store.settings(member.guild.id)
    try:
        role_id = settings["owner_role_id"]
    except (IndexError, KeyError):
        role_id = None
    return bool(role_id and any(role.id == role_id for role in member.roles))


def is_admin_member(member: discord.Member) -> bool:
    # ADM só serve para /admconfig (sorteio de filas)
    settings = store.settings(member.guild.id)
    role_id = settings["admin_role_id"]
    return bool(role_id and any(role.id == role_id for role in member.roles))


class ConfigView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    @discord.ui.button(label="Canal de Alertas", emoji=EMOJI_VERIFICADO, style=discord.ButtonStyle.secondary)
    async def alert_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⟦ <a:alerta_staff_animado:1516913572280533063> 𝐂𝐀𝐍𝐀𝐋 𝐃𝐄 𝐀𝐋𝐄𝐑𝐓𝐀𝐒 ⟧\nSelecione o canal:", view=TextChannelPickView("alert_channel_id"), ephemeral=True)

    @discord.ui.button(label="Cargo Dono", emoji=EMOJI_VERIFICADO, style=discord.ButtonStyle.secondary)
    async def owner_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⟦ <:staff:1516913606795464805> 𝐂𝐀𝐑𝐆𝐎 𝐃𝐎𝐍𝐎 ⟧", view=RolePickView("owner_role_id"), ephemeral=True)

    @discord.ui.button(label="Cargo ADM", emoji=EMOJI_VERIFICADO, style=discord.ButtonStyle.secondary)
    async def admin_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⟦ <:staff:1516913606795464805> 𝐂𝐀𝐑𝐆𝐎 𝐀𝐃𝐌 ⟧", view=RolePickView("admin_role_id"), ephemeral=True)

    @discord.ui.button(label="Cargo Staff", emoji=EMOJI_VERIFICADO, style=discord.ButtonStyle.secondary)
    async def staff_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⟦ <:staff:1516913606795464805> 𝐂𝐀𝐑𝐆𝐎 𝐒𝐓𝐀𝐅𝐅 ⟧", view=RolePickView("staff_role_id"), ephemeral=True)

    @discord.ui.button(label="Categoria Filas", emoji=EMOJI_EMU, style=discord.ButtonStyle.secondary)
    async def queue_cat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⟦ <:config:1516913563531215009> 𝐂𝐀𝐓𝐄𝐆𝐎𝐑𝐈𝐀 𝐅𝐈𝐋𝐀𝐒 ⟧", view=CategoryPickView("queue_category_id"), ephemeral=True)

    @discord.ui.button(label="Categoria Pagamentos", emoji=EMOJI_PIX, style=discord.ButtonStyle.secondary)
    async def pay_cat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⟦ <:config:1516913563531215009> 𝐂𝐀𝐓𝐄𝐆𝐎𝐑𝐈𝐀 𝐏𝐀𝐆𝐀𝐌𝐄𝐍𝐓𝐎𝐒 ⟧", view=CategoryPickView("payment_category_id"), ephemeral=True)

    @discord.ui.button(label="Setup Pix", emoji=EMOJI_PIX, style=discord.ButtonStyle.secondary)
    async def setup_pix(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not is_owner_member(interaction.user):
            await interaction.response.send_message("Somente Donos podem gerenciar os Pix cadastrados.", ephemeral=True)
            return
        rows = store.all_pix(interaction.guild_id)
        text = "\n\n".join(f"<@{r['user_id']}>\n{EMOJI_VERIFICADO} Nome: {r['name']}\n{EMOJI_PIX} Chave: `{r['pix_key']}`" for r in rows) or "Nenhum Pix cadastrado."
        await interaction.response.send_message(embed=red_embed(f"⟦ {EMOJI_PIX} 𝐒𝐄𝐓𝐔𝐏 𝐏𝐈𝐗 ⟧", text), view=PixSetupView(interaction.guild_id), ephemeral=True)

    @discord.ui.button(label="Ativar/Desativar Apostas", emoji=EMOJI_X, style=discord.ButtonStyle.secondary)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = store.settings(interaction.guild_id)
        new = 0 if settings["bets_enabled"] else 1
        store.update_setting(interaction.guild_id, "bets_enabled", new)
        msg = (
            "⟦ <:online:1516915759790559315> 𝐀𝐏𝐎𝐒𝐓𝐀𝐒 𝐀𝐓𝐈𝐕𝐀𝐃𝐀𝐒 ⟧\nAs filas foram liberadas novamente."
            if new
            else "⟦ <:offline:1516915772922794015> 𝐀𝐏𝐎𝐒𝐓𝐀𝐒 𝐃𝐄𝐒𝐀𝐓𝐈𝐕𝐀𝐃𝐀𝐒 ⟧\nAs filas foram pausadas. Ninguém poderá entrar até ativar novamente."
        )
        await interaction.response.edit_message(embed=config_embed(interaction.guild_id), view=ConfigView(interaction.guild_id))
        await interaction.followup.send(msg, ephemeral=True)

    @discord.ui.button(label="Divulgar Apostas", emoji=EMOJI_VERIFICADO, style=discord.ButtonStyle.secondary)
    async def divulgar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "⟦ <:divulgacao:1516913611304603842> 𝐃𝐈𝐕𝐔𝐋𝐆𝐀𝐑 ⟧\nSelecione o canal onde deseja divulgar:",
            view=DivulgarChannelView(),
            ephemeral=True,
        )


class PixDeleteSelect(discord.ui.Select):
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        rows = store.all_pix(guild_id)
        options = [
            discord.SelectOption(
                label=str(row["name"])[:100],
                description=f"Usuário: {row['user_id']}",
                value=str(row["user_id"]),
                emoji=EMOJI_PIX,
            )
            for row in rows[:25]
        ]
        super().__init__(placeholder="Selecione o Pix que deseja excluir", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not is_owner_member(interaction.user):
            await interaction.response.send_message("Somente Donos podem excluir Pix.", ephemeral=True)
            return
        user_id = int(self.values[0])
        pix = store.get_pix(self.guild_id, user_id)
        if not pix:
            await interaction.response.send_message("Esse Pix já foi removido.", ephemeral=True)
            return
        store.remove_pix(self.guild_id, user_id)
        await interaction.response.edit_message(
            content=f"{EMOJI_V} Pix de <@{user_id}> removido com sucesso.",
            embed=None,
            view=None,
        )


class PixDeleteView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=120)
        self.add_item(PixDeleteSelect(guild_id))


class PixSetupView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    @discord.ui.button(label="Excluir Pix", emoji=EMOJI_X, style=discord.ButtonStyle.danger)
    async def delete_pix(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not is_owner_member(interaction.user):
            await interaction.response.send_message("Somente Donos podem excluir Pix.", ephemeral=True)
            return
        if not store.all_pix(self.guild_id):
            await interaction.response.send_message("Não há Pix cadastrado para excluir.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Selecione o usuário cujo Pix será removido:",
            view=PixDeleteView(self.guild_id),
            ephemeral=True,
        )


class DivulgarChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(DivulgarChannelSelect())


class DivulgarChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="Selecione o canal de avisos",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        resolved = interaction.guild.get_channel(channel.id)
        if not resolved:
            await interaction.response.send_message("Canal não encontrado.", ephemeral=True)
            return
        await resolved.send("@everyone @here\n# <:free_fire:1516913587967361055> FILAS ABERTAS\nVenha apostar! <:pix:1516913599988105378>")
        await interaction.response.send_message(f"⟦ ✅ 𝐃𝐈𝐕𝐔𝐋𝐆𝐀𝐃𝐎 ⟧\nMensagem enviada em {resolved.mention}.", ephemeral=True)


class RolePickView(discord.ui.View):
    def __init__(self, field: str):
        super().__init__(timeout=120)
        self.add_item(RoleSelect(field))


class RoleSelect(discord.ui.RoleSelect):
    def __init__(self, field: str):
        super().__init__(placeholder="Selecione um cargo", min_values=1, max_values=1)
        self.field = field

    async def callback(self, interaction: discord.Interaction):
        role = self.values[0]
        store.update_setting(interaction.guild_id, self.field, role.id)
        await interaction.response.send_message(f"⟦ ✅ 𝐒𝐀𝐋𝐕𝐎 ⟧\nCargo definido como {role.mention}.", ephemeral=True)


class CategoryPickView(discord.ui.View):
    def __init__(self, field: str):
        super().__init__(timeout=120)
        self.add_item(CategorySelect(field))


class CategorySelect(discord.ui.ChannelSelect):
    def __init__(self, field: str):
        super().__init__(
            placeholder="Selecione uma categoria",
            channel_types=[discord.ChannelType.category],
            min_values=1,
            max_values=1,
        )
        self.field = field

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        store.update_setting(interaction.guild_id, self.field, category.id)
        await interaction.response.send_message(f"⟦ ✅ 𝐒𝐀𝐋𝐕𝐎 ⟧\nCategoria definida como {category.name}.", ephemeral=True)


class TextChannelPickView(discord.ui.View):
    def __init__(self, field: str):
        super().__init__(timeout=120)
        self.add_item(TextChannelSelect(field))


class TextChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, field: str):
        super().__init__(
            placeholder="Selecione um canal de texto",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
        )
        self.field = field

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        store.update_setting(interaction.guild_id, self.field, channel.id)
        await interaction.response.send_message(f"⟦ ✅ 𝐒𝐀𝐋𝐕𝐎 ⟧\nCanal definido como {channel.mention}.", ephemeral=True)


def config_embed(guild_id: int) -> discord.Embed:
    s = store.settings(guild_id)
    try:
        owner_role = f"<@&{s['owner_role_id']}>" if s["owner_role_id"] else "Nao definido"
    except (IndexError, KeyError):
        owner_role = "Nao definido"
    admin_role = f"<@&{s['admin_role_id']}>" if s["admin_role_id"] else "Nao definido"
    staff_role = f"<@&{s['staff_role_id']}>" if s["staff_role_id"] else "Nao definido"
    queue_category = f"<#{s['queue_category_id']}>" if s["queue_category_id"] else "Nao definida"
    payment_category = f"<#{s['payment_category_id']}>" if s["payment_category_id"] else "Nao definida"
    try:
        alert_channel = f"<#{s['alert_channel_id']}>" if s["alert_channel_id"] else "Nao definido"
    except (IndexError, KeyError):
        alert_channel = "Nao definido"
    return red_embed(
        f"⟦ {EMOJI_VERIFICADO} PAINEL DE CONFIG ⟧",
        (
            f"{EMOJI_VERIFICADO} **Cargo Dono:** {owner_role}\n"
            f"{EMOJI_VERIFICADO} **Cargo ADM:** {admin_role}\n"
            f"{EMOJI_VERIFICADO} **Cargo Staff:** {staff_role}\n"
            f"{EMOJI_EMU} **Categoria Filas:** {queue_category}\n"
            f"{EMOJI_PIX} **Categoria Pagamentos:** {payment_category}\n"
            f"{EMOJI_VERIFICADO} **Canal de Alertas:** {alert_channel}\n"
            f"{EMOJI_PIX} **Pix Cadastrados:** {len(store.all_pix(guild_id))}\n"
            f"{EMOJI_V if s['bets_enabled'] else EMOJI_X} **Apostas:** {'Ativadas' if s['bets_enabled'] else 'Desativadas'}"
        ),
    )


class BetConfigSelect(discord.ui.Select):
    def __init__(self, bet_id: int):
        self.bet_id = bet_id
        super().__init__(
            placeholder="Selecione uma função",
            options=[
                discord.SelectOption(label="Definir ganhador", emoji="<a:ganhador:1516913568639877140>", value="winner"),
                discord.SelectOption(label="Finalizar por WO", emoji="<:ranking_trofeu:1516913603863908373>", value="wo"),
                discord.SelectOption(label="Marcar empate", emoji="<a:atualizar:1516913555276955778>", value="draw"),
                discord.SelectOption(label="Enviar dados da sala", emoji="<:free_fire:1516913587967361055>", value="room"),
                discord.SelectOption(label="Renomear canal", emoji="<:editar:1516913582070304768>", value="rename"),
                discord.SelectOption(label="Encerrar aposta", emoji="<a:erro_animado:1516913586054631558>", value="close"),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        bet = store.bet(self.bet_id)
        if value == "winner":
            await interaction.response.send_message(embed=winner_embed(bet, "⟦ <a:ganhador:1516913568639877140> 𝐃𝐄𝐅𝐈𝐍𝐈𝐑 𝐆𝐀𝐍𝐇𝐀𝐃𝐎𝐑 ⟧"), view=PickWinnerView(self.bet_id, "winner"), ephemeral=True)
        elif value == "wo":
            await interaction.response.send_message(embed=winner_embed(bet, "⟦ <:ranking_trofeu:1516913603863908373> 𝐅𝐈𝐍𝐀𝐋𝐈𝐙𝐀𝐑 𝐏𝐎𝐑 𝐖𝐎 ⟧"), view=PickWinnerView(self.bet_id, "wo"), ephemeral=True)
        elif value == "draw":
            await interaction.response.send_message(embed=draw_embed(bet), view=DrawCloseView(self.bet_id), ephemeral=False)
        elif value == "room":
            await interaction.response.send_modal(RoomModal(self.bet_id))
        elif value == "rename":
            await interaction.response.send_modal(RenameModal())
        elif value == "close":
            await interaction.response.send_message("⟦ <a:erro_animado:1516913586054631558> 𝐀𝐏𝐎𝐒𝐓𝐀 𝐄𝐍𝐂𝐄𝐑𝐑𝐀𝐃𝐀 ⟧\nEncerrada com sucesso.")
            await close_bet_channel(interaction.channel, self.bet_id, winner_id=None)


class BetConfigView(discord.ui.View):
    def __init__(self, bet_id: int):
        super().__init__(timeout=300)
        self.add_item(BetConfigSelect(bet_id))


def bet_panel_embed(bet: sqlite3.Row) -> discord.Embed:
    return red_embed(
        "⟦ <:config:1516913563531215009> 𝐏𝐀𝐈𝐍𝐄𝐋 𝐃𝐀 𝐀𝐏𝐎𝐒𝐓𝐀 ⟧",
        (
            "Gerencie esta partida pelo menu abaixo.\n\n"
            f"<:staff:1516913606795464805> 𝐉𝐨𝐠𝐚𝐝𝐨𝐫𝐞𝐬: <@{bet['player1_id']}> <:free_fire:1516913587967361055> <@{bet['player2_id']}>\n"
            f"<:preco_dinheiro:1516919186046058658> 𝐕𝐚𝐥𝐨𝐫: {cents_to_money(bet['value_cents'])}\n"
            f"<:free_fire:1516913587967361055> 𝐌𝐨𝐝𝐨: {bet['kind']} {pretty_mode(bet['mode'])}\n"
            f"<:verificar:1516913570120470559> 𝐒𝐭𝐚𝐭𝐮𝐬: {bet['status'].title()}"
        ),
    )


def winner_embed(bet: sqlite3.Row, title: str) -> discord.Embed:
    return red_embed(title, f"Selecione abaixo quem venceu.\n\n<a:ganhador:1516913568639877140> 𝐉𝐨𝐠𝐚𝐝𝐨𝐫 𝟏: <@{bet['player1_id']}>\n<a:ganhador:1516913568639877140> 𝐉𝐨𝐠𝐚𝐝𝐨𝐫 𝟐: <@{bet['player2_id']}>")


class PickWinnerView(discord.ui.View):
    def __init__(self, bet_id: int, mode: str):
        super().__init__(timeout=120)
        self.bet_id = bet_id
        self.mode = mode
        bet = store.bet(bet_id)
        self.add_item(WinnerButton(bet_id, bet["player1_id"], "Jogador 1", mode))
        self.add_item(WinnerButton(bet_id, bet["player2_id"], "Jogador 2", mode))


class WinnerButton(discord.ui.Button):
    def __init__(self, bet_id: int, user_id: int, label: str, mode: str):
        emoji = "<:ranking_trofeu:1516913603863908373>" if mode == "wo" else "<a:ganhador:1516913568639877140>"
        super().__init__(label=label, emoji=emoji, style=discord.ButtonStyle.success)
        self.bet_id = bet_id
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"⟦ <a:ganhador:1516913568639877140> 𝐕𝐄𝐍𝐂𝐄𝐃𝐎𝐑 𝐃𝐄𝐅𝐈𝐍𝐈𝐃𝐎 ⟧\n<@{self.user_id}> venceu a aposta.")
        await close_bet_channel(interaction.channel, self.bet_id, winner_id=self.user_id)


def draw_embed(bet: sqlite3.Row) -> discord.Embed:
    return red_embed(
        "⟦ <a:atualizar:1516913555276955778> 𝐄𝐌𝐏𝐀𝐓𝐄 𝐃𝐄𝐂𝐋𝐀𝐑𝐀𝐃𝐎 ⟧",
        (
            "O administrador marcou empate nesta partida.\n\n"
            f"<:staff:1516913606795464805> 𝐉𝐨𝐠𝐚𝐝𝐨𝐫 𝟏: <@{bet['player1_id']}>\n"
            f"<:staff:1516913606795464805> 𝐉𝐨𝐠𝐚𝐝𝐨𝐫 𝟐: <@{bet['player2_id']}>\n"
            f"<:preco_dinheiro:1516919186046058658> 𝐕𝐚𝐥𝐨𝐫: {cents_to_money(bet['value_cents'])}"
        ),
    )


class DrawCloseView(discord.ui.View):
    def __init__(self, bet_id: int):
        super().__init__(timeout=120)
        self.bet_id = bet_id

    @discord.ui.button(label="Finalizar e fechar canal", emoji="<a:erro_animado:1516913586054631558>", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⟦ ✅ 𝐄𝐌𝐏𝐀𝐓𝐄 𝐌𝐀𝐑𝐂𝐀𝐃𝐎 ⟧\nEmpate declarado com sucesso.", ephemeral=True)
        await close_bet_channel(interaction.channel, self.bet_id, winner_id=None)


class RoomModal(discord.ui.Modal, title="Enviar Sala"):
    room_id = discord.ui.TextInput(label="ID da sala", placeholder="Ex: 123456")
    password = discord.ui.TextInput(label="Senha", placeholder="Ex: 123", required=False)

    def __init__(self, bet_id: int):
        super().__init__()
        self.bet_id = bet_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=red_embed("⟦ <:free_fire:1516913587967361055> 𝐒𝐀𝐋𝐀 𝐃𝐀 𝐏𝐀𝐑𝐓𝐈𝐃𝐀 ⟧", f"<:salas:1516920962258305075> 𝐈𝐃: `{self.room_id}`\n<:computador:1516913579591340284> 𝐒𝐞𝐧𝐡𝐚: `{self.password or 'Sem senha'}`")
        )


class RenameModal(discord.ui.Modal, title="Renomear Canal"):
    new_name = discord.ui.TextInput(label="Novo nome do canal", placeholder="Ex: fila-vip")

    async def on_submit(self, interaction: discord.Interaction):
        new_name = ensure_channel_name(str(self.new_name))
        await interaction.channel.edit(name=new_name)
        await interaction.response.send_message(f"⟦ ✅ 𝐂𝐀𝐍𝐀𝐋 𝐑𝐄𝐍𝐎𝐌𝐄𝐀𝐃𝐎 ⟧\nNovo nome: `{new_name}`", ephemeral=True)


# ════════════════════════════════════════════════════════════════════════════
# SISTEMA DE TICKETS
# ════════════════════════════════════════════════════════════════════════════

TICKET_TOPICS = [
    discord.SelectOption(label="SUPORTE", emoji=EMOJI_SUPORTE, value="suporte", description="Atendimento geral e dúvidas."),
    discord.SelectOption(label="REEMBOLSO", emoji=EMOJI_REEMBOLSO, value="reembolso", description="Solicitar análise de reembolso."),
    discord.SelectOption(label="RECEBER EVENTO", emoji=EMOJI_EVENTO, value="evento", description="Solicitar recebimento de evento."),
    discord.SelectOption(label="VAGAS MEDIADOR", emoji=EMOJI_VAGAS_MEDIADOR, value="vagas_mediador", description="Atendimento sobre vagas de mediador."),
    discord.SelectOption(label="DIVULGACAO", emoji=EMOJI_DIVULGACAO, value="divulgacao", description="Solicitar divulgação."),
]


def ticket_embed(title: str, description: str, image_url: Optional[str] = None) -> discord.Embed:
    if not title.startswith("╭ "):
        title = styled_title(title)
    embed = discord.Embed(title=title, description=description, color=RED)
    if image_url:
        embed.set_image(url=image_url)
    return embed


class TicketPanelModal(discord.ui.Modal, title="Criar painel de ticket"):
    titulo = discord.ui.TextInput(label="Titulo", placeholder="Exemplo: Atendimento")
    mensagem = discord.ui.TextInput(
        label="Mensagem do painel",
        placeholder="Seja bem-vindo(a), facilitando o nosso atendimento...",
        style=discord.TextStyle.paragraph,
    )
    imagem = discord.ui.TextInput(
        label="Link da imagem PNG (opcional)",
        placeholder="https://site.com/banner-ticket.png",
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        titulo = str(self.titulo)
        mensagem = str(self.mensagem)
        imagem = str(self.imagem).strip() or None

        if imagem and (not imagem.startswith("https://") or not imagem.lower().endswith(".png")):
            await interaction.response.send_message(
                "⟦ ⚠️ 𝐄𝐑𝐑𝐎 ⟧\nA URL da imagem precisa começar com https:// e terminar com .png",
                ephemeral=True,
            )
            return

        embed = ticket_embed(styled_title(titulo), f"{mensagem}\n\n{EMOJI_ADM} 𝐒𝐞𝐥𝐞𝐜𝐢𝐨𝐧𝐞 𝐮𝐦𝐚 𝐨𝐩𝐜̧𝐚̃𝐨 𝐚𝐛𝐚𝐢𝐱𝐨 𝐩𝐚𝐫𝐚 𝐢𝐧𝐢𝐜𝐢𝐚𝐫 𝐬𝐞𝐮 𝐚𝐭𝐞𝐧𝐝𝐢𝐦𝐞𝐧𝐭𝐨.", imagem)
        await interaction.channel.send(embed=embed, view=TicketPanelView())
        await interaction.response.send_message("⟦ ✅ 𝐏𝐀𝐈𝐍𝐄𝐋 𝐂𝐑𝐈𝐀𝐃𝐎 ⟧", ephemeral=True)


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTopicSelect())


class TicketTopicSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Selecione uma opcao para iniciar seu atendimento.",
            options=TICKET_TOPICS,
            custom_id="ticket_topic_select",
        )

    async def callback(self, interaction: discord.Interaction):
        topic_value = self.values[0]
        topic_label = next(o.label for o in TICKET_TOPICS if o.value == topic_value)

        ts = store.ticket_settings(interaction.guild_id)
        if not ts["category_id"]:
            await interaction.response.send_message(
                "⟦ ⚠️ ⟧ O sistema de tickets não está configurado. Peça ao ADM para usar `/configticket`.",
                ephemeral=True,
            )
            return

        category = interaction.guild.get_channel(ts["category_id"])
        staff_role = interaction.guild.get_role(ts["staff_role_id"]) if ts["staff_role_id"] else None

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        # dono do servidor também acessa
        owner = interaction.guild.owner
        if owner:
            overwrites[owner] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        channel_name = f"ticket-{interaction.user.name}".lower()
        channel_name = re.sub(r"[^a-z0-9-]", "-", channel_name)
        channel_name = re.sub(r"-+", "-", channel_name).strip("-")[:32] or "ticket"

        channel = await interaction.guild.create_text_channel(channel_name, category=category, overwrites=overwrites)

        ticket_id = store.create_ticket(interaction.guild_id, channel.id, interaction.user.id, topic_label)

        staff_mention = staff_role.mention if staff_role else ""
        embed = ticket_embed(
            styled_title("<:56644tools1:1516917629841969232> 𝐓𝐈𝐂𝐊𝐄𝐓・𝐀𝐁𝐄𝐑𝐓𝐎"),
            (
                f"{EMOJI_FORM} 𝐂𝐚𝐭𝐞𝐠𝐨𝐫𝐢𝐚: **{topic_label}**\n"
                f"{EMOJI_ADM} 𝐔𝐬𝐮𝐚́𝐫𝐢𝐨: {interaction.user.mention}\n"
                f"{EMOJI_SUPORTE} 𝐒𝐭𝐚𝐟𝐟: {staff_mention or 'Nenhum cargo definido'}\n\n"
                "Explique seu problema com detalhes. Apenas voce e o staff conseguem ver este ticket.\n\n"
                "O botao de fechar fica visivel para todos, mas so o staff ou o dono do servidor pode fechar."
            ),
        )

        await channel.send(
            content=f"{interaction.user.mention} {staff_mention}",
            embed=embed,
            view=TicketControlView(ticket_id),
        )

        await interaction.response.send_message(
            f"⟦ ✅ 𝐓𝐈𝐂𝐊𝐄𝐓 𝐀𝐁𝐄𝐑𝐓𝐎 ⟧\nSeu ticket foi criado: {channel.mention}",
            ephemeral=True,
        )


class TicketControlView(discord.ui.View):
    def __init__(self, ticket_id: int):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id

    def _can_manage(self, interaction: discord.Interaction) -> bool:
        if isinstance(interaction.user, discord.Member) and is_owner_member(interaction.user):
            return True
        ts = store.ticket_settings(interaction.guild_id)
        if ts["staff_role_id"] and isinstance(interaction.user, discord.Member):
            return any(r.id == ts["staff_role_id"] for r in interaction.user.roles)
        return False

    @discord.ui.button(label="Fechar Ticket", emoji="<a:erro_animado:1516913586054631558>", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._can_manage(interaction):
            await interaction.response.send_message("Somente staff ou dono do servidor pode fechar o ticket.", ephemeral=True)
            return
        ticket = store.ticket_by_channel(interaction.channel_id)
        await interaction.response.send_message("⟦ <a:erro_animado:1516913586054631558> 𝐓𝐈𝐂𝐊𝐄𝐓 𝐅𝐄𝐂𝐇𝐀𝐃𝐎 ⟧\nEncerrando o atendimento...")
        store.close_ticket(interaction.channel_id)
        if ticket:
            await send_rating_dm(interaction.guild, ticket["user_id"], ticket["id"])
        await countdown_and_delete(interaction.channel)

    @discord.ui.button(label="Assumir Ticket", emoji="<a:atualizar:1516913555276955778>", style=discord.ButtonStyle.primary, custom_id="ticket_assume")
    async def assume_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._can_manage(interaction):
            await interaction.response.send_message("Somente staff ou dono do servidor pode assumir o ticket.", ephemeral=True)
            return
        ticket = store.ticket_by_channel(interaction.channel_id)
        await interaction.response.send_message(
            f"⟦ <a:atualizar:1516913555276955778> 𝐓𝐈𝐂𝐊𝐄𝐓 𝐀𝐒𝐒𝐔𝐌𝐈𝐃𝐎 ⟧\n{interaction.user.mention} assumiu este ticket. Encerrando..."
        )
        store.close_ticket(interaction.channel_id)
        if ticket:
            await send_rating_dm(interaction.guild, ticket["user_id"], ticket["id"])
        await countdown_and_delete(interaction.channel)


async def countdown_and_delete(channel: discord.TextChannel) -> None:
    for n in range(5, 0, -1):
        await channel.send(f"<:relogio:1516913566253580470> Encerrando em {n}...")
        await asyncio.sleep(1)
    await channel.delete(reason="Ticket encerrado")


async def send_rating_dm(guild: discord.Guild, user_id: int, ticket_id: int) -> None:
    member = guild.get_member(user_id)
    if not member:
        return
    embed = discord.Embed(
        title="<a:sucesso_animado:1516913609303658506> AVALIAÇÃO REGISTRADA",
        description=(
            "Obrigado pela sua avaliação!\n\n"
            "Clique em uma estrela abaixo para avaliar o atendimento."
        ),
        color=RED,
    )
    try:
        await member.send(embed=embed, view=RatingView(guild.id, user_id, ticket_id))
    except discord.HTTPException:
        pass


class RatingView(discord.ui.View):
    def __init__(self, guild_id: int, user_id: int, ticket_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.user_id = user_id
        self.ticket_id = ticket_id
        for i in range(1, 6):
            self.add_item(RatingButton(guild_id, user_id, ticket_id, i))


class RatingButton(discord.ui.Button):
    def __init__(self, guild_id: int, user_id: int, ticket_id: int, rating: int):
        stars = "⭐" * rating
        super().__init__(
            label=str(rating),
            emoji="⭐",
            style=discord.ButtonStyle.secondary,
            custom_id=f"rating:{guild_id}:{user_id}:{ticket_id}:{rating}",
        )
        self.guild_id = guild_id
        self.user_id = user_id
        self.ticket_id = ticket_id
        self.rating = rating

    async def callback(self, interaction: discord.Interaction):
        store.add_ticket_rating(self.guild_id, self.user_id, self.ticket_id, self.rating)
        stars = "⭐" * self.rating
        embed = discord.Embed(
            title="<a:sucesso_animado:1516913609303658506> AVALIAÇÃO REGISTRADA",
            description=f"Obrigado pela sua avaliação!\n\nSua nota: **{self.rating}/5** {stars}",
            color=RED,
        )
        # desabilita todos os botões após votar
        for item in self.view.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self.view)


# ════════════════════════════════════════════════════════════════════════════
# EVENTOS E COMANDOS
# ════════════════════════════════════════════════════════════════════════════

_ready_once = False

@bot.event
async def on_ready():
    global _ready_once
    if _ready_once:
        return
    _ready_once = True
    for queue in store.active_queues():
        bot.add_view(QueueView(queue["id"], queue["kind"], queue["mode"]))
    bot.add_view(TicketPanelView())
    try:
        synced = await bot.tree.sync()
        print(f"Comandos sincronizados: {len(synced)}")
        # Sincroniza por guild para refletir mudanças de comandos mais rápido.
        for guild in bot.guilds:
            try:
                synced_guild = await bot.tree.sync(guild=guild)
                print(f"Comandos sincronizados (guild {guild.id}): {len(synced_guild)}")
            except Exception as exc_guild:
                print(f"Erro ao sincronizar na guild {guild.id}: {exc_guild}")
    except Exception as exc:
        print(f"Erro ao sincronizar comandos: {exc}")
    print(f"{BOT_NAME} conectado como {bot.user}")


@bot.event
async def on_guild_join(guild: discord.Guild):
    store.settings(guild.id)
    return
    embed = red_embed(
        f"{BOT_NAME} ATIVADO",
        (
            "Obrigado por me adicionar ao seu servidor.\n\n"
            "Vamos configurar suas filas agora?\n"
            "Bora organizar as partidas com um painel mais profissional.\n\n"
            "Comandos principais:\n"
            "`/config` - painel principal do servidor\n"
            "`/configfilas` - painel rapido de filas\n"
            "`/divulgacao` - painel de divulgacoes\n"
            "`/formulario` - painel de recrutamento\n"
            "`/configformulario` - configurar formulario\n"
            "`/blacklist` - gerenciar blacklist\n"
            "`/salvardados` - backup dos dados\n"
            "`/restaurardados` - restaurar backup dos dados\n"
            "`/criarfila` - criar uma fila manual\n"
            "`/criartodasfilas` - criar varias filas de uma vez\n"
            "`/admconfig` - painel do ADM e Pix\n"
            "`/configticket` - configurar tickets\n"
            "`/ticket` - criar painel de ticket\n"
            "`/veravaliacoes` - ver avaliacoes dos tickets\n"
            "`/apostas` - painel da aposta"
        ),
    )
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            await channel.send(embed=embed)
            break


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    """Revoga os dados do ADM quando o cargo configurado é removido."""
    if before.bot:
        return

    settings = store.settings(after.guild.id)
    admin_role_id = settings["admin_role_id"]
    if not admin_role_id:
        return

    had_admin_role = any(role.id == admin_role_id for role in before.roles)
    has_admin_role = any(role.id == admin_role_id for role in after.roles)
    if had_admin_role and not has_admin_role:
        store.remove_admin_data(after.guild.id, after.id)




@bot.tree.command(name="criarfila", description="Criar uma fila")
async def criarfila(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or not is_owner_member(interaction.user):
        await interaction.response.send_message("Somente Donos podem criar filas.", ephemeral=True)
        return
    await interaction.response.send_modal(CreateQueueModal())


@bot.tree.command(name="criartodasfilas", description="Criar varias filas por modo e valor")
async def criartodasfilas(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or not is_owner_member(interaction.user):
        await interaction.response.send_message("Somente Donos podem criar filas.", ephemeral=True)
        return
    await interaction.response.send_modal(CreateManyQueuesModal())


@bot.tree.command(name="config", description="Painel de configuracao do bot")
async def config(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or not is_owner_member(interaction.user):
        await interaction.response.send_message("Somente Donos podem abrir o painel.", ephemeral=True)
        return
    await interaction.response.send_message(embed=config_embed(interaction.guild_id), view=ConfigView(interaction.guild_id))


@bot.tree.command(name="configfilas", description="Painel para configurar, criar e excluir filas automaticas")
async def configfilas(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or not is_owner_member(interaction.user):
        await interaction.response.send_message("Somente Donos podem configurar filas.", ephemeral=True)
        return
    await interaction.response.send_message(
        embed=queue_panel_embed(interaction.guild_id),
        view=QueuePanelView(interaction.guild_id),
    )


@bot.tree.command(name="admconfig", description="Painel do ADM para gerenciar Pix")
async def admconfig(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or (not is_admin_member(interaction.user) and not is_owner_member(interaction.user)):
        await interaction.response.send_message("Somente ADM pode abrir este painel.", ephemeral=True)
        return
    await interaction.response.send_message(embed=adm_config_embed(interaction.guild_id, interaction.user), view=AdmConfigView(), ephemeral=True)


@bot.tree.command(name="configticket", description="Configura cargo staff e categoria dos tickets")
async def configticket(interaction: discord.Interaction, cargo_staff: discord.Role, categoria: discord.CategoryChannel):
    if not isinstance(interaction.user, discord.Member) or not is_owner_member(interaction.user):
        await interaction.response.send_message("Somente Donos podem configurar tickets.", ephemeral=True)
        return
    store.update_ticket_settings(interaction.guild_id, cargo_staff.id, categoria.id)
    await interaction.response.send_message(
        embed=ticket_embed(
            "<a:sucesso_animado:1516913609303658506> Ticket configurado",
            f"Cargo staff: {cargo_staff.mention}\nCategoria dos tickets: **{categoria.name}**",
        ),
        ephemeral=True,
    )


@bot.tree.command(name="ticket", description="Cria um painel de atendimento")
async def ticket(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or not is_owner_member(interaction.user):
        await interaction.response.send_message("Somente Donos podem criar painel de ticket.", ephemeral=True)
        return
    await interaction.response.send_modal(TicketPanelModal())


@bot.tree.command(name="veravaliacoes", description="Mostra as avaliacoes dos tickets")
async def veravaliacoes(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or not is_owner_member(interaction.user):
        await interaction.response.send_message("Somente Donos podem ver as avaliacoes.", ephemeral=True)
        return
    counts = store.ticket_rating_counts(interaction.guild_id)
    total = sum(counts.values())
    average = sum(rating * amount for rating, amount in counts.items()) / total if total else 0
    await interaction.response.send_message(
        embed=ticket_embed(
            "⭐ Avaliacoes dos tickets",
            (
                f"Total: **{total}**\n"
                f"Media: **{average:.1f}/5**\n\n"
                f"⭐⭐⭐⭐⭐: {counts[5]}\n"
                f"⭐⭐⭐⭐: {counts[4]}\n"
                f"⭐⭐⭐: {counts[3]}\n"
                f"⭐⭐: {counts[2]}\n"
                f"⭐: {counts[1]}"
            ),
        ),
        ephemeral=True,
    )


@bot.tree.command(name="rankadm", description="Mostra o ranking de partidas controladas pelos ADMs")
async def rankadm(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or not is_owner_member(interaction.user):
        await interaction.response.send_message("Somente Donos podem ver o ranking de ADM.", ephemeral=True)
        return
    rows = store.admin_rank_rows(interaction.guild_id)
    if not rows:
        await interaction.response.send_message(
            embed=red_embed(f"⟦ {EMOJI_VERIFICADO} RANKING ADM ⟧", "Ainda nao existe nenhuma partida controlada."),
            ephemeral=True,
        )
        return
    lines = []
    for index, row in enumerate(rows[:15], start=1):
        lines.append(f"**{index}.** <@{row['user_id']}> - **{row['total']}** partidas")
    await interaction.response.send_message(
        embed=red_embed(f"⟦ {EMOJI_VERIFICADO} RANKING ADM ⟧", "\n".join(lines)),
        ephemeral=True,
    )


@bot.tree.command(name="apostas", description="Painel privado para gerenciar a aposta deste canal")
async def apostas(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("Use este comando dentro de um servidor.", ephemeral=True)
        return
    if not is_admin_member(interaction.user) and not is_owner_member(interaction.user):
        await interaction.response.send_message("Somente ADM ou Dono pode usar este painel.", ephemeral=True)
        return
    bet = store.bet_by_channel(interaction.guild_id, interaction.channel_id)
    if not bet:
        await interaction.response.send_message(
            "⟦ ⚠️ 𝐍𝐄𝐍𝐇𝐔𝐌𝐀 𝐀𝐏𝐎𝐒𝐓𝐀 ⟧\nUse `/apostas` dentro do canal da aposta.",
            ephemeral=True,
        )
        return
    if bet["admin_id"] != interaction.user.id and not is_owner_member(interaction.user):
        await interaction.response.send_message(
            "Somente o ADM responsável por esta aposta ou o Dono pode gerenciá-la.",
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        embed=bet_panel_embed(bet),
        view=BetConfigView(bet["id"]),
        ephemeral=True,
    )




# ════════════════════════════════════════════════════════════════════════════
# COMANDO !bot - REPETIR MENSAGEM
# ════════════════════════════════════════════════════════════════════════════

@bot.command(name="bot")
async def bot_repeat(ctx: commands.Context, *, mensagem: str = ""):
    if not ctx.guild or not isinstance(ctx.author, discord.Member):
        return
    if not is_admin_member(ctx.author):
        return
    if not mensagem.strip():
        await ctx.reply("⟦ ⚠️ ⟧ Informe uma mensagem após `!bot`.", mention_author=False)
        return
    try:
        await ctx.message.delete()
    except discord.HTTPException:
        pass
    await ctx.channel.send(mensagem)


# ════════════════════════════════════════════════════════════════════════════
# SISTEMA DE BOAS-VINDAS
# ════════════════════════════════════════════════════════════════════════════

def get_welcome_settings(guild_id: int) -> dict:
    row = store.conn.execute(
        "SELECT channel_id, message FROM welcome_settings WHERE guild_id=?", (guild_id,)
    ).fetchone()
    if row:
        return {"channel_id": row["channel_id"], "message": row["message"]}
    return {"channel_id": None, "message": None}


def save_welcome_settings(guild_id: int, channel_id: Optional[int] = None, message: Optional[str] = None) -> None:
    store.conn.execute(
        """
        INSERT INTO welcome_settings (guild_id, channel_id, message)
        VALUES (?, ?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            channel_id = COALESCE(excluded.channel_id, channel_id),
            message = COALESCE(excluded.message, message)
        """,
        (guild_id, channel_id, message),
    )
    store.conn.commit()


# Criar tabela welcome_settings se não existir
store.conn.execute(
    """
    CREATE TABLE IF NOT EXISTS welcome_settings (
        guild_id INTEGER PRIMARY KEY,
        channel_id INTEGER,
        message TEXT
    )
    """
)
store.conn.commit()


def welcome_config_embed(guild_id: int) -> discord.Embed:
    cfg = get_welcome_settings(guild_id)
    channel = f"<#{cfg['channel_id']}>" if cfg["channel_id"] else "Não definido"
    msg = cfg["message"] or "Não definida"
    return red_embed(
        "⟦ 🎉 𝐁𝐎𝐀𝐒-𝐕𝐈𝐍𝐃𝐀𝐒 𝐂𝐎𝐍𝐅𝐈𝐆 ⟧",
        f"<:divulgacao:1516913611304603842> 𝐂𝐚𝐧𝐚𝐥: {channel}\n💬 𝐌𝐞𝐧𝐬𝐚𝐠𝐞𝐦: {msg[:100]}{'...' if len(msg) > 100 else ''}",
    )


class WelcomeConfigView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    @discord.ui.button(label="Canal", emoji="<:divulgacao:1516913611304603842>", style=discord.ButtonStyle.secondary)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "⟦ <:divulgacao:1516913611304603842> 𝐂𝐀𝐍𝐀𝐋 𝐁𝐎𝐀𝐒-𝐕𝐈𝐍𝐃𝐀𝐒 ⟧\nSelecione o canal:",
            view=WelcomeChannelPickView(self.guild_id),
            ephemeral=True,
        )

    @discord.ui.button(label="Mensagem", emoji="💬", style=discord.ButtonStyle.primary)
    async def set_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WelcomeMessageModal(self.guild_id))


class WelcomeChannelPickView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=120)
        self.add_item(WelcomeChannelSelect(guild_id))


class WelcomeChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, guild_id: int):
        super().__init__(
            placeholder="Selecione o canal de boas-vindas",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
        )
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        save_welcome_settings(self.guild_id, channel_id=channel.id)
        await interaction.response.send_message(
            f"⟦ ✅ 𝐒𝐀𝐋𝐕𝐎 ⟧\nCanal de boas-vindas definido como {channel.mention}.", ephemeral=True
        )


class WelcomeMessageModal(discord.ui.Modal, title="Mensagem de Boas-Vindas"):
    mensagem = discord.ui.TextInput(
        label="Mensagem",
        placeholder="Seja bem-vindo(a)! Esperamos que você tenha uma ótima experiência.",
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        save_welcome_settings(self.guild_id, message=str(self.mensagem))
        await interaction.response.send_message(
            f"⟦ ✅ 𝐒𝐀𝐋𝐕𝐎 ⟧\nMensagem de boas-vindas definida.", ephemeral=True
        )


def owner_only(member: discord.Member) -> bool:
    return isinstance(member, discord.Member) and is_owner_member(member)


async def deny_owner(interaction: discord.Interaction) -> None:
    await interaction.response.send_message("Somente Donos podem usar este comando.", ephemeral=True)


class BlacklistModal(discord.ui.Modal, title="Adicionar Blacklist"):
    user_id = discord.ui.TextInput(label="ID Discord", placeholder="Ex: 123456789012345678", max_length=30)
    motivo = discord.ui.TextInput(label="Motivo", placeholder="Ex: suspeita de cheat", style=discord.TextStyle.paragraph, max_length=300)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            target_id = int(str(self.user_id).strip())
        except ValueError:
            await interaction.response.send_message("ID invalido. Envie apenas numeros.", ephemeral=True)
            return
        store.add_blacklist(interaction.guild_id, target_id, str(self.motivo), interaction.user.id)
        await interaction.response.send_message(
            embed=red_embed(
                "BLACKLIST ATUALIZADA",
                f"{EMOJI_ALERTA} Usuario: <@{target_id}>\n{EMOJI_ADM} Adicionado por: {interaction.user.mention}\nMotivo: {self.motivo}",
            ),
            ephemeral=True,
        )


class RemoveBlacklistModal(discord.ui.Modal, title="Remover Blacklist"):
    user_id = discord.ui.TextInput(label="ID Discord", placeholder="Ex: 123456789012345678", max_length=30)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            target_id = int(str(self.user_id).strip())
        except ValueError:
            await interaction.response.send_message("ID invalido. Envie apenas numeros.", ephemeral=True)
            return
        store.remove_blacklist(interaction.guild_id, target_id)
        await interaction.response.send_message(f"{EMOJI_V} Usuario <@{target_id}> removido da blacklist.", ephemeral=True)


class BlacklistView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Adicionar blacklist", emoji=EMOJI_ALERTA, style=discord.ButtonStyle.secondary)
    async def add(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_modal(BlacklistModal())

    @discord.ui.button(label="Remover blacklist", emoji=EMOJI_X, style=discord.ButtonStyle.secondary)
    async def remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_modal(RemoveBlacklistModal())

    @discord.ui.button(label="Ver blacklist", emoji=EMOJI_FORM, style=discord.ButtonStyle.secondary)
    async def list_items(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        rows = store.blacklist_rows(interaction.guild_id)
        text = "\n".join(f"{index}. <@{row['user_id']}> - {row['reason'] or 'Sem motivo'}" for index, row in enumerate(rows, 1))
        await interaction.response.send_message(embed=red_embed("BLACKLIST", text or "Nenhum usuario na blacklist."), ephemeral=True)


class FormAnswersModal(discord.ui.Modal, title="Formulario de Recrutamento"):
    nome = discord.ui.TextInput(label="Nome", placeholder="Seu nome", max_length=80)
    idade = discord.ui.TextInput(label="Idade", placeholder="Ex: 17", max_length=10)
    pix = discord.ui.TextInput(label="Possui Pix?", placeholder="Sim ou Nao", max_length=20)
    disponibilidade = discord.ui.TextInput(label="Horas disponiveis por dia", placeholder="Ex: 5 horas, noite", max_length=80)
    experiencia = discord.ui.TextInput(label="Experiencia / observacao", placeholder="Conte rapidamente sua experiencia", style=discord.TextStyle.paragraph, max_length=400)

    def __init__(self, vacancy: str):
        super().__init__()
        self.vacancy = vacancy

    async def on_submit(self, interaction: discord.Interaction):
        settings = store.settings(interaction.guild_id)
        answers = {
            "Nome": str(self.nome),
            "Idade": str(self.idade),
            "Pix": str(self.pix),
            "Disponibilidade": str(self.disponibilidade),
            "Experiencia": str(self.experiencia),
            "Taxa": cents_to_money(settings["form_fee_cents"]),
        }
        submission_id = store.create_form_submission(interaction.guild_id, interaction.user.id, self.vacancy, answers)
        embed = red_embed(
            "NOVO FORMULARIO RECEBIDO",
            (
                f"{EMOJI_ADM} Candidato: {interaction.user.mention}\n"
                f"{EMOJI_FORM} Vaga: **{self.vacancy}**\n"
                f"{EMOJI_REEMBOLSO} Taxa semanal: **{cents_to_money(settings['form_fee_cents'])}**\n\n"
                + "\n".join(f"**{k}:** {v}" for k, v in answers.items())
            ),
        )
        channel = interaction.guild.get_channel(settings["form_channel_id"]) if settings["form_channel_id"] else interaction.channel
        await channel.send(embed=embed, view=FormReviewView(submission_id))
        await interaction.response.send_message(f"{EMOJI_V} Formulario enviado para analise.", ephemeral=True)


class FormVacancySelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Selecione a vaga",
            options=[
                discord.SelectOption(label="ADM", value="ADM", emoji=EMOJI_ADM),
                discord.SelectOption(label="Mediador", value="Mediador", emoji=EMOJI_VAGAS_MEDIADOR),
                discord.SelectOption(label="Suporte", value="Suporte", emoji=EMOJI_SUPORTE),
                discord.SelectOption(label="Divulgador", value="Divulgador", emoji=EMOJI_EVENTO),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FormAnswersModal(self.values[0]))


class FormPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(FormVacancySelect())


class FormReviewView(discord.ui.View):
    def __init__(self, submission_id: int):
        super().__init__(timeout=None)
        self.submission_id = submission_id

    @discord.ui.button(label="Aceitar", emoji=EMOJI_V, style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        sub = store.form_submission(self.submission_id)
        store.update_form_submission(self.submission_id, "accepted", interaction.user.id)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"{EMOJI_V} Formulario aceito por {interaction.user.mention}.")
        # DM para o candidato
        if sub:
            member = interaction.guild.get_member(sub["user_id"])
            if member:
                try:
                    embed_dm = discord.Embed(
                        title=f"╭ {EMOJI_V}・𝐅𝐎𝐑𝐌𝐔𝐋𝐀́𝐑𝐈𝐎 𝐀𝐂𝐄𝐈𝐓𝐎 ╮",
                        description=(
                            f"{EMOJI_V} Parabéns, **{member.display_name}**!\n\n"
                            f"Seu formulário para a vaga de **{sub['vacancy']}** foi **aceito**.\n\n"
                            f"{EMOJI_ADM} Revisado por: {interaction.user.mention}\n\n"
                            f"Aguarde o contato da equipe. Seja bem-vindo(a)! 🎉"
                        ),
                        color=discord.Color.green(),
                    )
                    await member.send(embed=embed_dm)
                except discord.HTTPException:
                    pass

    @discord.ui.button(label="Recusar", emoji=EMOJI_X, style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        sub = store.form_submission(self.submission_id)
        store.update_form_submission(self.submission_id, "rejected", interaction.user.id)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(f"{EMOJI_X} Formulario recusado por {interaction.user.mention}.")
        # DM para o candidato
        if sub:
            member = interaction.guild.get_member(sub["user_id"])
            if member:
                try:
                    embed_dm = discord.Embed(
                        title=f"╭ {EMOJI_X}・𝐅𝐎𝐑𝐌𝐔𝐋𝐀́𝐑𝐈𝐎 𝐑𝐄𝐂𝐔𝐒𝐀𝐃𝐎 ╮",
                        description=(
                            f"Olá, **{member.display_name}**.\n\n"
                            f"Infelizmente seu formulário para a vaga de **{sub['vacancy']}** foi **recusado**.\n\n"
                            f"{EMOJI_ADM} Revisado por: {interaction.user.mention}\n\n"
                            f"Você pode tentar novamente mais tarde. Obrigado pelo interesse!"
                        ),
                        color=discord.Color.red(),
                    )
                    await member.send(embed=embed_dm)
                except discord.HTTPException:
                    pass


class FormFeeModal(discord.ui.Modal, title="Configurar Taxa"):
    fee = discord.ui.TextInput(label="Taxa semanal", placeholder="Ex: 3,00", max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        cents = money_to_cents(str(self.fee))
        store.update_setting(interaction.guild_id, "form_fee_cents", cents)
        await interaction.response.send_message(f"{EMOJI_V} Taxa do formulario definida para {cents_to_money(cents)}.", ephemeral=True)


class FormConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Canal de respostas", emoji=EMOJI_FORM, style=discord.ButtonStyle.secondary)
    async def channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_message("Selecione o canal que recebera os formularios:", view=TextChannelPickView("form_channel_id"), ephemeral=True)

    @discord.ui.button(label="Mudar taxa", emoji=EMOJI_REEMBOLSO, style=discord.ButtonStyle.secondary)
    async def fee(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_modal(FormFeeModal())


class DivulgacaoConfigModal(discord.ui.Modal, title="Configurar Divulgacao"):
    mensagem = discord.ui.TextInput(label="Mensagem", placeholder="Ex: Filas abertas no Panda Apostas", style=discord.TextStyle.paragraph, max_length=800)
    link = discord.ui.TextInput(label="Link do servidor", placeholder="https://discord.gg/seulink", max_length=200)

    async def on_submit(self, interaction: discord.Interaction):
        store.update_setting(interaction.guild_id, "divulgacao_message", str(self.mensagem))
        store.update_setting(interaction.guild_id, "divulgacao_link", str(self.link))
        await interaction.response.send_message(f"{EMOJI_V} Divulgacao configurada.", ephemeral=True)


def divulgacao_embed(guild_id: int) -> discord.Embed:
    channels = store.divulgacao_channels(guild_id)
    settings = store.settings(guild_id)
    lines = []
    for slot_key, label, _kind, _mode in QUEUE_PANEL_SLOTS:
        channel_id = channels.get(slot_key)
        status = EMOJI_V if channel_id else EMOJI_X
        channel = f"<#{channel_id}>" if channel_id else "Nao definido"
        lines.append(f"{status} **{label}:** {channel}")
    return red_embed(
        "DIVULGACOES",
        (
            f"{EMOJI_RENOMEAR} Mensagem: {settings['divulgacao_message'] or 'Nao definida'}\n"
            f"{EMOJI_SALAS} Link: {settings['divulgacao_link'] or 'Nao definido'}\n\n"
            + "\n".join(lines)
        ),
    )


class DivulgacaoPanelView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        for slot_key, label, _kind, mode in QUEUE_PANEL_SLOTS:
            emoji = EMOJI_COMPUTER if mode == "misto" else EMOJI_FF
            self.add_item(DivulgacaoSlotButton(guild_id, slot_key, label, emoji))
        self.add_item(DivulgacaoConfigButton(guild_id))
        self.add_item(DivulgacaoStartButton(guild_id))
        self.add_item(DivulgacaoDeleteButton(guild_id))


class DivulgacaoSlotButton(discord.ui.Button):
    def __init__(self, guild_id: int, slot_key: str, label: str, emoji: str):
        super().__init__(label=label, emoji=emoji, style=discord.ButtonStyle.secondary)
        self.guild_id = guild_id
        self.slot_key = slot_key

    async def callback(self, interaction: discord.Interaction):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_message("Selecione o canal:", view=DivulgacaoChannelPickView(self.guild_id, self.slot_key), ephemeral=True)


class DivulgacaoChannelPickView(discord.ui.View):
    def __init__(self, guild_id: int, slot_key: str):
        super().__init__(timeout=120)
        self.add_item(DivulgacaoChannelPickSelect(guild_id, slot_key))


class DivulgacaoChannelPickSelect(discord.ui.ChannelSelect):
    def __init__(self, guild_id: int, slot_key: str):
        super().__init__(placeholder="Selecione o canal", channel_types=[discord.ChannelType.text], min_values=1, max_values=1)
        self.guild_id = guild_id
        self.slot_key = slot_key

    async def callback(self, interaction: discord.Interaction):
        store.set_divulgacao_channel(self.guild_id, self.slot_key, self.values[0].id)
        await interaction.response.send_message(f"{EMOJI_V} Canal salvo.", ephemeral=True)


class DivulgacaoConfigButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Configurar", emoji=EMOJI_RENOMEAR, style=discord.ButtonStyle.secondary)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_modal(DivulgacaoConfigModal())


class DivulgacaoStartButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Comecar divulgacao", emoji=EMOJI_DIVULGACAO, style=discord.ButtonStyle.secondary)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        settings = store.settings(self.guild_id)
        message_text = settings["divulgacao_message"] or "Filas abertas no servidor."
        link = settings["divulgacao_link"] or ""
        await interaction.response.defer(ephemeral=True)
        # Apagar mensagens antigas antes de enviar novas
        for row in store.divulgacao_messages(self.guild_id):
            channel = interaction.guild.get_channel(row["channel_id"])
            if channel:
                try:
                    msg = await channel.fetch_message(row["message_id"])
                    await msg.delete()
                except discord.HTTPException:
                    pass
        store.clear_divulgacao_messages(self.guild_id)
        # Enviar novas mensagens
        sent = 0
        for slot_key, channel_id in store.divulgacao_channels(self.guild_id).items():
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                continue
            try:
                msg = await channel.send(f"@everyone @here\n\n{EMOJI_DIVULGACAO} **DIVULGACAO PANDA APOSTAS**\n\n{message_text}\n\n{link}")
                store.add_divulgacao_message(self.guild_id, slot_key, channel.id, msg.id)
                sent += 1
            except discord.HTTPException:
                pass
        await interaction.followup.send(f"{EMOJI_V} Divulgacoes enviadas: {sent}.", ephemeral=True)


class DivulgacaoDeleteButton(discord.ui.Button):
    def __init__(self, guild_id: int):
        super().__init__(label="Excluir divulgacao", emoji=EMOJI_X, style=discord.ButtonStyle.secondary)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        deleted = 0
        await interaction.response.defer(ephemeral=True)
        for row in store.divulgacao_messages(self.guild_id):
            channel = interaction.guild.get_channel(row["channel_id"])
            if not channel:
                continue
            try:
                msg = await channel.fetch_message(row["message_id"])
                await msg.delete()
                deleted += 1
            except discord.HTTPException:
                pass
        store.clear_divulgacao_messages(self.guild_id)
        await interaction.followup.send(f"{EMOJI_X} Divulgacoes excluidas: {deleted}.", ephemeral=True)


@bot.tree.command(name="blacklist", description="Painel de blacklist")
async def blacklist(interaction: discord.Interaction):
    if not owner_only(interaction.user):
        await deny_owner(interaction)
        return
    await interaction.response.send_message(
        embed=red_embed("BLACKLIST", f"{EMOJI_ALERTA} Usuarios na blacklist nao conseguem entrar nas filas."),
        view=BlacklistView(),
        ephemeral=True,
    )


@bot.tree.command(name="formulario", description="Envia o painel de formulario de recrutamento")
async def formulario(interaction: discord.Interaction):
    if not owner_only(interaction.user):
        await deny_owner(interaction)
        return
    settings = store.settings(interaction.guild_id)
    await interaction.response.send_message(
        embed=red_embed(
            "FORMULARIO OFICIAL PANDA APOSTAS",
            f"Selecione abaixo a vaga desejada.\nTaxa semanal atual: **{cents_to_money(settings['form_fee_cents'])}**",
        ),
        view=FormPanelView(),
    )


@bot.tree.command(name="configformulario", description="Configura o formulario de recrutamento")
async def configformulario(interaction: discord.Interaction):
    if not owner_only(interaction.user):
        await deny_owner(interaction)
        return
    settings = store.settings(interaction.guild_id)
    channel = f"<#{settings['form_channel_id']}>" if settings["form_channel_id"] else "Nao definido"
    await interaction.response.send_message(
        embed=red_embed("CONFIG FORMULARIO", f"{EMOJI_FORM} Canal: {channel}\n{EMOJI_REEMBOLSO} Taxa: {cents_to_money(settings['form_fee_cents'])}"),
        view=FormConfigView(),
        ephemeral=True,
    )


@bot.tree.command(name="divulgacao", description="Painel de divulgacoes")
async def divulgacao(interaction: discord.Interaction):
    if not owner_only(interaction.user):
        await deny_owner(interaction)
        return
    await interaction.response.send_message(embed=divulgacao_embed(interaction.guild_id), view=DivulgacaoPanelView(interaction.guild_id), ephemeral=True)


@bot.tree.command(name="salvardados", description="Gera backup dos dados do servidor")
async def salvardados(interaction: discord.Interaction):
    if not owner_only(interaction.user):
        await deny_owner(interaction)
        return
    payload = json.dumps(store.backup_data(interaction.guild_id), ensure_ascii=False, indent=2)
    buffer = io.BytesIO(payload.encode("utf-8"))
    await interaction.response.send_message(
        content=f"{EMOJI_V} Backup gerado. Guarde este arquivo com seguranca.",
        file=discord.File(buffer, filename=f"backup-panda-apostas-{interaction.guild_id}.json"),
        ephemeral=True,
    )


@bot.tree.command(name="restaurardados", description="Restaura um backup JSON do servidor")
async def restaurardados(interaction: discord.Interaction, arquivo: discord.Attachment):
    if not owner_only(interaction.user):
        await deny_owner(interaction)
        return
    if not arquivo.filename.lower().endswith(".json"):
        await interaction.response.send_message("Envie um arquivo .json gerado pelo /salvardados.", ephemeral=True)
        return
    try:
        raw = await arquivo.read()
        data = json.loads(raw.decode("utf-8"))
        store.restore_data(interaction.guild_id, data)
    except Exception as exc:
        await interaction.response.send_message(f"{EMOJI_X} Nao consegui restaurar o backup: {exc}", ephemeral=True)
        return
    await interaction.response.send_message(f"{EMOJI_V} Backup restaurado com sucesso.", ephemeral=True)


@bot.tree.command(name="boasvindasconfig", description="Configura o sistema de boas-vindas")
async def boasvindasconfig(interaction: discord.Interaction):
    if not isinstance(interaction.user, discord.Member) or not is_owner_member(interaction.user):
        await interaction.response.send_message("Somente Donos podem CONFIGURAR as boas-vindas.", ephemeral=True)
        return
    await interaction.response.send_message(
        embed=welcome_config_embed(interaction.guild_id),
        view=WelcomeConfigView(interaction.guild_id),
        ephemeral=True,
    )


@bot.event
async def on_member_join(member: discord.Member):
    cfg = get_welcome_settings(member.guild.id)
    if not cfg["channel_id"] or not cfg["message"]:
        return
    channel = member.guild.get_channel(cfg["channel_id"])
    if not channel:
        return
    embed = discord.Embed(
        title="**Seja bem-vindo(a)!**",
        description=f"{member.mention}, {cfg['message']}",
        color=RED,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    try:
        await channel.send(content=member.mention, embed=embed)
    except discord.HTTPException:
        pass


# ════════════════════════════════════════════════════════════════════════════
# SISTEMA DE COBRANÇA DE ADM  (/admcobranca e /admcobrancaconfig)
# ════════════════════════════════════════════════════════════════════════════

# Tabelas do sistema de cobrança
store.conn.executescript(
    """
    CREATE TABLE IF NOT EXISTS adm_cobranca_config (
        guild_id INTEGER PRIMARY KEY,
        taxa_cents INTEGER NOT NULL DEFAULT 1000,
        prazo_horas INTEGER NOT NULL DEFAULT 24,
        canal_donos_id INTEGER,
        pix_nome TEXT,
        pix_chave TEXT
    );

    CREATE TABLE IF NOT EXISTS adm_pagamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        dono_user_id INTEGER,
        status TEXT NOT NULL DEFAULT 'pendente',
        pix_nome_informado TEXT,
        pix_chave_informada TEXT,
        criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        prazo_em TEXT,
        revisado_por INTEGER,
        cobranca_message_id INTEGER,
        cobranca_channel_id INTEGER
    );

    CREATE TABLE IF NOT EXISTS adm_donos_pix (
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        pix_nome TEXT NOT NULL,
        pix_chave TEXT NOT NULL,
        PRIMARY KEY (guild_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS adm_pix_historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        dono_user_id INTEGER NOT NULL,
        adm_user_id INTEGER NOT NULL,
        taxa_cents INTEGER NOT NULL,
        criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """
)
# Migrar coluna dono_user_id se não existir
try:
    store.conn.execute("ALTER TABLE adm_pagamentos ADD COLUMN dono_user_id INTEGER")
    store.conn.commit()
except Exception:
    pass


def get_adm_cobranca_config(guild_id: int) -> dict:
    store.conn.execute(
        "INSERT OR IGNORE INTO adm_cobranca_config (guild_id) VALUES (?)", (guild_id,)
    )
    store.conn.commit()
    row = store.conn.execute(
        "SELECT * FROM adm_cobranca_config WHERE guild_id=?", (guild_id,)
    ).fetchone()
    return dict(row)


def save_adm_cobranca_config(guild_id: int, **kwargs) -> None:
    allowed = {"taxa_cents", "prazo_horas", "canal_donos_id", "pix_nome", "pix_chave"}
    get_adm_cobranca_config(guild_id)
    for field, value in kwargs.items():
        if field not in allowed:
            continue
        store.conn.execute(
            f"UPDATE adm_cobranca_config SET {field}=? WHERE guild_id=?", (value, guild_id)
        )
    store.conn.commit()


def criar_pagamento(guild_id: int, user_id: int, prazo_horas: int, dono_user_id: int = 0) -> int:
    import datetime
    prazo = (datetime.datetime.utcnow() + datetime.timedelta(hours=prazo_horas)).isoformat()
    cur = store.conn.execute(
        "INSERT INTO adm_pagamentos (guild_id, user_id, dono_user_id, prazo_em) VALUES (?, ?, ?, ?)",
        (guild_id, user_id, dono_user_id, prazo),
    )
    store.conn.commit()
    return int(cur.lastrowid)


def atualizar_pagamento(pagamento_id: int, **kwargs) -> None:
    allowed = {"status", "pix_nome_informado", "pix_chave_informada", "revisado_por",
               "cobranca_message_id", "cobranca_channel_id", "dono_user_id"}
    for field, value in kwargs.items():
        if field not in allowed:
            continue
        store.conn.execute(
            f"UPDATE adm_pagamentos SET {field}=? WHERE id=?", (value, pagamento_id)
        )
    store.conn.commit()


# ── Funções helper: Pix dos donos ───────────────────────────────────────────

def get_donos_pix(guild_id: int) -> list[dict]:
    """Retorna todos os donos que têm Pix cadastrado na tabela adm_donos_pix."""
    rows = store.conn.execute(
        "SELECT * FROM adm_donos_pix WHERE guild_id=? ORDER BY user_id",
        (guild_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def save_dono_pix(guild_id: int, user_id: int, pix_nome: str, pix_chave: str) -> None:
    store.conn.execute(
        """
        INSERT INTO adm_donos_pix (guild_id, user_id, pix_nome, pix_chave)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id, user_id) DO UPDATE SET pix_nome=excluded.pix_nome, pix_chave=excluded.pix_chave
        """,
        (guild_id, user_id, pix_nome, pix_chave),
    )
    store.conn.commit()


def remove_dono_pix(guild_id: int, user_id: int) -> None:
    store.conn.execute(
        "DELETE FROM adm_donos_pix WHERE guild_id=? AND user_id=?",
        (guild_id, user_id),
    )
    store.conn.commit()


def registrar_historico_pix(guild_id: int, dono_user_id: int, adm_user_id: int, taxa_cents: int) -> None:
    store.conn.execute(
        "INSERT INTO adm_pix_historico (guild_id, dono_user_id, adm_user_id, taxa_cents) VALUES (?, ?, ?, ?)",
        (guild_id, dono_user_id, adm_user_id, taxa_cents),
    )
    store.conn.commit()


def get_historico_por_dono(guild_id: int) -> list[dict]:
    rows = store.conn.execute(
        """
        SELECT dono_user_id, COUNT(*) as total_pagamentos, SUM(taxa_cents) as total_cents
        FROM adm_pix_historico
        WHERE guild_id=?
        GROUP BY dono_user_id
        ORDER BY total_cents DESC
        """,
        (guild_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def adm_cobranca_config_embed(guild_id: int) -> discord.Embed:
    cfg = get_adm_cobranca_config(guild_id)
    canal = f"<#{cfg['canal_donos_id']}>" if cfg["canal_donos_id"] else "Nao definido"
    donos_pix = get_donos_pix(guild_id)
    if donos_pix:
        donos_txt = "\n".join(
            f"  <@{d['user_id']}> — `{d['pix_chave']}` ({d['pix_nome']})"
            for d in donos_pix
        )
    else:
        donos_txt = "  Nenhum dono com Pix cadastrado"
    return red_embed(
        "CONFIG・COBRANÇA ADM",
        (
            f"{EMOJI_PIX} **Taxa semanal:** {cents_to_money(cfg['taxa_cents'])}\n"
            f"<:relogio:1516913566253580470> **Prazo de pagamento:** {cfg['prazo_horas']}h\n"
            f"<:divulgacao:1516913611304603842> **Canal dos donos:** {canal}\n"
            f"{EMOJI_PIX} **Donos com Pix cadastrado:**\n{donos_txt}"
        ),
    )


class AdmCobrancaConfigView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    @discord.ui.button(label="Definir taxa", emoji=EMOJI_PIX, style=discord.ButtonStyle.secondary)
    async def taxa(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_modal(AdmCobrancaTaxaModal(self.guild_id))

    @discord.ui.button(label="Definir prazo", emoji="<:relogio:1516913566253580470>", style=discord.ButtonStyle.secondary)
    async def prazo(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_modal(AdmCobrancaPrazoModal(self.guild_id))

    @discord.ui.button(label="Canal dos donos", emoji="<:divulgacao:1516913611304603842>", style=discord.ButtonStyle.secondary)
    async def canal(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_message(
            "Selecione o canal onde o bot vai avisar os donos:",
            view=AdmCobrancaCanalView(self.guild_id),
            ephemeral=True,
        )

    @discord.ui.button(label="Meu Pix (dono)", emoji=EMOJI_PIX, style=discord.ButtonStyle.success)
    async def cadastrar_meu_pix(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_modal(AdmDonoPixModal(self.guild_id, interaction.user.id))

    @discord.ui.button(label="Remover meu Pix", emoji=EMOJI_X, style=discord.ButtonStyle.danger)
    async def remover_meu_pix(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        remove_dono_pix(self.guild_id, interaction.user.id)
        await interaction.response.edit_message(
            embed=adm_cobranca_config_embed(self.guild_id),
            view=AdmCobrancaConfigView(self.guild_id),
        )


class AdmCobrancaTaxaModal(discord.ui.Modal, title="Definir Taxa Semanal"):
    taxa = discord.ui.TextInput(label="Taxa (ex: 10,00)", placeholder="Ex: 10,00", max_length=20)

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            cents = money_to_cents(str(self.taxa))
            save_adm_cobranca_config(self.guild_id, taxa_cents=cents)
            await interaction.response.edit_message(
                embed=adm_cobranca_config_embed(self.guild_id),
                view=AdmCobrancaConfigView(self.guild_id),
            )
        except Exception as exc:
            await interaction.response.send_message(f"Erro: {exc}", ephemeral=True)


class AdmCobrancaPrazoModal(discord.ui.Modal, title="Definir Prazo de Pagamento"):
    prazo = discord.ui.TextInput(label="Prazo em horas (ex: 24)", placeholder="Ex: 24", max_length=5)

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            horas = int(str(self.prazo).strip())
            if horas < 1:
                raise ValueError("Minimo 1 hora.")
            save_adm_cobranca_config(self.guild_id, prazo_horas=horas)
            await interaction.response.edit_message(
                embed=adm_cobranca_config_embed(self.guild_id),
                view=AdmCobrancaConfigView(self.guild_id),
            )
        except Exception as exc:
            await interaction.response.send_message(f"Erro: {exc}", ephemeral=True)


class AdmDonoPixModal(discord.ui.Modal, title="Cadastrar meu Pix como Dono"):
    nome = discord.ui.TextInput(label="Seu nome", placeholder="Ex: João Silva", max_length=80)
    chave = discord.ui.TextInput(label="Sua chave Pix", placeholder="CPF, email, telefone ou aleatoria", max_length=160)

    def __init__(self, guild_id: int, user_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        save_dono_pix(self.guild_id, self.user_id, str(self.nome), str(self.chave))
        await interaction.response.edit_message(
            embed=adm_cobranca_config_embed(self.guild_id),
            view=AdmCobrancaConfigView(self.guild_id),
        )


class AdmCobrancaCanalView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=120)
        self.add_item(AdmCobrancaCanalSelect(guild_id))


class AdmCobrancaCanalSelect(discord.ui.ChannelSelect):
    def __init__(self, guild_id: int):
        super().__init__(
            placeholder="Selecione o canal dos donos",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
        )
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        save_adm_cobranca_config(self.guild_id, canal_donos_id=self.values[0].id)
        await interaction.response.send_message(
            f"{EMOJI_V} Canal dos donos definido como {self.values[0].mention}.", ephemeral=True
        )


# ── View da cobrança enviada no canal (botão Pagar) ─────────────────────────

class AdmCobrancaPanelView(discord.ui.View):
    def __init__(self, guild_id: int, pagamento_id: int, dono_user_id: int = 0):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.pagamento_id = pagamento_id
        self.dono_user_id = dono_user_id

    @discord.ui.button(label="💸  Pagar", style=discord.ButtonStyle.success, custom_id="adm_cobranca_pagar")
    async def pagar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Busca o pagamento do ADM que clicou especificamente
        row = store.conn.execute(
            "SELECT * FROM adm_pagamentos WHERE guild_id=? AND user_id=? AND dono_user_id=? AND status='pendente' ORDER BY id DESC LIMIT 1",
            (self.guild_id, interaction.user.id, self.dono_user_id),
        ).fetchone()
        if not row:
            # Fallback: busca pelo id do painel
            row = store.conn.execute(
                "SELECT * FROM adm_pagamentos WHERE id=?", (self.pagamento_id,)
            ).fetchone()
        if not row:
            await interaction.response.send_message("Cobrança não encontrada.", ephemeral=True)
            return
        if row["status"] != "pendente":
            await interaction.response.send_message(
                f"{EMOJI_V} Você já registrou o pagamento. Aguarde a confirmação do dono.", ephemeral=True
            )
            return
        await interaction.response.send_modal(
            AdmInformarPagamentoModal(self.guild_id, int(row["id"]), self.dono_user_id)
        )


class AdmInformarPagamentoModal(discord.ui.Modal, title="Confirmar Pagamento"):
    pix_nome = discord.ui.TextInput(label="Nome do Pix usado", placeholder="Ex: João Silva", max_length=80)
    pix_chave = discord.ui.TextInput(label="Chave Pix usada", placeholder="Ex: 000.000.000-00", max_length=160)

    def __init__(self, guild_id: int, pagamento_id: int, dono_user_id: int = 0):
        super().__init__()
        self.guild_id = guild_id
        self.pagamento_id = pagamento_id
        self.dono_user_id = dono_user_id

    async def on_submit(self, interaction: discord.Interaction):
        cfg = get_adm_cobranca_config(self.guild_id)
        canal_donos = interaction.guild.get_channel(cfg["canal_donos_id"]) if cfg["canal_donos_id"] else None
        if not canal_donos:
            await interaction.response.send_message(
                f"{EMOJI_X} Canal dos donos não configurado. Use `/admcobrancaconfig`.", ephemeral=True
            )
            return

        atualizar_pagamento(
            self.pagamento_id,
            status="aguardando_confirmacao",
            pix_nome_informado=str(self.pix_nome),
            pix_chave_informada=str(self.pix_chave),
        )

        # Busca o Pix que o ADM tem cadastrado no bot (via /admconfig) para conferência
        adm_pix = store.get_pix(self.guild_id, interaction.user.id)
        if adm_pix:
            pix_cadastrado_txt = (
                f"\n{EMOJI_VERIFICADO} **Pix cadastrado do ADM (conferir):**\n"
                f"  Nome: **{adm_pix['name']}**\n"
                f"  Chave: `{adm_pix['pix_key']}`"
            )
        else:
            pix_cadastrado_txt = f"\n{EMOJI_ALERTA} ADM não tem Pix cadastrado no bot."

        # Dono destinatário
        dono_mention = f"<@{self.dono_user_id}>" if self.dono_user_id else "Dono"

        embed = red_embed(
            "<:pix:1516913599988105378>・𝐂𝐎𝐌𝐏𝐑𝐎𝐕𝐀𝐍𝐓𝐄 𝐃𝐄 𝐏𝐀𝐆𝐀𝐌𝐄𝐍𝐓𝐎",
            (
                f"{EMOJI_ADM} **ADM:** {interaction.user.mention}\n"
                f"<:staff:1516913606795464805> **Pagando para:** {dono_mention}\n"
                f"{EMOJI_PIX} **Nome Pix informado:** {self.pix_nome}\n"
                f"{EMOJI_PIX} **Chave Pix informada:** `{self.pix_chave}`"
                f"{pix_cadastrado_txt}\n\n"
                f"Aguardando confirmação do dono."
            ),
        )
        msg = await canal_donos.send(
            content=dono_mention,
            embed=embed,
            view=AdmConfirmarPagamentoView(self.guild_id, self.pagamento_id, interaction.user.id, self.dono_user_id),
        )
        atualizar_pagamento(
            self.pagamento_id,
            cobranca_message_id=msg.id,
            cobranca_channel_id=canal_donos.id,
        )
        await interaction.response.send_message(
            f"{EMOJI_V} Comprovante enviado! Aguarde a confirmação do dono.", ephemeral=True
        )


# ── View no canal dos donos (Aceitar / Recusar pagamento) ───────────────────

class AdmConfirmarPagamentoView(discord.ui.View):
    def __init__(self, guild_id: int, pagamento_id: int, adm_user_id: int, dono_user_id: int = 0):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.pagamento_id = pagamento_id
        self.adm_user_id = adm_user_id
        self.dono_user_id = dono_user_id

    @discord.ui.button(label="✅  Aceitar pagamento", style=discord.ButtonStyle.success, custom_id="adm_pag_aceitar")
    async def aceitar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        cfg = get_adm_cobranca_config(self.guild_id)
        atualizar_pagamento(self.pagamento_id, status="pago", revisado_por=interaction.user.id)
        # Registrar no histórico
        if self.dono_user_id:
            registrar_historico_pix(self.guild_id, self.dono_user_id, self.adm_user_id, cfg["taxa_cents"])
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            f"{EMOJI_V} Pagamento de <@{self.adm_user_id}> **confirmado** por {interaction.user.mention}."
        )
        # DM para o ADM
        member = interaction.guild.get_member(self.adm_user_id)
        if member:
            try:
                embed_dm = discord.Embed(
                    title=f"╭ {EMOJI_V}・𝐏𝐀𝐆𝐀𝐌𝐄𝐍𝐓𝐎 𝐂𝐎𝐍𝐅𝐈𝐑𝐌𝐀𝐃𝐎 ╮",
                    description=(
                        f"<a:sucesso_animado:1516913609303658506> Seu pagamento da taxa semanal foi **confirmado**!\n\n"
                        f"{EMOJI_PIX} Valor: **{cents_to_money(cfg['taxa_cents'])}**\n"
                        f"{EMOJI_ADM} Confirmado por: {interaction.user.mention}\n\n"
                        f"Obrigado por estar em dia. 🎉"
                    ),
                    color=discord.Color.green(),
                )
                await member.send(embed=embed_dm)
            except discord.HTTPException:
                pass

    @discord.ui.button(label="❌  Recusar pagamento", style=discord.ButtonStyle.danger, custom_id="adm_pag_recusar")
    async def recusar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        atualizar_pagamento(self.pagamento_id, status="recusado", revisado_por=interaction.user.id)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            f"{EMOJI_X} Pagamento de <@{self.adm_user_id}> **recusado** por {interaction.user.mention}."
        )
        # DM para o ADM
        member = interaction.guild.get_member(self.adm_user_id)
        if member:
            try:
                embed_dm = discord.Embed(
                    title=f"╭ {EMOJI_X}・𝐏𝐀𝐆𝐀𝐌𝐄𝐍𝐓𝐎 𝐑𝐄𝐂𝐔𝐒𝐀𝐃𝐎 ╮",
                    description=(
                        f"<a:erro_animado:1516913586054631558> Seu pagamento da taxa semanal foi **recusado**.\n\n"
                        f"{EMOJI_ADM} Recusado por: {interaction.user.mention}\n\n"
                        f"Por favor, refaça o pagamento com os dados corretos e tente novamente."
                    ),
                    color=discord.Color.red(),
                )
                await member.send(embed=embed_dm)
            except discord.HTTPException:
                pass


# ── Comandos slash ───────────────────────────────────────────────────────────

@bot.tree.command(name="admcobrancaconfig", description="Configura o sistema de cobrança semanal dos ADMs")
async def admcobrancaconfig(interaction: discord.Interaction):
    if not owner_only(interaction.user):
        await deny_owner(interaction)
        return
    await interaction.response.send_message(
        embed=adm_cobranca_config_embed(interaction.guild_id),
        view=AdmCobrancaConfigView(interaction.guild_id),
        ephemeral=True,
    )


@bot.tree.command(name="admcobranca", description="Envia a cobrança semanal para todos os ADMs")
async def admcobranca(interaction: discord.Interaction):
    if not owner_only(interaction.user):
        await deny_owner(interaction)
        return

    cfg = get_adm_cobranca_config(interaction.guild_id)
    donos_pix = get_donos_pix(interaction.guild_id)

    if not donos_pix:
        await interaction.response.send_message(
            f"{EMOJI_X} Nenhum dono com Pix cadastrado. Use `/admcobrancaconfig` → **Meu Pix (dono)**.", ephemeral=True
        )
        return

    settings = store.settings(interaction.guild_id)
    admin_role_id = settings["admin_role_id"]
    if not admin_role_id:
        await interaction.response.send_message(
            f"{EMOJI_X} Configure o cargo ADM primeiro com `/config`.", ephemeral=True
        )
        return

    admin_role = interaction.guild.get_role(admin_role_id)
    if not admin_role or not admin_role.members:
        await interaction.response.send_message(f"{EMOJI_X} Nenhum ADM encontrado com esse cargo.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    adm_members = list(admin_role.members)
    n_donos = len(donos_pix)

    # Dividir ADMs entre donos em rodízio (round-robin)
    # adm_members[i] → donos_pix[i % n_donos]
    adm_por_dono: dict[int, list] = {d["user_id"]: [] for d in donos_pix}
    for i, member in enumerate(adm_members):
        dono = donos_pix[i % n_donos]
        adm_por_dono[dono["user_id"]].append(member)

    # Linha de menção ao cargo ADM + donos
    mencoes_donos = " ".join(f"<@{d['user_id']}>" for d in donos_pix)
    mencao_cargo = f"<@&{admin_role_id}>"

    # Para cada dono, enviar UMA mensagem com QR Code do Pix dele
    # listando quais ADMs devem pagar pra ele
    msg_ids = []
    for dono in donos_pix:
        adms_deste_dono = adm_por_dono[dono["user_id"]]
        if not adms_deste_dono:
            continue

        pix_code = pix_copy_code(
            dono["pix_chave"],
            dono["pix_nome"],
            cfg["taxa_cents"],
            "TAXAADM",
        )
        qr_file = make_qr_file(pix_code)

        lista_adms = "\n".join(f"  {m.mention}" for m in adms_deste_dono)

        embed = discord.Embed(
            title=f"╭ {EMOJI_PIX}・𝐂𝐎𝐁𝐑𝐀𝐍𝐂̧𝐀 𝐒𝐄𝐌𝐀𝐍𝐀𝐋 ╮",
            description=(
                f"{EMOJI_ALERTA} {mencao_cargo} **Atenção, ADMs!**\n\n"
                f"A taxa semanal está sendo cobrada. Realize o pagamento dentro do prazo.\n\n"
                f"{EMOJI_PIX} **Valor:** {cents_to_money(cfg['taxa_cents'])}\n"
                f"{EMOJI_PIX} **Pagar para:** <@{dono['user_id']}> — {dono['pix_nome']}\n"
                f"{EMOJI_PIX} **Chave Pix:** `{dono['pix_chave']}`\n"
                f"<:relogio:1516913566253580470> **Prazo:** {cfg['prazo_horas']} horas\n\n"
                f"**ADMs que pagam para este dono:**\n{lista_adms}\n\n"
                f"Clique em **<:pix:1516913599988105378> Pagar** abaixo para registrar seu pagamento."
            ),
            color=discord.Color(0x2B2D31),
        )
        embed.set_image(url="attachment://pix-qrcode.png")
        embed.set_footer(text="Panda Supreme Apostas • Cobrança Semanal")

        # Cria pagamentos individuais por ADM já vinculados ao dono
        pagamento_ids = []
        for member in adms_deste_dono:
            pid = criar_pagamento(interaction.guild_id, member.id, cfg["prazo_horas"], dono_user_id=dono["user_id"])
            pagamento_ids.append(pid)

        # Usa o primeiro pagamento como referência para o painel
        panel_pid = pagamento_ids[0]

        mencoes_adms = " ".join(m.mention for m in adms_deste_dono)
        msg = await interaction.channel.send(
            content=f"{mencoes_adms}",
            embed=embed,
            file=qr_file,
            view=AdmCobrancaPanelView(interaction.guild_id, panel_pid, dono["user_id"]),
        )

        # Atualiza todos os pagamentos desta mensagem com o msg id
        for pid in pagamento_ids:
            atualizar_pagamento(pid, cobranca_message_id=msg.id, cobranca_channel_id=interaction.channel_id)

        msg_ids.append(msg.id)

    # Agendar expiração automática da mensagem
    if msg_ids:
        bot.loop.create_task(
            _expirar_cobranca(
                guild_id=interaction.guild_id,
                channel_id=interaction.channel_id,
                message_ids=msg_ids,
                prazo_horas=cfg["prazo_horas"],
            )
        )

    await interaction.followup.send(
        f"{EMOJI_V} Cobrança enviada para **{len(adm_members)}** ADMs divididos entre **{n_donos}** dono(s).",
        ephemeral=True,
    )


async def _expirar_cobranca(guild_id: int, channel_id: int, message_ids: list[int], prazo_horas: int):
    """Aguarda o prazo e deleta as mensagens de cobrança, marcando pendentes como expirado."""
    import asyncio as _asyncio
    await _asyncio.sleep(prazo_horas * 3600)

    # Marcar pagamentos pendentes como expirado
    store.conn.execute(
        """
        UPDATE adm_pagamentos
        SET status='expirado'
        WHERE guild_id=? AND cobranca_channel_id=? AND status='pendente'
        """,
        (guild_id, channel_id),
    )
    store.conn.commit()

    # Deletar as mensagens de cobrança
    guild = bot.get_guild(guild_id)
    if not guild:
        return
    channel = guild.get_channel(channel_id)
    if not channel:
        return
    for mid in message_ids:
        try:
            msg = await channel.fetch_message(mid)
            await msg.delete()
        except discord.HTTPException:
            pass


@bot.tree.command(name="admpix", description="Histórico de pagamentos recebidos por cada dono")
async def admpix(interaction: discord.Interaction):
    if not owner_only(interaction.user):
        await deny_owner(interaction)
        return

    cfg = get_adm_cobranca_config(interaction.guild_id)
    taxa_cents = cfg["taxa_cents"]

    historico = get_historico_por_dono(interaction.guild_id)
    donos_pix = get_donos_pix(interaction.guild_id)

    # Mapa user_id → pix info
    pix_map = {d["user_id"]: d for d in donos_pix}

    if not historico:
        await interaction.response.send_message(
            embed=red_embed(
                f"{EMOJI_PIX}・𝐇𝐈𝐒𝐓Ó𝐑𝐈𝐂𝐎 𝐃𝐄 𝐏𝐈𝐗",
                "Nenhum pagamento confirmado ainda.",
            ),
            ephemeral=True,
        )
        return

    linhas = []
    for row in historico:
        uid = row["dono_user_id"]
        total_pag = row["total_pagamentos"]
        total_cents = row["total_cents"]
        pix_info = pix_map.get(uid)
        pix_txt = f"`{pix_info['pix_chave']}`" if pix_info else "Pix removido"
        linhas.append(
            f"{EMOJI_ADM} <@{uid}>\n"
            f"  {EMOJI_PIX} Chave: {pix_txt}\n"
            f"  <:preco_dinheiro:1516919186046058658> Pagamentos recebidos: **{total_pag}**\n"
            f"  <:preco_dinheiro:1516919186046058658> Total recebido: **{cents_to_money(total_cents)}**\n"
        )

    desc = f"Taxa atual: **{cents_to_money(taxa_cents)}**\n\n" + "\n".join(linhas)

    await interaction.response.send_message(
        embed=red_embed(f"{EMOJI_PIX}・𝐇𝐈𝐒𝐓Ó𝐑𝐈𝐂𝐎 𝐃𝐄 𝐏𝐈𝐗", desc),
        ephemeral=True,
    )


# ════════════════════════════════════════════════════════════════════════════
# SISTEMA DE AUTO MENSAGENS
# ════════════════════════════════════════════════════════════════════════════

store.conn.executescript("""
    CREATE TABLE IF NOT EXISTS automsg_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        nome TEXT NOT NULL,
        canais_json TEXT NOT NULL DEFAULT '[]'
    );
    CREATE TABLE IF NOT EXISTS automsg_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        guild_id INTEGER NOT NULL,
        texto TEXT NOT NULL,
        intervalo_minutos INTEGER NOT NULL DEFAULT 60
    );
    CREATE TABLE IF NOT EXISTS automsg_sent (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        message_id INTEGER NOT NULL,
        channel_id INTEGER NOT NULL
    );
""")
store.conn.commit()

# tasks de loop por mensagem
automsg_tasks: dict[int, asyncio.Task] = {}


def automsg_get_categories(guild_id: int) -> list[sqlite3.Row]:
    return store.conn.execute(
        "SELECT * FROM automsg_categories WHERE guild_id=? ORDER BY nome",
        (guild_id,)
    ).fetchall()


def automsg_get_messages(category_id: int) -> list[sqlite3.Row]:
    return store.conn.execute(
        "SELECT * FROM automsg_messages WHERE category_id=? ORDER BY id",
        (category_id,)
    ).fetchall()


def automsg_get_category(cat_id: int) -> Optional[sqlite3.Row]:
    return store.conn.execute(
        "SELECT * FROM automsg_categories WHERE id=?", (cat_id,)
    ).fetchone()


def automsg_save_sent(guild_id: int, message_id: int, channel_id: int) -> None:
    store.conn.execute(
        "INSERT INTO automsg_sent (guild_id, message_id, channel_id) VALUES (?,?,?)",
        (guild_id, message_id, channel_id)
    )
    store.conn.commit()


def automsg_clear_all(guild_id: int) -> list[dict]:
    sent = store.conn.execute(
        "SELECT message_id, channel_id FROM automsg_sent WHERE guild_id=?", (guild_id,)
    ).fetchall()
    refs = [{"message_id": r["message_id"], "channel_id": r["channel_id"]} for r in sent]
    store.conn.execute("DELETE FROM automsg_sent WHERE guild_id=?", (guild_id,))
    store.conn.execute(
        "DELETE FROM automsg_messages WHERE guild_id=?", (guild_id,)
    )
    store.conn.execute(
        "DELETE FROM automsg_categories WHERE guild_id=?", (guild_id,)
    )
    store.conn.commit()
    return refs


async def _automsg_loop(guild_id: int, msg_id: int, texto: str, channel_ids: list[int], intervalo: int):
    await asyncio.sleep(intervalo * 60)
    while True:
        guild = bot.get_guild(guild_id)
        if not guild:
            break
        for cid in channel_ids:
            ch = guild.get_channel(cid)
            if ch:
                try:
                    sent = await ch.send(texto)
                    automsg_save_sent(guild_id, sent.id, cid)
                except discord.HTTPException:
                    pass
        await asyncio.sleep(intervalo * 60)


def automsg_start_task(guild_id: int, msg_id: int, texto: str, channel_ids: list[int], intervalo: int):
    if msg_id in automsg_tasks:
        automsg_tasks[msg_id].cancel()
    task = bot.loop.create_task(
        _automsg_loop(guild_id, msg_id, texto, channel_ids, intervalo)
    )
    automsg_tasks[msg_id] = task


def automsg_stop_task(msg_id: int):
    task = automsg_tasks.pop(msg_id, None)
    if task:
        task.cancel()


# ── Modais ───────────────────────────────────────────────────────────────────

class AutoMsgCriarCategoriaModal(discord.ui.Modal, title="Criar Categoria"):
    nome = discord.ui.TextInput(
        label="Nome da categoria",
        placeholder="Ex: Privado, Público, Eventos...",
        max_length=50,
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        nome = self.nome.value.strip()
        store.conn.execute(
            "INSERT INTO automsg_categories (guild_id, nome) VALUES (?,?)",
            (self.guild_id, nome)
        )
        store.conn.commit()
        await interaction.response.send_message(
            embed=red_embed(
                f"╭ {EMOJI_V}・𝐂𝐀𝐓𝐄𝐆𝐎𝐑𝐈𝐀 𝐂𝐑𝐈𝐀𝐃𝐀 ╮",
                f"{EMOJI_FORM} Categoria **{nome}** criada com sucesso!\n\n"
                f"{EMOJI_ALERTA} Agora vá em **Ver Categorias** para adicionar mensagens e canais."
            ),
            ephemeral=True
        )


class AutoMsgCriarMensagemModal(discord.ui.Modal, title="Criar Mensagem"):
    texto = discord.ui.TextInput(
        label="Texto da mensagem",
        style=discord.TextStyle.long,
        placeholder="Digite a mensagem que será enviada automaticamente...",
        max_length=2000,
    )
    intervalo = discord.ui.TextInput(
        label="Intervalo em minutos",
        placeholder="Ex: 30 (envia a cada 30 minutos)",
        max_length=6,
    )

    def __init__(self, guild_id: int, category_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.category_id = category_id

    async def on_submit(self, interaction: discord.Interaction):
        try:
            intervalo = int(self.intervalo.value.strip())
            if intervalo < 1:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                f"{EMOJI_X} Intervalo inválido. Use um número inteiro maior que 0.", ephemeral=True
            )
            return

        cur = store.conn.execute(
            "INSERT INTO automsg_messages (category_id, guild_id, texto, intervalo_minutos) VALUES (?,?,?,?)",
            (self.category_id, self.guild_id, self.texto.value.strip(), intervalo)
        )
        store.conn.commit()
        msg_id = cur.lastrowid

        cat = automsg_get_category(self.category_id)
        canais = json.loads(cat["canais_json"]) if cat else []

        if canais:
            automsg_start_task(self.guild_id, msg_id, self.texto.value.strip(), canais, intervalo)

        await interaction.response.send_message(
            embed=red_embed(
                f"╭ {EMOJI_V}・𝐌𝐄𝐍𝐒𝐀𝐆𝐄𝐌 𝐂𝐑𝐈𝐀𝐃𝐀 ╮",
                f"{EMOJI_FORM} Mensagem criada!\n\n"
                f"{EMOJI_RELOGIO} **Intervalo:** {intervalo} minutos\n"
                f"{EMOJI_SALAS} **Canais:** {len(canais)} canal(is) configurado(s)\n\n"
                f"{EMOJI_ALERTA} O bot começará a enviar automaticamente."
            ),
            ephemeral=True
        )


# ── Views ─────────────────────────────────────────────────────────────────────

class AutoMsgCanaisSelect(discord.ui.ChannelSelect):
    def __init__(self, guild_id: int, category_id: int):
        super().__init__(
            placeholder="Selecione os canais de destino...",
            min_values=1,
            max_values=25,
            channel_types=[discord.ChannelType.text],
        )
        self.guild_id = guild_id
        self.category_id = category_id

    async def callback(self, interaction: discord.Interaction):
        canais = [c.id for c in self.values]
        store.conn.execute(
            "UPDATE automsg_categories SET canais_json=? WHERE id=?",
            (json.dumps(canais), self.category_id)
        )
        store.conn.commit()

        msgs = automsg_get_messages(self.category_id)
        for m in msgs:
            automsg_start_task(self.guild_id, m["id"], m["texto"], canais, m["intervalo_minutos"])

        nomes = ", ".join(c.mention for c in self.values)
        await interaction.response.send_message(
            embed=red_embed(
                f"╭ {EMOJI_V}・𝐂𝐀𝐍𝐀𝐈𝐒 𝐒𝐀𝐋𝐕𝐎𝐒 ╮",
                f"{EMOJI_SALAS} Canais configurados:\n{nomes}"
            ),
            ephemeral=True
        )


class AutoMsgCanaisView(discord.ui.View):
    def __init__(self, guild_id: int, category_id: int):
        super().__init__(timeout=120)
        self.add_item(AutoMsgCanaisSelect(guild_id, category_id))


class AutoMsgCategoriaPanel(discord.ui.View):
    def __init__(self, guild_id: int, category_id: int, cat_nome: str):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.category_id = category_id
        self.cat_nome = cat_nome

    @discord.ui.button(label="Criar Mensagem", emoji="<:adicionar:1516913558238265563>", style=discord.ButtonStyle.success)
    async def criar_msg(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            AutoMsgCriarMensagemModal(self.guild_id, self.category_id)
        )

    @discord.ui.button(label="Canais", emoji="<:salas:1516920962258305075>", style=discord.ButtonStyle.secondary)
    async def canais(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=red_embed(
                f"╭ {EMOJI_SALAS}・𝐒𝐄𝐋𝐄𝐂𝐈𝐎𝐍𝐀𝐑 𝐂𝐀𝐍𝐀𝐈𝐒 ╮",
                f"{EMOJI_ALERTA} Selecione os canais onde as mensagens da categoria **{self.cat_nome}** serão enviadas."
            ),
            view=AutoMsgCanaisView(self.guild_id, self.category_id),
            ephemeral=True
        )

    @discord.ui.button(label="Excluir Mensagem", emoji="<:remover:1516913556812075028>", style=discord.ButtonStyle.danger)
    async def excluir_msg(self, interaction: discord.Interaction, button: discord.ui.Button):
        msgs = automsg_get_messages(self.category_id)
        if not msgs:
            await interaction.response.send_message(
                f"{EMOJI_X} Nenhuma mensagem nesta categoria.", ephemeral=True
            )
            return
        view = AutoMsgExcluirMsgView(self.guild_id, self.category_id, msgs)
        await interaction.response.send_message(
            embed=red_embed(
                f"╭ {EMOJI_ENCERRAR}・𝐄𝐗𝐂𝐋𝐔𝐈𝐑 𝐌𝐄𝐍𝐒𝐀𝐆𝐄𝐌 ╮",
                f"{EMOJI_ALERTA} Selecione a mensagem que deseja excluir."
            ),
            view=view,
            ephemeral=True
        )


class AutoMsgExcluirMsgSelect(discord.ui.Select):
    def __init__(self, guild_id: int, msgs: list):
        options = [
            discord.SelectOption(
                label=f"Mensagem #{m['id']}",
                description=m["texto"][:80],
                value=str(m["id"])
            )
            for m in msgs[:25]
        ]
        super().__init__(placeholder="Selecione a mensagem...", options=options)
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        msg_id = int(self.values[0])
        automsg_stop_task(msg_id)
        store.conn.execute("DELETE FROM automsg_messages WHERE id=?", (msg_id,))
        store.conn.commit()
        await interaction.response.send_message(
            embed=red_embed(
                f"╭ {EMOJI_V}・𝐌𝐄𝐍𝐒𝐀𝐆𝐄𝐌 𝐄𝐗𝐂𝐋𝐔𝐈́𝐃𝐀 ╮",
                f"{EMOJI_X} Mensagem **#{msg_id}** excluída e envio automático cancelado."
            ),
            ephemeral=True
        )


class AutoMsgExcluirMsgView(discord.ui.View):
    def __init__(self, guild_id: int, category_id: int, msgs: list):
        super().__init__(timeout=60)
        self.add_item(AutoMsgExcluirMsgSelect(guild_id, msgs))


class AutoMsgVerCategoriasSelect(discord.ui.Select):
    def __init__(self, guild_id: int, cats: list):
        options = [
            discord.SelectOption(
                label=c["nome"],
                description=f"ID #{c['id']}",
                value=str(c["id"])
            )
            for c in cats[:25]
        ]
        super().__init__(placeholder="Selecione uma categoria...", options=options)
        self.guild_id = guild_id
        self.cats = {c["id"]: c for c in cats}

    async def callback(self, interaction: discord.Interaction):
        cat_id = int(self.values[0])
        cat = self.cats.get(cat_id)
        if not cat:
            await interaction.response.send_message(f"{EMOJI_X} Categoria não encontrada.", ephemeral=True)
            return

        canais = json.loads(cat["canais_json"])
        msgs = automsg_get_messages(cat_id)

        desc = (
            f"{EMOJI_FORM} **Categoria:** {cat['nome']}\n"
            f"{EMOJI_SALAS} **Canais:** {len(canais)} configurado(s)\n"
            f"{EMOJI_RELOGIO} **Mensagens:** {len(msgs)} criada(s)\n\n"
            f"{EMOJI_ALERTA} Use os botões abaixo para gerenciar."
        )
        await interaction.response.send_message(
            embed=red_embed(f"╭ {EMOJI_FORM}・{cat['nome'].upper()} ╮", desc),
            view=AutoMsgCategoriaPanel(self.guild_id, cat_id, cat["nome"]),
            ephemeral=True
        )


class AutoMsgVerCategoriasView(discord.ui.View):
    def __init__(self, guild_id: int, cats: list):
        super().__init__(timeout=60)
        self.add_item(AutoMsgVerCategoriasSelect(guild_id, cats))


class AutoMsgMainView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=120)
        self.guild_id = guild_id

    @discord.ui.button(label="Criar Categoria", emoji="<:adicionar:1516913558238265563>", style=discord.ButtonStyle.success, row=0)
    async def criar_categoria(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AutoMsgCriarCategoriaModal(self.guild_id))

    @discord.ui.button(label="Ver Categorias", emoji="<:config:1516913563531215009>", style=discord.ButtonStyle.secondary, row=0)
    async def ver_categorias(self, interaction: discord.Interaction, button: discord.ui.Button):
        cats = automsg_get_categories(self.guild_id)
        if not cats:
            await interaction.response.send_message(
                f"{EMOJI_X} Nenhuma categoria criada ainda. Clique em **Criar Categoria**.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            embed=red_embed(
                f"╭ {EMOJI_FORM}・𝐂𝐀𝐓𝐄𝐆𝐎𝐑𝐈𝐀𝐒 ╮",
                f"{EMOJI_ALERTA} Selecione uma categoria para gerenciar."
            ),
            view=AutoMsgVerCategoriasView(self.guild_id, cats),
            ephemeral=True
        )

    @discord.ui.button(label="Enviar Todas", emoji="<a:sucesso_animado:1516913609303658506>", style=discord.ButtonStyle.primary, row=1)
    async def enviar_todas(self, interaction: discord.Interaction, button: discord.ui.Button):
        cats = automsg_get_categories(self.guild_id)
        if not cats:
            await interaction.response.send_message(f"{EMOJI_X} Nenhuma categoria criada.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        total_enviadas = 0
        for cat in cats:
            canais = json.loads(cat["canais_json"])
            if not canais:
                continue
            msgs = automsg_get_messages(cat["id"])
            for m in msgs:
                for cid in canais:
                    ch = interaction.guild.get_channel(cid)
                    if ch:
                        try:
                            sent = await ch.send(m["texto"])
                            automsg_save_sent(self.guild_id, sent.id, cid)
                            total_enviadas += 1
                        except discord.HTTPException:
                            pass

        await interaction.followup.send(
            embed=red_embed(
                f"╭ {EMOJI_V}・𝐄𝐍𝐕𝐈𝐀𝐃𝐎 ╮",
                f"{EMOJI_V} **{total_enviadas}** mensagem(ns) enviada(s) em todos os canais configurados."
            ),
            ephemeral=True
        )

    @discord.ui.button(label="Excluir Tudo", emoji="<a:erro_animado:1516913586054631558>", style=discord.ButtonStyle.danger, row=1)
    async def excluir_tudo(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=red_embed(
                f"╭ {EMOJI_ALERTA}・𝐂𝐎𝐍𝐅𝐈𝐑𝐌𝐀𝐑 ╮",
                f"{EMOJI_ALERTA} Isso vai apagar **todas** as categorias, mensagens e deletar todas as mensagens enviadas pelo bot.\n\n"
                f"{EMOJI_X} Tem certeza?"
            ),
            view=AutoMsgConfirmarExcluirView(self.guild_id),
            ephemeral=True
        )


class AutoMsgConfirmarExcluirView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=30)
        self.guild_id = guild_id

    @discord.ui.button(label="Sim, excluir tudo", emoji="<a:erro_animado:1516913586054631558>", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Para todas as tasks
        msgs = store.conn.execute(
            "SELECT id FROM automsg_messages WHERE guild_id=?", (self.guild_id,)
        ).fetchall()
        for m in msgs:
            automsg_stop_task(m["id"])

        refs = automsg_clear_all(self.guild_id)
        await interaction.response.defer(ephemeral=True)

        deletadas = 0
        for ref in refs:
            ch = interaction.guild.get_channel(ref["channel_id"])
            if ch:
                try:
                    msg = await ch.fetch_message(ref["message_id"])
                    await msg.delete()
                    deletadas += 1
                except discord.HTTPException:
                    pass

        await interaction.followup.send(
            embed=red_embed(
                f"╭ {EMOJI_V}・𝐄𝐗𝐂𝐋𝐔𝐈́𝐃𝐎 ╮",
                f"{EMOJI_X} Tudo apagado!\n\n"
                f"{EMOJI_REEMBOLSO} Mensagens deletadas nos canais: **{deletadas}**\n"
                f"{EMOJI_ENCERRAR} Categorias e mensagens removidas do sistema."
            ),
            ephemeral=True
        )

    @discord.ui.button(label="Cancelar", emoji="<:sair:1516917997539692655>", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"{EMOJI_V} Cancelado.", ephemeral=True)


# ── Comando slash ─────────────────────────────────────────────────────────────

@bot.tree.command(name="automensagem", description="Painel de auto mensagens automáticas")
async def automensagem(interaction: discord.Interaction):
    if not owner_only(interaction.user):
        await deny_owner(interaction)
        return

    cats = automsg_get_categories(interaction.guild_id)
    desc = (
        f"{EMOJI_FORM} **Categorias criadas:** {len(cats)}\n\n"
        f"<:adicionar:1516913558238265563> **Criar Categoria** — cria uma nova categoria\n"
        f"<:config:1516913563531215009> **Ver Categorias** — gerencia categorias existentes\n"
        f"<a:sucesso_animado:1516913609303658506> **Enviar Todas** — envia todas as mensagens agora\n"
        f"<a:erro_animado:1516913586054631558> **Excluir Tudo** — apaga tudo e deleta mensagens enviadas"
    )
    await interaction.response.send_message(
        embed=red_embed(f"╭ {EMOJI_COMPUTER}・𝐀𝐔𝐓𝐎 𝐌𝐄𝐍𝐒𝐀𝐆𝐄𝐍𝐒 ╮", desc),
        view=AutoMsgMainView(interaction.guild_id),
        ephemeral=True
    )


# ════════════════════════════════════════════════════════════════════════════

import final_extensions
final_extensions.setup(globals())

import events_extension
events_extension.setup(globals())

token = os.getenv("DISCORD_TOKEN", "").strip().strip('"').strip("'")
if not token or token == "coloque_seu_token_aqui":
    raise RuntimeError("Configure DISCORD_TOKEN no arquivo .env")
if not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token):
    raise RuntimeError("DISCORD_TOKEN tem formato inválido. Cole somente o token do bot, sem Bot, aspas ou espaços.")

bot.run(token)
