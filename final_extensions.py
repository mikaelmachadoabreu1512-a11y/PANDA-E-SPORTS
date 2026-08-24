import asyncio
import json
import random
import re
import sqlite3
from typing import Any, Optional

import discord


EM = {
    "sucesso": "<a:sucesso_animado:1516913609303658506>",
    "erro": "<a:erro_animado:1516913586054631558>",
    "aviso": "<a:alerta_staff_animado:1516913572280533063>",
    "alerta": "<a:alerta_staff_animado:1516913572280533063>",
    "sino": "<a:anuncio_animado:1516913573748539402>",
    "bloqueado": "<:bloqueado:1516913576848130208>",
    "config": "<:config:1516913563531215009>",
    "editar": "<:editar:1516913582070304768>",
    "adicionar": "<:adicionar:1516913558238265563>",
    "remover": "<:remover:1516913556812075028>",
    "limpar": "<:limpar:1516913544476627294>",
    "atualizar": "<a:atualizar:1516913555276955778>",
    "verificar": "<:verificar:1516913570120470559>",
    "iniciar": "<:iniciar:1516913565028716625>",
    "parar": "<:parar:1516913548146769940>",
    "sair": "<:sair:1516917997539692655>",
    "ajuda": "<:ajuda:1516913559781507212>",
    "apostas": "<:modoapostas:1516913590530080998>",
    "modo": "<:modoapostas:1516913590530080998>",
    "freefire": "<:free_fire:1516913587967361055>",
    "free_fire": "<:free_fire:1516913587967361055>",
    "emulador": "<:emulador_bluestacks:1516913584679026731>",
    "bluestacks": "<:emulador_bluestacks:1516913584679026731>",
    "ump": "<:arma_ump:1516913575237652572>",
    "preco": "<:preco:1516913562147229726>",
    "taxa": "<:preco_dinheiro:1516919186046058658>",
    "dinheiro": "<a:dinheiro_animado:1516913580614619157>",
    "jogador": "<:perfil_usuario:1516913596842643557>",
    "jogadores": "<:perfil_usuario:1516913596842643557>",
    "perfil": "<:perfil_usuario:1516913596842643557>",
    "historico": "<:email:1516913583273934959>",
    "relatorio": "<:email:1516913583273934959>",
    "ranking": "<a:ranking:1516913552034631721>",
    "ganhador": "<a:ganhador:1516913568639877140>",
    "trofeu": "<:ranking_trofeu:1516913603863908373>",
    "sala": "<:salas:1516920962258305075>",
    "gelo": "<:gelo:1516915451999813682>",
    "pix": "<:pix:1516913599988105378>",
    "coins": "<:coins:1516913545856417972>",
    "saldo": "<:preco:1516913562147229726>",
    "reembolso": "<:preco_dinheiro:1516919186046058658>",
    "mediador": "<:staff:1516913606795464805>",
    "staff": "<:staff:1516913606795464805>",
    "online": "<:online:1516915759790559315>",
    "offline": "<:offline:1516915772922794015>",
    "ticket": "<:divulgacao:1516913611304603842>",
    "suporte": "<:56644tools1:1516917629841969232>",
    "evento": "<:presente:1516913602399834132>",
    "presente": "<:presente:1516913602399834132>",
    "divulgacao": "<:divulgacao:1516913611304603842>",
    "divulgaao": "<:divulgacao:1516913611304603842>",
    "loja": "<:loja_carrinho:1516913591817736212>",
    "carrinho": "<:loja_carrinho:1516913591817736212>",
    "computador": "<:computador:1516913579591340284>",
    "cadeado": "<:cadeado_privado:1516913578077061130>",
    "privado": "<:cadeado_privado:1516913578077061130>",
    "tempo": "<:relogio:1516913566253580470>",
    "relogio": "<:relogio:1516913566253580470>",
    "id": "🆔",
    "imagem": "🖼️",
    "link": "🔗",
    "canal": "#️⃣",
    "backup": "💾",
    "restaurar": "♻️",
    "emoji": "😀",
    "data": "📅",
}


def setup(ctx: dict[str, Any]) -> None:
    bot = ctx["bot"]
    store = ctx["store"]
    discord_mod = ctx["discord"]
    money_to_cents = ctx["money_to_cents"]
    cents_to_money = ctx["cents_to_money"]
    pretty_mode = ctx["pretty_mode"]
    queue_players = ctx["queue_players"]
    red_embed = ctx["red_embed"]
    ensure_channel_name = ctx["ensure_channel_name"]
    is_owner_member = ctx["is_owner_member"]
    owner_only = ctx["owner_only"]
    deny_owner = ctx["deny_owner"]
    is_admin_member = ctx["is_admin_member"]
    queue_lock = ctx["queue_lock"]
    validate_kind_mode = ctx["validate_kind_mode"]
    match_embed = ctx["match_embed"]
    send_mediator_alert = ctx["send_mediator_alert"]
    make_qr_file = ctx["make_qr_file"]
    pix_copy_code = ctx["pix_copy_code"]
    get_adm_cobranca_config = ctx["get_adm_cobranca_config"]
    get_donos_pix = ctx["get_donos_pix"]

    # Replace the old emoji globals without changing the original flow.
    replacements = {
        "EMOJI_ADM": EM["staff"],
        "EMOJI_OFFLINE": EM["offline"],
        "EMOJI_ONLINE": EM["online"],
        "EMOJI_EMPATE": EM["atualizar"],
        "EMOJI_SALAS": EM["sala"],
        "EMOJI_RENOMEAR": EM["editar"],
        "EMOJI_ENCERRAR": EM["erro"],
        "EMOJI_FINALIZAR_WO": EM["trofeu"],
        "EMOJI_GANHADOR": EM["ganhador"],
        "EMOJI_FORM": "📧",
        "EMOJI_ALERTA": EM["aviso"],
        "EMOJI_COMPUTER": EM["computador"],
        "EMOJI_FF": EM["freefire"],
        "EMOJI_GELO": EM["gelo"],
        "EMOJI_PIX": EM["pix"],
        "EMOJI_UMP": EM["ump"],
        "EMOJI_BLUESTACKS": EM["emulador"],
        "EMOJI_V": EM["sucesso"],
        "EMOJI_X": EM["erro"],
        "EMOJI_VAGAS_MEDIADOR": EM["staff"],
        "EMOJI_EVENTO": EM["presente"],
        "EMOJI_DIVULGACAO": EM["divulgacao"],
        "EMOJI_RELOGIO": EM["relogio"],
        "EMOJI_GANHADOR_TROFEU": EM["ganhador"],
        "EMOJI_WO": EM["trofeu"],
        "EMOJI_REEMBOLSO": EM["reembolso"],
        "EMOJI_SUPORTE": EM["suporte"],
        "EMOJI_VERIFICADO": EM["sucesso"],
        "EMOJI_EMU": EM["emulador"],
        "EMOJI_SAIR": EM["sair"],
    }
    ctx.update(replacements)

    def ensure_final_schema() -> None:
        store.ensure_columns(
            "settings",
            {
                "log_open_channel_id": "INTEGER",
                "log_confirmed_channel_id": "INTEGER",
                "log_cancelled_channel_id": "INTEGER",
                "log_finished_channel_id": "INTEGER",
                "store_channel_id": "INTEGER",
                "store_logs_channel_id": "INTEGER",
                "store_cart_category_id": "INTEGER",
                "roulette_channel_id": "INTEGER",
                "roulette_logs_channel_id": "INTEGER",
                "roulette_cost": "INTEGER NOT NULL DEFAULT 10",
                "roulette_chance": "INTEGER NOT NULL DEFAULT 15",
                "entry_payment_cents": "INTEGER NOT NULL DEFAULT 300",
                "entry_payment_channel_id": "INTEGER",
                "ticket_image_url": "TEXT",
            },
        )
        store.ensure_columns("support_tickets", {"assigned_staff_id": "INTEGER", "claimed_by": "INTEGER"})
        store.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_coins (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                coins INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS coin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS store_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT,
                role_id INTEGER,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS roulette_prizes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                role_id INTEGER,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS entry_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pendente',
                pix_nome TEXT,
                pix_chave TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reviewed_by INTEGER
            );
            -- Mensagem atual do lifecycle (Abertas -> Confirmadas -> Canceladas/Finalizadas)
            -- Guardamos message_id para conseguir deletar a mensagem antiga ao trocar de canal.
            CREATE TABLE IF NOT EXISTS bet_lifecycle_messages (
                guild_id INTEGER NOT NULL,
                bet_id INTEGER NOT NULL,
                stage TEXT NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, bet_id)
            );
            """
        )
        store.conn.commit()

    ensure_final_schema()

    def replace_emoji_shortcuts(text: str) -> str:
        def repl(match: re.Match[str]) -> str:
            return EM.get(match.group(1).strip().lower(), match.group(0))
        return re.sub(r"<([a-zA-Z0-9_]+)>", repl, text or "")

    def get_coins(guild_id: int, user_id: int) -> int:
        store.conn.execute(
            "INSERT OR IGNORE INTO user_coins (guild_id, user_id, coins) VALUES (?, ?, 0)",
            (guild_id, user_id),
        )
        store.conn.commit()
        row = store.conn.execute(
            "SELECT coins FROM user_coins WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        ).fetchone()
        return int(row["coins"] if row else 0)

    def add_coins(guild_id: int, user_id: int, amount: int, reason: str = "") -> int:
        get_coins(guild_id, user_id)
        store.conn.execute(
            "UPDATE user_coins SET coins=coins+? WHERE guild_id=? AND user_id=?",
            (amount, guild_id, user_id),
        )
        store.conn.execute(
            "INSERT INTO coin_logs (guild_id, user_id, amount, reason) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, amount, reason),
        )
        store.conn.commit()
        return get_coins(guild_id, user_id)

    def status_name(status: str) -> str:
        return {
            "open": "Aberta",
            "awaiting_mediator": "Confirmada",
            "payment": "Pagamento",
            "closed": "Finalizada",
            "cancelled": "Cancelada",
            "draw": "Empate",
        }.get(status or "", (status or "desconhecido").title())

    def queue_embed(queue: sqlite3.Row) -> discord.Embed:
        players = queue_players(queue)
        if players:
            text = "\n".join(
                f"{EM['jogadores']} <@{p['user_id']}> - {p['choice']}" if p.get("choice")
                else f"{EM['jogadores']} <@{p['user_id']}>"
                for p in players
            )
            if len(players) < 2:
                text += f"\n\n{EM['jogadores']} 𝐀𝐠𝐮𝐚𝐫𝐝𝐚𝐧𝐝𝐨 𝐨𝐮𝐭𝐫𝐨 𝐣𝐨𝐠𝐚𝐝𝐨𝐫..."
        else:
            text = f"{EM['jogadores']} 𝐀𝐠𝐮𝐚𝐫𝐝𝐚𝐧𝐝𝐨 𝐣𝐨𝐠𝐚𝐝𝐨𝐫𝐞𝐬..."
        from discord import Embed, Color
        title_styled = {
            "1v1": "𝟏𝐕𝟏", "2v2": "𝟐𝐕𝟐", "3v3": "𝟑𝐕𝟑", "4v4": "𝟒𝐕𝟒",
        }.get(queue["kind"], queue["kind"].upper())
        embed = red_embed(
            f"╭ {title_styled}・𝐅𝐈𝐋𝐀𝐒 ╮",
            (
                f"{EM['freefire']} 𝐌𝐨𝐝𝐨: **{queue['kind']} {pretty_mode(queue['mode'])}**\n"
                f"{EM['preco']} 𝐕𝐚𝐥𝐨𝐫: **{cents_to_money(queue['value_cents'])}**\n"
                f"{EM['taxa']} 𝐓𝐚𝐱𝐚: **{cents_to_money(queue['fee_cents'])}**\n\n"
                f"{EM['jogadores']} 𝐉𝐨𝐠𝐚𝐝𝐨𝐫𝐞𝐬:\n{text}"
            ),
        )
        if queue["image_url"]:
            embed.set_thumbnail(url=queue["image_url"])
        return embed

    ctx["queue_embed"] = queue_embed

    def entry_private_message(queue: sqlite3.Row, choice: str) -> str:
        extra = f"\n{EM['modo']} Escolha: **{choice}**" if choice and choice != "Entrar" else ""
        return (
            f"{EM['sucesso']} Você entrou na fila.\n\n"
            f"{EM['modo']} Modo: **{queue['kind']} {pretty_mode(queue['mode'])}**\n"
            f"{EM['preco']} Valor: **{cents_to_money(queue['value_cents'])}**\n"
            f"{EM['taxa']} Taxa: **{cents_to_money(queue['fee_cents'])}**"
            f"{extra}\n\n{EM['tempo']} Aguarde outro jogador."
        )

    ctx["entry_private_message"] = entry_private_message

    async def send_bet_log(guild: discord.Guild, key: str, embed: discord.Embed) -> None:
        settings = store.settings(guild.id)
        field = {
            "open": "log_open_channel_id",
            "confirmed": "log_confirmed_channel_id",
            "cancelled": "log_cancelled_channel_id",
            "finished": "log_finished_channel_id",
        }.get(key)
        channel_id = settings[field] if field and field in settings.keys() else None
        channel = guild.get_channel(channel_id) if channel_id else None
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                pass

    def bet_log_embed(bet: sqlite3.Row, title: str, status: str, extra: str = "") -> discord.Embed:
        desc = (
            f"{EM['jogadores']} **Jogadores:** <@{bet['player1_id']}> vs <@{bet['player2_id']}>\n"
            f"{EM['modo']} **Modo:** {bet['kind']} {pretty_mode(bet['mode'])}\n"
            f"{EM['preco']} **Valor:** {cents_to_money(bet['value_cents'])}\n"
            f"{EM['taxa']} **Taxa:** {cents_to_money(bet['fee_cents'])}\n"
            f"{EM['verificar']} **Status:** {status}"
        )
        if extra:
            desc += "\n" + extra
        return discord.Embed(title=title, description=desc, color=discord.Color(0x2B2D31))

    def bet_lifecycle_embed(bet: sqlite3.Row, stage: str) -> discord.Embed:
        stage = (stage or "").lower().strip()

        if stage == "confirmed":
            admin_id = bet["admin_id"] if "admin_id" in bet.keys() else None
            mediador_text = f"<@{admin_id}>" if admin_id else "Aguardando mediador"
            desc = (
                f"{EM['mediador']} Mediador: {mediador_text}\n"
                f"{EM['jogadores']} Jogadores: <@{bet['player1_id']}> vs <@{bet['player2_id']}>\n"
                f"{EM['freefire']} Modo: {bet['kind']} {pretty_mode(bet['mode'])}\n"
                f"{EM['preco']} Valor: **{cents_to_money(bet['value_cents'])}**\n"
                f"{EM['taxa']} Taxa: **{cents_to_money(bet['fee_cents'])}**\n\n"
                f"{EM['sucesso']} Confirmada (aguardando mediador)"
            )
            return red_embed(f"╭ {EM['sucesso']}・𝐀𝐏𝐎𝐒𝐓𝐀 𝐂𝐎𝐍𝐅𝐈𝐑𝐌𝐀𝐃𝐀 ╮", desc)

        elif stage == "cancelled":
            desc = (
                f"{EM['jogadores']} Jogadores: <@{bet['player1_id']}> vs <@{bet['player2_id']}>\n"
                f"{EM['freefire']} Modo: {bet['kind']} {pretty_mode(bet['mode'])}\n"
                f"{EM['preco']} Valor: **{cents_to_money(bet['value_cents'])}**\n"
                f"{EM['taxa']} Taxa: **{cents_to_money(bet['fee_cents'])}**\n\n"
                f"{EM['erro']} Cancelada"
            )
            return red_embed(f"╭ {EM['erro']}・𝐀𝐏𝐎𝐒𝐓𝐀 𝐂𝐀𝐍𝐂𝐄𝐋𝐀𝐃𝐀 ╮", desc)

        elif stage == "finished":
            winner_id = bet["winner_id"] if "winner_id" in bet.keys() else None
            if winner_id:
                loser_id = bet["player2_id"] if winner_id == bet["player1_id"] else bet["player1_id"]
                resultado = (
                    f"\n{EM['ganhador']} Vencedor: <@{winner_id}>\n"
                    f"{EM['erro']} Perdedor: <@{loser_id}>"
                )
            else:
                resultado = f"\n{EM['ganhador']} Resultado registrado"
            desc = (
                f"{EM['jogadores']} Jogadores: <@{bet['player1_id']}> vs <@{bet['player2_id']}>\n"
                f"{EM['freefire']} Modo: {bet['kind']} {pretty_mode(bet['mode'])}\n"
                f"{EM['preco']} Valor: **{cents_to_money(bet['value_cents'])}**\n"
                f"{EM['taxa']} Taxa: **{cents_to_money(bet['fee_cents'])}**"
                f"{resultado}"
            )
            return red_embed(f"╭ {EM['ganhador']}・𝐀𝐏𝐎𝐒𝐓𝐀 𝐅𝐈𝐍𝐀𝐋𝐈𝐙𝐀𝐃𝐀 ╮", desc)

        else:  # open ou outros
            desc = (
                f"{EM['jogadores']} Jogadores: <@{bet['player1_id']}> vs <@{bet['player2_id']}>\n"
                f"{EM['freefire']} Modo: {bet['kind']} {pretty_mode(bet['mode'])}\n"
                f"{EM['preco']} Valor: **{cents_to_money(bet['value_cents'])}**\n"
                f"{EM['taxa']} Taxa: **{cents_to_money(bet['fee_cents'])}**\n\n"
                f"{EM['relogio']} Aguardando confirmação"
            )
            return red_embed(f"╭ {EM['iniciar']}・𝐀𝐏𝐎𝐒𝐓𝐀 𝐀𝐁𝐄𝐑𝐓𝐀 ╮", desc)

    def _bet_lifecycle_field_for_stage(stage: str) -> Optional[str]:
        return {
            "open": "log_open_channel_id",
            "confirmed": "log_confirmed_channel_id",
            "cancelled": "log_cancelled_channel_id",
            "finished": "log_finished_channel_id",
        }.get((stage or "").lower().strip())

    async def bet_lifecycle_transition(guild: discord.Guild, bet: sqlite3.Row, stage: str) -> None:
        stage = (stage or "").lower().strip()
        field = _bet_lifecycle_field_for_stage(stage)
        if not field:
            return

        settings = store.settings(guild.id)
        channel_id = settings[field] if hasattr(settings, "keys") and field in settings.keys() else None
        if not channel_id:
            return

        # Deleta a mensagem anterior do lifecycle (se existir).
        prev = store.conn.execute(
            "SELECT channel_id, message_id FROM bet_lifecycle_messages WHERE guild_id=? AND bet_id=?",
            (guild.id, bet["id"]),
        ).fetchone()
        if prev:
            old_channel_id = prev["channel_id"]
            old_message_id = prev["message_id"]
            old_channel = guild.get_channel(old_channel_id)
            if old_channel is None:
                try:
                    old_channel = await guild.fetch_channel(old_channel_id)
                except discord.HTTPException:
                    old_channel = None
            if old_channel:
                try:
                    old_msg = await old_channel.fetch_message(old_message_id)
                    await old_msg.delete()
                except discord.HTTPException:
                    pass
                except discord.NotFound:
                    pass

        channel = guild.get_channel(channel_id)
        if channel is None:
            try:
                channel = await guild.fetch_channel(channel_id)
            except discord.HTTPException:
                channel = None
        if channel is None:
            return

        try:
            sent = await channel.send(embed=bet_lifecycle_embed(bet, stage))
        except discord.HTTPException:
            return

        store.conn.execute(
            """
            INSERT OR REPLACE INTO bet_lifecycle_messages (guild_id, bet_id, stage, channel_id, message_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (guild.id, bet["id"], stage, channel_id, sent.id),
        )
        store.conn.commit()

    async def complete_queue(guild: discord.Guild, queue: sqlite3.Row, players: list[dict[str, Any]], origin) -> bool:
        bet_id = store.create_bet(queue, players, None)
        settings = store.settings(guild.id)
        counter = store.next_counter(guild.id, "queue_counter")
        category = guild.get_channel(settings["queue_category_id"]) if settings["queue_category_id"] else None
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        for role_field in ("staff_role_id", "owner_role_id"):
            role_id = settings[role_field] if role_field in settings.keys() else None
            role = guild.get_role(role_id) if role_id else None
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        for player in players:
            member = guild.get_member(player["user_id"])
            if member:
                overwrites[member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        channel = await guild.create_text_channel(f"fila-{counter:04d}", category=category, overwrites=overwrites)
        store.update_bet(bet_id, queue_channel_id=channel.id)
        bet = store.bet(bet_id)
        await channel.send(content=f"<@{players[0]['user_id']}> <@{players[1]['user_id']}>", embed=match_embed(bet), view=ctx["ConfirmView"](bet_id))
        await bet_lifecycle_transition(guild, bet, "open")
        return True

    ctx["complete_queue"] = complete_queue

    async def close_bet_channel(channel, bet_id: int, winner_id: Optional[int]) -> None:
        bet = store.bet(bet_id)
        if not bet:
            return
        guild = channel.guild
        if winner_id:
            loser_id = bet["player2_id"] if winner_id == bet["player1_id"] else bet["player1_id"]
            store.update_bet(bet_id, status="closed", winner_id=winner_id)
            bet = store.bet(bet_id)
            await bet_lifecycle_transition(guild, bet, "finished")
        else:
            store.update_bet(bet_id, status="cancelled")
            bet = store.bet(bet_id)
            await bet_lifecycle_transition(guild, bet, "cancelled")
        await asyncio.sleep(3)
        try:
            await channel.delete(reason="Aposta encerrada")
        except discord.HTTPException:
            pass

    ctx["close_bet_channel"] = close_bet_channel

    class ConfirmView(discord.ui.View):
        def __init__(self, bet_id: int):
            super().__init__(timeout=None)
            self.bet_id = bet_id

        @discord.ui.button(label="Confirmar", emoji=EM["sucesso"], style=discord.ButtonStyle.secondary, custom_id="bet_confirm")
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
                await interaction.response.send_message(f"{EM['aviso']} Você já confirmou.", ephemeral=True)
                return
            confirms[str(interaction.user.id)] = True
            store.update_bet(self.bet_id, confirms_json=json.dumps(confirms))
            bet = store.bet(self.bet_id)
            await interaction.message.edit(embed=match_embed(bet), view=self)
            await interaction.response.send_message(f"{EM['sucesso']} Confirmação registrada.", ephemeral=True)
            if confirms.get(str(bet["player1_id"])) and confirms.get(str(bet["player2_id"])):
                store.update_bet(self.bet_id, status="awaiting_mediator")
                bet = store.bet(self.bet_id)
                await interaction.message.edit(embed=match_embed(bet), view=None)
                await interaction.channel.send(embed=red_embed(f"{EM['mediador']} Aguardando Mediador", "Os dois jogadores confirmaram. Um mediador pode assumir a aposta."))
                await bet_lifecycle_transition(interaction.guild, bet, "confirmed")
                await send_mediator_alert(interaction.guild, bet, interaction.channel)

        @discord.ui.button(label="Regras", emoji="📜", style=discord.ButtonStyle.secondary, custom_id="bet_rules")
        async def rules(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("Combine as regras da partida com o adversário antes de confirmar.", ephemeral=True)

        @discord.ui.button(label="Cancelar", emoji=EM["erro"], style=discord.ButtonStyle.danger, custom_id="bet_cancel")
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            bet = store.bet(self.bet_id)
            if not bet:
                return
            allowed = {bet["player1_id"], bet["player2_id"], bet["admin_id"]}
            if interaction.user.id not in allowed and not is_owner_member(interaction.user):
                await interaction.response.send_message("Você não pode cancelar esta aposta.", ephemeral=True)
                return
            await interaction.response.send_message(f"{EM['erro']} Aposta cancelada.")
            await close_bet_channel(interaction.channel, self.bet_id, winner_id=None)

    ctx["ConfirmView"] = ConfirmView

    # Backup completo.
    def final_backup_data(guild_id: int) -> dict[str, Any]:
        tables = [
            "settings", "pix", "admin_presence", "admin_stats", "queue_panel_channels",
            "queue_panel_values", "ticket_settings", "blacklist", "form_submissions",
            "divulgacao_channels", "welcome_settings", "adm_cobranca_config",
            "adm_donos_pix", "adm_pix_historico", "adm_pagamentos", "user_coins",
            "coin_logs", "store_products", "roulette_prizes", "entry_payments",
            "ticket_ratings", "invite_config", "invite_tracking",
        ]
        data: dict[str, Any] = {"guild_id": guild_id, "tables": {}}
        for table in tables:
            try:
                rows = store.conn.execute(f"SELECT * FROM {table} WHERE guild_id=?", (guild_id,)).fetchall()
                data["tables"][table] = [dict(row) for row in rows]
            except sqlite3.Error:
                data["tables"][table] = []
        return data

    def final_restore_data(guild_id: int, data: dict[str, Any]) -> None:
        tables = data.get("tables", {})
        allowed = set(final_backup_data(guild_id)["tables"].keys())
        with store.conn:
            for table, rows in tables.items():
                if table not in allowed:
                    continue
                store.conn.execute(f"DELETE FROM {table} WHERE guild_id=?", (guild_id,))
                for row in rows:
                    row = dict(row)
                    row["guild_id"] = guild_id
                    columns = list(row.keys())
                    placeholders = ", ".join("?" for _ in columns)
                    store.conn.execute(
                        f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                        [row[c] for c in columns],
                    )

    store.backup_data = final_backup_data
    store.restore_data = final_restore_data

    # Ticket melhorado: mantem o painel/formulario original, troca so a abertura.
    ticket_topics = [
        discord.SelectOption(label="SUPORTE", emoji=EM["suporte"], value="suporte", description="Atendimento geral e dúvidas."),
        discord.SelectOption(label="REEMBOLSO", emoji=EM["reembolso"], value="reembolso", description="Solicitar análise de reembolso."),
        discord.SelectOption(label="RECEBER EVENTO", emoji=EM["presente"], value="evento", description="Solicitar recebimento de evento."),
        discord.SelectOption(label="VAGAS MEDIADOR", emoji=EM["staff"], value="vagas_mediador", description="Atendimento sobre vagas de mediador."),
        discord.SelectOption(label="DIVULGACAO", emoji=EM["divulgacao"], value="divulgacao", description="Solicitar divulgação."),
    ]
    ctx["TICKET_TOPICS"] = ticket_topics

    def pick_online_support(guild: discord.Guild, role: Optional[discord.Role]) -> Optional[discord.Member]:
        if not role:
            return None
        candidates = [m for m in role.members if not m.bot and m.status != discord.Status.offline]
        return sorted(candidates, key=lambda m: m.id)[0] if candidates else None

    class TicketTopicSelect(discord.ui.Select):
        def __init__(self):
            super().__init__(
                placeholder="Selecione uma opção para iniciar seu atendimento.",
                options=ticket_topics,
                custom_id="ticket_topic_select",
            )

        async def callback(self, interaction: discord.Interaction):
            topic_value = self.values[0]
            topic_label = next(o.label for o in ticket_topics if o.value == topic_value)
            ts = store.ticket_settings(interaction.guild_id)
            if not ts["category_id"]:
                await interaction.response.send_message(f"{EM['aviso']} O sistema de tickets não está configurado.", ephemeral=True)
                return
            category = interaction.guild.get_channel(ts["category_id"])
            staff_role = interaction.guild.get_role(ts["staff_role_id"]) if ts["staff_role_id"] else None
            assigned = pick_online_support(interaction.guild, staff_role)
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            }
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            channel_name = ensure_channel_name(f"ticket-{interaction.user.display_name}-{topic_value.replace('_', '-')}")
            channel = await interaction.guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
            ticket_id = store.create_ticket(interaction.guild_id, channel.id, interaction.user.id, topic_label)
            if assigned:
                store.conn.execute("UPDATE support_tickets SET assigned_staff_id=? WHERE id=?", (assigned.id, ticket_id))
                store.conn.commit()
            staff_text = assigned.mention if assigned else (staff_role.mention if staff_role else "Nenhum suporte online")
            embed = ctx["ticket_embed"](
                f"{EM['ticket']} 𝐓𝐈𝐂𝐊𝐄𝐓・𝐀𝐁𝐄𝐑𝐓𝐎",
                (
                    f"{EM['ticket']} **Categoria:** {topic_label}\n"
                    f"{EM['perfil']} **Usuário:** {interaction.user.mention}\n"
                    f"{EM['suporte']} **Suporte:** {staff_text}\n\n"
                    "Explique seu problema com detalhes. Apenas você e a equipe conseguem ver este ticket."
                ),
            )
            await channel.send(content=f"{interaction.user.mention} {staff_text}", embed=embed, view=ctx["TicketControlView"](ticket_id))
            await interaction.response.send_message(f"{EM['sucesso']} Ticket criado: {channel.mention}", ephemeral=True)

    ctx["TicketTopicSelect"] = TicketTopicSelect

    # ════════════════════════════════════════════════════════════════
    # /config_logs (Select Menus)
    # ════════════════════════════════════════════════════════════════

    _LOG_FIELDS = [
        ("log_open_channel_id", f"{EM['apostas']} Apostas Abertas"),
        ("log_confirmed_channel_id", f"{EM['sucesso']} Apostas Confirmadas"),
        ("log_cancelled_channel_id", f"{EM['erro']} Apostas Canceladas"),
        ("log_finished_channel_id", f"{EM['ganhador']} Apostas Finalizadas"),
    ]

    class LogsChannelSelect(discord.ui.ChannelSelect):
        def __init__(self, field: str, label: str):
            super().__init__(
                placeholder=f"Selecionar canal: {label}",
                channel_types=[discord.ChannelType.text],
                min_values=1,
                max_values=1,
            )
            self.field = field
            self.label = label

        async def callback(self, interaction: discord.Interaction):
            if not owner_only(interaction.user):
                await deny_owner(interaction)
                return

            chosen = self.values[0]
            s = store.settings(interaction.guild_id)

            other_fields = [f for f, _ in _LOG_FIELDS if f != self.field]
            for f in other_fields:
                try:
                    val = s[f] if f in s.keys() else None
                except Exception:
                    val = None
                if val and int(val) == int(chosen.id):
                    await interaction.response.send_message(
                        f"{EM['erro']} Canais devem ser distintos. Esse canal ja esta em outra etapa.",
                        ephemeral=True,
                    )
                    return

            # SQL direto pois os campos de log nao estao na whitelist do store.update_setting
            store.conn.execute(
                f"UPDATE settings SET {self.field}=? WHERE guild_id=?",
                (chosen.id, interaction.guild_id),
            )
            store.conn.commit()
            await interaction.response.send_message(
                f"{EM['sucesso']} Canal definido: {self.label} -> {chosen.mention}",
                ephemeral=True,
            )

    class ConfigLogsView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
            for field, label in _LOG_FIELDS:
                self.add_item(LogsChannelSelect(field, label))

    @bot.tree.command(name="config_logs", description="Configurar canais de lifecycle das apostas")
    async def config_logs(interaction: discord.Interaction):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return

        s = store.settings(interaction.guild_id)

        def fmt(field: str) -> str:
            if field in s.keys() and s[field]:
                return f"<#{s[field]}>"
            return "Não definido"

        desc = "\n".join([f"{label}: {fmt(field)}" for field, label in _LOG_FIELDS])
        embed = red_embed(f"{EM['historico']} Lifecycle de Apostas", desc)
        await interaction.response.send_message(embed=embed, view=ConfigLogsView(), ephemeral=True)

    # Troca o /blacklist antigo por um painel público de consulta.
    try:
        bot.tree.remove_command("blacklist")
    except Exception:
        pass

    class CheckBlacklistModal(discord.ui.Modal, title="Verificar Blacklist"):
        user_id = discord.ui.TextInput(label="ID do usuário", max_length=30)

        async def on_submit(self, interaction: discord.Interaction):
            raw = str(self.user_id).strip()
            if not raw.isdigit():
                await interaction.response.send_message(f"{EM['erro']} ID inválido.", ephemeral=True)
                return
            uid = int(raw)
            row = store.conn.execute(
                "SELECT * FROM blacklist WHERE guild_id=? AND user_id=?",
                (interaction.guild_id, uid),
            ).fetchone()
            if row:
                await interaction.response.send_message(
                    f"{EM['bloqueado']} Este usuário está na blacklist.\n"
                    f"{EM['perfil']} Usuário: <@{uid}>\n"
                    f"{EM['aviso']} Motivo: **{row['reason']}**",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(f"{EM['sucesso']} Este ID não está na blacklist.", ephemeral=True)

    class PublicBlacklistView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="Verificar ID", emoji=EM["verificar"], style=discord.ButtonStyle.secondary, custom_id="blacklist_check_public")
        async def check(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(CheckBlacklistModal())

    @bot.tree.command(name="blacklist", description="Verificar se um usuário está na blacklist")
    async def blacklist_public(interaction: discord.Interaction):
        embed = red_embed(
            f"{EM['bloqueado']} Painel de Consulta de Blacklist",
            "Clique no botão para verificar se um ID está na blacklist do servidor.",
        )
        await interaction.response.send_message(embed=embed, view=PublicBlacklistView())

    @bot.tree.command(name="blacklist_config", description="Gerenciar blacklist")
    async def blacklist_config(interaction: discord.Interaction):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_message(
            embed=red_embed(f"{EM['bloqueado']} Blacklist - Configuração", "Adicione, remova e liste usuários bloqueados das filas."),
            view=ctx["BlacklistView"](),
            ephemeral=True,
        )

    @bot.tree.command(name="emojisconfig", description="Mostra todos os atalhos de emojis configurados")
    async def emojisconfig(interaction: discord.Interaction):
        lines = [f"<{name}> = {value}" for name, value in EM.items()]
        chunks = ["\n".join(lines[i:i + 18]) for i in range(0, len(lines), 18)]
        await interaction.response.send_message(embed=red_embed(f"{EM['emoji']} Emojis Configurados 1/{len(chunks)}", chunks[0]), ephemeral=True)
        for idx, chunk in enumerate(chunks[1:], start=2):
            await interaction.followup.send(embed=red_embed(f"{EM['emoji']} Emojis Configurados {idx}/{len(chunks)}", chunk), ephemeral=True)

    class SendMessageModal(discord.ui.Modal, title="Enviar Mensagem"):
        titulo = discord.ui.TextInput(label="Título (deixe vazio para sem embed)", required=False, max_length=120)
        conteudo = discord.ui.TextInput(label="Conteúdo / Mensagem", style=discord.TextStyle.paragraph, max_length=1800)
        imagem = discord.ui.TextInput(label="URL imagem (opcional, só com embed)", required=False, max_length=300)
        cor = discord.ui.TextInput(label="Cor hex sem #", required=False, max_length=6)
        modo = discord.ui.TextInput(label="Modo: embed ou texto", default="embed", max_length=10)

        def __init__(self, channel: discord.TextChannel):
            super().__init__()
            self.channel = channel

        async def on_submit(self, interaction: discord.Interaction):
            content = replace_emoji_shortcuts(str(self.conteudo))
            if str(self.modo).strip().lower() == "texto":
                await self.channel.send(content)
            else:
                color = discord.Color(0x2B2D31)
                raw_color = str(self.cor).strip().replace("#", "")
                if raw_color:
                    try:
                        color = discord.Color(int(raw_color, 16))
                    except ValueError:
                        pass
                embed = discord.Embed(title=replace_emoji_shortcuts(str(self.titulo)) or None, description=content, color=color)
                if str(self.imagem).strip():
                    embed.set_image(url=str(self.imagem).strip())
                await self.channel.send(embed=embed)
            await interaction.response.send_message(f"{EM['sucesso']} Mensagem enviada em {self.channel.mention}.", ephemeral=True)

    @bot.tree.command(name="enviar_msg", description="Enviar texto ou embed em um canal")
    async def enviar_msg(interaction: discord.Interaction, canal: discord.TextChannel):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_modal(SendMessageModal(canal))

    @bot.tree.command(name="coins_add", description="Adicionar coins a um usuário")
    async def coins_add(interaction: discord.Interaction, usuario: discord.Member, qtd: int):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        saldo = add_coins(interaction.guild_id, usuario.id, abs(qtd), "coins_add")
        await interaction.response.send_message(f"{EM['coins']} {usuario.mention} recebeu **{abs(qtd)}** coins. Saldo: **{saldo}**.", ephemeral=True)

    @bot.tree.command(name="coins_rem", description="Remover coins de um usuário")
    async def coins_rem(interaction: discord.Interaction, usuario: discord.Member, qtd: int):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        saldo = add_coins(interaction.guild_id, usuario.id, -abs(qtd), "coins_rem")
        await interaction.response.send_message(f"{EM['coins']} {usuario.mention} perdeu **{abs(qtd)}** coins. Saldo: **{saldo}**.", ephemeral=True)

    @bot.tree.command(name="saldo", description="Ver saldo de coins")
    async def saldo(interaction: discord.Interaction, usuario: Optional[discord.Member] = None):
        target = usuario or interaction.user
        await interaction.response.send_message(f"{EM['coins']} Saldo de {target.mention}: **{get_coins(interaction.guild_id, target.id)}** coins.", ephemeral=True)

    @bot.tree.command(name="pagar", description="Enviar coins para outro usuário")
    async def pagar(interaction: discord.Interaction, usuario: discord.Member, qtd: int):
        if usuario.bot or usuario.id == interaction.user.id or qtd <= 0:
            await interaction.response.send_message(f"{EM['erro']} Pagamento inválido.", ephemeral=True)
            return
        if get_coins(interaction.guild_id, interaction.user.id) < qtd:
            await interaction.response.send_message(f"{EM['erro']} Saldo insuficiente.", ephemeral=True)
            return
        add_coins(interaction.guild_id, interaction.user.id, -qtd, "transferencia enviada")
        add_coins(interaction.guild_id, usuario.id, qtd, "transferencia recebida")
        await interaction.response.send_message(f"{EM['sucesso']} Você enviou **{qtd}** coins para {usuario.mention}.", ephemeral=True)

    def products_for(guild_id: int) -> list[sqlite3.Row]:
        return store.conn.execute("SELECT * FROM store_products WHERE guild_id=? AND active=1 ORDER BY id", (guild_id,)).fetchall()

    def store_panel_embed(guild_id: int) -> discord.Embed:
        rows = products_for(guild_id)
        text = "\n".join(f"**#{r['id']}** {r['name']} - **{r['price']} coins**\n{r['description'] or ''}" for r in rows) or "Nenhum produto cadastrado."
        return red_embed(f"{EM['loja']} LOJA COIN", f"Junte suas coins e troque por prêmios.\n\n{EM['presente']} **Produtos**\n{text}")

    class AddProductModal(discord.ui.Modal, title="Adicionar Produto"):
        nome = discord.ui.TextInput(label="Nome do produto", max_length=80)
        preco = discord.ui.TextInput(label="Preço em coins", placeholder="Ex: 50", max_length=8)
        descricao = discord.ui.TextInput(label="Descrição opcional", required=False, style=discord.TextStyle.paragraph, max_length=300)
        cargo = discord.ui.TextInput(label="ID cargo entregue (opcional)", required=False, max_length=30)

        async def on_submit(self, interaction: discord.Interaction):
            role_id = int(str(self.cargo)) if str(self.cargo).strip().isdigit() else None
            store.conn.execute(
                "INSERT INTO store_products (guild_id, name, price, description, role_id) VALUES (?, ?, ?, ?, ?)",
                (interaction.guild_id, str(self.nome), int(str(self.preco)), str(self.descricao), role_id),
            )
            store.conn.commit()
            await interaction.response.send_message(f"{EM['sucesso']} Produto adicionado.", ephemeral=True)

    class RemoveProductModal(discord.ui.Modal, title="Remover Produto"):
        produto_id = discord.ui.TextInput(label="ID do produto", max_length=10)

        async def on_submit(self, interaction: discord.Interaction):
            store.conn.execute("UPDATE store_products SET active=0 WHERE guild_id=? AND id=?", (interaction.guild_id, int(str(self.produto_id))))
            store.conn.commit()
            await interaction.response.send_message(f"{EM['sucesso']} Produto removido.", ephemeral=True)

    class StorePublicView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="Suas Coins", emoji=EM["coins"], style=discord.ButtonStyle.success, custom_id="store_my_coins")
        async def my_coins(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message(f"{EM['coins']} Suas coins: **{get_coins(interaction.guild_id, interaction.user.id)}**", ephemeral=True)

        @discord.ui.button(label="Rank Coins", emoji=EM["ranking"], style=discord.ButtonStyle.secondary, custom_id="store_rank")
        async def rank(self, interaction: discord.Interaction, button: discord.ui.Button):
            rows = store.conn.execute("SELECT user_id, coins FROM user_coins WHERE guild_id=? ORDER BY coins DESC LIMIT 10", (interaction.guild_id,)).fetchall()
            text = "\n".join(f"**#{i}** <@{r['user_id']}> - **{r['coins']}**" for i, r in enumerate(rows, 1)) or "Sem ranking ainda."
            await interaction.response.send_message(embed=red_embed(f"{EM['ranking']} Rank Coins", text), ephemeral=True)

    class StoreConfigView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)

        @discord.ui.button(label="Enviar painel", emoji=EM["sucesso"], style=discord.ButtonStyle.success)
        async def send_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.channel.send(embed=store_panel_embed(interaction.guild_id), view=StorePublicView())
            await interaction.response.send_message("Painel enviado.", ephemeral=True)

        @discord.ui.button(label="Adicionar produto", emoji=EM["adicionar"], style=discord.ButtonStyle.secondary)
        async def add_product(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(AddProductModal())

        @discord.ui.button(label="Remover produto", emoji=EM["remover"], style=discord.ButtonStyle.danger)
        async def remove_product(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(RemoveProductModal())

        @discord.ui.button(label="Ver loja", emoji=EM["loja"], style=discord.ButtonStyle.secondary)
        async def view_store(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message(embed=store_panel_embed(interaction.guild_id), ephemeral=True)

    @bot.tree.command(name="loja_config", description="Painel único para configurar loja")
    async def loja_config(interaction: discord.Interaction):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_message(embed=red_embed(f"{EM['loja']} Loja - Configuração", "Configure produtos e envie o painel da loja."), view=StoreConfigView(), ephemeral=True)

    def roulette_embed(guild_id: int) -> discord.Embed:
        s = store.settings(guild_id)
        prizes = store.conn.execute("SELECT * FROM roulette_prizes WHERE guild_id=? AND active=1 ORDER BY id", (guild_id,)).fetchall()
        text = "\n".join(f"**#{p['id']}** {p['name']}" for p in prizes) or "Nenhum prêmio cadastrado."
        return red_embed(f"{EM['presente']} Roleta de Prêmios", f"{EM['coins']} Custo: **{s['roulette_cost']} coins**\n{EM['ganhador']} Chance: **{s['roulette_chance']}%**\n\n{EM['presente']} **Prêmios**\n{text}")

    class RoulettePublicView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="Girar Roleta", emoji=EM["presente"], style=discord.ButtonStyle.success, custom_id="roulette_spin")
        async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
            s = store.settings(interaction.guild_id)
            cost = int(s["roulette_cost"] or 0)
            if get_coins(interaction.guild_id, interaction.user.id) < cost:
                await interaction.response.send_message(f"{EM['erro']} Coins insuficientes.", ephemeral=True)
                return
            prize = store.conn.execute("SELECT * FROM roulette_prizes WHERE guild_id=? AND active=1 ORDER BY RANDOM() LIMIT 1", (interaction.guild_id,)).fetchone()
            add_coins(interaction.guild_id, interaction.user.id, -cost, "roleta")
            await interaction.response.send_message(f"{EM['presente']} Girando a roleta...", ephemeral=True)
            await asyncio.sleep(2)
            if prize and random.randint(1, 100) <= int(s["roulette_chance"] or 15):
                role_id = prize["role_id"]
                if role_id and isinstance(interaction.user, discord.Member):
                    role = interaction.guild.get_role(role_id)
                    if role:
                        try:
                            await interaction.user.add_roles(role, reason="Prêmio da roleta")
                        except discord.HTTPException:
                            pass
                await interaction.followup.send(f"{EM['ganhador']} Você ganhou: **{prize['name']}**!", ephemeral=True)
            else:
                await interaction.followup.send(f"{EM['erro']} Não foi dessa vez.", ephemeral=True)

    class RouletteConfigModal(discord.ui.Modal, title="Configurar Roleta"):
        chance = discord.ui.TextInput(label="Chance de ganhar em %", required=False)
        custo = discord.ui.TextInput(label="Custo em coins", required=False)

        async def on_submit(self, interaction: discord.Interaction):
            if str(self.chance).strip():
                store.update_setting(interaction.guild_id, "roulette_chance", max(1, min(100, int(str(self.chance)))))
            if str(self.custo).strip():
                store.update_setting(interaction.guild_id, "roulette_cost", max(0, int(str(self.custo))))
            await interaction.response.send_message(f"{EM['sucesso']} Roleta configurada.", ephemeral=True)

    class AddPrizeModal(discord.ui.Modal, title="Adicionar Prêmio"):
        nome = discord.ui.TextInput(label="Nome do prêmio", max_length=80)
        descricao = discord.ui.TextInput(label="Descrição opcional", required=False, style=discord.TextStyle.paragraph, max_length=300)
        cargo = discord.ui.TextInput(label="ID cargo entregue (opcional)", required=False, max_length=30)

        async def on_submit(self, interaction: discord.Interaction):
            role_id = int(str(self.cargo)) if str(self.cargo).strip().isdigit() else None
            store.conn.execute(
                "INSERT INTO roulette_prizes (guild_id, name, description, role_id) VALUES (?, ?, ?, ?)",
                (interaction.guild_id, str(self.nome), str(self.descricao), role_id),
            )
            store.conn.commit()
            await interaction.response.send_message(f"{EM['sucesso']} Prêmio adicionado.", ephemeral=True)

    class RemovePrizeModal(discord.ui.Modal, title="Remover Prêmio"):
        premio_id = discord.ui.TextInput(label="ID do prêmio", max_length=10)

        async def on_submit(self, interaction: discord.Interaction):
            store.conn.execute("UPDATE roulette_prizes SET active=0 WHERE guild_id=? AND id=?", (interaction.guild_id, int(str(self.premio_id))))
            store.conn.commit()
            await interaction.response.send_message(f"{EM['sucesso']} Prêmio removido.", ephemeral=True)

    class RouletteConfigView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)

        @discord.ui.button(label="Configurar", emoji=EM["config"], style=discord.ButtonStyle.secondary)
        async def config_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(RouletteConfigModal())

        @discord.ui.button(label="Enviar painel", emoji=EM["sucesso"], style=discord.ButtonStyle.success)
        async def send_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.channel.send(embed=roulette_embed(interaction.guild_id), view=RoulettePublicView())
            await interaction.response.send_message("Painel enviado.", ephemeral=True)

        @discord.ui.button(label="Adicionar prêmio", emoji=EM["adicionar"], style=discord.ButtonStyle.secondary)
        async def add_prize(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(AddPrizeModal())

        @discord.ui.button(label="Remover prêmio", emoji=EM["remover"], style=discord.ButtonStyle.danger)
        async def remove_prize(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(RemovePrizeModal())

        @discord.ui.button(label="Ver prêmios", emoji=EM["ranking"], style=discord.ButtonStyle.secondary)
        async def prizes(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message(embed=roulette_embed(interaction.guild_id), ephemeral=True)

    @bot.tree.command(name="roleta_config", description="Configurar roleta de prêmios")
    async def roleta_config(interaction: discord.Interaction):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_message(embed=roulette_embed(interaction.guild_id), view=RouletteConfigView(), ephemeral=True)

    @bot.tree.command(name="roleta", description="Girar a roleta usando coins")
    async def roleta(interaction: discord.Interaction):
        await interaction.response.send_message(embed=roulette_embed(interaction.guild_id), view=RoulettePublicView(), ephemeral=True)

    @bot.tree.command(name="historico", description="Ver as últimas 15 apostas")
    async def historico(interaction: discord.Interaction):
        rows = store.conn.execute("SELECT * FROM bets WHERE guild_id=? ORDER BY id DESC LIMIT 15", (interaction.guild_id,)).fetchall()
        text = "\n".join(f"**#{r['id']}** <@{r['player1_id']}> vs <@{r['player2_id']}> - {status_name(r['status'])}" for r in rows) or "Nenhuma aposta encontrada."
        await interaction.response.send_message(embed=red_embed(f"{EM['historico']} Histórico de Apostas", text), ephemeral=True)

    @bot.tree.command(name="apostas_diaria", description="Relatório do dia")
    async def apostas_diaria(interaction: discord.Interaction):
        rows = store.conn.execute("SELECT * FROM bets WHERE guild_id=?", (interaction.guild_id,)).fetchall()
        finalizadas = [r for r in rows if r["status"] == "closed"]
        ativas = [r for r in rows if r["status"] not in {"closed", "cancelled"}]
        canceladas = [r for r in rows if r["status"] == "cancelled"]
        lucro = sum(int(r["fee_cents"] or 0) for r in finalizadas)
        desc = (
            f"{EM['apostas']} Apostas hoje: **{len(rows)}**\n"
            f"{EM['ganhador']} Finalizadas: **{len(finalizadas)}**\n"
            f"{EM['online']} Ativas: **{len(ativas)}**\n"
            f"{EM['erro']} Canceladas: **{len(canceladas)}**\n"
            f"{EM['dinheiro']} Lucro em taxas: **{cents_to_money(lucro)}**"
        )
        await interaction.response.send_message(embed=red_embed(f"{EM['relatorio']} Relatório Diário", desc), ephemeral=True)

    @bot.tree.command(name="diagnostico", description="Verificar configuração, emojis e permissões do bot")
    async def diagnostico(interaction: discord.Interaction):
        s = store.settings(interaction.guild_id)
        perms = interaction.channel.permissions_for(interaction.guild.me)
        checks = [
            ("Cargo ADM", bool(s["admin_role_id"])),
            ("Cargo Staff", bool(s["staff_role_id"])),
            ("Categoria filas", bool(s["queue_category_id"])),
            ("Categoria pagamento", bool(s["payment_category_id"])),
            ("Logs abertas", bool(s["log_open_channel_id"])),
            ("Logs confirmadas", bool(s["log_confirmed_channel_id"])),
            ("Logs canceladas", bool(s["log_cancelled_channel_id"])),
            ("Logs finalizadas", bool(s["log_finished_channel_id"])),
        ]
        lines = [f"{EM['sucesso'] if ok else EM['erro']} {name}: {'OK' if ok else 'Não configurado'}" for name, ok in checks]
        lines += [
            "",
            f"{EM['cadeado']} Enviar mensagens: {'OK' if perms.send_messages else 'Falta'}",
            f"{EM['cadeado']} Embeds: {'OK' if perms.embed_links else 'Falta'}",
            f"{EM['cadeado']} Anexos/QR: {'OK' if perms.attach_files else 'Falta'}",
            f"{EM['cadeado']} Criar canais: {'OK' if perms.manage_channels else 'Falta'}",
        ]
        await interaction.response.send_message(embed=red_embed(f"{EM['aviso']} Diagnóstico do Bot", "\n".join(lines)), ephemeral=True)

    @bot.tree.command(name="perfil_ranking", description="Perfil compacto do jogador")
    async def perfil_ranking(interaction: discord.Interaction, usuario: Optional[discord.Member] = None):
        target = usuario or interaction.user
        rows = store.conn.execute("SELECT * FROM bets WHERE guild_id=? AND (player1_id=? OR player2_id=?)", (interaction.guild_id, target.id, target.id)).fetchall()
        wins = [r for r in rows if r["winner_id"] == target.id]
        losses = [r for r in rows if r["winner_id"] and r["winner_id"] != target.id]
        profit = sum(int(r["value_cents"] or 0) for r in wins) - sum(int(r["value_cents"] or 0) for r in losses)
        embed = red_embed(
            f"{EM['perfil']} Perfil de {target.display_name}",
            (
                f"{EM['coins']} Coins: **{get_coins(interaction.guild_id, target.id)}**\n"
                f"{EM['apostas']} Apostas: **{len(rows)}**\n"
                f"{EM['ganhador']} Vitórias: **{len(wins)}**\n"
                f"{EM['erro']} Derrotas: **{len(losses)}**\n"
                f"{EM['preco']} Lucro: **{cents_to_money(profit)}**"
            ),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="perfil_coins", description="Perfil compacto: saldo e desempenho")
    async def perfil_coins(interaction: discord.Interaction, usuario: Optional[discord.Member] = None):
        target = usuario or interaction.user

        rows = store.conn.execute(
            "SELECT winner_id FROM bets WHERE guild_id=? AND (player1_id=? OR player2_id=?)",
            (interaction.guild_id, target.id, target.id),
        ).fetchall()

        total = len(rows)
        wins = sum(1 for r in rows if r["winner_id"] == target.id)
        losses = sum(1 for r in rows if r["winner_id"] is not None and r["winner_id"] != target.id)

        saldo = get_coins(interaction.guild_id, target.id)

        embed = discord.Embed(title=f"{EM['coins']} Perfil de {target.display_name}", color=discord.Color(0x2B2D31))
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name=f"{EM['coins']} Saldo", value=f"**{saldo}** coins", inline=True)
        embed.add_field(name=f"{EM['apostas']} Partidas Jogadas", value=f"**{total}**", inline=True)
        embed.add_field(name=f"{EM['ganhador']} Vitórias", value=f"**{wins}**", inline=True)
        embed.add_field(name=f"{EM['erro']} Derrotas", value=f"**{losses}**", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    class EntryPaymentModal(discord.ui.Modal, title="Confirmar Pagamento"):
        pix_nome = discord.ui.TextInput(label="Nome do Pix usado", max_length=80)
        pix_chave = discord.ui.TextInput(label="Chave Pix usada", max_length=160)

        async def on_submit(self, interaction: discord.Interaction):
            store.conn.execute(
                "INSERT INTO entry_payments (guild_id, user_id, pix_nome, pix_chave) VALUES (?, ?, ?, ?)",
                (interaction.guild_id, interaction.user.id, str(self.pix_nome), str(self.pix_chave)),
            )
            store.conn.commit()
            cfg = get_adm_cobranca_config(interaction.guild_id)
            channel = interaction.guild.get_channel(cfg["canal_donos_id"]) if cfg["canal_donos_id"] else None
            embed = red_embed(
                f"{EM['pix']} Pagamento de Entrada",
                f"{EM['perfil']} Usuário: {interaction.user.mention}\n{EM['pix']} Nome Pix: {self.pix_nome}\n{EM['pix']} Chave: `{self.pix_chave}`",
            )
            if channel:
                await channel.send(embed=embed)
            await interaction.response.send_message(f"{EM['sucesso']} Pagamento enviado para análise.", ephemeral=True)

    class EntryPaymentView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="Pagar", emoji=EM["pix"], style=discord.ButtonStyle.success, custom_id="entry_payment_pay")
        async def pay(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(EntryPaymentModal())

    @bot.tree.command(name="pagamento", description="Enviar cobrança Pix para entrada de ADM/suporte")
    async def pagamento(interaction: discord.Interaction):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        cfg = get_adm_cobranca_config(interaction.guild_id)
        donos = get_donos_pix(interaction.guild_id)
        if not donos:
            await interaction.response.send_message(f"{EM['erro']} Cadastre um Pix de dono em `/admcobrancaconfig`.", ephemeral=True)
            return
        dono = donos[0]
        pix_code = pix_copy_code(dono["pix_chave"], dono["pix_nome"], cfg["taxa_cents"], "ENTRADA")
        file = make_qr_file(pix_code)
        embed = red_embed(
            f"{EM['pix']} Pagamento de Entrada",
            (
                f"{EM['preco']} Valor: **{cents_to_money(cfg['taxa_cents'])}**\n"
                f"{EM['pix']} Recebedor: **{dono['pix_nome']}**\n"
                f"{EM['pix']} Chave Pix: `{dono['pix_chave']}`\n\n"
                "Escaneie o QR Code ou use a chave Pix. Depois clique em **Pagar**."
            ),
        )
        embed.set_image(url="attachment://pix-qrcode.png")
        await interaction.response.send_message(embed=embed, file=file, view=EntryPaymentView())

    _persistent_views_registered = False

    async def _register_final_persistent_views():
        nonlocal _persistent_views_registered
        if _persistent_views_registered:
            return
        bot.add_view(StorePublicView())
        bot.add_view(RoulettePublicView())
        bot.add_view(EntryPaymentView())
        _persistent_views_registered = True

    bot.add_listener(_register_final_persistent_views, "on_ready")

    # ════════════════════════════════════════════════════════════════════
    # /enviarmsgconfig  — sistema de mensagem automática com loop
    # ════════════════════════════════════════════════════════════════════

    store.conn.executescript("""
        CREATE TABLE IF NOT EXISTS enviar_msg_config (
            guild_id   INTEGER PRIMARY KEY,
            channel_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS enviar_msg_mensagens (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id   INTEGER NOT NULL,
            conteudo   TEXT    NOT NULL,
            intervalo  INTEGER NOT NULL,
            imagem_url TEXT,
            cor_hex    TEXT,
            modo       TEXT    NOT NULL DEFAULT 'embed',
            ativo      INTEGER NOT NULL DEFAULT 0
        );
    """)
    store.conn.commit()

    # Tarefas ativas: msg_id -> asyncio.Task
    _enviar_tasks: dict[int, asyncio.Task] = {}

    def _enviar_get_channel(guild_id: int) -> Optional[int]:
        row = store.conn.execute(
            "SELECT channel_id FROM enviar_msg_config WHERE guild_id=?", (guild_id,)
        ).fetchone()
        return row["channel_id"] if row else None

    def _enviar_set_channel(guild_id: int, channel_id: int) -> None:
        store.conn.execute(
            "INSERT OR REPLACE INTO enviar_msg_config (guild_id, channel_id) VALUES (?,?)",
            (guild_id, channel_id),
        )
        store.conn.commit()

    def _enviar_get_msgs(guild_id: int) -> list:
        return store.conn.execute(
            "SELECT * FROM enviar_msg_mensagens WHERE guild_id=? ORDER BY id",
            (guild_id,),
        ).fetchall()

    def _enviar_get_msg(msg_id: int):
        return store.conn.execute(
            "SELECT * FROM enviar_msg_mensagens WHERE id=?", (msg_id,)
        ).fetchone()

    def _enviar_build_content(msg_row) -> tuple[str, Optional[discord.Embed]]:
        """Retorna (content, embed_or_None)."""
        texto = replace_emoji_shortcuts(msg_row["conteudo"])
        mention = "@everyone @here"
        if msg_row["modo"] == "embed":
            cor = discord.Color(int(msg_row["cor_hex"], 16)) if msg_row["cor_hex"] else discord.Color(0x2B2D31)
            embed = discord.Embed(description=texto, color=cor)
            if msg_row["imagem_url"]:
                embed.set_image(url=msg_row["imagem_url"])
            return mention, embed
        else:
            return f"{mention}\n{texto}", None

    async def _enviar_loop(guild: discord.Guild, msg_id: int) -> None:
        while True:
            row = _enviar_get_msg(msg_id)
            if not row:
                break
            channel_id = _enviar_get_channel(guild.id)
            if not channel_id:
                break
            channel = guild.get_channel(channel_id)
            if not channel:
                break
            content, embed = _enviar_build_content(row)
            try:
                sent = await channel.send(content=content, embed=embed)
            except discord.HTTPException:
                await asyncio.sleep(60)
                continue
            await asyncio.sleep(row["intervalo"] * 60)
            try:
                await sent.delete()
            except discord.HTTPException:
                pass
            # verifica se ainda está ativo
            row = _enviar_get_msg(msg_id)
            if not row or not row["ativo"]:
                break

    def _enviar_start(guild: discord.Guild, msg_id: int) -> None:
        _enviar_stop(msg_id)
        store.conn.execute("UPDATE enviar_msg_mensagens SET ativo=1 WHERE id=?", (msg_id,))
        store.conn.commit()
        task = asyncio.get_event_loop().create_task(_enviar_loop(guild, msg_id))
        _enviar_tasks[msg_id] = task

    def _enviar_stop(msg_id: int) -> None:
        task = _enviar_tasks.pop(msg_id, None)
        if task:
            task.cancel()
        store.conn.execute("UPDATE enviar_msg_mensagens SET ativo=0 WHERE id=?", (msg_id,))
        store.conn.commit()

    # ── Modais ────────────────────────────────────────────────────────

    class EnviarMsgCriarModal(discord.ui.Modal, title="Criar Mensagem"):
        conteudo = discord.ui.TextInput(
            label="Conteúdo / Mensagem",
            style=discord.TextStyle.paragraph,
            placeholder="Use <sino>, <sucesso>, <erro> etc...",
            max_length=1800,
        )
        intervalo = discord.ui.TextInput(
            label="Intervalo em minutos",
            placeholder="Ex: 30  (a cada 30 minutos)",
            max_length=6,
        )
        imagem_url = discord.ui.TextInput(
            label="URL imagem (opcional, só com embed)",
            required=False,
            max_length=300,
        )
        cor_hex = discord.ui.TextInput(
            label="Cor hex sem #  (opcional)",
            required=False,
            placeholder="Ex: FF5500",
            max_length=6,
        )
        modo = discord.ui.TextInput(
            label="Modo: embed ou texto",
            default="embed",
            max_length=5,
        )

        async def on_submit(self, interaction: discord.Interaction):
            try:
                minutos = int(str(self.intervalo).strip())
                if minutos < 1:
                    raise ValueError
            except ValueError:
                await interaction.response.send_message(
                    f"{EM['erro']} Intervalo inválido. Digite um número inteiro maior que 0.",
                    ephemeral=True,
                )
                return

            modo_val = str(self.modo).strip().lower()
            if modo_val not in ("embed", "texto"):
                modo_val = "embed"

            cor_val = str(self.cor_hex).strip().upper()
            if cor_val:
                try:
                    int(cor_val, 16)
                except ValueError:
                    await interaction.response.send_message(
                        f"{EM['erro']} Cor hex inválida. Use só os 6 caracteres sem #.",
                        ephemeral=True,
                    )
                    return
            else:
                cor_val = None

            img = str(self.imagem_url).strip() or None
            texto_msg = str(self.conteudo)

            cur = store.conn.execute(
                "INSERT INTO enviar_msg_mensagens (guild_id, conteudo, intervalo, imagem_url, cor_hex, modo) VALUES (?,?,?,?,?,?)",
                (interaction.guild_id, texto_msg, minutos, img, cor_val, modo_val),
            )
            store.conn.commit()
            msg_id = cur.lastrowid

            # Após salvar, exibe a mensagem criada + botão [Adicionar Canais]
            preview = texto_msg[:200].replace("\n", " ")
            await interaction.response.send_message(
                embed=red_embed(
                    f"╭ {EM['sucesso']}・𝐌𝐄𝐍𝐒𝐀𝐆𝐄𝐌 𝐂𝐑𝐈𝐀𝐃𝐀 ╮",
                    f"{EM['sucesso']} Mensagem salva com sucesso!\n"
                    f"{EM['relogio']} Intervalo: **{minutos} min** | Modo: **{modo_val}**\n"
                    f"📝 Prévia: `{preview}{'…' if len(texto_msg) > 200 else ''}`\n\n"
                    f"{EM['aviso']} Selecione os canais onde esta mensagem será enviada:",
                ),
                view=EnviarMsgAdicionarCanaisView(interaction.guild_id, msg_id, interaction.guild),
                ephemeral=True,
            )

    # ── View após criar mensagem: botão [Adicionar Canais] ────────────

    class EnviarMsgAdicionarCanaisSelect(discord.ui.ChannelSelect):
        def __init__(self, guild_id: int, msg_id: int, guild: discord.Guild):
            super().__init__(
                placeholder="Selecione os canais onde a mensagem será enviada…",
                channel_types=[discord.ChannelType.text],
                min_values=1,
                max_values=25,
            )
            self.guild_id = guild_id
            self.msg_id = msg_id
            self.guild = guild

        async def callback(self, interaction: discord.Interaction):
            channel_ids = [c.id for c in self.values]
            # Salva o último canal selecionado como canal principal da config
            _enviar_set_channel(self.guild_id, channel_ids[0])
            # Inicia o loop para cada canal selecionado
            row = _enviar_get_msg(self.msg_id)
            if row:
                for ch_id in channel_ids:
                    _enviar_stop(self.msg_id)
                    # Inicia com o canal principal; os demais são enviados manualmente via loop custom
                    break
                # Guarda lista de canais extras na categoria da msg (reutilizamos automsg_categories)
                # Por simplicidade, salvamos os canais adicionais e iniciamos o task com todos
                _enviar_start_multi(self.guild, self.msg_id, channel_ids, row["intervalo"])

            mencoes = ", ".join(f"<#{c.id}>" for c in self.values)
            # Deleta a mensagem temporária do select e volta ao painel principal
            await interaction.response.edit_message(
                embed=red_embed(
                    f"╭ {EM['sucesso']}・𝐂𝐀𝐍𝐀𝐈𝐒 𝐀𝐃𝐈𝐂𝐈𝐎𝐍𝐀𝐃𝐎𝐒 ╮",
                    f"{EM['sucesso']} Canais configurados: {mencoes}\n\n"
                    f"{EM['iniciar']} O envio automático foi iniciado!\n"
                    f"{EM['aviso']} Use o painel `/enviarmsgconfig` para gerenciar.",
                ),
                view=None,
            )

    class EnviarMsgAdicionarCanaisView(discord.ui.View):
        def __init__(self, guild_id: int, msg_id: int, guild: discord.Guild):
            super().__init__(timeout=120)
            self.guild_id = guild_id
            self.msg_id = msg_id
            self.guild = guild
            self.add_item(EnviarMsgAdicionarCanaisSelect(guild_id, msg_id, guild))

        @discord.ui.button(label="Pular (configurar depois)", emoji="⏭️", style=discord.ButtonStyle.secondary, row=1)
        async def pular(self, interaction: discord.Interaction, button: discord.ui.Button):
            # Volta visualmente ao painel principal
            guild_id = self.guild_id
            msgs = _enviar_get_msgs(guild_id)
            ch_id = _enviar_get_channel(guild_id)
            ativas = sum(1 for m in msgs if m["ativo"])
            desc = _enviar_main_desc(msgs, ch_id, ativas)
            await interaction.response.edit_message(
                embed=red_embed(f"╭ {EM['sino']}・𝐄𝐍𝐕𝐈𝐀𝐑 𝐌𝐒𝐆 𝐂𝐎𝐍𝐅𝐈𝐆 ╮", desc),
                view=EnviarMsgMainView(guild_id),
            )

    # Suporte a múltiplos canais por mensagem
    _enviar_multi_channels: dict[int, list[int]] = {}

    def _enviar_start_multi(guild: discord.Guild, msg_id: int, channel_ids: list[int], intervalo: int) -> None:
        _enviar_multi_channels[msg_id] = channel_ids
        _enviar_stop(msg_id)
        store.conn.execute("UPDATE enviar_msg_mensagens SET ativo=1 WHERE id=?", (msg_id,))
        store.conn.commit()
        task = asyncio.get_event_loop().create_task(_enviar_loop_multi(guild, msg_id, channel_ids, intervalo))
        _enviar_tasks[msg_id] = task

    async def _enviar_loop_multi(guild: discord.Guild, msg_id: int, channel_ids: list[int], intervalo: int) -> None:
        await asyncio.sleep(intervalo * 60)
        while True:
            row = _enviar_get_msg(msg_id)
            if not row or not row["ativo"]:
                break
            # Usa canais salvos em memória ou fallback ao canal principal
            active_channels = _enviar_multi_channels.get(msg_id, channel_ids)
            content, embed = _enviar_build_content(row)
            sent_msgs = []
            for ch_id in active_channels:
                channel = guild.get_channel(ch_id)
                if channel:
                    try:
                        sent = await channel.send(content=content, embed=embed)
                        sent_msgs.append((channel, sent))
                    except discord.HTTPException:
                        pass
            await asyncio.sleep(intervalo * 60)
            for channel, sent in sent_msgs:
                try:
                    await sent.delete()
                except discord.HTTPException:
                    pass
            row = _enviar_get_msg(msg_id)
            if not row or not row["ativo"]:
                break

    # ── "Ver Mensagens": lista + menu por mensagem ────────────────────

    class EnviarMsgDetalheView(discord.ui.View):
        """Exibido ao clicar em uma mensagem na lista. 3 botões: Editar, Excluir, Voltar."""
        def __init__(self, guild_id: int, msg_id: int, guild: discord.Guild):
            super().__init__(timeout=120)
            self.guild_id = guild_id
            self.msg_id = msg_id
            self.guild = guild

        @discord.ui.button(label="Editar Mensagem", emoji="✏️", style=discord.ButtonStyle.primary)
        async def editar(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(EnviarMsgEditarModal(self.guild_id, self.msg_id))

        @discord.ui.button(label="Excluir Mensagem", emoji="🗑️", style=discord.ButtonStyle.danger)
        async def excluir(self, interaction: discord.Interaction, button: discord.ui.Button):
            _enviar_stop(self.msg_id)
            store.conn.execute("DELETE FROM enviar_msg_mensagens WHERE id=?", (self.msg_id,))
            store.conn.commit()
            # Volta ao painel principal
            msgs = _enviar_get_msgs(self.guild_id)
            ch_id = _enviar_get_channel(self.guild_id)
            ativas = sum(1 for m in msgs if m["ativo"])
            desc = _enviar_main_desc(msgs, ch_id, ativas)
            await interaction.response.edit_message(
                embed=red_embed(f"╭ {EM['sino']}・𝐄𝐍𝐕𝐈𝐀𝐑 𝐌𝐒𝐆 𝐂𝐎𝐍𝐅𝐈𝐆 ╮", desc),
                view=EnviarMsgMainView(self.guild_id),
            )

        @discord.ui.button(label="Voltar", emoji="↩️", style=discord.ButtonStyle.secondary)
        async def voltar(self, interaction: discord.Interaction, button: discord.ui.Button):
            msgs = _enviar_get_msgs(self.guild_id)
            ch_id = _enviar_get_channel(self.guild_id)
            ativas = sum(1 for m in msgs if m["ativo"])
            desc = _enviar_main_desc(msgs, ch_id, ativas)
            await interaction.response.edit_message(
                embed=red_embed(f"╭ {EM['sino']}・𝐄𝐍𝐕𝐈𝐀𝐑 𝐌𝐒𝐆 𝐂𝐎𝐍𝐅𝐈𝐆 ╮", desc),
                view=EnviarMsgMainView(self.guild_id),
            )

    class EnviarMsgEditarModal(discord.ui.Modal, title="Editar Mensagem"):
        conteudo = discord.ui.TextInput(
            label="Novo conteúdo",
            style=discord.TextStyle.paragraph,
            max_length=1800,
        )
        intervalo = discord.ui.TextInput(
            label="Novo intervalo em minutos",
            max_length=6,
        )

        def __init__(self, guild_id: int, msg_id: int):
            super().__init__()
            self.guild_id = guild_id
            self.msg_id = msg_id
            row = _enviar_get_msg(msg_id)
            if row:
                self.conteudo.default = row["conteudo"]
                self.intervalo.default = str(row["intervalo"])

        async def on_submit(self, interaction: discord.Interaction):
            try:
                minutos = int(str(self.intervalo).strip())
                if minutos < 1:
                    raise ValueError
            except ValueError:
                await interaction.response.send_message(
                    f"{EM['erro']} Intervalo inválido.", ephemeral=True
                )
                return
            store.conn.execute(
                "UPDATE enviar_msg_mensagens SET conteudo=?, intervalo=? WHERE id=?",
                (str(self.conteudo), minutos, self.msg_id),
            )
            store.conn.commit()
            await interaction.response.send_message(
                f"{EM['sucesso']} Mensagem **#{self.msg_id}** editada.", ephemeral=True
            )

    class EnviarMsgListaSelect(discord.ui.Select):
        """Select com a lista de mensagens salvas; ao clicar abre o menu de 3 botões."""
        def __init__(self, guild_id: int, msgs: list, guild: discord.Guild):
            options = [
                discord.SelectOption(
                    label=f"#{m['id']} | {m['conteudo'][:50].replace(chr(10), ' ')}",
                    description=f"Intervalo: {m['intervalo']} min | {m['modo']} | {'Ativa' if m['ativo'] else 'Parada'}",
                    value=str(m["id"]),
                    emoji=EM["sucesso"] if m["ativo"] else EM["erro"],
                )
                for m in msgs[:25]
            ]
            super().__init__(placeholder="Selecione uma mensagem…", options=options)
            self.guild_id = guild_id
            self.guild = guild

        async def callback(self, interaction: discord.Interaction):
            msg_id = int(self.values[0])
            row = _enviar_get_msg(msg_id)
            if not row:
                await interaction.response.send_message(f"{EM['erro']} Mensagem não encontrada.", ephemeral=True)
                return
            preview = row["conteudo"][:300].replace("\n", " ")
            status = f"{EM['sucesso']} Ativa" if row["ativo"] else f"{EM['erro']} Parada"
            await interaction.response.edit_message(
                embed=red_embed(
                    f"╭ 👁️・𝐌𝐄𝐍𝐒𝐀𝐆𝐄𝐌 #{msg_id} ╮",
                    f"{status} | {EM['relogio']} **{row['intervalo']} min** | Modo: **{row['modo']}**\n\n"
                    f"📝 `{preview}{'…' if len(row['conteudo']) > 300 else ''}`",
                ),
                view=EnviarMsgDetalheView(self.guild_id, msg_id, self.guild),
            )

    class EnviarMsgListaView(discord.ui.View):
        def __init__(self, guild_id: int, msgs: list, guild: discord.Guild):
            super().__init__(timeout=120)
            self.add_item(EnviarMsgListaSelect(guild_id, msgs, guild))

    # ── Select: escolher mensagem para iniciar ────────────────────────

    class EnviarMsgIniciarSelect(discord.ui.Select):
        def __init__(self, guild: discord.Guild, msgs: list):
            options = [
                discord.SelectOption(
                    label=f"#{m['id']} | {m['conteudo'][:40]}",
                    description=f"Intervalo: {m['intervalo']} min | modo: {m['modo']}",
                    value=str(m["id"]),
                    emoji=EM["sucesso"] if m["ativo"] else EM["parar"],
                )
                for m in msgs[:25]
            ]
            super().__init__(placeholder="Selecione a mensagem para iniciar…", options=options)
            self.guild = guild

        async def callback(self, interaction: discord.Interaction):
            mid = int(self.values[0])
            ch_id = _enviar_get_channel(interaction.guild_id)
            if not ch_id:
                await interaction.response.send_message(
                    f"{EM['erro']} Nenhum canal configurado. Crie uma mensagem e adicione canais.",
                    ephemeral=True,
                )
                return
            row = _enviar_get_msg(mid)
            channel_ids = _enviar_multi_channels.get(mid, [ch_id])
            _enviar_start_multi(self.guild, mid, channel_ids, row["intervalo"] if row else 60)
            await interaction.response.send_message(
                embed=red_embed(
                    f"╭ {EM['sucesso']}・𝐈𝐍𝐈𝐂𝐈𝐀𝐃𝐎 ╮",
                    f"{EM['iniciar']} Mensagem **#{mid}** sendo enviada automaticamente!\n"
                    f"{EM['relogio']} Canal(is): {', '.join(f'<#{c}>' for c in channel_ids)}",
                ),
                ephemeral=True,
            )

    class EnviarMsgIniciarView(discord.ui.View):
        def __init__(self, guild: discord.Guild, msgs: list):
            super().__init__(timeout=60)
            self.add_item(EnviarMsgIniciarSelect(guild, msgs))

    # ── Select: parar mensagem ─────────────────────────────────────────

    class EnviarMsgPararSelect(discord.ui.Select):
        def __init__(self, msgs: list):
            ativas = [m for m in msgs if m["ativo"]]
            options = [
                discord.SelectOption(
                    label=f"#{m['id']} | {m['conteudo'][:40]}",
                    description=f"Intervalo: {m['intervalo']} min",
                    value=str(m["id"]),
                    emoji=EM["parar"],
                )
                for m in ativas[:25]
            ] if ativas else [discord.SelectOption(label="Nenhuma ativa", value="none")]
            super().__init__(placeholder="Selecione a mensagem para parar…", options=options)
            self.tem_ativas = bool(ativas)

        async def callback(self, interaction: discord.Interaction):
            if not self.tem_ativas or self.values[0] == "none":
                await interaction.response.send_message(f"{EM['aviso']} Nenhuma mensagem ativa.", ephemeral=True)
                return
            mid = int(self.values[0])
            _enviar_stop(mid)
            await interaction.response.send_message(
                embed=red_embed(
                    f"╭ {EM['parar']}・𝐏𝐀𝐑𝐀𝐃𝐎 ╮",
                    f"{EM['parar']} Mensagem **#{mid}** parada com sucesso.",
                ),
                ephemeral=True,
            )

    class EnviarMsgPararView(discord.ui.View):
        def __init__(self, msgs: list):
            super().__init__(timeout=60)
            self.add_item(EnviarMsgPararSelect(msgs))

    # ── Helper: descrição do painel principal ─────────────────────────

    def _enviar_main_desc(msgs: list, ch_id: Optional[int], ativas: int) -> str:
        return (
            f"✏️ **Mensagens criadas:** {len(msgs)}\n"
            f"▶️ **Ativas agora:** {ativas}\n\n"
            f"👁️ **Ver Mensagens** — lista, edita e exclui mensagens\n"
            f"✏️ **Criar Mensagem** — cria mensagem e escolhe os canais\n"
            f"▶️ **Começar** — inicia o loop de envio\n"
            f"⏹️ **Parar** — para o envio de uma mensagem\n\n"
            f"{EM['aviso']} `@everyone @here` é adicionado automaticamente em cada envio."
        )

    # ── Painel principal (sem botão Selecionar Canal) ──────────────────

    class EnviarMsgMainView(discord.ui.View):
        def __init__(self, guild_id: int):
            super().__init__(timeout=180)
            self.guild_id = guild_id

        @discord.ui.button(label="Ver Mensagens", emoji="👁️", style=discord.ButtonStyle.secondary, row=0)
        async def ver_mensagens(self, interaction: discord.Interaction, button: discord.ui.Button):
            msgs = _enviar_get_msgs(interaction.guild_id)
            if not msgs:
                await interaction.response.send_message(
                    f"{EM['aviso']} Nenhuma mensagem criada. Use **✏️ Criar Mensagem**.",
                    ephemeral=True,
                )
                return
            linhas = []
            for m in msgs:
                status = f"{EM['sucesso']} Ativa" if m["ativo"] else f"{EM['erro']} Parada"
                preview = m["conteudo"][:50].replace("\n", " ")
                linhas.append(
                    f"**#{m['id']}** {status} | {EM['relogio']} {m['intervalo']} min | **{m['modo']}**\n"
                    f"📝 `{preview}…`"
                )
            desc = "\n\n".join(linhas)
            await interaction.response.edit_message(
                embed=red_embed(f"╭ 👁️・𝐌𝐄𝐍𝐒𝐀𝐆𝐄𝐍𝐒 ╮", f"{desc}\n\n{EM['aviso']} Selecione uma mensagem abaixo:"),
                view=EnviarMsgListaView(interaction.guild_id, list(msgs), interaction.guild),
            )

        @discord.ui.button(label="Criar Mensagem", emoji="✏️", style=discord.ButtonStyle.success, row=0)
        async def criar_mensagem(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(EnviarMsgCriarModal())

        @discord.ui.button(label="Começar", emoji="▶️", style=discord.ButtonStyle.primary, row=1)
        async def comecar(self, interaction: discord.Interaction, button: discord.ui.Button):
            msgs = _enviar_get_msgs(interaction.guild_id)
            if not msgs:
                await interaction.response.send_message(
                    f"{EM['erro']} Nenhuma mensagem criada. Use **✏️ Criar Mensagem** primeiro.",
                    ephemeral=True,
                )
                return
            await interaction.response.send_message(
                embed=red_embed(
                    f"╭ ▶️・𝐂𝐎𝐌𝐄𝐂̧𝐀𝐑 ╮",
                    f"{EM['aviso']} Selecione qual mensagem iniciar:",
                ),
                view=EnviarMsgIniciarView(interaction.guild, list(msgs)),
                ephemeral=True,
            )

        @discord.ui.button(label="Parar", emoji="⏹️", style=discord.ButtonStyle.danger, row=1)
        async def parar(self, interaction: discord.Interaction, button: discord.ui.Button):
            msgs = _enviar_get_msgs(interaction.guild_id)
            ativas = [m for m in msgs if m["ativo"]]
            if not ativas:
                await interaction.response.send_message(
                    f"{EM['aviso']} Nenhuma mensagem está ativa no momento.",
                    ephemeral=True,
                )
                return
            await interaction.response.send_message(
                embed=red_embed(
                    f"╭ ⏹️・𝐏𝐀𝐑𝐀𝐑 ╮",
                    f"{EM['aviso']} Selecione qual mensagem parar:",
                ),
                view=EnviarMsgPararView(list(msgs)),
                ephemeral=True,
            )

    @bot.tree.command(name="enviarmsgconfig", description="Painel de mensagens automáticas com loop")
    async def enviarmsgconfig(interaction: discord.Interaction):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return

        guild_id = interaction.guild_id
        msgs = _enviar_get_msgs(guild_id)
        ch_id = _enviar_get_channel(guild_id)
        ativas = sum(1 for m in msgs if m["ativo"])

        desc = _enviar_main_desc(msgs, ch_id, ativas)
        await interaction.response.send_message(
            embed=red_embed(f"╭ {EM['sino']}・𝐄𝐍𝐕𝐈𝐀𝐑 𝐌𝐒𝐆 𝐂𝐎𝐍𝐅𝐈𝐆 ╮", desc),
            view=EnviarMsgMainView(guild_id),
            ephemeral=True,
        )

    import pro_extensions
    pro_extensions.setup(ctx)

    import invite_extension
    invite_extension.setup(ctx)
