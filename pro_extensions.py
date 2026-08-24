import asyncio
import json
import os
import sqlite3
from typing import Any, Optional

import aiohttp
import discord


def setup(ctx: dict[str, Any]) -> None:
    bot = ctx["bot"]
    store = ctx["store"]
    queue_players = ctx["queue_players"]
    queue_embed = ctx["queue_embed"]
    entry_private_message = ctx["entry_private_message"]
    complete_queue = ctx["complete_queue"]
    match_embed = ctx["match_embed"]
    send_mediator_alert = ctx["send_mediator_alert"]
    bet_lifecycle_transition = ctx.get("bet_lifecycle_transition")
    red_embed = ctx["red_embed"]
    owner_only = ctx["owner_only"]
    deny_owner = ctx["deny_owner"]
    is_owner_member = ctx["is_owner_member"]
    is_admin_member = ctx["is_admin_member"]
    make_qr_file = ctx["make_qr_file"]
    pix_copy_code = ctx["pix_copy_code"]
    cents_to_money = ctx["cents_to_money"]

    emoji = {
        "ok": "<a:sucesso_animado:1516913609303658506>",
        "x": "<a:erro_animado:1516913586054631558>",
        "warn": "<a:alerta_staff_animado:1516913572280533063>",
        "pix": "<:pix:1516913599988105378>",
        "staff": "<:staff:1516913606795464805>",
        "clock": "<:relogio:1516913566253580470>",
        "med": "<:staff:1516913606795464805>",
        "ajuda": "<:ajuda:1516913559781507212>",
        "ranking": "<a:ranking:1516913552034631721>",
        "coins": "<:coins:1516913545856417972>",
        "loja": "<:loja_carrinho:1516913591817736212>",
        "apostas": "<:modoapostas:1516913590530080998>",
        "gelo": "<:gelo:1516915451999813682>",
        "bloqueado": "<:bloqueado:1516913576848130208>",
        "freefire": "<:free_fire:1516913587967361055>",
    }

    async def fallback_bet_lifecycle_transition(guild: discord.Guild, bet: sqlite3.Row, stage: str) -> None:
        field = {
            "open": "log_open_channel_id",
            "confirmed": "log_confirmed_channel_id",
            "cancelled": "log_cancelled_channel_id",
            "finished": "log_finished_channel_id",
        }.get(stage)
        if not field or not bet:
            return
        settings = store.settings(guild.id)
        try:
            channel_id = settings[field]
        except (IndexError, KeyError):
            channel_id = None
        channel = guild.get_channel(channel_id) if channel_id else None
        if not channel:
            return
        title = {
            "open": "Aposta Aberta",
            "confirmed": "Aposta Confirmada",
            "cancelled": "Aposta Cancelada",
            "finished": "Aposta Finalizada",
        }.get(stage, "Aposta")
        winner_text = ""
        try:
            if stage == "finished" and bet["winner_id"]:
                winner_text = f"\nVencedor: <@{bet['winner_id']}>"
        except (IndexError, KeyError):
            pass
        embed = red_embed(
            title,
            (
                f"Jogadores: <@{bet['player1_id']}> vs <@{bet['player2_id']}>\n"
                f"Modo: **{bet['kind']} {bet['mode']}**\n"
                f"Valor: **{cents_to_money(bet['value_cents'])}**"
                f"{winner_text}"
            ),
        )
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass

    if bet_lifecycle_transition is None:
        bet_lifecycle_transition = fallback_bet_lifecycle_transition

    def ensure_schema() -> None:
        store.ensure_columns(
            "settings",
            {
                "queue_confirm_timeout_minutes": "INTEGER NOT NULL DEFAULT 5",
                "payment_timeout_minutes": "INTEGER NOT NULL DEFAULT 5",
                "blacklist_log_channel_id": "INTEGER",
                "ai_enabled": "INTEGER NOT NULL DEFAULT 0",
                "ai_logs_channel_id": "INTEGER",
                "ai_owner_logs_channel_id": "INTEGER",
                "ai_moderation_channel_id": "INTEGER",
            },
        )
        store.ensure_columns("bets", {"winner_id": "INTEGER", "result_type": "TEXT"})
        store.conn.commit()

    ensure_schema()

    old_update_bet = store.update_bet

    def update_bet_allowing_results(bet_id: int, **fields: Any) -> None:
        extra = {"winner_id", "result_type"}
        normal = {k: v for k, v in fields.items() if k not in extra}
        special = {k: v for k, v in fields.items() if k in extra}
        if normal:
            old_update_bet(bet_id, **normal)
        if special:
            sets = ", ".join(f"{key}=?" for key in special)
            store.conn.execute(f"UPDATE bets SET {sets} WHERE id=?", (*special.values(), bet_id))
            store.conn.commit()

    store.update_bet = update_bet_allowing_results

    def setting_int(guild_id: int, field: str, default: int) -> int:
        settings = store.settings(guild_id)
        try:
            return max(1, int(settings[field] or default))
        except Exception:
            return default

    def set_setting(guild_id: int, field: str, value: int) -> None:
        store.settings(guild_id)
        store.conn.execute(f"UPDATE settings SET {field}=? WHERE guild_id=?", (value, guild_id))
        store.conn.commit()

    def choice_key(choice: str) -> str:
        return (choice or "Entrar").lower().replace(" ", "").replace("-", "")

    def choices_match(queue: sqlite3.Row, first: dict[str, Any], second: dict[str, Any]) -> bool:
        kind = str(queue["kind"]).lower()
        mode = str(queue["mode"]).lower()
        first_choice = choice_key(first.get("choice") or "Entrar")
        second_choice = choice_key(second.get("choice") or "Entrar")
        if kind == "1v1" and mode in {"mobile", "emulador", "gel"}:
            return first_choice == second_choice
        if mode == "misto":
            return first_choice == second_choice
        return True

    def find_match(queue: sqlite3.Row, players: list[dict[str, Any]]) -> Optional[list[dict[str, Any]]]:
        for index, first in enumerate(players):
            for second in players[index + 1:]:
                if choices_match(queue, first, second):
                    return [first, second]
        return None

    async def refresh_queue_message(guild: discord.Guild, queue_id: int) -> None:
        queue = store.queue(queue_id)
        if not queue or not queue["message_id"]:
            return
        channel = guild.get_channel(queue["channel_id"])
        if not channel:
            return
        try:
            message = await channel.fetch_message(queue["message_id"])
            await message.edit(
                embed=queue_embed(queue),
                view=ctx["QueueView"](queue["id"], queue["kind"], queue["mode"]),
            )
        except discord.HTTPException:
            pass

    async def remove_players_from_other_queues(guild: discord.Guild, matched_ids: set[int], current_queue_id: int) -> None:
        for other in store.active_queues():
            if other["id"] == current_queue_id:
                continue
            players = queue_players(other)
            remaining = [p for p in players if int(p["user_id"]) not in matched_ids]
            if len(remaining) != len(players):
                store.set_queue_players(other["id"], remaining)
                await refresh_queue_message(guild, other["id"])

    async def expire_confirm_later(guild: discord.Guild, bet_id: int) -> None:
        minutes = setting_int(guild.id, "queue_confirm_timeout_minutes", 5)
        await asyncio.sleep(minutes * 60)
        bet = store.bet(bet_id)
        if not bet or bet["status"] != "confirming":
            return
        store.update_bet(bet_id, status="cancelled", result_type="confirm_timeout")
        bet = store.bet(bet_id)
        await bet_lifecycle_transition(guild, bet, "cancelled")
        channel = guild.get_channel(bet["queue_channel_id"]) if bet["queue_channel_id"] else None
        if channel:
            try:
                await channel.send(f"{emoji['clock']} Tempo de confirmacao esgotado. Canal fecha em 5 segundos.")
            except discord.HTTPException:
                pass
            await delete_channel_after(channel, 5)

    async def expire_payment_later(guild: discord.Guild, bet_id: int, channel_id: int) -> None:
        minutes = setting_int(guild.id, "payment_timeout_minutes", 5)
        await asyncio.sleep(minutes * 60)
        bet = store.bet(bet_id)
        if not bet or bet["status"] != "payment":
            return
        store.update_bet(bet_id, status="cancelled", result_type="payment_timeout")
        bet = store.bet(bet_id)
        await bet_lifecycle_transition(guild, bet, "cancelled")
        channel = guild.get_channel(channel_id)
        if channel:
            try:
                await channel.send(f"{emoji['clock']} Tempo de pagamento esgotado. Canal fecha em 5 segundos.")
            except discord.HTTPException:
                pass
            await delete_channel_after(channel, 5)

    async def enter_queue(interaction: discord.Interaction, queue_id: int, choice: str) -> None:
        queue = store.queue(queue_id)
        if not queue or queue["status"] != "open":
            await interaction.response.send_message(f"{emoji['warn']} Fila indisponivel.", ephemeral=True)
            return
        settings = store.settings(interaction.guild_id)
        if not settings["bets_enabled"]:
            await interaction.response.send_message(f"{emoji['x']} No momento as apostas estao desativadas.", ephemeral=True)
            return
        if store.is_blacklisted(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message(f"{emoji['warn']} Voce esta na blacklist e nao pode entrar nas filas.", ephemeral=True)
            return

        players = [p for p in queue_players(queue) if int(p["user_id"]) != interaction.user.id]
        players.append({"user_id": interaction.user.id, "choice": "" if choice == "Entrar" else choice})
        match = find_match(queue, players)

        if match:
            matched_ids = {int(match[0]["user_id"]), int(match[1]["user_id"])}
            store.set_queue_players(queue_id, [p for p in players if int(p["user_id"]) not in matched_ids])
            queue = store.queue(queue_id)
            await remove_players_from_other_queues(interaction.guild, matched_ids, queue_id)
            await interaction.response.send_message(entry_private_message(queue, choice), ephemeral=True)
            await interaction.message.edit(embed=queue_embed(queue), view=ctx["QueueView"](queue["id"], queue["kind"], queue["mode"]))
            await complete_queue(interaction.guild, queue, match, interaction.channel)
            bet = store.conn.execute(
                "SELECT id FROM bets WHERE guild_id=? AND queue_id=? ORDER BY id DESC LIMIT 1",
                (interaction.guild_id, queue_id),
            ).fetchone()
            if bet:
                asyncio.create_task(expire_confirm_later(interaction.guild, int(bet["id"])))
            return

        store.set_queue_players(queue_id, players)
        queue = store.queue(queue_id)
        await interaction.response.send_message(entry_private_message(queue, choice), ephemeral=True)
        await interaction.message.edit(embed=queue_embed(queue), view=ctx["QueueView"](queue["id"], queue["kind"], queue["mode"]))

    ctx["enter_queue"] = enter_queue

    async def delete_channel_after(channel, seconds: int = 5) -> None:
        await asyncio.sleep(seconds)
        try:
            await channel.delete(reason="Aposta encerrada")
        except discord.HTTPException:
            pass

    async def close_bet_channel(channel, bet_id: int, winner_id: Optional[int]) -> None:
        bet = store.bet(bet_id)
        if not bet:
            return
        if winner_id:
            store.update_bet(bet_id, status="closed", winner_id=winner_id, result_type="winner")
            await bet_lifecycle_transition(channel.guild, store.bet(bet_id), "finished")
        else:
            store.update_bet(bet_id, status="cancelled", result_type="cancelled")
            await bet_lifecycle_transition(channel.guild, store.bet(bet_id), "cancelled")
        await delete_channel_after(channel, 5)

    ctx["close_bet_channel"] = close_bet_channel

    class ConfirmView(discord.ui.View):
        def __init__(self, bet_id: int):
            super().__init__(timeout=None)
            self.bet_id = bet_id

        @discord.ui.button(label="Confirmar", emoji=emoji["ok"], style=discord.ButtonStyle.secondary, custom_id="bet_confirm")
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            bet = store.bet(self.bet_id)
            if not bet:
                await interaction.response.send_message("Aposta nao encontrada.", ephemeral=True)
                return
            if interaction.user.id not in {bet["player1_id"], bet["player2_id"]}:
                await interaction.response.send_message("Somente jogadores podem confirmar.", ephemeral=True)
                return
            confirms = json.loads(bet["confirms_json"] or "{}")
            confirms[str(interaction.user.id)] = True
            store.update_bet(self.bet_id, confirms_json=json.dumps(confirms))
            bet = store.bet(self.bet_id)
            await interaction.message.edit(embed=match_embed(bet), view=self)
            await interaction.response.send_message(f"{emoji['ok']} Confirmacao registrada.", ephemeral=True)
            if confirms.get(str(bet["player1_id"])) and confirms.get(str(bet["player2_id"])):
                store.update_bet(self.bet_id, status="awaiting_mediator")
                bet = store.bet(self.bet_id)
                await interaction.message.edit(embed=match_embed(bet), view=None)
                await interaction.channel.send(embed=red_embed(f"{emoji['med']} Aguardando Mediador", "Os dois jogadores confirmaram. Um mediador pode assumir a aposta."))
                await bet_lifecycle_transition(interaction.guild, bet, "confirmed")
                await send_mediator_alert(interaction.guild, bet, interaction.channel)

        @discord.ui.button(label="Regras", style=discord.ButtonStyle.secondary, custom_id="bet_rules")
        async def rules(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("Combine as regras antes de confirmar.", ephemeral=True)

        @discord.ui.button(label="Cancelar", emoji=emoji["x"], style=discord.ButtonStyle.danger, custom_id="bet_cancel")
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            bet = store.bet(self.bet_id)
            if not bet:
                return
            if interaction.user.id not in {bet["player1_id"], bet["player2_id"]}:
                await interaction.response.send_message("Somente os jogadores podem cancelar essa confirmacao.", ephemeral=True)
                return
            await interaction.response.send_message(f"{emoji['x']} Aposta cancelada.")
            await close_bet_channel(interaction.channel, self.bet_id, None)

    ctx["ConfirmView"] = ConfirmView

    class DrawCloseView(discord.ui.View):
        def __init__(self, bet_id: int):
            super().__init__(timeout=120)
            self.bet_id = bet_id

        @discord.ui.button(label="Finalizar e fechar canal", emoji=emoji["x"], style=discord.ButtonStyle.danger)
        async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
            store.update_bet(self.bet_id, status="closed", result_type="draw")
            await bet_lifecycle_transition(interaction.guild, store.bet(self.bet_id), "finished")
            await interaction.response.send_message(f"{emoji['ok']} Empate declarado. Canal fecha em 5 segundos.", ephemeral=True)
            await delete_channel_after(interaction.channel, 5)

    ctx["DrawCloseView"] = DrawCloseView

    class PaymentView(discord.ui.View):
        def __init__(self, bet_id: int):
            super().__init__(timeout=None)
            self.bet_id = bet_id

        @discord.ui.button(label="Liberar Pix", emoji=emoji["pix"], style=discord.ButtonStyle.secondary, custom_id="pay_release_pix")
        async def release_pix(self, interaction: discord.Interaction, button: discord.ui.Button):
            bet = store.bet(self.bet_id)
            if not bet:
                await interaction.response.send_message("Aposta nao encontrada.", ephemeral=True)
                return
            if interaction.user.id != bet["admin_id"]:
                await interaction.response.send_message("Somente o ADM responsavel pode liberar o Pix.", ephemeral=True)
                return
            pix = store.get_pix(interaction.guild_id, bet["admin_id"])
            if not pix:
                await interaction.response.send_message("Voce nao tem Pix cadastrado. Use /admconfig.", ephemeral=True)
                return
            total = bet["value_cents"] + bet["fee_cents"]
            minutes = setting_int(interaction.guild_id, "payment_timeout_minutes", 5)
            pix_code = pix_copy_code(pix["pix_key"], pix["name"], total, f"APOSTA{bet['id']}")
            file = make_qr_file(pix_code)
            embed = red_embed(
                "PIX LIBERADO",
                f"{emoji['staff']} Recebedor: {pix['name']}\n{emoji['pix']} Valor: {cents_to_money(total)}\n{emoji['pix']} Chave PIX: `{pix['pix_key']}`\n\n{emoji['clock']} Este pagamento fecha em **{minutes} minuto(s)**.",
            )
            embed.set_image(url="attachment://pix-qrcode.png")
            button.disabled = True
            await interaction.response.defer(ephemeral=True)
            try:
                await interaction.message.edit(view=self)
            except discord.HTTPException:
                pass
            await interaction.channel.send(embed=embed, file=file, view=ctx["PixCopyView"](pix["pix_key"], pix_code))
            await interaction.followup.send(f"{emoji['ok']} Pix liberado.", ephemeral=True)
            asyncio.create_task(expire_payment_later(interaction.guild, self.bet_id, interaction.channel_id))

    ctx["PaymentView"] = PaymentView

    class LimitTimeModal(discord.ui.Modal, title="Definir Tempo"):
        minutos = discord.ui.TextInput(label="Tempo em minutos", placeholder="Ex: 5", max_length=4)

        def __init__(self, guild_id: int, field: str):
            super().__init__()
            self.guild_id = guild_id
            self.field = field

        async def on_submit(self, interaction: discord.Interaction):
            try:
                value = max(1, int(str(self.minutos).strip()))
            except ValueError:
                await interaction.response.send_message(f"{emoji['x']} Informe um numero valido.", ephemeral=True)
                return
            set_setting(self.guild_id, self.field, value)
            await interaction.response.send_message(f"{emoji['ok']} Tempo definido para **{value} minuto(s)**.", ephemeral=True)

    class LimitTimeView(discord.ui.View):
        def __init__(self, guild_id: int):
            super().__init__(timeout=180)
            self.guild_id = guild_id

        @discord.ui.button(label="Tempo de filas", emoji=emoji["clock"], style=discord.ButtonStyle.secondary)
        async def filas(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(LimitTimeModal(self.guild_id, "queue_confirm_timeout_minutes"))

        @discord.ui.button(label="Tempo de pagamento", emoji=emoji["pix"], style=discord.ButtonStyle.secondary)
        async def pagamento(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(LimitTimeModal(self.guild_id, "payment_timeout_minutes"))

    try:
        bot.tree.remove_command("limite_filas")
    except Exception:
        pass

    @bot.tree.command(name="limite_filas", description="Configurar tempo das filas e pagamentos")
    async def limite_filas(interaction: discord.Interaction):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        confirm = setting_int(interaction.guild_id, "queue_confirm_timeout_minutes", 5)
        pay = setting_int(interaction.guild_id, "payment_timeout_minutes", 5)
        await interaction.response.send_message(
            embed=red_embed(f"{emoji['clock']} LIMITES DE FILAS", f"{emoji['clock']} Confirmacao: **{confirm} min**\n{emoji['pix']} Pagamento: **{pay} min**"),
            view=LimitTimeView(interaction.guild_id),
            ephemeral=True,
        )

    def help_embed(admin: bool) -> discord.Embed:
        if admin:
            return red_embed(
                f"{emoji['staff']} AJUDA ADM",
                f"{emoji['apostas']} `/apostas` painel da aposta no canal atual\n"
                f"{emoji['pix']} `/admconfig` cadastrar Pix e ficar online/offline\n"
                f"{emoji['ranking']} `/rankadm` ranking de partidas controladas\n"
                f"{emoji['pix']} `/pagamento` cobrança Pix para entrada de ADM/suporte\n"
                f"{emoji['clock']} `/historico` consultar ultimas apostas\n"
                f"{emoji['ranking']} `/perfil_ranking` ver desempenho de jogador\n\n"
                f"{emoji['staff']} No painel `/apostas`, o mediador pode enviar sala, definir ganhador, finalizar por WO, marcar empate, renomear e encerrar.",
            )
        return red_embed(
            f"{emoji['ajuda']} AJUDA",
            f"{emoji['ranking']} `/perfil_ranking` seu perfil de apostas\n"
            f"{emoji['ranking']} `/ranking` ranking dos jogadores\n"
            f"{emoji['clock']} `/historico` suas ultimas apostas\n"
            f"{emoji['coins']} `/saldo` ver suas coins\n"
            f"{emoji['coins']} `/pagar` enviar coins para outro usuario\n"
            f"{emoji['loja']} `/loja` loja por coins\n"
            f"{emoji['coins']} `/roleta` girar roleta usando coins\n"
            f"{emoji['bloqueado']} `/blacklist` consultar blacklist\n\n"
            f"{emoji['freefire']} Para apostar: entre na fila, aguarde o match, confirme no canal criado e siga o pagamento com o mediador.",
        )

    for command_name in ("ajuda", "ajuda_adm"):
        try:
            bot.tree.remove_command(command_name)
        except Exception:
            pass

    @bot.tree.command(name="ajuda", description="Mostra os comandos principais")
    async def ajuda(interaction: discord.Interaction):
        await interaction.response.send_message(embed=help_embed(False), ephemeral=True)

    @bot.tree.command(name="ajuda_adm", description="Mostra comandos de ADM")
    async def ajuda_adm(interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or (not is_admin_member(interaction.user) and not is_owner_member(interaction.user)):
            await interaction.response.send_message("Somente ADM/mediador pode usar.", ephemeral=True)
            return
        await interaction.response.send_message(embed=help_embed(True), ephemeral=True)

    message_bot_options = {
        "regras": ("Regras Oficiais", f"{emoji['warn']} REGRAS OFICIAIS | ORG APOSTAS FF", f"{emoji['x']} PROIBIDO\n- Usar hack/mod/bug\n- Xitar ou trapacar\n- Ofender/xingar\n- Sair no meio da partida\n- Nao pagar a aposta\n\n{emoji['ok']} REGRAS GERAIS\n- Pagamento antes da partida\n- Print/gravacao obrigatoria\n- Resultado definido pelo ADM\n- Respeito obrigatorio\n\n{emoji['bloqueado']} PUNICOES\n- Quebrou regra = ban\n- Suspeita de hack = ban + analise\n- Nao pagou = ban permanente"),
        "regras_x1": ("Regras X1", f"{emoji['gelo']} REGRAS DO X1 - FREE FIRE", f"{emoji['ok']} REGRAS GERAIS\n- Gel infinito liberado\n- Obrigatorio trocar soco\n- Apenas Mini Uzi e Desert no primeiro round\n\n{emoji['x']} PROIBICOES\n- Nao pode se trancar no gel\n- Nao pode se trancar no gas\n- Proibido usar 2 armas de rush\n\n{emoji['warn']} QUEBRA DE REGRA\n- Dar round ate o fim\n- Ou W.O em caso grave"),
        "regras_mediador": ("Regras Mediador", f"{emoji['staff']} REGRAS PARA MEDIADORES | APOSTAS FF", f"{emoji['ok']} OBRIGACOES\n- Ter Pix cadastrado\n- Ficar online no painel\n- Ficar pelo menos 5 horas na org\n- Ser rapido na criacao de partidas\n- Manter respeito com todos\n\n{emoji['warn']} OBS: caso nao queira controlar fila por um tempo, basta abrir o painel e ficar OFF."),
        "regras_suporte": ("Regras Suporte", f"{emoji['staff']} REGRAS PARA SUPORTE | APOSTAS FF", f"{emoji['ok']} OBRIGACOES\n- Responder tickets rapido\n- Tratar todos com respeito\n- Ficar ativo no servidor\n- Ter paciencia com membros\n- Encaminhar problemas graves para ADM\n- Fechar ticket apenas apos resolver\n\n{emoji['x']} PROIBIDO\n- Ignorar tickets\n- Demorar para responder\n- Ofender membros\n- Fechar ticket sem motivo\n- Abusar do cargo"),
        "como_apostar": ("Como Apostar", f"{emoji['freefire']} COMO APOSTAR", f"{emoji['apostas']} 1. Escolha o modo: 1v1, 2v2, 3v3 ou 4v4\n{emoji['coins']} 2. Escolha o valor da aposta\n{emoji['ok']} 3. Entre na fila e aguarde adversario\n{emoji['clock']} 4. Um chat sera aberto para confirmar\n{emoji['pix']} 5. Aguarde o ADM liberar o Pix\n{emoji['freefire']} 6. Apos o pagamento, o ADM libera ID e senha da sala\n{emoji['ok']} 7. Se vencer, envie sua chave Pix para receber"),
        "bancos": ("Bancos Proibidos", f"{emoji['bloqueado']} ATENCAO | BANCOS PROIBIDOS", f"{emoji['x']} BANCOS NAO PERMITIDOS:\n- Inter\n- PicPay\n- Acrescimo\n\n{emoji['pix']} Caso use os bancos acima, sera cobrado + R$ 0,05."),
    }

    class MensagemBotSelect(discord.ui.Select):
        def __init__(self):
            super().__init__(
                placeholder="Escolha a mensagem",
                options=[discord.SelectOption(label=value[0], value=key) for key, value in message_bot_options.items()],
                min_values=1,
                max_values=1,
            )

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.edit_message(embed=red_embed("Escolha o canal", "Selecione onde enviar."), view=MensagemBotChannelView(self.values[0]))

    class MensagemBotChannelSelect(discord.ui.ChannelSelect):
        def __init__(self, option: str):
            super().__init__(placeholder="Canal para enviar", channel_types=[discord.ChannelType.text], min_values=1, max_values=1)
            self.option = option

        async def callback(self, interaction: discord.Interaction):
            label, title, desc = message_bot_options[self.option]
            channel = self.values[0]
            await interaction.response.defer(ephemeral=True)
            permissions = channel.permissions_for(interaction.guild.me)
            if not permissions.send_messages:
                await interaction.followup.send(f"{emoji['x']} Nao consigo enviar mensagens em {channel.mention}.", ephemeral=True)
                return
            try:
                await channel.send(embed=red_embed(title, desc))
            except discord.HTTPException as exc:
                await interaction.followup.send(f"{emoji['x']} Nao consegui enviar nesse canal: `{exc}`", ephemeral=True)
                return
            try:
                await interaction.message.edit(embed=red_embed("Enviado", f"Mensagem **{label}** enviada em {channel.mention}."), view=None)
            except discord.HTTPException:
                pass
            await interaction.followup.send(f"{emoji['ok']} Mensagem enviada em {channel.mention}.", ephemeral=True)

    class MensagemBotChannelView(discord.ui.View):
        def __init__(self, option: str):
            super().__init__(timeout=120)
            self.add_item(MensagemBotChannelSelect(option))

    class MensagemBotView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.add_item(MensagemBotSelect())

    try:
        bot.tree.remove_command("mensagem_bot")
    except Exception:
        pass

    @bot.tree.command(name="mensagem_bot", description="Enviar regras e mensagens prontas")
    async def mensagem_bot(interaction: discord.Interaction):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_message(embed=red_embed("MENSAGENS DO BOT", "Escolha a mensagem pronta."), view=MensagemBotView(), ephemeral=True)

    def replace_shortcuts(text: str) -> str:
        shortcuts = {
            "<pix>": emoji["pix"],
            "<preco>": "<:preco:1516913562147229726>",
            "<preco_dinheiro>": "<:preco_dinheiro:1516919186046058658>",
            "<staff>": emoji["staff"],
            "<adm>": emoji["staff"],
            "<gelo>": emoji["gelo"],
            "<freefire>": emoji["freefire"],
            "<ajuda>": emoji["ajuda"],
            "<ranking>": emoji["ranking"],
            "<coins>": emoji["coins"],
            "<loja>": emoji["loja"],
            "<apostas>": emoji["apostas"],
            "<bloqueado>": emoji["bloqueado"],
            "<sucesso>": emoji["ok"],
            "<erro>": emoji["x"],
            "<aviso>": emoji["warn"],
            "<relogio>": emoji["clock"],
        }
        for key, value in shortcuts.items():
            text = text.replace(key, value)
        return text

    class SendDmModal(discord.ui.Modal, title="Enviar DM"):
        titulo = discord.ui.TextInput(label="Titulo opcional", required=False, max_length=120)
        conteudo = discord.ui.TextInput(label="Mensagem", style=discord.TextStyle.paragraph, max_length=1800)
        modo = discord.ui.TextInput(label="Modo: embed ou texto", default="embed", max_length=10)

        def __init__(self, member: discord.Member):
            super().__init__()
            self.member = member

        async def on_submit(self, interaction: discord.Interaction):
            content = replace_shortcuts(str(self.conteudo))
            try:
                if str(self.modo).strip().lower() == "texto":
                    await self.member.send(content)
                else:
                    title = replace_shortcuts(str(self.titulo)).strip() or None
                    await self.member.send(embed=discord.Embed(title=title, description=content, color=discord.Color(0x2B2D31)))
            except discord.HTTPException:
                await interaction.response.send_message(f"{emoji['x']} Nao consegui enviar DM para {self.member.mention}.", ephemeral=True)
                return
            await interaction.response.send_message(f"{emoji['ok']} DM enviada para {self.member.mention}.", ephemeral=True)

    try:
        bot.tree.remove_command("enviar_dm")
    except Exception:
        pass

    @bot.tree.command(name="enviar_dm", description="Enviar mensagem/embeds na DM de um usuario")
    async def enviar_dm(interaction: discord.Interaction, usuario: discord.Member):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_modal(SendDmModal(usuario))

    def ai_settings_embed(guild_id: int) -> discord.Embed:
        settings = store.settings(guild_id)
        enabled = bool(settings["ai_enabled"]) if "ai_enabled" in settings.keys() else False
        logs = settings["ai_logs_channel_id"] if "ai_logs_channel_id" in settings.keys() else None
        owner_logs = settings["ai_owner_logs_channel_id"] if "ai_owner_logs_channel_id" in settings.keys() else None
        moderation = settings["ai_moderation_channel_id"] if "ai_moderation_channel_id" in settings.keys() else None
        return red_embed(
            f"{emoji['ajuda']} CONFIGURAR IA",
            (
                f"{emoji['ok'] if enabled else emoji['x']} Status: **{'Ativada' if enabled else 'Desativada'}**\n"
                f"{emoji['staff']} Logs IA: {f'<#{logs}>' if logs else 'Nao definido'}\n"
                f"{emoji['staff']} Logs dono: {f'<#{owner_logs}>' if owner_logs else 'Nao definido'}\n"
                f"{emoji['warn']} Canal monitorado: {f'<#{moderation}>' if moderation else 'Nao definido'}\n\n"
                "A IA leve responde tickets com mensagens rapidas, avisa logs quando chamam dono e detecta spam/toxicidade simples no canal monitorado."
            ),
        )

    class AiChannelSelect(discord.ui.ChannelSelect):
        def __init__(self, field: str):
            super().__init__(placeholder="Selecione o canal", channel_types=[discord.ChannelType.text], min_values=1, max_values=1)
            self.field = field

        async def callback(self, interaction: discord.Interaction):
            if not owner_only(interaction.user):
                await deny_owner(interaction)
                return
            channel = self.values[0]
            store.conn.execute(f"UPDATE settings SET {self.field}=? WHERE guild_id=?", (channel.id, interaction.guild_id))
            store.conn.commit()
            await interaction.response.edit_message(embed=ai_settings_embed(interaction.guild_id), view=AiConfigView(interaction.guild_id))

    class AiChannelView(discord.ui.View):
        def __init__(self, guild_id: int, field: str):
            super().__init__(timeout=120)
            self.guild_id = guild_id
            self.add_item(AiChannelSelect(field))

    class AiConfigView(discord.ui.View):
        def __init__(self, guild_id: int):
            super().__init__(timeout=180)
            self.guild_id = guild_id

        @discord.ui.button(label="Ativar/Desativar", emoji=emoji["ajuda"], style=discord.ButtonStyle.secondary)
        async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not owner_only(interaction.user):
                await deny_owner(interaction)
                return
            settings = store.settings(interaction.guild_id)
            enabled = 0 if settings["ai_enabled"] else 1
            store.conn.execute("UPDATE settings SET ai_enabled=? WHERE guild_id=?", (enabled, interaction.guild_id))
            store.conn.commit()
            await interaction.response.edit_message(embed=ai_settings_embed(interaction.guild_id), view=AiConfigView(interaction.guild_id))

        @discord.ui.button(label="Logs IA", emoji=emoji["staff"], style=discord.ButtonStyle.secondary)
        async def logs(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(embed=ai_settings_embed(interaction.guild_id), view=AiChannelView(interaction.guild_id, "ai_logs_channel_id"))

        @discord.ui.button(label="Logs dono", emoji=emoji["staff"], style=discord.ButtonStyle.secondary)
        async def owner_logs(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(embed=ai_settings_embed(interaction.guild_id), view=AiChannelView(interaction.guild_id, "ai_owner_logs_channel_id"))

        @discord.ui.button(label="Canal monitorado", emoji=emoji["warn"], style=discord.ButtonStyle.secondary)
        async def moderation(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(embed=ai_settings_embed(interaction.guild_id), view=AiChannelView(interaction.guild_id, "ai_moderation_channel_id"))

    try:
        bot.tree.remove_command("configurar_ia")
    except Exception:
        pass

    @bot.tree.command(name="configurar_ia", description="Configurar IA de tickets, logs e moderacao")
    async def configurar_ia(interaction: discord.Interaction):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_message(embed=ai_settings_embed(interaction.guild_id), view=AiConfigView(interaction.guild_id), ephemeral=True)

    async def ai_log(guild: discord.Guild, field: str, embed: discord.Embed) -> None:
        settings = store.settings(guild.id)
        try:
            channel_id = settings[field]
        except (IndexError, KeyError):
            channel_id = None
        channel = guild.get_channel(channel_id) if channel_id else None
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                pass

    @bot.event
    async def on_message(message: discord.Message):
        if message.author.bot or not message.guild:
            return
        settings = store.settings(message.guild.id)
        try:
            enabled = bool(settings["ai_enabled"])
        except (IndexError, KeyError):
            enabled = False
        if not enabled:
            return

        content = (message.content or "").lower().strip()
        is_ticket = message.channel.name.startswith("ticket-") if hasattr(message.channel, "name") else False
        if is_ticket and content in {"oi", "ola", "olá", "opa", "eae", "bom dia", "boa tarde", "boa noite"}:
            await message.channel.send(f"{emoji['ajuda']} Ola! Para agilizar o atendimento, va direto ao assunto.")
            return
        if is_ticket and ("dono" in content or "falar com o dono" in content or "conversar com o dono" in content):
            await ai_log(
                message.guild,
                "ai_owner_logs_channel_id",
                red_embed(
                    f"{emoji['staff']} CHAMARAM O DONO",
                    f"Usuario: {message.author.mention}\nTicket: {message.channel.mention}\nMensagem: {message.content[:800]}",
                ),
            )
            await message.channel.send(f"{emoji['staff']} Pedido registrado. Um responsavel vai verificar o ticket.")
            return

        moderation_channel = settings["ai_moderation_channel_id"] if "ai_moderation_channel_id" in settings.keys() else None
        if moderation_channel and message.channel.id == moderation_channel:
            blocked_words = {"lixo", "fdp", "desgraça", "desgraca", "porra", "caralho"}
            too_many_mentions = len(message.mentions) >= 5
            toxic = any(word in content for word in blocked_words)
            if too_many_mentions or toxic:
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass
                await ai_log(
                    message.guild,
                    "ai_logs_channel_id",
                    red_embed(
                        f"{emoji['warn']} IA MODERACAO",
                        f"Usuario: {message.author.mention}\nCanal: {message.channel.mention}\nMotivo: {'spam' if too_many_mentions else 'toxicidade'}\nMensagem: {message.content[:800]}",
                    ),
                )

    async def gemini_generate(prompt: str) -> Optional[str]:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            return None
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 220},
        }
        try:
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=15)
                async with session.post(url, json=payload, timeout=timeout) as response:
                    if response.status >= 400:
                        return None
                    data = await response.json()
        except Exception:
            return None
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError):
            return None

    async def gemini_ticket_reply(message: discord.Message) -> Optional[str]:
        prompt = (
            "Voce e uma IA de suporte de uma organizacao de apostas de Free Fire no Discord. "
            "Responda em portugues brasileiro, curto, educado e direto. "
            "Nao invente regras, nao confirme pagamento, nao finalize aposta e nao peca dados sensiveis. "
            "Se o usuario pedir dono, diga que vai registrar para a equipe. "
            "Se for apenas oi/opa/ola, peca para ir direto ao assunto.\n\n"
            f"Mensagem do usuario: {message.content[:1200]}"
        )
        return await gemini_generate(prompt)

    async def gemini_moderation_reason(message: discord.Message) -> Optional[str]:
        prompt = (
            "Analise esta mensagem de Discord para moderacao. "
            "Responda apenas uma palavra: OK, SPAM ou TOXICO. "
            "Use TOXICO para ofensa grave, palavroes agressivos, ameaca ou conteudo improprio. "
            "Use SPAM para flood, propaganda repetitiva ou muitas mencoes. "
            "Use OK se nao houver problema.\n\n"
            f"Mensagem: {message.content[:1200]}\nMencoes: {len(message.mentions)}"
        )
        result = await gemini_generate(prompt)
        if not result:
            return None
        result = result.upper()
        if "TOXICO" in result:
            return "toxicidade"
        if "SPAM" in result:
            return "spam"
        return None

    @bot.event
    async def on_message(message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.content.startswith("?"):
            await bot.process_commands(message)
            return
        settings = store.settings(message.guild.id)
        try:
            enabled = bool(settings["ai_enabled"])
        except (IndexError, KeyError):
            enabled = False
        if not enabled:
            await bot.process_commands(message)
            return

        content = (message.content or "").lower().strip()
        is_ticket = message.channel.name.startswith("ticket-") if hasattr(message.channel, "name") else False
        if is_ticket and content in {"oi", "ola", "olá", "opa", "eae", "bom dia", "boa tarde", "boa noite"}:
            reply = await gemini_ticket_reply(message)
            await message.channel.send(reply or f"{emoji['ajuda']} Ola! Para agilizar o atendimento, va direto ao assunto.")
            return
        if is_ticket and ("dono" in content or "falar com o dono" in content or "conversar com o dono" in content):
            await ai_log(
                message.guild,
                "ai_owner_logs_channel_id",
                red_embed(
                    f"{emoji['staff']} CHAMARAM O DONO",
                    f"Usuario: {message.author.mention}\nTicket: {message.channel.mention}\nMensagem: {message.content[:800]}",
                ),
            )
            reply = await gemini_ticket_reply(message)
            await message.channel.send(reply or f"{emoji['staff']} Pedido registrado. Um responsavel vai verificar o ticket.")
            return
        if is_ticket and len(content) >= 8:
            reply = await gemini_ticket_reply(message)
            if reply:
                await message.channel.send(reply[:1800])
                await ai_log(
                    message.guild,
                    "ai_logs_channel_id",
                    red_embed(
                        f"{emoji['ajuda']} IA RESPONDEU TICKET",
                        f"Usuario: {message.author.mention}\nTicket: {message.channel.mention}\nPergunta: {message.content[:600]}\nResposta: {reply[:600]}",
                    ),
                )
                return

        moderation_channel = settings["ai_moderation_channel_id"] if "ai_moderation_channel_id" in settings.keys() else None
        if moderation_channel and message.channel.id == moderation_channel:
            blocked_words = {"lixo", "fdp", "desgraça", "desgraca", "porra", "caralho"}
            too_many_mentions = len(message.mentions) >= 5
            toxic = any(word in content for word in blocked_words)
            reason = await gemini_moderation_reason(message)
            reason = reason or ("spam" if too_many_mentions else "toxicidade" if toxic else None)
            if reason:
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass
                await ai_log(
                    message.guild,
                    "ai_logs_channel_id",
                    red_embed(
                        f"{emoji['warn']} IA MODERACAO",
                        f"Usuario: {message.author.mention}\nCanal: {message.channel.mention}\nMotivo: {reason}\nMensagem: {message.content[:800]}",
                    ),
                )
                return
        await bot.process_commands(message)

    # Blacklist com canal de logs e limpeza da mensagem ao remover.
    store.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS blacklist_log_messages (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        );
        """
    )
    store.conn.commit()

    def blacklist_log_channel_id(guild_id: int) -> Optional[int]:
        settings = store.settings(guild_id)
        try:
            return settings["blacklist_log_channel_id"]
        except (IndexError, KeyError):
            return None

    def blacklist_config_embed(guild_id: int) -> discord.Embed:
        channel_id = blacklist_log_channel_id(guild_id)
        channel = f"<#{channel_id}>" if channel_id else "Nao definido"
        rows = store.blacklist_rows(guild_id)
        return red_embed(
            f"{emoji['bloqueado']} BLACKLIST CONFIG",
            (
                f"{emoji['staff']} Canal de logs: {channel}\n"
                f"{emoji['bloqueado']} Usuarios na blacklist: **{len(rows)}**\n\n"
                f"{emoji['warn']} Pessoas na blacklist nao conseguem entrar nas filas."
            ),
        )

    async def send_blacklist_log(
        guild: discord.Guild,
        user_id: int,
        action: str,
        reason: str,
        moderator: discord.Member | discord.User,
    ) -> None:
        channel_id = blacklist_log_channel_id(guild.id)
        channel = guild.get_channel(channel_id) if channel_id else None
        if not channel:
            return
        if action == "remove":
            row = store.conn.execute(
                "SELECT channel_id, message_id FROM blacklist_log_messages WHERE guild_id=? AND user_id=?",
                (guild.id, user_id),
            ).fetchone()
            if row:
                old_channel = guild.get_channel(row["channel_id"])
                if old_channel:
                    try:
                        old_message = await old_channel.fetch_message(row["message_id"])
                        await old_message.delete()
                    except discord.HTTPException:
                        pass
            store.conn.execute("DELETE FROM blacklist_log_messages WHERE guild_id=? AND user_id=?", (guild.id, user_id))
            store.conn.commit()
            try:
                await channel.send(
                    embed=red_embed(
                        f"{emoji['ok']} REMOVIDO DA BLACKLIST",
                        f"{emoji['staff']} Usuario: <@{user_id}>\n{emoji['ok']} Removido por: {moderator.mention}",
                    )
                )
            except discord.HTTPException:
                pass
            return

        try:
            sent = await channel.send(
                embed=red_embed(
                    f"{emoji['bloqueado']} ADICIONADO NA BLACKLIST",
                    (
                        f"{emoji['staff']} Usuario: <@{user_id}>\n"
                        f"{emoji['warn']} Motivo: {reason or 'Sem motivo'}\n"
                        f"{emoji['staff']} Adicionado por: {moderator.mention}"
                    ),
                )
            )
        except discord.HTTPException:
            return
        store.conn.execute(
            """
            INSERT OR REPLACE INTO blacklist_log_messages (guild_id, user_id, channel_id, message_id)
            VALUES (?, ?, ?, ?)
            """,
            (guild.id, user_id, channel.id, sent.id),
        )
        store.conn.commit()

    class BlacklistLogChannelSelect(discord.ui.ChannelSelect):
        def __init__(self):
            super().__init__(
                placeholder="Escolha o canal de logs da blacklist",
                channel_types=[discord.ChannelType.text],
                min_values=1,
                max_values=1,
            )

        async def callback(self, interaction: discord.Interaction):
            if not owner_only(interaction.user):
                await deny_owner(interaction)
                return
            channel = self.values[0]
            store.settings(interaction.guild_id)
            store.conn.execute(
                "UPDATE settings SET blacklist_log_channel_id=? WHERE guild_id=?",
                (channel.id, interaction.guild_id),
            )
            store.conn.commit()
            await interaction.response.edit_message(embed=blacklist_config_embed(interaction.guild_id), view=ProBlacklistView())

    class BlacklistLogChannelView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.add_item(BlacklistLogChannelSelect())

    class ProBlacklistAddModal(discord.ui.Modal, title="Adicionar Blacklist"):
        user_id = discord.ui.TextInput(label="ID Discord", placeholder="Ex: 123456789012345678", max_length=30)
        motivo = discord.ui.TextInput(label="Motivo", placeholder="Ex: nao pagou aposta", max_length=200)

        async def on_submit(self, interaction: discord.Interaction):
            try:
                target_id = int(str(self.user_id).strip())
            except ValueError:
                await interaction.response.send_message("ID invalido. Envie apenas numeros.", ephemeral=True)
                return
            store.add_blacklist(interaction.guild_id, target_id, str(self.motivo), interaction.user.id)
            await send_blacklist_log(interaction.guild, target_id, "add", str(self.motivo), interaction.user)
            await interaction.response.send_message(
                embed=red_embed(
                    f"{emoji['bloqueado']} BLACKLIST ATUALIZADA",
                    f"{emoji['staff']} Usuario: <@{target_id}>\n{emoji['warn']} Motivo: {self.motivo}",
                ),
                ephemeral=True,
            )

    class ProBlacklistRemoveModal(discord.ui.Modal, title="Remover Blacklist"):
        user_id = discord.ui.TextInput(label="ID Discord", placeholder="Ex: 123456789012345678", max_length=30)

        async def on_submit(self, interaction: discord.Interaction):
            try:
                target_id = int(str(self.user_id).strip())
            except ValueError:
                await interaction.response.send_message("ID invalido. Envie apenas numeros.", ephemeral=True)
                return
            store.remove_blacklist(interaction.guild_id, target_id)
            await send_blacklist_log(interaction.guild, target_id, "remove", "", interaction.user)
            await interaction.response.send_message(f"{emoji['ok']} Usuario <@{target_id}> removido da blacklist.", ephemeral=True)

    class ProBlacklistView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)

        @discord.ui.button(label="Canal logs", emoji=emoji["staff"], style=discord.ButtonStyle.secondary)
        async def logs(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not owner_only(interaction.user):
                await deny_owner(interaction)
                return
            await interaction.response.edit_message(embed=blacklist_config_embed(interaction.guild_id), view=BlacklistLogChannelView())

        @discord.ui.button(label="Adicionar", emoji=emoji["warn"], style=discord.ButtonStyle.secondary)
        async def add(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not owner_only(interaction.user):
                await deny_owner(interaction)
                return
            await interaction.response.send_modal(ProBlacklistAddModal())

        @discord.ui.button(label="Remover", emoji=emoji["x"], style=discord.ButtonStyle.secondary)
        async def remove(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not owner_only(interaction.user):
                await deny_owner(interaction)
                return
            await interaction.response.send_modal(ProBlacklistRemoveModal())

        @discord.ui.button(label="Ver blacklist", emoji=emoji["bloqueado"], style=discord.ButtonStyle.secondary)
        async def list_items(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not owner_only(interaction.user):
                await deny_owner(interaction)
                return
            rows = store.blacklist_rows(interaction.guild_id)
            text = "\n".join(f"{index}. <@{row['user_id']}> - {row['reason'] or 'Sem motivo'}" for index, row in enumerate(rows, 1))
            await interaction.response.send_message(embed=red_embed(f"{emoji['bloqueado']} BLACKLIST", text or "Nenhum usuario na blacklist."), ephemeral=True)

    try:
        bot.tree.remove_command("blacklist_config")
    except Exception:
        pass

    @bot.tree.command(name="blacklist_config", description="Gerenciar blacklist e logs")
    async def blacklist_config(interaction: discord.Interaction):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        await interaction.response.send_message(embed=blacklist_config_embed(interaction.guild_id), view=ProBlacklistView(), ephemeral=True)
