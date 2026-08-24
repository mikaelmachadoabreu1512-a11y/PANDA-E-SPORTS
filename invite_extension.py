import discord
from typing import Any, Optional

EM_INV = {
    "sucesso":  "<a:sucesso_animado:1516913609303658506>",
    "erro":     "<a:erro_animado:1516913586054631558>",
    "aviso":    "<a:alerta_staff_animado:1516913572280533063>",
    "staff":    "<:staff:1516913606795464805>",
    "perfil":   "<:perfil_usuario:1516913596842643557>",
    "presente": "<:presente:1516913602399834132>",
    "ranking":  "<a:ranking:1516913552034631721>",
    "suporte":  "<:56644tools1:1516917629841969232>",
    "config":   "<:config:1516913563531215009>",
    "adicionar":"<:adicionar:1516913558238265563>",
    "sair":     "<:sair:1516917997539692655>",
    "bloqueado":"<:bloqueado:1516913576848130208>",
}

# Cache global de invites: {guild_id: {code: uses}}
invite_cache: dict[int, dict[str, int]] = {}


def setup(ctx: dict[str, Any]) -> None:
    bot = ctx["bot"]
    store = ctx["store"]
    red_embed = ctx["red_embed"]
    owner_only = ctx["owner_only"]
    deny_owner = ctx["deny_owner"]

    # ── Criar tabelas ────────────────────────────────────────────────────────
    store.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS invite_config (
            guild_id INTEGER PRIMARY KEY,
            log_channel_id INTEGER,
            dm_message TEXT
        );
        CREATE TABLE IF NOT EXISTS invite_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            inviter_id INTEGER NOT NULL,
            invited_id INTEGER NOT NULL,
            invite_code TEXT,
            joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    store.conn.commit()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def get_invite_config(guild_id: int) -> dict:
        row = store.conn.execute(
            "SELECT * FROM invite_config WHERE guild_id=?", (guild_id,)
        ).fetchone()
        if not row:
            store.conn.execute(
                "INSERT OR IGNORE INTO invite_config (guild_id) VALUES (?)", (guild_id,)
            )
            store.conn.commit()
            row = store.conn.execute(
                "SELECT * FROM invite_config WHERE guild_id=?", (guild_id,)
            ).fetchone()
        return dict(row)

    def get_invite_count(guild_id: int, inviter_id: int) -> int:
        row = store.conn.execute(
            "SELECT COUNT(*) AS total FROM invite_tracking WHERE guild_id=? AND inviter_id=?",
            (guild_id, inviter_id),
        ).fetchone()
        return int(row["total"]) if row else 0

    def invite_config_embed(guild_id: int) -> discord.Embed:
        cfg = get_invite_config(guild_id)
        canal = f"<#{cfg['log_channel_id']}>" if cfg.get("log_channel_id") else "Não definido"
        dm = cfg.get("dm_message") or "Mensagem padrão"
        desc = (
            f"{EM_INV['config']} **Canal de log:** {canal}\n"
            f"{EM_INV['sucesso']} **DM personalizada:** {dm[:100]}{'...' if len(dm) > 100 else ''}\n\n"
            f"{EM_INV['aviso']} Variáveis disponíveis: `{{user}}`, `{{inviter}}`, `{{count}}`"
        )
        return discord.Embed(
            title=f"╭ {EM_INV['config']}・𝐂𝐎𝐍𝐅𝐈𝐆 𝐈𝐍𝐕𝐈𝐓𝐄𝐒 ╮",
            description=desc,
            color=discord.Color(0x2B2D31),
        )

    # ── Modais ───────────────────────────────────────────────────────────────

    class InviteDmModal(discord.ui.Modal, title="Configurar DM de Boas-Vindas"):
        mensagem = discord.ui.TextInput(
            label="Mensagem da DM",
            placeholder="Olá, {user}! Você foi convidado por {inviter}. Total: {count}",
            style=discord.TextStyle.paragraph,
            max_length=1000,
        )

        async def on_submit(self, interaction: discord.Interaction):
            try:
                store.conn.execute(
                    "UPDATE invite_config SET dm_message=? WHERE guild_id=?",
                    (str(self.mensagem), interaction.guild_id),
                )
                store.conn.commit()
                await interaction.response.send_message(
                    embed=red_embed(
                        f"╭ {EM_INV['sucesso']}・𝐌𝐄𝐍𝐒𝐀𝐆𝐄𝐌 𝐒𝐀𝐋𝐕𝐀 ╮",
                        f"{EM_INV['sucesso']} Mensagem da DM atualizada com sucesso!",
                    ),
                    ephemeral=True,
                )
            except Exception as exc:
                await interaction.response.send_message(
                    f"{EM_INV['erro']} Erro ao salvar: {exc}", ephemeral=True
                )

    # ── Canal Select ─────────────────────────────────────────────────────────

    class InviteLogChannelSelect(discord.ui.ChannelSelect):
        def __init__(self):
            super().__init__(
                placeholder="Selecionar canal de log de entradas",
                channel_types=[discord.ChannelType.text],
                min_values=1,
                max_values=1,
            )

        async def callback(self, interaction: discord.Interaction):
            try:
                channel = self.values[0]
                store.conn.execute(
                    "UPDATE invite_config SET log_channel_id=? WHERE guild_id=?",
                    (channel.id, interaction.guild_id),
                )
                store.conn.commit()
                await interaction.response.send_message(
                    embed=red_embed(
                        f"╭ {EM_INV['sucesso']}・𝐂𝐀𝐍𝐀𝐋 𝐃𝐄𝐅𝐈𝐍𝐈𝐃𝐎 ╮",
                        f"{EM_INV['sucesso']} Canal de log: {channel.mention}",
                    ),
                    ephemeral=True,
                )
            except Exception as exc:
                await interaction.response.send_message(
                    f"{EM_INV['erro']} Erro: {exc}", ephemeral=True
                )

    class InviteLogChannelView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.add_item(InviteLogChannelSelect())

    # ── Painel Principal ─────────────────────────────────────────────────────

    class InviteConfigView(discord.ui.View):
        def __init__(self, guild_id: int):
            super().__init__(timeout=180)
            self.guild_id = guild_id

        @discord.ui.button(
            label="Configurar Canal",
            emoji="<:config:1516913563531215009>",
            style=discord.ButtonStyle.secondary,
        )
        async def config_canal(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not owner_only(interaction.user):
                await deny_owner(interaction)
                return
            await interaction.response.send_message(
                embed=red_embed(
                    f"╭ {EM_INV['config']}・𝐒𝐄𝐋𝐄𝐂𝐈𝐎𝐍𝐀𝐑 𝐂𝐀𝐍𝐀𝐋 ╮",
                    f"{EM_INV['aviso']} Selecione o canal onde serão enviadas as mensagens de entrada.",
                ),
                view=InviteLogChannelView(),
                ephemeral=True,
            )

        @discord.ui.button(
            label="Configurar DM",
            emoji="<:adicionar:1516913558238265563>",
            style=discord.ButtonStyle.secondary,
        )
        async def config_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not owner_only(interaction.user):
                await deny_owner(interaction)
                return
            await interaction.response.send_modal(InviteDmModal())

    # ── Comandos Slash ───────────────────────────────────────────────────────

    try:
        bot.tree.remove_command("invite_config")
    except Exception:
        pass

    @bot.tree.command(name="invite_config", description="Painel de configuração do sistema de invites")
    async def invite_config_cmd(interaction: discord.Interaction):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        try:
            get_invite_config(interaction.guild_id)
            await interaction.response.send_message(
                embed=invite_config_embed(interaction.guild_id),
                view=InviteConfigView(interaction.guild_id),
                ephemeral=True,
            )
        except Exception as exc:
            await interaction.response.send_message(
                f"{EM_INV['erro']} Erro ao abrir painel: {exc}", ephemeral=True
            )

    try:
        bot.tree.remove_command("invites")
    except Exception:
        pass

    @bot.tree.command(name="invites", description="Ver total de convites de um usuário")
    async def invites_cmd(interaction: discord.Interaction, usuario: discord.Member):
        if not owner_only(interaction.user):
            await deny_owner(interaction)
            return
        try:
            total = get_invite_count(interaction.guild_id, usuario.id)
            embed = discord.Embed(
                title=f"╭ {EM_INV['ranking']}・𝐂𝐎𝐍𝐕𝐈𝐓𝐄𝐒 ╮",
                description=(
                    f"{EM_INV['perfil']} **Usuário:** {usuario.mention}\n"
                    f"{EM_INV['ranking']} **Total de convites:** **{total}**"
                ),
                color=discord.Color(0x2B2D31),
            )
            embed.set_thumbnail(url=usuario.display_avatar.url)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as exc:
            await interaction.response.send_message(
                f"{EM_INV['erro']} Erro: {exc}", ephemeral=True
            )

    # ── Eventos via add_listener (evita sobrescrever on_ready e on_member_join do main.py) ──

    async def invite_on_ready():
        for guild in bot.guilds:
            try:
                invs = await guild.invites()
                invite_cache[guild.id] = {inv.code: inv.uses for inv in invs}
            except discord.HTTPException:
                invite_cache[guild.id] = {}

    async def invite_on_member_join(member: discord.Member):
        guild = member.guild
        inviter: Optional[discord.Member] = None
        used_code: Optional[str] = None

        try:
            new_invites = await guild.invites()
            old_cache = invite_cache.get(guild.id, {})
            for inv in new_invites:
                old_uses = old_cache.get(inv.code, 0)
                if inv.uses > old_uses:
                    inviter_user = inv.inviter
                    if inviter_user:
                        inviter = guild.get_member(inviter_user.id)
                    used_code = inv.code
                    break
            invite_cache[guild.id] = {inv.code: inv.uses for inv in new_invites}
        except discord.HTTPException:
            pass

        if inviter:
            try:
                store.conn.execute(
                    "INSERT INTO invite_tracking (guild_id, inviter_id, invited_id, invite_code) VALUES (?, ?, ?, ?)",
                    (guild.id, inviter.id, member.id, used_code),
                )
                store.conn.commit()
            except Exception:
                pass

            total = get_invite_count(guild.id, inviter.id)

            # Log no canal configurado
            try:
                cfg = get_invite_config(guild.id)
                log_channel_id = cfg.get("log_channel_id")
                if log_channel_id:
                    log_channel = guild.get_channel(log_channel_id)
                    if log_channel:
                        embed = discord.Embed(
                            title=f"╭ {EM_INV['presente']}・𝐄𝐍𝐓𝐑𝐀𝐃𝐀 ╮",
                            description=(
                                f"{EM_INV['perfil']} {member.mention} foi convidado por {inviter.mention}\n"
                                f"{EM_INV['ranking']} Total de convites de {inviter.mention}: **{total}**"
                            ),
                            color=discord.Color(0x2B2D31),
                        )
                        embed.set_thumbnail(url=member.display_avatar.url)
                        await log_channel.send(embed=embed)
            except Exception:
                pass

            # DM para quem entrou
            try:
                cfg = get_invite_config(guild.id)
                dm_template = cfg.get("dm_message") or ""
                if not dm_template:
                    dm_template = (
                        f"╭ {EM_INV['sucesso']}・𝐁𝐄𝐌-𝐕𝐈𝐍𝐃𝐎! ╮\n\n"
                        f"Olá, {{user}}!\n"
                        f"Você foi convidado(a) por {{inviter}} e agora faz parte do nosso servidor!\n\n"
                        f"{EM_INV['presente']} Esperamos que aproveite tudo!\n"
                        f"{EM_INV['staff']} Nossa equipe está aqui para te ajudar.\n"
                        f"{EM_INV['suporte']} Qualquer dúvida, abra um ticket!"
                    )
                mensagem_dm = dm_template.format(
                    user=member.display_name,
                    inviter=inviter.display_name,
                    count=total,
                )
                await member.send(mensagem_dm)
            except Exception:
                pass

    # Registrar via add_listener para não sobrescrever os eventos do main.py
    bot.add_listener(invite_on_ready, "on_ready")
    bot.add_listener(invite_on_member_join, "on_member_join")
