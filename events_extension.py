import asyncio
import random
import re
import sqlite3
from typing import Any, Optional

import discord


def setup(ctx: dict[str, Any]) -> None:
    bot: discord.Client = ctx["bot"]
    store = ctx["store"]
    red_embed = ctx["red_embed"]
    is_owner_member = ctx["is_owner_member"]
    ensure_channel_name = ctx["ensure_channel_name"]

    EM_EVENTO = ctx.get("EMOJI_EVENTO", "<:presente:1516913602399834132>")
    EM_FF = ctx.get("EMOJI_FF", "<:free_fire:1516913587967361055>")
    EM_ADM = ctx.get("EMOJI_ADM", "<:staff:1516913606795464805>")
    EM_CLOCK = ctx.get("EMOJI_RELOGIO", "<:relogio:1516913566253580470>")
    EM_WIN = ctx.get("EMOJI_GANHADOR_TROFEU", "<:ranking_trofeu:1516913603863908373>")
    EM_OK = ctx.get("EMOJI_V", "<a:sucesso_animado:1516913609303658506>")
    EM_X = ctx.get("EMOJI_X", "<a:erro_animado:1516913586054631558>")
    EM_CONFIG = "<:config:1516913563531215009>"

    store.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS event_config (
            guild_id INTEGER PRIMARY KEY,
            event_channel_id INTEGER,
            teams_category_id INTEGER,
            logs_channel_id INTEGER,
            admin_channel_id INTEGER,
            current_event_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS game_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            prize TEXT NOT NULL DEFAULT '',
            event_type TEXT NOT NULL DEFAULT 'BR',
            team_size INTEGER NOT NULL DEFAULT 1,
            capacity INTEGER NOT NULL DEFAULT 48,
            starts_at TEXT NOT NULL DEFAULT '',
            banner_url TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            room_id TEXT,
            room_password TEXT,
            room_minutes INTEGER NOT NULL DEFAULT 5,
            public_channel_id INTEGER,
            public_message_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS event_entries (
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            ff_id TEXT NOT NULL,
            PRIMARY KEY (event_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS event_teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            captain_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            channel_id INTEGER,
            log_message_id INTEGER,
            qualified_slot INTEGER,
            locked INTEGER NOT NULL DEFAULT 0,
            UNIQUE (event_id, code)
        );
        CREATE TABLE IF NOT EXISTS event_team_members (
            event_id INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            ff_id TEXT NOT NULL,
            PRIMARY KEY (event_id, user_id)
        );
        """
    )
    store.conn.commit()

    def cfg(guild_id: int) -> sqlite3.Row:
        store.conn.execute("INSERT OR IGNORE INTO event_config (guild_id) VALUES (?)", (guild_id,))
        store.conn.commit()
        return store.conn.execute("SELECT * FROM event_config WHERE guild_id=?", (guild_id,)).fetchone()

    def current_event(guild_id: int) -> Optional[sqlite3.Row]:
        row = cfg(guild_id)
        if not row["current_event_id"]:
            return None
        return store.conn.execute("SELECT * FROM game_events WHERE id=? AND guild_id=?", (row["current_event_id"], guild_id)).fetchone()

    def count_players(event_id: int) -> int:
        solo = store.conn.execute("SELECT COUNT(*) FROM event_entries WHERE event_id=?", (event_id,)).fetchone()[0]
        teams = store.conn.execute("SELECT COUNT(*) FROM event_team_members WHERE event_id=?", (event_id,)).fetchone()[0]
        return solo + teams

    def team_members(team_id: int) -> list[sqlite3.Row]:
        return store.conn.execute("SELECT * FROM event_team_members WHERE team_id=? ORDER BY user_id", (team_id,)).fetchall()

    def user_team(event_id: int, user_id: int) -> Optional[sqlite3.Row]:
        return store.conn.execute(
            "SELECT t.* FROM event_teams t JOIN event_team_members m ON m.team_id=t.id WHERE m.event_id=? AND m.user_id=?",
            (event_id, user_id),
        ).fetchone()

    def event_status(event: sqlite3.Row) -> str:
        return {"draft": "Rascunho", "open": "Inscrições abertas", "closed": "Inscrições fechadas", "running": "Em andamento"}.get(event["status"], "Encerrado")

    def event_embed(event: sqlite3.Row) -> discord.Embed:
        teams_max = event["capacity"] // event["team_size"]
        members = count_players(event["id"])
        team_format = "Solo" if event["team_size"] == 1 else f"{event['team_size']} jogadores por equipe"
        lines = [
            f"{EM_FF} **Tipo:** {event['event_type']} • {team_format}",
            f"{EM_ADM} **Jogadores:** {members}/{event['capacity']}",
            f"{EM_EVENTO} **Equipes:** {len(store.conn.execute('SELECT id FROM event_teams WHERE event_id=?', (event['id'],)).fetchall())}/{teams_max}" if event["team_size"] > 1 else "",
            f"{EM_WIN} **Prêmio:** {event['prize'] or 'Não definido'}",
            f"{EM_CLOCK} **Data e hora:** {event['starts_at'] or 'Não definida'}",
            f"{EM_CONFIG} **Status:** {event_status(event)}",
        ]
        if event["description"]:
            lines.extend(["", event["description"]])
        embed = red_embed(f"╭ {EM_EVENTO}・{event['name'].upper()} ╮", "\n".join(line for line in lines if line))
        if event["banner_url"]:
            embed.set_image(url=event["banner_url"])
        return embed

    def team_embed(event: sqlite3.Row, team: sqlite3.Row) -> discord.Embed:
        members = team_members(team["id"])
        status = "Completa" if len(members) >= event["team_size"] else f"Aguardando {event['team_size'] - len(members)} jogador(es)"
        if team["qualified_slot"]:
            status = f"Classificada como Squad {team['qualified_slot']}"
        lines = "\n".join(f"{EM_ADM} <@{m['user_id']}> • `{m['ff_id']}`" for m in members) or "Nenhum membro"
        return red_embed(
            f"╭ {EM_EVENTO}・{team['name'].upper()} ╮",
            f"{EM_ADM} **Capitão:** <@{team['captain_id']}>\n{EM_FF} **Vagas:** {len(members)}/{event['team_size']}\n{EM_CONFIG} **Status:** {status}\n\n{lines}",
        )

    async def refresh_public(guild: discord.Guild, event: sqlite3.Row) -> None:
        if not event["public_channel_id"] or not event["public_message_id"]:
            return
        channel = guild.get_channel(event["public_channel_id"])
        if isinstance(channel, discord.TextChannel):
            try:
                message = await channel.fetch_message(event["public_message_id"])
                await message.edit(embed=event_embed(event), view=EventPublicView(event["id"]))
            except discord.HTTPException:
                pass

    async def refresh_team(guild: discord.Guild, event: sqlite3.Row, team: sqlite3.Row) -> None:
        embed = team_embed(event, team)
        channel = guild.get_channel(team["channel_id"]) if team["channel_id"] else None
        if isinstance(channel, discord.TextChannel):
            try:
                messages = [message async for message in channel.history(limit=10)]
                header = next((message for message in messages if message.author == bot.user and message.embeds), None)
                if header:
                    await header.edit(embed=embed)
            except discord.HTTPException:
                pass
        logs = cfg(guild.id)["logs_channel_id"]
        log_channel = guild.get_channel(logs) if logs else None
        if isinstance(log_channel, discord.TextChannel):
            try:
                if team["log_message_id"]:
                    message = await log_channel.fetch_message(team["log_message_id"])
                    await message.edit(embed=embed)
                else:
                    message = await log_channel.send(embed=embed)
                    store.conn.execute("UPDATE event_teams SET log_message_id=? WHERE id=?", (message.id, team["id"]))
                    store.conn.commit()
            except discord.HTTPException:
                pass

    async def dm_code(member: discord.Member, team: sqlite3.Row, event: sqlite3.Row) -> bool:
        try:
            await member.send(embed=red_embed(f"╭ {EM_EVENTO}・CÓDIGO DA EQUIPE ╮", f"{EM_EVENTO} **Evento:** {event['name']}\n{EM_ADM} **Equipe:** {team['name']}\n{EM_CONFIG} **Código:** `{team['code']}`\n\nCompartilhe apenas com os jogadores da sua equipe."))
            return True
        except discord.Forbidden:
            return False

    def owner(interaction: discord.Interaction) -> bool:
        return isinstance(interaction.user, discord.Member) and is_owner_member(interaction.user)

    async def deny_owner(interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Somente o Dono pode usar este painel.", ephemeral=True)

    def active_for_entry(event: sqlite3.Row) -> bool:
        return event["status"] == "open"

    class EventCreateModal(discord.ui.Modal, title="Criar Evento"):
        name = discord.ui.TextInput(label="Nome do evento", max_length=80)
        description = discord.ui.TextInput(label="Descrição e regras", style=discord.TextStyle.paragraph, required=False, max_length=1000)
        prize = discord.ui.TextInput(label="Prêmio", required=False, max_length=120)
        kind = discord.ui.TextInput(label="Tipo e jogadores por equipe", placeholder="BR 1, BR 2, BR 3, BR 4 ou CS", max_length=10)
        when = discord.ui.TextInput(label="Data e hora", placeholder="Ex: 30/08 às 20:00", required=False, max_length=80)

        async def on_submit(self, interaction: discord.Interaction):
            if not owner(interaction):
                await deny_owner(interaction)
                return
            raw = str(self.kind).strip().upper().replace(" ", "")
            match = re.fullmatch(r"BR([1-4])", raw)
            if raw == "CS":
                event_type, team_size, capacity = "CS", 4, 8
            elif match:
                event_type, team_size, capacity = "BR", int(match.group(1)), 48
            else:
                await interaction.response.send_message("Use `BR 1`, `BR 2`, `BR 3`, `BR 4` ou `CS`.", ephemeral=True)
                return
            cursor = store.conn.execute(
                "INSERT INTO game_events (guild_id, name, description, prize, event_type, team_size, capacity, starts_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (interaction.guild_id, str(self.name), str(self.description), str(self.prize), event_type, team_size, capacity, str(self.when)),
            )
            store.conn.execute("UPDATE event_config SET current_event_id=? WHERE guild_id=?", (cursor.lastrowid, interaction.guild_id))
            store.conn.commit()
            await interaction.response.edit_message(embed=config_embed(interaction.guild_id), view=EventConfigView(interaction.guild_id))

    class BannerModal(discord.ui.Modal, title="Banner do Evento"):
        url = discord.ui.TextInput(label="Link do banner (840 x 260 recomendado)", placeholder="https://site.com/banner.png", required=False, max_length=500)

        async def on_submit(self, interaction: discord.Interaction):
            event = current_event(interaction.guild_id)
            url = str(self.url).strip()
            if not event:
                await interaction.response.send_message("Crie um evento primeiro.", ephemeral=True)
                return
            if url and not url.startswith("https://"):
                await interaction.response.send_message("O banner precisa ser um link HTTPS.", ephemeral=True)
                return
            store.conn.execute("UPDATE game_events SET banner_url=? WHERE id=?", (url or None, event["id"]))
            store.conn.commit()
            await interaction.response.edit_message(embed=config_embed(interaction.guild_id), view=EventConfigView(interaction.guild_id))

    class EditEventModal(discord.ui.Modal, title="Editar Evento"):
        name = discord.ui.TextInput(label="Nome do evento", max_length=80)
        description = discord.ui.TextInput(label="Descrição e regras", style=discord.TextStyle.paragraph, required=False, max_length=1000)
        prize = discord.ui.TextInput(label="Prêmio", required=False, max_length=120)
        when = discord.ui.TextInput(label="Data e hora", required=False, max_length=80)

        def __init__(self, event: sqlite3.Row):
            super().__init__()
            self.event_id = event["id"]
            self.name.default = event["name"]
            self.description.default = event["description"]
            self.prize.default = event["prize"]
            self.when.default = event["starts_at"]

        async def on_submit(self, interaction: discord.Interaction):
            if not owner(interaction):
                await deny_owner(interaction)
                return
            store.conn.execute(
                "UPDATE game_events SET name=?, description=?, prize=?, starts_at=? WHERE id=?",
                (str(self.name), str(self.description), str(self.prize), str(self.when), self.event_id),
            )
            store.conn.commit()
            event = store.conn.execute("SELECT * FROM game_events WHERE id=?", (self.event_id,)).fetchone()
            await refresh_public(interaction.guild, event)
            await interaction.response.edit_message(embed=config_embed(interaction.guild_id), view=EventConfigView(interaction.guild_id))

    class RoomModal(discord.ui.Modal, title="Definir Sala do Evento"):
        room_id = discord.ui.TextInput(label="ID da sala", max_length=80)
        password = discord.ui.TextInput(label="Senha da sala", required=False, max_length=80)
        minutes = discord.ui.TextInput(label="Minutos para entrar", default="5", max_length=2)

        async def on_submit(self, interaction: discord.Interaction):
            event = current_event(interaction.guild_id)
            try:
                minutes = max(1, min(30, int(str(self.minutes))))
            except ValueError:
                await interaction.response.send_message("Informe um número de 1 a 30 minutos.", ephemeral=True)
                return
            if not event:
                await interaction.response.send_message("Nenhum evento selecionado.", ephemeral=True)
                return
            store.conn.execute("UPDATE game_events SET room_id=?, room_password=?, room_minutes=? WHERE id=?", (str(self.room_id), str(self.password), minutes, event["id"]))
            store.conn.commit()
            await interaction.response.edit_message(embed=config_embed(interaction.guild_id), view=EventConfigView(interaction.guild_id))

    class EventChannelSelect(discord.ui.ChannelSelect):
        def __init__(self, field: str, category: bool = False):
            self.field = field
            super().__init__(placeholder="Selecione o destino", channel_types=[discord.ChannelType.category] if category else [discord.ChannelType.text], min_values=1, max_values=1)

        async def callback(self, interaction: discord.Interaction):
            store.conn.execute(f"UPDATE event_config SET {self.field}=? WHERE guild_id=?", (self.values[0].id, interaction.guild_id))
            store.conn.commit()
            await interaction.response.edit_message(embed=config_embed(interaction.guild_id), view=EventConfigView(interaction.guild_id))

    class EventChannelView(discord.ui.View):
        def __init__(self, field: str, category: bool = False):
            super().__init__(timeout=120)
            self.add_item(EventChannelSelect(field, category))

    class TeamJoinModal(discord.ui.Modal, title="Entrar com Código"):
        code = discord.ui.TextInput(label="Código de 6 dígitos", max_length=6)
        full_name = discord.ui.TextInput(label="Nome completo", max_length=100)
        ff_id = discord.ui.TextInput(label="ID do Free Fire", max_length=80)

        def __init__(self, event_id: int):
            super().__init__()
            self.event_id = event_id

        async def on_submit(self, interaction: discord.Interaction):
            event = store.conn.execute("SELECT * FROM game_events WHERE id=?", (self.event_id,)).fetchone()
            if not event or not active_for_entry(event):
                await interaction.response.send_message("As inscrições não estão abertas.", ephemeral=True)
                return
            if user_team(event["id"], interaction.user.id):
                await interaction.response.send_message("Você já está em uma guilda deste evento.", ephemeral=True)
                return
            team = store.conn.execute("SELECT * FROM event_teams WHERE event_id=? AND code=?", (event["id"], str(self.code).strip())).fetchone()
            if not team:
                await interaction.response.send_message("Código de equipe inválido.", ephemeral=True)
                return
            if team["locked"]:
                await interaction.response.send_message("Esta guilda já está travada/classificada.", ephemeral=True)
                return
            if len(team_members(team["id"])) >= event["team_size"] or count_players(event["id"]) >= event["capacity"]:
                await interaction.response.send_message("Não há mais vaga nesta guilda ou no evento.", ephemeral=True)
                return
            store.conn.execute("INSERT INTO event_team_members (event_id, team_id, user_id, full_name, ff_id) VALUES (?, ?, ?, ?, ?)", (event["id"], team["id"], interaction.user.id, str(self.full_name), str(self.ff_id)))
            store.conn.commit()
            guild = interaction.guild
            channel = guild.get_channel(team["channel_id"]) if guild and team["channel_id"] else None
            if isinstance(channel, discord.TextChannel) and isinstance(interaction.user, discord.Member):
                await channel.set_permissions(interaction.user, view_channel=True, send_messages=True, read_message_history=True)
                await channel.send(f"{EM_OK} {interaction.user.mention} entrou na guilda.")
            team = store.conn.execute("SELECT * FROM event_teams WHERE id=?", (team["id"],)).fetchone()
            await lock_cs_team(guild, event, team)
            team = store.conn.execute("SELECT * FROM event_teams WHERE id=?", (team["id"],)).fetchone()
            event = store.conn.execute("SELECT * FROM game_events WHERE id=?", (event["id"],)).fetchone()
            await refresh_team(guild, event, team)
            await refresh_public(guild, event)
            await interaction.response.send_message(f"{EM_OK} Você entrou na guilda **{team['name']}**.", ephemeral=True)

    class TeamCreateModal(discord.ui.Modal, title="Criar Guilda"):
        team_name = discord.ui.TextInput(label="Nome da guilda", max_length=60)
        full_name = discord.ui.TextInput(label="Seu nome completo", max_length=100)
        ff_id = discord.ui.TextInput(label="Seu ID do Free Fire", max_length=80)

        def __init__(self, event_id: int):
            super().__init__()
            self.event_id = event_id

        async def on_submit(self, interaction: discord.Interaction):
            event = store.conn.execute("SELECT * FROM game_events WHERE id=?", (self.event_id,)).fetchone()
            config = cfg(interaction.guild_id)
            if not event or not active_for_entry(event):
                await interaction.response.send_message("As inscrições não estão abertas.", ephemeral=True)
                return
            if event["team_size"] == 1:
                await interaction.response.send_message("Este evento é solo.", ephemeral=True)
                return
            if user_team(event["id"], interaction.user.id):
                await interaction.response.send_message("Você já está em uma guilda deste evento.", ephemeral=True)
                return
            if count_players(event["id"]) >= event["capacity"]:
                await interaction.response.send_message("O evento já está cheio.", ephemeral=True)
                return
            if not config["teams_category_id"]:
                await interaction.response.send_message("O Dono ainda não definiu a categoria das guildas.", ephemeral=True)
                return
            code = ""
            while not code or store.conn.execute("SELECT 1 FROM event_teams WHERE event_id=? AND code=?", (event["id"], code)).fetchone():
                code = f"{random.randint(0, 999999):06d}"
            cursor = store.conn.execute("INSERT INTO event_teams (event_id, name, captain_id, code) VALUES (?, ?, ?, ?)", (event["id"], str(self.team_name), interaction.user.id, code))
            team_id = cursor.lastrowid
            store.conn.execute("INSERT INTO event_team_members (event_id, team_id, user_id, full_name, ff_id) VALUES (?, ?, ?, ?, ?)", (event["id"], team_id, interaction.user.id, str(self.full_name), str(self.ff_id)))
            store.conn.commit()
            guild = interaction.guild
            category = guild.get_channel(config["teams_category_id"]) if guild else None
            if not isinstance(category, discord.CategoryChannel):
                await interaction.response.send_message("A categoria das guildas não foi encontrada.", ephemeral=True)
                return
            leader = interaction.user
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                leader: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                guild.owner: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            }
            channel = await category.create_text_channel(ensure_channel_name(f"{event['name']}-{self.team_name}"), overwrites=overwrites, reason="Canal de guilda do evento")
            store.conn.execute("UPDATE event_teams SET channel_id=? WHERE id=?", (channel.id, team_id))
            store.conn.commit()
            team = store.conn.execute("SELECT * FROM event_teams WHERE id=?", (team_id,)).fetchone()
            await channel.send(content=leader.mention, embed=team_embed(event, team))
            await channel.send(embed=red_embed(f"╭ {EM_CONFIG}・CÓDIGO DA EQUIPE ╮", f"{EM_CONFIG} Código da guilda: `{team['code']}`\nEnvie esse código apenas aos jogadores que deseja convidar."))
            sent_dm = await dm_code(leader, team, event)
            await refresh_team(guild, event, team)
            await refresh_public(guild, event)
            dm_text = "O código também foi enviado na sua DM." if sent_dm else "Sua DM está fechada; o código está no canal privado da guilda."
            await interaction.response.send_message(f"{EM_OK} Guilda criada: {channel.mention}. {dm_text}", ephemeral=True)

    class SoloEntryModal(discord.ui.Modal, title="Entrar no Evento"):
        full_name = discord.ui.TextInput(label="Nome completo", max_length=100)
        ff_id = discord.ui.TextInput(label="ID do Free Fire", max_length=80)

        def __init__(self, event_id: int):
            super().__init__()
            self.event_id = event_id

        async def on_submit(self, interaction: discord.Interaction):
            event = store.conn.execute("SELECT * FROM game_events WHERE id=?", (self.event_id,)).fetchone()
            if not event or not active_for_entry(event):
                await interaction.response.send_message("As inscrições não estão abertas.", ephemeral=True)
                return
            if store.conn.execute("SELECT 1 FROM event_entries WHERE event_id=? AND user_id=?", (event["id"], interaction.user.id)).fetchone():
                await interaction.response.send_message("Você já está inscrito neste evento.", ephemeral=True)
                return
            if count_players(event["id"]) >= event["capacity"]:
                await interaction.response.send_message("O evento já está cheio.", ephemeral=True)
                return
            store.conn.execute("INSERT INTO event_entries (event_id, user_id, full_name, ff_id) VALUES (?, ?, ?, ?)", (event["id"], interaction.user.id, str(self.full_name), str(self.ff_id)))
            store.conn.commit()
            await refresh_public(interaction.guild, event)
            await interaction.response.send_message(f"{EM_OK} Inscrição realizada com sucesso.", ephemeral=True)

    class MyEventView(discord.ui.View):
        def __init__(self, event_id: int, user_id: int):
            super().__init__(timeout=180)
            self.event_id, self.user_id = event_id, user_id
            self.add_item(LeaveEventButton(event_id, user_id))

    class LeaveEventButton(discord.ui.Button):
        def __init__(self, event_id: int, user_id: int):
            super().__init__(label="Cancelar inscrição", emoji=EM_X, style=discord.ButtonStyle.danger)
            self.event_id, self.user_id = event_id, user_id

        async def callback(self, interaction: discord.Interaction):
            event = store.conn.execute("SELECT * FROM game_events WHERE id=?", (self.event_id,)).fetchone()
            if interaction.user.id != self.user_id or not event or event["status"] != "open":
                await interaction.response.send_message("A inscrição não pode mais ser cancelada.", ephemeral=True)
                return
            store.conn.execute("DELETE FROM event_entries WHERE event_id=? AND user_id=?", (self.event_id, self.user_id))
            store.conn.commit()
            await refresh_public(interaction.guild, event)
            await interaction.response.edit_message(content=f"{EM_OK} Inscrição cancelada.", embed=None, view=None)

    class TeamDashboardView(discord.ui.View):
        def __init__(self, event_id: int, team_id: int, user_id: int):
            super().__init__(timeout=180)
            self.event_id, self.team_id, self.user_id = event_id, team_id, user_id
            self.add_item(TeamLeaveButton(event_id, team_id, user_id))
            self.add_item(TeamCodeButton(event_id, team_id, user_id))
            team = store.conn.execute("SELECT * FROM event_teams WHERE id=?", (team_id,)).fetchone()
            if team and team["captain_id"] == user_id:
                self.add_item(TeamRemoveMemberButton(event_id, team_id))

    class TeamLeaveButton(discord.ui.Button):
        def __init__(self, event_id: int, team_id: int, user_id: int):
            super().__init__(label="Sair da guilda", emoji=EM_X, style=discord.ButtonStyle.danger)
            self.event_id, self.team_id, self.user_id = event_id, team_id, user_id

        async def callback(self, interaction: discord.Interaction):
            event = store.conn.execute("SELECT * FROM game_events WHERE id=?", (self.event_id,)).fetchone()
            team = store.conn.execute("SELECT * FROM event_teams WHERE id=?", (self.team_id,)).fetchone()
            if interaction.user.id != self.user_id or not event or not team or event["status"] != "open" or team["locked"]:
                await interaction.response.send_message("Esta guilda está travada ou as inscrições fecharam.", ephemeral=True)
                return
            members = team_members(team["id"])
            if team["captain_id"] == self.user_id and len(members) > 1:
                await interaction.response.send_message("O capitão deve remover os membros antes de excluir a guilda.", ephemeral=True)
                return
            store.conn.execute("DELETE FROM event_team_members WHERE event_id=? AND user_id=?", (self.event_id, self.user_id))
            if len(members) == 1:
                await cleanup_team(interaction.guild, team)
                store.conn.execute("DELETE FROM event_teams WHERE id=?", (team["id"],))
            else:
                channel = interaction.guild.get_channel(team["channel_id"]) if team["channel_id"] else None
                if isinstance(channel, discord.TextChannel):
                    await channel.set_permissions(interaction.user, overwrite=None)
            store.conn.commit()
            await refresh_public(interaction.guild, event)
            await interaction.response.edit_message(content=f"{EM_OK} Você saiu da guilda.", embed=None, view=None)

    class TeamCodeButton(discord.ui.Button):
        def __init__(self, event_id: int, team_id: int, user_id: int):
            super().__init__(label="Reenviar código", emoji=EM_CONFIG, style=discord.ButtonStyle.secondary)
            self.event_id, self.team_id, self.user_id = event_id, team_id, user_id

        async def callback(self, interaction: discord.Interaction):
            team = store.conn.execute("SELECT * FROM event_teams WHERE id=?", (self.team_id,)).fetchone()
            event = store.conn.execute("SELECT * FROM game_events WHERE id=?", (self.event_id,)).fetchone()
            if not team or team["captain_id"] != interaction.user.id:
                await interaction.response.send_message("Somente o capitão pode receber o código.", ephemeral=True)
                return
            sent = await dm_code(interaction.user, team, event)
            await interaction.response.send_message(f"{EM_OK} {'Código reenviado na sua DM.' if sent else 'Sua DM está fechada; use o canal privado da guilda.'}", ephemeral=True)

    class TeamRemoveMemberButton(discord.ui.Button):
        def __init__(self, event_id: int, team_id: int):
            super().__init__(label="Remover membro", emoji=EM_X, style=discord.ButtonStyle.secondary)
            self.event_id, self.team_id = event_id, team_id

        async def callback(self, interaction: discord.Interaction):
            team = store.conn.execute("SELECT * FROM event_teams WHERE id=?", (self.team_id,)).fetchone()
            if not team or team["captain_id"] != interaction.user.id or team["locked"]:
                await interaction.response.send_message("Você não pode remover membros desta guilda.", ephemeral=True)
                return
            members = [member for member in team_members(self.team_id) if member["user_id"] != interaction.user.id]
            if not members:
                await interaction.response.send_message("Não há membro para remover.", ephemeral=True)
                return
            await interaction.response.send_message("Selecione o membro que deseja remover:", view=TeamRemoveMemberView(self.event_id, self.team_id, members), ephemeral=True)

    class TeamRemoveMemberSelect(discord.ui.Select):
        def __init__(self, event_id: int, team_id: int, members: list[sqlite3.Row]):
            self.event_id, self.team_id = event_id, team_id
            options = [discord.SelectOption(label=str(member["full_name"])[:100], description=f"ID Free Fire: {member['ff_id']}", value=str(member["user_id"]), emoji=EM_ADM) for member in members[:25]]
            super().__init__(placeholder="Selecione um membro", options=options, min_values=1, max_values=1)

        async def callback(self, interaction: discord.Interaction):
            event = store.conn.execute("SELECT * FROM game_events WHERE id=?", (self.event_id,)).fetchone()
            team = store.conn.execute("SELECT * FROM event_teams WHERE id=?", (self.team_id,)).fetchone()
            user_id = int(self.values[0])
            if not event or not team or team["captain_id"] != interaction.user.id or team["locked"] or event["status"] != "open":
                await interaction.response.send_message("A remoção não é permitida agora.", ephemeral=True)
                return
            store.conn.execute("DELETE FROM event_team_members WHERE event_id=? AND team_id=? AND user_id=?", (self.event_id, self.team_id, user_id))
            store.conn.commit()
            channel = interaction.guild.get_channel(team["channel_id"]) if team["channel_id"] else None
            member = interaction.guild.get_member(user_id)
            if isinstance(channel, discord.TextChannel) and member:
                await channel.set_permissions(member, overwrite=None)
            await refresh_team(interaction.guild, event, team)
            await refresh_public(interaction.guild, event)
            await interaction.response.edit_message(content=f"{EM_OK} Membro removido da guilda.", view=None)

    class TeamRemoveMemberView(discord.ui.View):
        def __init__(self, event_id: int, team_id: int, members: list[sqlite3.Row]):
            super().__init__(timeout=90)
            self.add_item(TeamRemoveMemberSelect(event_id, team_id, members))

    class EventPublicView(discord.ui.View):
        def __init__(self, event_id: int):
            super().__init__(timeout=None)
            event = store.conn.execute("SELECT * FROM game_events WHERE id=?", (event_id,)).fetchone()
            if not event:
                return
            if event["team_size"] == 1:
                self.add_item(EventButton("Entrar no evento", EM_OK, event_id, "solo", f"event:solo:{event_id}"))
            else:
                self.add_item(EventButton("Criar guilda", EM_EVENTO, event_id, "create", f"event:create:{event_id}"))
                self.add_item(EventButton("Entrar com código", EM_CONFIG, event_id, "code", f"event:code:{event_id}"))
            self.add_item(EventButton("Atualizar", EM_CLOCK, event_id, "mine", f"event:mine:{event_id}"))

    class EventButton(discord.ui.Button):
        def __init__(self, label: str, emoji: str, event_id: int, action: str, custom_id: str):
            super().__init__(label=label, emoji=emoji, style=discord.ButtonStyle.secondary, custom_id=custom_id)
            self.event_id, self.action = event_id, action

        async def callback(self, interaction: discord.Interaction):
            event = store.conn.execute("SELECT * FROM game_events WHERE id=?", (self.event_id,)).fetchone()
            if not event:
                await interaction.response.send_message("Este evento não existe mais.", ephemeral=True)
                return
            if self.action == "solo":
                await interaction.response.send_modal(SoloEntryModal(self.event_id))
            elif self.action == "create":
                await interaction.response.send_modal(TeamCreateModal(self.event_id))
            elif self.action == "code":
                await interaction.response.send_modal(TeamJoinModal(self.event_id))
            else:
                if event["team_size"] == 1:
                    row = store.conn.execute("SELECT * FROM event_entries WHERE event_id=? AND user_id=?", (self.event_id, interaction.user.id)).fetchone()
                    if not row:
                        await interaction.response.send_message("Você ainda não está inscrito.", ephemeral=True)
                        return
                    await interaction.response.send_message(embed=red_embed(f"╭ {EM_EVENTO}・MINHA INSCRIÇÃO ╮", f"{EM_ADM} {interaction.user.mention}\n{EM_CONFIG} Nome: **{row['full_name']}**\n{EM_FF} ID: `{row['ff_id']}`"), view=MyEventView(self.event_id, interaction.user.id), ephemeral=True)
                else:
                    team = user_team(self.event_id, interaction.user.id)
                    if not team:
                        await interaction.response.send_message("Você ainda não participa de uma guilda.", ephemeral=True)
                        return
                    await interaction.response.send_message(embed=team_embed(event, team), view=TeamDashboardView(self.event_id, team["id"], interaction.user.id), ephemeral=True)

    async def cleanup_team(guild: discord.Guild, team: sqlite3.Row) -> None:
        if team["channel_id"]:
            channel = guild.get_channel(team["channel_id"])
            if isinstance(channel, discord.TextChannel):
                try:
                    await channel.delete(reason="Guilda removida do evento")
                except discord.HTTPException:
                    pass
        logs_id = cfg(guild.id)["logs_channel_id"]
        if logs_id and team["log_message_id"]:
            channel = guild.get_channel(logs_id)
            if isinstance(channel, discord.TextChannel):
                try:
                    await (await channel.fetch_message(team["log_message_id"])).delete()
                except discord.HTTPException:
                    pass

    async def lock_cs_team(guild: discord.Guild, event: sqlite3.Row, team: sqlite3.Row) -> None:
        if event["event_type"] != "CS" or len(team_members(team["id"])) < 4 or team["qualified_slot"]:
            return
        qualified = store.conn.execute("SELECT COUNT(*) FROM event_teams WHERE event_id=? AND qualified_slot IS NOT NULL", (event["id"],)).fetchone()[0]
        if qualified >= 2:
            return
        slot = qualified + 1
        store.conn.execute("UPDATE event_teams SET locked=1, qualified_slot=? WHERE id=?", (slot, team["id"]))
        if slot == 2:
            store.conn.execute("UPDATE game_events SET status='closed' WHERE id=?", (event["id"],))
        store.conn.commit()

    async def remove_event(guild: discord.Guild, event: sqlite3.Row) -> None:
        teams = store.conn.execute("SELECT * FROM event_teams WHERE event_id=?", (event["id"],)).fetchall()
        for team in teams:
            await cleanup_team(guild, team)
        if event["public_channel_id"] and event["public_message_id"]:
            channel = guild.get_channel(event["public_channel_id"])
            if isinstance(channel, discord.TextChannel):
                try:
                    await (await channel.fetch_message(event["public_message_id"])).delete()
                except discord.HTTPException:
                    pass
        store.conn.execute("DELETE FROM event_team_members WHERE event_id=?", (event["id"],))
        store.conn.execute("DELETE FROM event_teams WHERE event_id=?", (event["id"],))
        store.conn.execute("DELETE FROM event_entries WHERE event_id=?", (event["id"],))
        store.conn.execute("DELETE FROM game_events WHERE id=?", (event["id"],))
        store.conn.execute("UPDATE event_config SET current_event_id=NULL WHERE guild_id=?", (guild.id,))
        store.conn.commit()

    async def room_countdown(guild: discord.Guild, event_id: int, minutes: int) -> None:
        """Envia atualizações por minuto apenas durante a janela de entrada na sala."""
        for remaining in range(minutes - 1, 0, -1):
            await asyncio.sleep(60)
            event = store.conn.execute("SELECT * FROM game_events WHERE id=?", (event_id,)).fetchone()
            if not event or event["status"] != "running":
                return
            notice = f"{EM_CLOCK} Restam **{remaining} minuto(s)** para entrar na sala."
            for team in store.conn.execute("SELECT channel_id FROM event_teams WHERE event_id=?", (event_id,)).fetchall():
                channel = guild.get_channel(team["channel_id"])
                if isinstance(channel, discord.TextChannel):
                    try:
                        await channel.send(notice)
                    except discord.HTTPException:
                        pass
        event = store.conn.execute("SELECT * FROM game_events WHERE id=?", (event_id,)).fetchone()
        if event and event["status"] == "running":
            for team in store.conn.execute("SELECT channel_id FROM event_teams WHERE event_id=?", (event_id,)).fetchall():
                channel = guild.get_channel(team["channel_id"])
                if isinstance(channel, discord.TextChannel):
                    try:
                        await channel.send(f"{EM_X} O prazo para entrar na sala terminou.")
                    except discord.HTTPException:
                        pass

    class RemoveEventConfirm(discord.ui.View):
        def __init__(self, event_id: int):
            super().__init__(timeout=45)
            self.event_id = event_id

        @discord.ui.button(label="Confirmar remoção", emoji=EM_X, style=discord.ButtonStyle.danger)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not owner(interaction):
                await deny_owner(interaction)
                return
            event = store.conn.execute("SELECT * FROM game_events WHERE id=?", (self.event_id,)).fetchone()
            if event:
                await remove_event(interaction.guild, event)
            await interaction.response.edit_message(content=f"{EM_OK} Evento removido, equipes e códigos resetados.", embed=None, view=None)

    class EventConfigMenu(discord.ui.Select):
        def __init__(self, guild_id: int):
            self.guild_id = guild_id
            options = [
                discord.SelectOption(label="Configurar canal do evento", value="event_channel", emoji=EM_EVENTO),
                discord.SelectOption(label="Configurar categoria das guildas", value="category", emoji=EM_ADM),
                discord.SelectOption(label="Configurar canal de logs", value="logs", emoji=EM_CONFIG),
                discord.SelectOption(label="Configurar canal administrativo", value="admin", emoji=EM_ADM),
            ]
            super().__init__(placeholder="Configurações de canais", options=options)

        async def callback(self, interaction: discord.Interaction):
            mapping = {"event_channel": ("event_channel_id", False), "category": ("teams_category_id", True), "logs": ("logs_channel_id", False), "admin": ("admin_channel_id", False)}
            field, category = mapping[self.values[0]]
            await interaction.response.send_message("Selecione o destino:", view=EventChannelView(field, category), ephemeral=True)

    class EventConfigView(discord.ui.View):
        def __init__(self, guild_id: int):
            super().__init__(timeout=600)
            self.guild_id = guild_id
            self.add_item(EventConfigMenu(guild_id))

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if owner(interaction):
                return True
            await interaction.response.send_message("Somente o Dono pode usar este painel.", ephemeral=True)
            return False

        @discord.ui.button(label="Criar evento", emoji=EM_EVENTO, style=discord.ButtonStyle.secondary, row=1)
        async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not owner(interaction):
                await deny_owner(interaction)
                return
            await interaction.response.send_modal(EventCreateModal())

        @discord.ui.button(label="Banner", emoji=EM_CONFIG, style=discord.ButtonStyle.secondary, row=1)
        async def banner(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not current_event(interaction.guild_id):
                await interaction.response.send_message("Crie um evento primeiro.", ephemeral=True)
                return
            await interaction.response.send_modal(BannerModal())

        @discord.ui.button(label="Editar evento", emoji=EM_CONFIG, style=discord.ButtonStyle.secondary, row=1)
        async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
            event = current_event(interaction.guild_id)
            if not event:
                await interaction.response.send_message("Crie um evento primeiro.", ephemeral=True)
                return
            await interaction.response.send_modal(EditEventModal(event))

        @discord.ui.button(label="Visualizar", emoji=EM_CLOCK, style=discord.ButtonStyle.secondary, row=1)
        async def preview(self, interaction: discord.Interaction, button: discord.ui.Button):
            event = current_event(interaction.guild_id)
            if not event:
                await interaction.response.send_message("Crie um evento primeiro.", ephemeral=True)
                return
            await interaction.response.send_message(embed=event_embed(event), view=EventPublicView(event["id"]), ephemeral=True)

        @discord.ui.button(label="Enviar evento", emoji=EM_OK, style=discord.ButtonStyle.success, row=1)
        async def publish(self, interaction: discord.Interaction, button: discord.ui.Button):
            event, config = current_event(interaction.guild_id), cfg(interaction.guild_id)
            if not event or not config["event_channel_id"]:
                await interaction.response.send_message("Crie o evento e selecione o canal do evento primeiro.", ephemeral=True)
                return
            channel = interaction.guild.get_channel(config["event_channel_id"])
            if not isinstance(channel, discord.TextChannel):
                await interaction.response.send_message("Canal do evento não encontrado.", ephemeral=True)
                return
            store.conn.execute("UPDATE game_events SET status='open' WHERE id=?", (event["id"],))
            event = store.conn.execute("SELECT * FROM game_events WHERE id=?", (event["id"],)).fetchone()
            message = await channel.send(embed=event_embed(event), view=EventPublicView(event["id"]))
            store.conn.execute("UPDATE game_events SET public_channel_id=?, public_message_id=? WHERE id=?", (channel.id, message.id, event["id"]))
            store.conn.commit()
            if config["admin_channel_id"]:
                admin_channel = interaction.guild.get_channel(config["admin_channel_id"])
                if isinstance(admin_channel, discord.TextChannel):
                    await admin_channel.send(embed=red_embed(f"╭ {EM_EVENTO}・EVENTO ENVIADO ╮", f"{EM_OK} **{event['name']}** foi enviado em {channel.mention}."))
            await interaction.response.edit_message(embed=config_embed(interaction.guild_id), view=EventConfigView(interaction.guild_id))

        @discord.ui.button(label="Abrir/fechar", emoji=EM_CLOCK, style=discord.ButtonStyle.secondary, row=2)
        async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
            event = current_event(interaction.guild_id)
            if not event:
                await interaction.response.send_message("Nenhum evento selecionado.", ephemeral=True)
                return
            status = "closed" if event["status"] == "open" else "open"
            store.conn.execute("UPDATE game_events SET status=? WHERE id=?", (status, event["id"]))
            store.conn.commit()
            event = store.conn.execute("SELECT * FROM game_events WHERE id=?", (event["id"],)).fetchone()
            await refresh_public(interaction.guild, event)
            await interaction.response.edit_message(embed=config_embed(interaction.guild_id), view=EventConfigView(interaction.guild_id))

        @discord.ui.button(label="Definir sala", emoji=EM_FF, style=discord.ButtonStyle.secondary, row=2)
        async def room(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not current_event(interaction.guild_id):
                await interaction.response.send_message("Nenhum evento selecionado.", ephemeral=True)
                return
            await interaction.response.send_modal(RoomModal())

        @discord.ui.button(label="Começar evento", emoji=EM_WIN, style=discord.ButtonStyle.success, row=2)
        async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
            event = current_event(interaction.guild_id)
            if not event or not event["room_id"]:
                await interaction.response.send_message("Defina ID e senha da sala antes de começar.", ephemeral=True)
                return
            store.conn.execute("UPDATE game_events SET status='running' WHERE id=?", (event["id"],))
            store.conn.commit()
            event = store.conn.execute("SELECT * FROM game_events WHERE id=?", (event["id"],)).fetchone()
            room_embed = red_embed(f"╭ {EM_FF}・SALA DO EVENTO ╮", f"{EM_FF} **ID:** `{event['room_id']}`\n{EM_CONFIG} **Senha:** `{event['room_password'] or 'Sem senha'}`\n{EM_CLOCK} Vocês têm **{event['room_minutes']} minuto(s)** para entrar na sala.")
            teams = store.conn.execute("SELECT * FROM event_teams WHERE event_id=?", (event["id"],)).fetchall()
            for team in teams:
                channel = interaction.guild.get_channel(team["channel_id"]) if team["channel_id"] else None
                if isinstance(channel, discord.TextChannel):
                    await channel.send(embed=room_embed)
            public_channel = interaction.guild.get_channel(event["public_channel_id"]) if event["public_channel_id"] else None
            if isinstance(public_channel, discord.TextChannel):
                await public_channel.send(embed=room_embed)
            asyncio.create_task(room_countdown(interaction.guild, event["id"], event["room_minutes"]))
            await refresh_public(interaction.guild, event)
            await interaction.response.edit_message(embed=config_embed(interaction.guild_id), view=EventConfigView(interaction.guild_id))

        @discord.ui.button(label="Remover evento", emoji=EM_X, style=discord.ButtonStyle.danger, row=2)
        async def remove(self, interaction: discord.Interaction, button: discord.ui.Button):
            event = current_event(interaction.guild_id)
            if not event:
                await interaction.response.send_message("Nenhum evento selecionado.", ephemeral=True)
                return
            await interaction.response.send_message(embed=red_embed(f"╭ {EM_X}・CONFIRMAR REMOÇÃO ╮", "Isso apagará canais de guilda, logs, códigos e inscrições deste evento."), view=RemoveEventConfirm(event["id"]), ephemeral=True)

    def config_embed(guild_id: int) -> discord.Embed:
        config, event = cfg(guild_id), current_event(guild_id)
        event_name = event["name"] if event else "Nenhum evento criado"
        event_channel = f"<#{config['event_channel_id']}>" if config["event_channel_id"] else "Não definido"
        teams_category = f"<#{config['teams_category_id']}>" if config["teams_category_id"] else "Não definida"
        logs_channel = f"<#{config['logs_channel_id']}>" if config["logs_channel_id"] else "Não definido"
        admin_channel = f"<#{config['admin_channel_id']}>" if config["admin_channel_id"] else "Não definido"
        return red_embed(
            f"╭ {EM_EVENTO}・CONFIG EVENTOS ╮",
            f"{EM_EVENTO} **Evento atual:** {event_name}\n"
            f"{EM_FF} **Canal do evento:** {event_channel}\n"
            f"{EM_ADM} **Categoria das guildas:** {teams_category}\n"
            f"{EM_CONFIG} **Canal de logs:** {logs_channel}\n"
            f"{EM_ADM} **Canal administrativo:** {admin_channel}",
        )

    @bot.tree.command(name="configeventos", description="Painel para configurar e publicar eventos")
    async def configeventos(interaction: discord.Interaction):
        if not interaction.guild or not owner(interaction):
            await interaction.response.send_message("Somente o Dono pode configurar eventos.", ephemeral=True)
            return
        await interaction.response.send_message(embed=config_embed(interaction.guild_id), view=EventConfigView(interaction.guild_id), ephemeral=True)

    @bot.tree.command(name="criarevento", description="Atalho para criar um evento")
    async def criarevento(interaction: discord.Interaction):
        if not interaction.guild or not owner(interaction):
            await interaction.response.send_message("Somente o Dono pode criar eventos.", ephemeral=True)
            return
        cfg(interaction.guild_id)
        await interaction.response.send_modal(EventCreateModal())

    @bot.tree.command(name="eventos", description="Abrir o painel de configuração dos eventos")
    async def eventos(interaction: discord.Interaction):
        if not interaction.guild or not owner(interaction):
            await interaction.response.send_message("Use a mensagem pública do evento para entrar. Somente o Dono abre a configuração.", ephemeral=True)
            return
        await interaction.response.send_message(embed=config_embed(interaction.guild_id), view=EventConfigView(interaction.guild_id), ephemeral=True)

    async def register_views() -> None:
        for event in store.conn.execute("SELECT id FROM game_events WHERE status IN ('open', 'closed', 'running')").fetchall():
            bot.add_view(EventPublicView(event["id"]))

    bot.add_listener(register_views, "on_ready")
