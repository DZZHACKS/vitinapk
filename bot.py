import discord
from discord.ui import Button, View, Modal, TextInput, Select
from discord.ext import commands, tasks
import sqlite3
from datetime import datetime, timedelta
import random
import string
from flask import Flask, jsonify, request
from flask_cors import CORS
import threading

# Initialize intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Required for role management
bot = commands.Bot(command_prefix="!", intents=intents)

# SQLite database
db = sqlite3.connect("keys.db", check_same_thread=False)
cursor = db.cursor()

# Create tables
cursor.execute('''CREATE TABLE IF NOT EXISTS keys (
    key TEXT PRIMARY KEY,
    user_id TEXT,
    expiration TEXT,
    status TEXT,
    registration_date TEXT,
    android_uid TEXT
)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS banned_users (
    user_id TEXT PRIMARY KEY
)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS maintenance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    active BOOLEAN NOT NULL,
    end_time TEXT,
    last_updated TEXT
)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS user_languages (
    user_id TEXT PRIMARY KEY,
    language TEXT NOT NULL
)''')
db.commit()

# Initialize maintenance state
cursor.execute("SELECT * FROM maintenance WHERE id = 1")
if not cursor.fetchone():
    cursor.execute("INSERT INTO maintenance (id, active, end_time, last_updated) VALUES (?, ?, ?, ?)",
                   (1, False, None, datetime.now().isoformat()))
    db.commit()

# Language dictionary
LANGUAGES = {
    "en": {
        "admin_controls_title": "Admin Controls",
        "admin_controls_desc": "Manage VIP keys, users, and maintenance with the buttons below.",
        "support_tickets_title": "Support Tickets",
        "support_tickets_desc": "Open a ticket to report a bug or request payment information.",
        "report_bug_label": "Report a Bug",
        "request_payment_label": "Request Payment Info",
        "close_ticket_label": "Close Ticket",
        "add_key_label": "Add Key",
        "check_key_label": "Check Key",
        "extend_key_label": "Extend Key",
        "delete_key_label": "Delete Key",
        "list_keys_label": "List Keys",
        "revoke_key_label": "Revoke Key",
        "ban_user_label": "Ban User",
        "maintenance_label": "Maintenance",
        "key_added": "Key sent to <@{}>!",
        "key_not_found": "Key not found.",
        "maintenance_enabled": "Maintenance mode enabled until {}.",
        "server_maintenance": "Server under maintenance",
        "invalid_key": "Invalid key",
        "footer": "Powered by VITINAPK",
        "language_set": "Your language has been set to English!",
        "select_language": "Select Language",
        "language_option_en": "English",
        "language_option_ptbr": "Portuguese (Brazilian)",
        "only_admins": "Only admins can use this!",
        "duration_error": "Duration must be an integer!",
        "user_banned": "This user is banned and cannot receive a key!",
        "ticket_created": "Your ticket has been created: {channel}",
        "ticket_description_bug": "Please describe the issue in detail.",
        "ticket_description_payment": "Please specify your payment method and plan.",
        "ticket_closed": "Ticket closed by {user}.",
        "invalid_user": "Invalid user ID provided!"
    },
    "pt-BR": {
        "admin_controls_title": "Controles de Admin",
        "admin_controls_desc": "Gerencie chaves VIP, usuários e manutenção com os botões abaixo.",
        "support_tickets_title": "Tickets de Suporte",
        "support_tickets_desc": "Abra um ticket para relatar um bug ou solicitar informações de pagamento.",
        "report_bug_label": "Relatar um Bug",
        "request_payment_label": "Solicitar Info de Pagamento",
        "close_ticket_label": "Fechar Ticket",
        "add_key_label": "Adicionar Chave",
        "check_key_label": "Verificar Chave",
        "extend_key_label": "Estender Chave",
        "delete_key_label": "Deletar Chave",
        "list_keys_label": "Listar Chaves",
        "revoke_key_label": "Revogar Chave",
        "ban_user_label": "Banir Usuário",
        "maintenance_label": "Manutenção",
        "key_added": "Chave enviada para <@{}>!",
        "key_not_found": "Chave não encontrada.",
        "maintenance_enabled": "Modo de manutenção ativado até {}.",
        "server_maintenance": "Servidor em manutenção",
        "invalid_key": "Chave inválida",
        "footer": "Desenvolvido por VITINAPK",
        "language_set": "Sua linguagem foi definida como Português (Brasileiro)!",
        "select_language": "Selecionar Idioma",
        "language_option_en": "Inglês",
        "language_option_ptbr": "Português (Brasileiro)",
        "only_admins": "Apenas administradores podem usar isso!",
        "duration_error": "A duração deve ser um número inteiro!",
        "user_banned": "Este usuário está banido e não pode receber uma chave!",
        "ticket_created": "Seu ticket foi criado: {channel}",
        "ticket_description_bug": "Por favor, descreva o problema em detalhes.",
        "ticket_description_payment": "Por favor, especifique seu método de pagamento e plano.",
        "ticket_closed": "Ticket fechado por {user}.",
        "invalid_user": "ID de usuário inválido fornecido!"
    }
}

DEFAULT_LANGUAGE = "en"

def get_user_language(user_id):
    cursor.execute("SELECT language FROM user_languages WHERE user_id = ?", (str(user_id),))
    row = cursor.fetchone()
    return row[0] if row else DEFAULT_LANGUAGE

def set_user_language(user_id, language):
    cursor.execute("INSERT OR REPLACE INTO user_languages (user_id, language) VALUES (?, ?)",
                   (str(user_id), language))
    db.commit()

def get_text(key, user_id=None, lang=None, **kwargs):
    if lang is None and user_id is not None:
        lang = get_user_language(user_id)
    text = LANGUAGES.get(lang, LANGUAGES[DEFAULT_LANGUAGE]).get(key, key)
    return text.format(**kwargs) if kwargs else text

# Admin role, Guild, and VIP role IDs
ADMIN_ROLE_ID = "1352747825372467331"
GUILD_ID = "1352747474481188937"
VIP_ROLE_ID = "1352808904224018533"

# Flask application
app = Flask(__name__)
CORS(app)

def is_maintenance_active():
    cursor.execute("SELECT active, end_time FROM maintenance WHERE id = 1")
    row = cursor.fetchone()
    if not row or not row[0] or not row[1]:
        return False
    return datetime.now() < datetime.fromisoformat(row[1])

@app.route('/check_maintenance', methods=['GET'])
def check_maintenance():
    cursor.execute("SELECT active, end_time FROM maintenance WHERE id = 1")
    row = cursor.fetchone()
    if not row or not row[0] or not row[1]:
        return jsonify({"active": False, "end_time": None}), 200
    end_time_dt = datetime.fromisoformat(row[1])
    if datetime.now() > end_time_dt:
        cursor.execute("UPDATE maintenance SET active = ?, end_time = ? WHERE id = ?", (False, None, 1))
        db.commit()
        return jsonify({"active": False, "end_time": None}), 200
    return jsonify({"active": True, "end_time": row[1]}), 200

@app.route('/check_key', methods=['GET'])
def check_key():
    if is_maintenance_active():
        return jsonify({"error": get_text("server_maintenance", lang=DEFAULT_LANGUAGE)}), 503
    key = request.args.get('key')
    cursor.execute("SELECT * FROM keys WHERE key = ?", (key,))
    row = cursor.fetchone()
    if row:
        return jsonify({"key": row[0], "user_id": row[1], "expiration": row[2], "status": row[3], "registration_date": row[4]})
    return jsonify({"error": get_text("invalid_key", lang=DEFAULT_LANGUAGE)}), 404

@app.route('/check_uid', methods=['GET'])
def check_uid():
    if is_maintenance_active():
        return jsonify({"error": get_text("server_maintenance", lang=DEFAULT_LANGUAGE)}), 503
    key = request.args.get('key')
    android_uid = request.args.get('android_uid')
    if not key or not android_uid:
        return jsonify({"error": "Invalid request"}), 400
    cursor.execute("SELECT android_uid FROM keys WHERE key = ?", (key,))
    row = cursor.fetchone()
    if not row:
        return jsonify({"error": get_text("invalid_key", lang=DEFAULT_LANGUAGE)}), 404
    if row[0]:
        if row[0] != android_uid:
            return jsonify({"error": "Key already in use"}), 403
        return jsonify({"exists": True}), 200
    return jsonify({"exists": False}), 200

@app.route('/register_uid', methods=['GET', 'POST'])
def register_uid():
    if is_maintenance_active():
        return jsonify({"error": get_text("server_maintenance", lang=DEFAULT_LANGUAGE)}), 503
    try:
        data = request.get_json() if request.method == 'POST' else request.args
        key, discord_id, android_uid = data.get('key'), data.get('discord_id'), data.get('android_uid')
        if not all([key, discord_id, android_uid]):
            return jsonify({"error": "Invalid request"}), 400
        cursor.execute("SELECT * FROM banned_users WHERE user_id = ?", (discord_id,))
        if cursor.fetchone():
            return jsonify({"error": "Access denied"}), 403
        cursor.execute("SELECT user_id FROM keys WHERE key = ?", (key,))
        if not cursor.fetchone():
            return jsonify({"error": get_text("invalid_key", lang=DEFAULT_LANGUAGE)}), 404
        cursor.execute("UPDATE keys SET android_uid = ?, user_id = ? WHERE key = ?", (android_uid, discord_id, key))
        db.commit()
        log_channel = discord.utils.get(bot.get_guild(int(GUILD_ID)).channels, name="logs")
        if log_channel:
            ip = request.remote_addr
            bot.loop.create_task(log_channel.send(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] User {discord_id} registered UID with key {key} | IP: {ip}"))
        guild = bot.get_guild(int(GUILD_ID))
        member = guild.get_member(int(discord_id))
        if member:
            vip_role = guild.get_role(int(VIP_ROLE_ID))
            if vip_role and vip_role not in member.roles:
                bot.loop.create_task(member.add_roles(vip_role))
                if log_channel:
                    bot.loop.create_task(log_channel.send(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] VIP role added to user {discord_id} | IP: {ip}"))
        return jsonify({"success": "UID registered"}), 200
    except Exception as e:
        return jsonify({"error": "Server error"}), 500

@app.route('/log_usage', methods=['GET', 'POST'])
def log_usage():
    if is_maintenance_active():
        return jsonify({"error": get_text("server_maintenance", lang=DEFAULT_LANGUAGE)}), 503
    try:
        data = request.get_json() if request.method == 'POST' else request.args
        key, action = data.get('key'), data.get('action')
        if not key or not action:
            return jsonify({"error": "Invalid request"}), 400
        cursor.execute("SELECT user_id FROM keys WHERE key = ?", (key,))
        discord_id = cursor.fetchone()[0] if cursor.fetchone() else "Unknown"
        log_channel = discord.utils.get(bot.get_guild(int(GUILD_ID)).channels, name="logs")
        if log_channel:
            ip = request.remote_addr
            bot.loop.create_task(log_channel.send(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Key `{key}` used action: {action} | Discord ID: {discord_id} | IP: {ip}"))
        return jsonify({"success": "Logged"}), 200
    except Exception:
        return jsonify({"error": "Server error"}), 500

@app.route('/script_execution', methods=['GET', 'POST'])
def script_execution():
    if is_maintenance_active():
        return jsonify({"error": get_text("server_maintenance", lang=DEFAULT_LANGUAGE)}), 503
    try:
        data = request.get_json() if request.method == 'POST' else request.args
        key = data.get('key')
        if not key:
            return jsonify({"error": "Invalid request"}), 400
        cursor.execute("SELECT user_id FROM keys WHERE key = ?", (key,))
        discord_id = cursor.fetchone()[0] if cursor.fetchone() else "Unknown"
        log_channel = discord.utils.get(bot.get_guild(int(GUILD_ID)).channels, name="logs")
        if log_channel:
            ip = request.remote_addr
            bot.loop.create_task(log_channel.send(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Script executed with key `{key}` | Discord ID: {discord_id} | IP: {ip}"))
        return jsonify({"success": "Execution logged"}), 200
    except Exception:
        return jsonify({"error": "Server error"}), 500

def generate_unique_key():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def is_admin(user):
    return any(role.id == int(ADMIN_ROLE_ID) for role in user.roles)

class TicketActionsView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        lang = get_user_language(interaction.user.id)
        button.label = get_text("close_ticket_label", interaction.user.id)
        if not is_admin(interaction.user):
            await interaction.response.send_message(get_text("only_admins", interaction.user.id), ephemeral=True)
            return
        channel = interaction.channel
        await channel.send(get_text("ticket_closed", interaction.user.id, user=interaction.user.mention))
        log_channel = discord.utils.get(interaction.guild.channels, name="logs")
        if log_channel:
            await log_channel.send(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Ticket {channel.name} closed by {interaction.user.mention}")
        await channel.delete()

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.report_bug_button = Button(label=get_text("report_bug_label", lang=DEFAULT_LANGUAGE), style=discord.ButtonStyle.red, custom_id="report_bug")
        self.request_payment_button = Button(label=get_text("request_payment_label", lang=DEFAULT_LANGUAGE), style=discord.ButtonStyle.green, custom_id="request_payment")
        self.language_select = Select(
            placeholder=get_text("select_language", lang=DEFAULT_LANGUAGE),
            options=[
                discord.SelectOption(label=get_text("language_option_en", lang=DEFAULT_LANGUAGE), value="en", emoji="🇬🇧"),
                discord.SelectOption(label=get_text("language_option_ptbr", lang=DEFAULT_LANGUAGE), value="pt-BR", emoji="🇧🇷")
            ],
            custom_id="ticket_language_select"
        )
        self.add_item(self.report_bug_button)
        self.add_item(self.request_payment_button)
        self.add_item(self.language_select)
        self.report_bug_button.callback = self.report_bug
        self.request_payment_button.callback = self.request_payment
        self.language_select.callback = self.language_select_callback

    async def update_message(self, interaction: discord.Interaction):
        lang = get_user_language(interaction.user.id)
        self.report_bug_button.label = get_text("report_bug_label", interaction.user.id)
        self.request_payment_button.label = get_text("request_payment_label", interaction.user.id)
        self.language_select.placeholder = get_text("select_language", interaction.user.id)
        for option in self.language_select.options:
            option.label = get_text(f"language_option_{option.value}", interaction.user.id)
        embed = discord.Embed(
            title=get_text("support_tickets_title", interaction.user.id),
            description=get_text("support_tickets_desc", interaction.user.id),
            color=discord.Color.red()
        )
        embed.set_footer(text=get_text("footer", interaction.user.id))
        await interaction.message.edit(embed=embed, view=self)

    async def report_bug(self, interaction: discord.Interaction):
        await self.update_message(interaction)
        guild = interaction.guild
        user = interaction.user
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(int(ADMIN_ROLE_ID)): discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        ticket_channel = await guild.create_text_channel(
            f"bug-{user.name}",
            overwrites=overwrites,
            topic=get_text("support_tickets_desc", user.id),
            category=discord.utils.get(guild.categories, name="Tickets")
        )
        await ticket_channel.send(
            f"{get_text('support_tickets_title', user.id)} created by {user.mention}. {get_text('ticket_description_bug', user.id)}",
            view=TicketActionsView()
        )
        await interaction.response.send_message(
            get_text("ticket_created", user.id, channel=ticket_channel.mention),
            ephemeral=True
        )

    async def request_payment(self, interaction: discord.Interaction):
        await self.update_message(interaction)
        guild = interaction.guild
        user = interaction.user
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(int(ADMIN_ROLE_ID)): discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        ticket_channel = await guild.create_text_channel(
            f"payment-{user.name}",
            overwrites=overwrites,
            topic=get_text("support_tickets_desc", user.id),
            category=discord.utils.get(guild.categories, name="Tickets")
        )
        await ticket_channel.send(
            f"{get_text('support_tickets_title', user.id)} created by {user.mention}. {get_text('ticket_description_payment', user.id)}",
            view=TicketActionsView()
        )
        await interaction.response.send_message(
            get_text("ticket_created", user.id, channel=ticket_channel.mention),
            ephemeral=True
        )

    async def language_select_callback(self, interaction: discord.Interaction):
        lang = interaction.data['values'][0]
        set_user_language(interaction.user.id, lang)
        await self.update_message(interaction)
        await interaction.response.send_message(get_text("language_set", interaction.user.id), ephemeral=True)

class AdminView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_key_button = Button(label=get_text("add_key_label", lang=DEFAULT_LANGUAGE), style=discord.ButtonStyle.green, custom_id="add_key")
        self.check_key_button = Button(label=get_text("check_key_label", lang=DEFAULT_LANGUAGE), style=discord.ButtonStyle.blurple, custom_id="check_key")
        self.extend_key_button = Button(label=get_text("extend_key_label", lang=DEFAULT_LANGUAGE), style=discord.ButtonStyle.blurple, custom_id="extend_key")
        self.delete_key_button = Button(label=get_text("delete_key_label", lang=DEFAULT_LANGUAGE), style=discord.ButtonStyle.red, custom_id="delete_key")
        self.list_keys_button = Button(label=get_text("list_keys_label", lang=DEFAULT_LANGUAGE), style=discord.ButtonStyle.blurple, custom_id="list_keys")
        self.revoke_key_button = Button(label=get_text("revoke_key_label", lang=DEFAULT_LANGUAGE), style=discord.ButtonStyle.red, custom_id="revoke_key")
        self.ban_user_button = Button(label=get_text("ban_user_label", lang=DEFAULT_LANGUAGE), style=discord.ButtonStyle.red, custom_id="ban_user")
        self.maintenance_button = Button(label=get_text("maintenance_label", lang=DEFAULT_LANGUAGE), style=discord.ButtonStyle.grey, custom_id="maintenance")
        self.language_select = Select(
            placeholder=get_text("select_language", lang=DEFAULT_LANGUAGE),
            options=[
                discord.SelectOption(label=get_text("language_option_en", lang=DEFAULT_LANGUAGE), value="en", emoji="🇬🇧"),
                discord.SelectOption(label=get_text("language_option_ptbr", lang=DEFAULT_LANGUAGE), value="pt-BR", emoji="🇧🇷")
            ],
            custom_id="admin_language_select_v1"
        )
        self.add_item(self.add_key_button)
        self.add_item(self.check_key_button)
        self.add_item(self.extend_key_button)
        self.add_item(self.delete_key_button)
        self.add_item(self.list_keys_button)
        self.add_item(self.revoke_key_button)
        self.add_item(self.ban_user_button)
        self.add_item(self.maintenance_button)
        self.add_item(self.language_select)
        self.add_key_button.callback = self.add_key
        self.check_key_button.callback = self.check_key
        self.extend_key_button.callback = self.extend_key
        self.delete_key_button.callback = self.delete_key
        self.list_keys_button.callback = self.list_keys
        self.revoke_key_button.callback = self.revoke_key
        self.ban_user_button.callback = self.ban_user
        self.maintenance_button.callback = self.maintenance
        self.language_select.callback = self.language_select_callback

    async def update_message(self, interaction: discord.Interaction):
        lang = get_user_language(interaction.user.id)
        self.add_key_button.label = get_text("add_key_label", interaction.user.id)
        self.check_key_button.label = get_text("check_key_label", interaction.user.id)
        self.extend_key_button.label = get_text("extend_key_label", interaction.user.id)
        self.delete_key_button.label = get_text("delete_key_label", interaction.user.id)
        self.list_keys_button.label = get_text("list_keys_label", interaction.user.id)
        self.revoke_key_button.label = get_text("revoke_key_label", interaction.user.id)
        self.ban_user_button.label = get_text("ban_user_label", interaction.user.id)
        self.maintenance_button.label = get_text("maintenance_label", interaction.user.id)
        self.language_select.placeholder = get_text("select_language", interaction.user.id)
        for option in self.language_select.options:
            option.label = get_text(f"language_option_{option.value}", interaction.user.id)
        embed = discord.Embed(
            title=get_text("admin_controls_title", interaction.user.id),
            description=get_text("admin_controls_desc", interaction.user.id),
            color=discord.Color.red()
        )
        embed.set_footer(text=get_text("footer", interaction.user.id))
        await interaction.message.edit(embed=embed, view=self)

    async def add_key(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message(get_text("only_admins", interaction.user.id), ephemeral=True)
            return
        await self.update_message(interaction)
        await interaction.response.send_modal(AddKeyModal(interaction.user.id))

    async def check_key(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message(get_text("only_admins", interaction.user.id), ephemeral=True)
            return
        await self.update_message(interaction)
        await interaction.response.send_modal(CheckKeyModal(interaction.user.id))

    async def extend_key(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message(get_text("only_admins", interaction.user.id), ephemeral=True)
            return
        await self.update_message(interaction)
        await interaction.response.send_modal(ExtendKeyModal(interaction.user.id))

    async def delete_key(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message(get_text("only_admins", interaction.user.id), ephemeral=True)
            return
        await self.update_message(interaction)
        await interaction.response.send_modal(DeleteKeyModal(interaction.user.id))

    async def list_keys(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message(get_text("only_admins", interaction.user.id), ephemeral=True)
            return
        await self.update_message(interaction)
        cursor.execute("SELECT * FROM keys WHERE status = 'active'")
        keys = cursor.fetchall()
        if keys:
            keys_list = "\n".join([f"Key: `{k[0]}` | User: <@{k[1]}> | Registered: {k[4].split('T')[0]} | Expires: {k[2].split('T')[0]}" for k in keys])
            await interaction.response.send_message(f"**Active Keys:**\n{keys_list}", ephemeral=True)
        else:
            await interaction.response.send_message(get_text("key_not_found", interaction.user.id), ephemeral=True)

    async def revoke_key(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message(get_text("only_admins", interaction.user.id), ephemeral=True)
            return
        await self.update_message(interaction)
        await interaction.response.send_modal(RevokeKeyModal(interaction.user.id))

    async def ban_user(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message(get_text("only_admins", interaction.user.id), ephemeral=True)
            return
        await self.update_message(interaction)
        await interaction.response.send_modal(BanUserModal(interaction.user.id))

    async def maintenance(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message(get_text("only_admins", interaction.user.id), ephemeral=True)
            return
        await self.update_message(interaction)
        await interaction.response.send_modal(MaintenanceModal(interaction.user.id))

    async def language_select_callback(self, interaction: discord.Interaction):
        lang = interaction.data['values'][0]
        set_user_language(interaction.user.id, lang)
        await self.update_message(interaction)
        await interaction.response.send_message(get_text("language_set", interaction.user.id), ephemeral=True)

class AddKeyModal(Modal):
    def __init__(self, user_id):
        lang = get_user_language(user_id)
        super().__init__(title="Add a VIP Key" if lang == "en" else "Adicionar uma Chave VIP")
        self.user_id = user_id
        self.duration = TextInput(label="Duration (days)" if lang == "en" else "Duração (dias)", placeholder="e.g., 7")
        self.user_id_input = TextInput(label="User ID" if lang == "en" else "ID do Usuário", placeholder="e.g., 123456789")
        self.add_item(self.duration)
        self.add_item(self.user_id_input)

    async def on_submit(self, interaction: discord.Interaction):
        lang = get_user_language(self.user_id)
        try:
            duration_days = int(self.duration.value)
            user_id = self.user_id_input.value
            cursor.execute("SELECT * FROM banned_users WHERE user_id = ?", (user_id,))
            if cursor.fetchone():
                await interaction.response.send_message(get_text("user_banned", self.user_id), ephemeral=True)
                return
            key = generate_unique_key()
            expiration = datetime.now() + timedelta(days=duration_days)
            registration_date = datetime.now().isoformat()
            cursor.execute("INSERT INTO keys (key, user_id, expiration, status, registration_date, android_uid) VALUES (?, ?, ?, ?, ?, ?)",
                           (key, user_id, expiration.isoformat(), "active", registration_date, None))
            db.commit()
            try:
                user = await bot.fetch_user(int(user_id))
                await user.send(f"Your VIP Key: `{key}`\nExpires on: {expiration.strftime('%Y-%m-%d')}" if lang == "en" else f"Sua Chave VIP: `{key}`\nExpira em: {expiration.strftime('%Y-%m-%d')}")
                await interaction.response.send_message(get_text("key_added", user_id=self.user_id).format(user_id), ephemeral=True)
            except discord.errors.NotFound:
                await interaction.response.send_message(get_text("invalid_user", self.user_id), ephemeral=True)
                return
            keys_channel = discord.utils.get(interaction.guild.channels, name="keys")
            if keys_channel:
                await keys_channel.send(f"Key: `{key}`\nUser: {user.name} (<@{user_id}>)\nRegistered: {registration_date.split('T')[0]}\nExpires: {expiration.strftime('%Y-%m-%d')}")
        except ValueError:
            await interaction.response.send_message(get_text("duration_error", self.user_id), ephemeral=True)

class CheckKeyModal(Modal):
    def __init__(self, user_id):
        lang = get_user_language(user_id)
        super().__init__(title="Check a VIP Key" if lang == "en" else "Verificar uma Chave VIP")
        self.user_id = user_id
        self.key = TextInput(label="Key" if lang == "en" else "Chave", placeholder="e.g., ABC123")
        self.add_item(self.key)

    async def on_submit(self, interaction: discord.Interaction):
        lang = get_user_language(self.user_id)
        cursor.execute("SELECT * FROM keys WHERE key = ?", (self.key.value,))
        row = cursor.fetchone()
        if row:
            user_id, expiration, status, registration_date = row[1], row[2], row[3], row[4]
            await interaction.response.send_message(
                f"Key: `{self.key.value}`\nUser: <@{user_id}>\nRegistered: {registration_date.split('T')[0]}\nExpiration: {expiration.split('T')[0]}\nStatus: {status}" if lang == "en" else
                f"Chave: `{self.key.value}`\nUsuário: <@{user_id}>\nRegistrada: {registration_date.split('T')[0]}\nExpiração: {expiration.split('T')[0]}\nStatus: {status}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(get_text("key_not_found", self.user_id), ephemeral=True)

class ExtendKeyModal(Modal):
    def __init__(self, user_id):
        lang = get_user_language(user_id)
        super().__init__(title="Extend a VIP Key" if lang == "en" else "Estender uma Chave VIP")
        self.user_id = user_id
        self.key = TextInput(label="Key" if lang == "en" else "Chave", placeholder="e.g., ABC123")
        self.duration = TextInput(label="Additional Days" if lang == "en" else "Dias Adicionais", placeholder="e.g., 7")
        self.add_item(self.key)
        self.add_item(self.duration)

    async def on_submit(self, interaction: discord.Interaction):
        lang = get_user_language(self.user_id)
        try:
            extra_days = int(self.duration.value)
            cursor.execute("SELECT * FROM keys WHERE key = ?", (self.key.value,))
            row = cursor.fetchone()
            if row:
                current_expiration = datetime.fromisoformat(row[2])
                new_expiration = current_expiration + timedelta(days=extra_days)
                cursor.execute("UPDATE keys SET expiration = ? WHERE key = ?", (new_expiration.isoformat(), self.key.value))
                db.commit()
                await interaction.response.send_message(f"Key `{self.key.value}` extended until {new_expiration.strftime('%Y-%m-%d')}" if lang == "en" else f"Chave `{self.key.value}` estendida até {new_expiration.strftime('%Y-%m-%d')}", ephemeral=True)
                keys_channel = discord.utils.get(interaction.guild.channels, name="keys")
                if keys_channel:
                    await keys_channel.send(f"Key `{self.key.value}` extended until {new_expiration.strftime('%Y-%m-%d')}" if lang == "en" else f"Chave `{self.key.value}` estendida até {new_expiration.strftime('%Y-%m-%d')}")
            else:
                await interaction.response.send_message(get_text("key_not_found", self.user_id), ephemeral=True)
        except ValueError:
            await interaction.response.send_message(get_text("duration_error", self.user_id), ephemeral=True)

class DeleteKeyModal(Modal):
    def __init__(self, user_id):
        lang = get_user_language(user_id)
        super().__init__(title="Delete a VIP Key" if lang == "en" else "Deletar uma Chave VIP")
        self.user_id = user_id
        self.key = TextInput(label="Key" if lang == "en" else "Chave", placeholder="e.g., ABC123")
        self.add_item(self.key)

    async def on_submit(self, interaction: discord.Interaction):
        lang = get_user_language(self.user_id)
        cursor.execute("SELECT user_id FROM keys WHERE key = ?", (self.key.value,))
        row = cursor.fetchone()
        if row:
            user_id = row[0]
            cursor.execute("DELETE FROM keys WHERE key = ?", (self.key.value,))
            db.commit()
            await interaction.response.send_message(f"Key `{self.key.value}` deleted." if lang == "en" else f"Chave `{self.key.value}` deletada.", ephemeral=True)
            keys_channel = discord.utils.get(interaction.guild.channels, name="keys")
            if keys_channel:
                await keys_channel.send(f"Key `{self.key.value}` deleted." if lang == "en" else f"Chave `{self.key.value}` deletada.")
            guild = interaction.guild
            member = guild.get_member(int(user_id))
            if member:
                vip_role = guild.get_role(int(VIP_ROLE_ID))
                if vip_role and vip_role in member.roles:
                    await member.remove_roles(vip_role)
                    log_channel = discord.utils.get(guild.channels, name="logs")
                    if log_channel:
                        await log_channel.send(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] VIP role removed from user {user_id} due to key deletion")
        else:
            await interaction.response.send_message(get_text("key_not_found", self.user_id), ephemeral=True)

class RevokeKeyModal(Modal):
    def __init__(self, user_id):
        lang = get_user_language(user_id)
        super().__init__(title="Revoke a VIP Key" if lang == "en" else "Revogar uma Chave VIP")
        self.user_id = user_id
        self.key = TextInput(label="Key" if lang == "en" else "Chave", placeholder="e.g., ABC123")
        self.add_item(self.key)

    async def on_submit(self, interaction: discord.Interaction):
        lang = get_user_language(self.user_id)
        cursor.execute("SELECT user_id FROM keys WHERE key = ?", (self.key.value,))
        row = cursor.fetchone()
        if row:
            user_id = row[0]
            cursor.execute("UPDATE keys SET status = 'inactive' WHERE key = ?", (self.key.value,))
            db.commit()
            await interaction.response.send_message(f"Key `{self.key.value}` has been revoked." if lang == "en" else f"Chave `{self.key.value}` foi revogada.", ephemeral=True)
            guild = interaction.guild
            member = guild.get_member(int(user_id))
            if member:
                vip_role = guild.get_role(int(VIP_ROLE_ID))
                if vip_role and vip_role in member.roles:
                    await member.remove_roles(vip_role)
                    log_channel = discord.utils.get(guild.channels, name="logs")
                    if log_channel:
                        await log_channel.send(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] VIP role removed from user {user_id} due to key revocation")
        else:
            await interaction.response.send_message(get_text("key_not_found", self.user_id), ephemeral=True)

class BanUserModal(Modal):
    def __init__(self, user_id):
        lang = get_user_language(user_id)
        super().__init__(title="Ban a User" if lang == "en" else "Banir um Usuário")
        self.user_id = user_id
        self.user_id_input = TextInput(label="User ID" if lang == "en" else "ID do Usuário", placeholder="e.g., 123456789")
        self.add_item(self.user_id_input)

    async def on_submit(self, interaction: discord.Interaction):
        lang = get_user_language(self.user_id)
        user_id = self.user_id_input.value
        cursor.execute("INSERT OR IGNORE INTO banned_users (user_id) VALUES (?)", (user_id,))
        cursor.execute("DELETE FROM keys WHERE user_id = ?", (user_id,))
        db.commit()
        await interaction.response.send_message(
            f"User <@{user_id}> has been banned and all their keys have been deleted." if lang == "en" else f"Usuário <@{user_id}> foi banido e todas as suas chaves foram deletadas.",
            ephemeral=True
        )
        guild = interaction.guild
        member = guild.get_member(int(user_id))
        if member:
            vip_role = guild.get_role(int(VIP_ROLE_ID))
            if vip_role and vip_role in member.roles:
                await member.remove_roles(vip_role)
                log_channel = discord.utils.get(guild.channels, name="logs")
                if log_channel:
                    await log_channel.send(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] VIP role removed from user {user_id} due to ban")

class MaintenanceModal(Modal):
    def __init__(self, user_id):
        lang = get_user_language(user_id)
        super().__init__(title="Manage Maintenance Mode" if lang == "en" else "Gerenciar Modo de Manutenção")
        self.user_id = user_id
        self.action = TextInput(label="Action (enable/disable/add_time)" if lang == "en" else "Ação (ativar/desativar/adicionar_tempo)", placeholder="e.g., enable" if lang == "en" else "e.g., ativar")
        self.duration = TextInput(label="Duration (hours, if enabling/adding)" if lang == "en" else "Duração (horas, se ativar/adicionar)", placeholder="e.g., 24", required=False)
        self.add_item(self.action)
        self.add_item(self.duration)

    async def on_submit(self, interaction: discord.Interaction):
        lang = get_user_language(self.user_id)
        action = self.action.value.lower()
        log_channel = discord.utils.get(interaction.guild.channels, name="logs")
        action_map = {"ativar": "enable", "desativar": "disable", "adicionar_tempo": "add_time"}
        action = action_map.get(action, action)
        if action not in ["enable", "disable", "add_time"]:
            await interaction.response.send_message("Invalid action! Use 'enable', 'disable', or 'add_time'." if lang == "en" else "Ação inválida! Use 'ativar', 'desativar' ou 'adicionar_tempo'.", ephemeral=True)
            return
        if action == "disable":
            cursor.execute("UPDATE maintenance SET active = ?, end_time = ?, last_updated = ? WHERE id = ?", (False, None, datetime.now().isoformat(), 1))
            db.commit()
            await interaction.response.send_message("Maintenance mode disabled." if lang == "en" else "Modo de manutenção desativado.", ephemeral=True)
            if log_channel:
                await log_channel.send(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Maintenance mode disabled by {interaction.user.mention}")
            return
        if not self.duration.value:
            await interaction.response.send_message("Duration is required for enabling or adding time!" if lang == "en" else "Duração é necessária para ativar ou adicionar tempo!", ephemeral=True)
            return
        try:
            duration_hours = int(self.duration.value)
            if duration_hours <= 0:
                raise ValueError
            if action == "enable":
                end_time = datetime.now() + timedelta(hours=duration_hours)
                cursor.execute("UPDATE maintenance SET active = ?, end_time = ?, last_updated = ? WHERE id = ?", (True, end_time.isoformat(), datetime.now().isoformat(), 1))
                db.commit()
                await interaction.response.send_message(f"Maintenance mode enabled until {end_time.strftime('%Y-%m-%d %H:%M:%S')}." if lang == "en" else f"Modo de manutenção ativado até {end_time.strftime('%Y-%m-%d %H:%M:%S')}.", ephemeral=True)
                if log_channel:
                    await log_channel.send(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Maintenance mode enabled by {interaction.user.mention} until {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            elif action == "add_time":
                cursor.execute("SELECT active, end_time FROM maintenance WHERE id = 1")
                row = cursor.fetchone()
                if not row or not row[0]:
                    await interaction.response.send_message("Maintenance mode is not active! Enable it first." if lang == "en" else "Modo de manutenção não está ativo! Ative-o primeiro.", ephemeral=True)
                    return
                current_end_time = datetime.fromisoformat(row[1])
                if datetime.now() > current_end_time:
                    await interaction.response.send_message("Maintenance mode has already ended! Enable it again." if lang == "en" else "Modo de manutenção já terminou! Ative-o novamente.", ephemeral=True)
                    return
                new_end_time = current_end_time + timedelta(hours=duration_hours)
                cursor.execute("UPDATE maintenance SET end_time = ?, last_updated = ? WHERE id = ?", (new_end_time.isoformat(), datetime.now().isoformat(), 1))
                db.commit()
                await interaction.response.send_message(f"Maintenance time extended until {new_end_time.strftime('%Y-%m-%d %H:%M:%S')}." if lang == "en" else f"Tempo de manutenção estendido até {new_end_time.strftime('%Y-%m-%d %H:%M:%S')}.", ephemeral=True)
                if log_channel:
                    await log_channel.send(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Maintenance time extended by {interaction.user.mention} until {new_end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        except ValueError:
            await interaction.response.send_message("Duration must be a positive integer (in hours)!" if lang == "en" else "Duração deve ser um número inteiro positivo (em horas)!", ephemeral=True)

@tasks.loop(minutes=60)
async def check_expired_keys():
    cursor.execute("SELECT * FROM keys WHERE status = 'active'")
    keys = cursor.fetchall()
    guild = bot.get_guild(int(GUILD_ID))
    log_channel = discord.utils.get(guild.channels, name="logs")
    for key in keys:
        key_value, user_id, expiration = key[0], key[1], key[2]
        if datetime.now() > datetime.fromisoformat(expiration):
            cursor.execute("UPDATE keys SET status = 'inactive' WHERE key = ?", (key_value,))
            db.commit()
            if log_channel:
                await log_channel.send(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Key `{key_value}` has expired for user {user_id}")
            member = guild.get_member(int(user_id))
            if member:
                vip_role = guild.get_role(int(VIP_ROLE_ID))
                if vip_role and vip_role in member.roles:
                    await member.remove_roles(vip_role)
                    if log_channel:
                        await log_channel.send(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] VIP role removed from user {user_id} due to key expiration")

@tasks.loop(minutes=10)
async def refresh_messages():
    guild = bot.get_guild(int(GUILD_ID))
    if not guild:
        return
    admin_channel = discord.utils.get(guild.channels, name="admin")
    tickets_channel = discord.utils.get(guild.channels, name="tickets")
    if admin_channel:
        async for message in admin_channel.history(limit=10):
            if message.author == bot.user and message.embeds and "Admin Controls" in message.embeds[0].title:
                embed = discord.Embed(title=get_text("admin_controls_title", lang=DEFAULT_LANGUAGE), description=get_text("admin_controls_desc", lang=DEFAULT_LANGUAGE), color=discord.Color.red())
                embed.set_footer(text=get_text("footer", lang=DEFAULT_LANGUAGE))
                await message.edit(embed=embed, view=AdminView())
                break
    if tickets_channel:
        async for message in tickets_channel.history(limit=10):
            if message.author == bot.user and message.embeds and "Support Tickets" in message.embeds[0].title:
                embed = discord.Embed(title=get_text("support_tickets_title", lang=DEFAULT_LANGUAGE), description=get_text("support_tickets_desc", lang=DEFAULT_LANGUAGE), color=discord.Color.red())
                embed.set_footer(text=get_text("footer", lang=DEFAULT_LANGUAGE))
                await message.edit(embed=embed, view=TicketView())
                break

def setup_persistent_views():
    bot.add_view(AdminView())
    bot.add_view(TicketView())
    bot.add_view(TicketActionsView())

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    guild = bot.get_guild(int(GUILD_ID))
    if not guild:
        print("Guild not found! Check GUILD_ID.")
        return
    setup_persistent_views()
    if not refresh_messages.is_running():
        refresh_messages.start()
    if not check_expired_keys.is_running():
        check_expired_keys.start()
    private_overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False), guild.get_role(int(ADMIN_ROLE_ID)): discord.PermissionOverwrite(view_channel=True, send_messages=True)}
    management_category = discord.utils.get(guild.categories, name="VITINAPK Management") or await guild.create_category("VITINAPK Management")
    tickets_category = discord.utils.get(guild.categories, name="Tickets") or await guild.create_category("Tickets")
    admin_channel = discord.utils.get(guild.channels, name="admin") or await guild.create_text_channel("admin", category=management_category, overwrites=private_overwrites)
    admin_message = None
    async for message in admin_channel.history(limit=10):
        if message.author == bot.user and message.embeds and "Admin Controls" in message.embeds[0].title:
            admin_message = message
            break
    admin_embed = discord.Embed(title=get_text("admin_controls_title", lang=DEFAULT_LANGUAGE), description=get_text("admin_controls_desc", lang=DEFAULT_LANGUAGE), color=discord.Color.red())
    admin_embed.set_footer(text=get_text("footer", lang=DEFAULT_LANGUAGE))
    if admin_message:
        await admin_message.edit(embed=admin_embed, view=AdminView())
        print("Updated existing admin message.")
    else:
        await admin_channel.send(embed=admin_embed, view=AdminView())
        print("Sent new admin message.")
    tickets_channel = discord.utils.get(guild.channels, name="tickets") or await guild.create_text_channel("tickets", category=tickets_category)
    tickets_message = None
    async for message in tickets_channel.history(limit=10):
        if message.author == bot.user and message.embeds and "Support Tickets" in message.embeds[0].title:
            tickets_message = message
            break
    ticket_embed = discord.Embed(title=get_text("support_tickets_title", lang=DEFAULT_LANGUAGE), description=get_text("support_tickets_desc", lang=DEFAULT_LANGUAGE), color=discord.Color.red())
    ticket_embed.set_footer(text=get_text("footer", lang=DEFAULT_LANGUAGE))
    if tickets_message:
        await tickets_message.edit(embed=ticket_embed, view=TicketView())
        print("Updated existing tickets message.")
    else:
        await tickets_channel.send(embed=ticket_embed, view=TicketView())
        print("Sent new tickets message.")
    logs_channel = discord.utils.get(guild.channels, name="logs") or await guild.create_text_channel("logs", category=management_category, overwrites=private_overwrites)
    async for message in logs_channel.history(limit=1):
        if message.author == bot.user:
            break
    else:
        await logs_channel.send("Logs will appear here when the script is executed or actions are performed.")
    keys_channel = discord.utils.get(guild.channels, name="keys") or await guild.create_text_channel("keys", category=management_category, overwrites=private_overwrites)
    async for message in keys_channel.history(limit=1):
        if message.author == bot.user:
            break
    else:
        cursor.execute("SELECT * FROM keys")
        keys = cursor.fetchall()
        if keys:
            keys_list = "\n".join([f"Key: `{k[0]}` | User: <@{k[1]}> | Registered: {k[4].split('T')[0]} | Expires: {k[2].split('T')[0]} | Status: {k[3]}" for k in keys])
            await keys_channel.send(f"**Existing Keys:**\n{keys_list}")
        else:
            await keys_channel.send("No keys registered yet.")

@bot.event
async def on_interaction_error(interaction: discord.Interaction, error: Exception):
    await interaction.response.send_message("An error occurred while processing your request. Please try again later.", ephemeral=True)
    print(f"Interaction error: {error}")

@bot.event
async def on_disconnect():
    print("Bot disconnected from Discord.")

@bot.event
async def on_connect():
    print("Bot connected to Discord.")

@bot.event
async def on_resumed():
    print("Bot session resumed.")


    # Start Flask and the bot
if __name__ == "__main__":
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=5031)).start()
    bot.run("DISCORD_TOKEN")
